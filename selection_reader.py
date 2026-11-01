# -*- coding: utf-8 -*-
"""
Smart Selection Copy - Bộ lắng nghe thao tác bôi đen thông minh (SelectionReader)
Cải tiến:
1. Lọc nhiễu thao tác click/rung chuột (loại bỏ hoàn toàn false-positive).
2. Hỗ trợ đa dạng Patterns: TextPattern, TextPattern2.
3. Không spam thông báo lỗi khi người dùng click vào vùng trống hoặc bỏ chọn.
4. Quản lý hàng đợi và luồng worker UIA an toàn (Thread-safe COM).
"""

import math
import time
import queue
import threading
from pynput import mouse, keyboard
import uiautomation as auto
import comtypes

class SelectionReader:
    """
    Lớp SelectionReader chịu trách nhiệm chạy ngầm để lắng nghe các sự kiện chuột và bàn phím,
    phát hiện khi người dùng kết thúc thao tác bôi đen chữ, sau đó trích xuất văn bản qua UIA.
    """
    def __init__(self, callback):
        """
        :param callback: Hàm callback nhận hai tham số: (selected_text: str, is_copy_protected: bool)
        """
        self.callback = callback
        self.mouse_listener = None
        self.keyboard_listener = None
        self.is_running = False
        self.enabled = True

        # Theo dõi chuột
        self.start_x = 0
        self.start_y = 0
        self.press_time = 0
        self.last_release_time = 0

        # Theo dõi phím
        self.pressed_keys = set()

        # Hàng đợi tác vụ
        self.task_queue = queue.Queue()
        self.worker_thread = None

    def start(self):
        """Khởi chạy bộ lắng nghe và worker thread."""
        if self.is_running:
            return
        self.is_running = True

        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

        self.mouse_listener = mouse.Listener(on_click=self._on_click)
        self.mouse_listener.start()

        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.keyboard_listener.start()

    def stop(self):
        """Dừng tất cả listener và giải phóng worker."""
        self.is_running = False
        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except Exception:
                pass
            self.mouse_listener = None

        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except Exception:
                pass
            self.keyboard_listener = None

        self.task_queue.put(None)
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
            self.worker_thread = None

    def set_enabled(self, enabled):
        """Bật/tắt việc tiếp nhận sự kiện."""
        self.enabled = enabled

    def _on_click(self, x, y, button, pressed):
        if not self.enabled:
            return

        if button == mouse.Button.left:
            now = time.time()
            if pressed:
                self.start_x = x
                self.start_y = y
                self.press_time = now
            else:
                dist = math.hypot(x - self.start_x, y - self.start_y)
                duration = now - self.press_time

                # 1. Kéo rê bôi đen hợp lệ: Khoảng cách > 12px và thời gian nhấn giữ > 70ms
                # Tránh tình trạng nhấp chuột thường nhưng tay hơi rung
                is_drag = (dist > 12) and (duration > 0.07)

                # 2. Nhấp đúp / nhấp 3 lần để chọn từ hoặc đoạn văn
                is_multi_click = (now - self.last_release_time < 0.35) and (dist < 8)
                self.last_release_time = now

                if is_drag or is_multi_click:
                    # Gửi cờ kiểm tra kèm loại thao tác
                    self.task_queue.put(("CHECK_SELECTION", is_drag))

    def _on_press(self, key):
        if not self.enabled:
            return
        self.pressed_keys.add(key)

    def _on_release(self, key):
        if not self.enabled:
            return
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

        is_nav_key = key in (
            keyboard.Key.left, keyboard.Key.right,
            keyboard.Key.up, keyboard.Key.down,
            keyboard.Key.home, keyboard.Key.end,
            keyboard.Key.page_up, keyboard.Key.page_down
        )

        has_shift = any(
            k in self.pressed_keys
            for k in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r)
        )
        has_ctrl = any(
            k in self.pressed_keys
            for k in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r)
        )

        # Shift + mũi tên / home / end
        if is_nav_key and has_shift:
            self.task_queue.put(("CHECK_SELECTION", True))

        # Ctrl + A
        is_a_key = False
        if hasattr(key, 'char') and key.char == 'a':
            is_a_key = True
        elif hasattr(key, 'vk') and key.vk == 65:
            is_a_key = True

        if is_a_key and has_ctrl:
            self.task_queue.put(("CHECK_SELECTION", True))

    def _worker_loop(self):
        try:
            comtypes.CoInitialize()
        except Exception:
            pass

        while self.is_running:
            try:
                task = self.task_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if task is None:
                break

            task_type, is_drag = task

            # Lọc bỏ các yêu cầu trùng lặp dồn ứ trong queue
            while not self.task_queue.empty():
                try:
                    self.task_queue.get_nowait()
                except queue.Empty:
                    break

            # Chờ 120ms để ứng dụng nguồn cập nhật trạng thái lựa chọn
            time.sleep(0.12)

            try:
                text, is_protected = self._query_selected_text()
                if text or is_protected:
                    self.callback(text, is_protected)
            except Exception:
                pass

        try:
            comtypes.CoUninitialize()
        except Exception:
            pass

    def _query_selected_text(self):
        """
        Truy vấn văn bản bôi đen qua UI Automation.
        Trả về: (selected_text: str, is_protected: bool)
        """
        # 1. Thử từ control đang được focus
        focused_ctrl = auto.GetFocusedControl()
        if focused_ctrl:
            text, is_prot = self._get_text_from_control(focused_ctrl)
            if text:
                return text, False
            if is_prot:
                return "", True

        # 2. Thử từ control dưới con trỏ chuột
        cursor_ctrl = auto.ControlFromCursor()
        if cursor_ctrl:
            if not focused_ctrl or cursor_ctrl.GetRuntimeId() != focused_ctrl.GetRuntimeId():
                text, is_prot = self._get_text_from_control(cursor_ctrl)
                if text:
                    return text, False
                if is_prot:
                    return "", True

        return "", False

    def _get_text_from_control(self, ctrl):
        """
        Trích xuất bôi đen từ một control cụ thể.
        """
        if not ctrl:
            return "", False

        # Thử TextPattern
        try:
            text_pattern = ctrl.GetPattern(auto.PatternId.TextPattern)
            if text_pattern:
                selections = text_pattern.GetSelection()
                if selections and len(selections) > 0:
                    selected_text = selections[0].GetText()
                    if selected_text:
                        return selected_text, False
                return "", False
        except Exception:
            # Nếu control có dạng Document / Edit mà không cho đọc, có thể bị chặn
            control_type = ctrl.ControlTypeName
            if control_type in ("DocumentControl", "EditControl", "PaneControl"):
                return "", True

        # Thử TextPattern2
        try:
            tp2 = getattr(auto.PatternId, 'TextPattern2', None)
            if tp2:
                text_pattern2 = ctrl.GetPattern(tp2)
                if text_pattern2:
                    selections = text_pattern2.GetSelection()
                    if selections and len(selections) > 0:
                        selected_text = selections[0].GetText()
                        if selected_text:
                            return selected_text, False
                    return "", False
        except Exception:
            pass

        return "", False
