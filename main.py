# -*- coding: utf-8 -*-
"""
Smart Selection Copy - Trình Bắt Văn Bản Bôi Đen & OCR Đa Năng
Khởi chạy chính của hệ thống.
"""

import sys

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import ctypes
import threading
from pynput import keyboard

# 1. Kích hoạt DPI Awareness trước khi tạo bất kỳ cửa sổ Tkinter nào
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from config import load_config
from ui import SelectionAppUI
from selection_reader import SelectionReader
from ocr_helper import ScreenCropper, run_ocr
from tray_helper import SystemTrayManager

def main():
    config = load_config()
    app = None
    reader = None
    tray = None
    hotkey_listener = None

    def on_selection_received(text, is_protected, cursor_pos=None):
        """Callback từ SelectionReader gửi tới UI."""
        if app:
            app.get_msg_queue().put(("UIA_EVENT", (text, is_protected, cursor_pos)))

    def on_crop_finished(image):
        """Callback sau khi kéo chọn chụp màn hình kết thúc."""
        if not app:
            return

        # Phục hồi cửa sổ chính
        app.deiconify()
        app.focus_force()
        app.wm_attributes("-topmost", app.always_on_top_var.get())

        if image:
            app.set_status("● Đang tiến hành nhận diện OCR...", "yellow")

            def ocr_worker():
                engine_pref = app.config_data.get("ocr_engine", "auto")
                clean_breaks = app.config_data.get("clean_linebreaks", True)
                text, engine_used, err = run_ocr(image, engine_pref=engine_pref, clean_breaks=clean_breaks)
                app.get_msg_queue().put(("OCR_RESULT", (text, engine_used, err)))

            threading.Thread(target=ocr_worker, daemon=True).start()
        else:
            app.set_status("● Đã hủy chụp ảnh màn hình.", "subtext")

    def launch_screen_cropper():
        try:
            ScreenCropper(app, on_crop_finished)
        except Exception as e:
            app.deiconify()
            app.get_msg_queue().put(("OCR_RESULT", ("", "", f"Lỗi khởi chạy chụp màn hình: {e}")))

    def trigger_ocr_flow():
        """Bắt đầu quy trình quét OCR màn hình."""
        if not app:
            return
        app.withdraw()
        # Chờ 250ms để cửa sổ chính hoàn toàn biến mất trước khi chụp GDI
        app.after(250, launch_screen_cropper)

    def show_app_window():
        """Hiện lại cửa sổ từ System Tray."""
        if app:
            app.after(0, lambda: (
                app.deiconify(),
                app.focus_force(),
                app.wm_attributes("-topmost", app.always_on_top_var.get())
            ))

    def on_app_exit():
        """Dọn dẹp toàn bộ tài nguyên khi tắt ứng dụng hoàn toàn."""
        nonlocal reader, tray, hotkey_listener
        print("Đang dọn dẹp tài nguyên và tắt ứng dụng...")
        if hotkey_listener:
            try:
                hotkey_listener.stop()
            except Exception:
                pass
            hotkey_listener = None

        if reader:
            try:
                reader.stop()
            except Exception:
                pass
            reader = None

        if tray:
            try:
                tray.stop()
            except Exception:
                pass
            tray = None

    try:
        # Khởi tạo UI chính
        app = SelectionAppUI(
            config=config,
            on_close_callback=on_app_exit,
            on_ocr_callback=trigger_ocr_flow
        )

        # Khởi tạo SelectionReader
        reader = SelectionReader(on_selection_received)
        reader.set_auto_copy(config.get("auto_copy", False))
        reader.start()
        app.set_reader(reader)

        # Khởi tạo System Tray
        tray = SystemTrayManager(
            on_show=show_app_window,
            on_ocr=lambda: app.after(0, trigger_ocr_flow),
            on_exit=lambda: app.after(0, app._exit_app)
        )
        tray.start()

        # Đăng ký phím tắt toàn cục Global Hotkey (Mặc định Alt+Q)
        hotkey_str = config.get("hotkey_ocr", "<alt>+q").lower()
        try:
            hotkey_listener = keyboard.GlobalHotKeys({
                hotkey_str: lambda: app.after(0, trigger_ocr_flow)
            })
            hotkey_listener.start()
        except Exception as e:
            print(f"Không thể đăng ký phím tắt {hotkey_str}: {e}")

        print("Smart Selection Copy & OCR đang hoạt động...")
        print(f"Phím tắt quét OCR nhanh: {hotkey_str.upper()}")
        print("Bôi đen văn bản ở bất kỳ ứng dụng nào hoặc kéo chọn màn hình để bắt đầu.")

        app.mainloop()

    except KeyboardInterrupt:
        on_app_exit()
        sys.exit(0)
    except Exception as e:
        print(f"Lỗi hệ thống: {e}")
        on_app_exit()
        sys.exit(1)

if __name__ == "__main__":
    main()
