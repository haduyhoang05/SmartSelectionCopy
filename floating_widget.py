# -*- coding: utf-8 -*-
"""
Smart Selection Copy - Floating Translate Widget (Biểu tượng & Popup Dịch nhanh nổi)
Cải tiến:
1. Icon hình Google Translate chính hãng với hiệu ứng di chuột (Hover) mượt mà.
2. Cố định vị trí ở một bên góc bôi đen (không nhảy loạn hay đè lên văn bản).
3. Triệt tiêu hoàn toàn nháy trắng (Zero-flicker) bằng kỹ thuật render tức thời.
4. Tăng tốc độ xuất hiện cực nhanh ngay khi vừa buông chuột.
"""

import os
import sys
import ctypes
from ctypes import wintypes
import threading
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
import customtkinter as ctk

from utils import translate_bidirectional, speak_text_async

user32 = ctypes.windll.user32

def get_virtual_screen_bounds():
    """Lấy tọa độ và kích thước toàn bộ không gian màn hình (hỗ trợ đa màn hình)."""
    vx = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
    vy = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
    vw = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
    vh = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
    return vx, vy, vw, vh

def get_asset_file(filename):
    """Tìm đường dẫn file tài nguyên an toàn khi chạy file python hoặc exe đóng gói."""
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, "assets", filename),
        os.path.join("assets", filename),
        filename
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

class FloatingTranslateManager:
    """Quản lý hiển thị biểu tượng dịch nổi và popup kết quả dịch."""
    def __init__(self, parent_ui):
        self.parent = parent_ui
        self.icon_window = None
        self.popup_window = None
        self.hide_timer = None
        self.current_text = ""
        self.last_translated = ""

        # Biến theo dõi kéo di chuyển popup
        self._drag_start_x = 0
        self._drag_start_y = 0

        # Tải hình ảnh biểu tượng Google Translate
        self.photo_normal = None
        self.photo_hover = None
        self._load_icon_images()

    def _load_icon_images(self):
        """Tải hoặc khởi tạo ảnh biểu tượng Google Translate chuẩn nét."""
        path_norm = get_asset_file("translate_btn_normal.png")
        path_hov = get_asset_file("translate_btn_hover.png")

        if path_norm and path_hov:
            try:
                im1 = Image.open(path_norm).convert("RGBA")
                im2 = Image.open(path_hov).convert("RGBA")
                self.photo_normal = ImageTk.PhotoImage(im1)
                self.photo_hover = ImageTk.PhotoImage(im2)
                return
            except Exception:
                pass

        # Tự sinh ảnh biểu tượng Google Translate trong bộ nhớ nếu không tìm thấy file
        try:
            size = 36
            im_n = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            d1 = ImageDraw.Draw(im_n)
            d1.ellipse((1, 1, size - 2, size - 2), fill=(255, 255, 255, 255), outline=(218, 220, 224, 255), width=1)
            # Vẽ hình dạng 2 thẻ Google Translate
            d1.rounded_rectangle([7, 8, 22, 23], radius=3, fill=(241, 243, 244, 255))
            d1.rounded_rectangle([14, 13, 29, 28], radius=3, fill=(26, 115, 232, 255))

            im_h = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            d2 = ImageDraw.Draw(im_h)
            d2.ellipse((1, 1, size - 2, size - 2), fill=(245, 248, 255, 255), outline=(26, 115, 232, 255), width=2)
            d2.rounded_rectangle([7, 8, 22, 23], radius=3, fill=(241, 243, 244, 255))
            d2.rounded_rectangle([14, 13, 29, 28], radius=3, fill=(26, 115, 232, 255))

            self.photo_normal = ImageTk.PhotoImage(im_n)
            self.photo_hover = ImageTk.PhotoImage(im_h)
        except Exception:
            pass

    def _calculate_anchor(self, bounds, icon_w=36, icon_h=36):
        """
        Tính tọa độ neo cố định ở góc bên phải của vùng bôi đen:
        - Giúp icon luôn ở vị trí ổn định, dễ bấm.
        - Không bị đè lên dòng chữ người dùng vừa bôi đen.
        """
        if not bounds or len(bounds) < 2:
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            ex, ey = pt.x, pt.y
            sx, sy = ex, ey
        elif len(bounds) == 2:
            ex, ey = bounds
            sx, sy = ex, ey
        else:
            sx, sy, ex, ey = bounds

        vx, vy, vw, vh = get_virtual_screen_bounds()

        # Cố định ở góc bên phải của điểm kết thúc bôi đen
        target_x = ex + 10
        target_y = ey - 32

        # Nếu quá sát mép trên màn hình, nhảy xuống dưới con trỏ
        if target_y < vy + 10:
            target_y = ey + 18

        # Nếu quá sát mép phải màn hình, đặt về phía bên trái điểm kết thúc
        if target_x + icon_w > vx + vw - 10:
            target_x = ex - icon_w - 10

        # Giới hạn an toàn trong không gian hiển thị
        target_x = max(vx + 6, min(target_x, vx + vw - icon_w - 6))
        target_y = max(vy + 6, min(target_y, vy + vh - icon_h - 6))

        return target_x, target_y

    def show_icon(self, text, bounds=None):
        """Hiển thị biểu tượng dịch nổi tròn Google Translate mượt mà và tức thì."""
        if not text or not text.strip():
            return

        self.current_text = text.strip()

        # Nếu popup kết quả đang hiển thị, không đè icon mới
        if self.popup_window and self.popup_window.winfo_exists():
            return

        icon_w, icon_h = 36, 36
        target_x, target_y = self._calculate_anchor(bounds, icon_w, icon_h)

        # Hủy timer cũ nếu có
        if self.hide_timer:
            try:
                self.parent.after_cancel(self.hide_timer)
            except Exception:
                pass
            self.hide_timer = None

        # Nếu icon_window đã có và đang hiển thị, chỉ cần cập nhật vị trí mới mượt mà
        if self.icon_window and self.icon_window.winfo_exists():
            try:
                self.icon_window.geometry(f"+{target_x}+{target_y}")
                self.icon_window.lift()
                self.hide_timer = self.parent.after(4500, self.hide_icon)
                return
            except Exception:
                pass

        # Tạo mới cửa sổ icon với cơ chế Zero-Flicker (không nháy trắng)
        try:
            top = tk.Toplevel(self.parent)
            top.withdraw()  # Ẩn trước để triệt tiêu hoàn toàn hiện tượng nháy trắng
            top.overrideredirect(True)
            top.attributes("-topmost", True)
            top.wm_attributes("-transparentcolor", "#000001")
            top.configure(bg="#000001")
            top.geometry(f"{icon_w}x{icon_h}+{target_x}+{target_y}")

            self.icon_window = top

            if self.photo_normal:
                lbl = tk.Label(
                    top,
                    image=self.photo_normal,
                    bg="#000001",
                    bd=0,
                    cursor="hand2"
                )
                lbl.pack(fill="both", expand=True)

                lbl.bind("<Enter>", lambda e: lbl.configure(image=self.photo_hover) if self.photo_hover else None)
                lbl.bind("<Leave>", lambda e: lbl.configure(image=self.photo_normal) if self.photo_normal else None)
                lbl.bind("<Button-1>", lambda e: self._on_icon_clicked(target_x, target_y))
            else:
                lbl = tk.Label(
                    top,
                    text="🌐",
                    font=("Segoe UI", 12),
                    fg="#ffffff",
                    bg="#1a73e8",
                    bd=0,
                    cursor="hand2"
                )
                lbl.pack(fill="both", expand=True)
                lbl.bind("<Button-1>", lambda e: self._on_icon_clicked(target_x, target_y))

            # Xuất hiện mượt mà tức thì
            top.deiconify()
            top.lift()

            # Tự động ẩn icon sau 4.5 giây nếu người dùng không bấm
            self.hide_timer = self.parent.after(4500, self.hide_icon)
        except Exception as e:
            print(f"Lỗi hiển thị Floating Icon: {e}")

    def hide_icon(self):
        """Ẩn biểu tượng dịch nổi."""
        if self.hide_timer:
            try:
                self.parent.after_cancel(self.hide_timer)
            except Exception:
                pass
            self.hide_timer = None

        if self.icon_window:
            try:
                if self.icon_window.winfo_exists():
                    self.icon_window.destroy()
            except Exception:
                pass
            self.icon_window = None

    def _on_icon_clicked(self, icon_x, icon_y):
        """Xử lý khi người dùng nhấn vào biểu tượng dịch nổi."""
        text_to_translate = self.current_text
        self.hide_icon()
        self.show_popup(text_to_translate, icon_x, icon_y)

    def show_popup(self, text, anchor_x, anchor_y):
        """Hiển thị popup kết quả dịch văn bản và nút Đọc."""
        if not text or not text.strip():
            return

        self.hide_popup()
        self.last_translated = ""

        vx, vy, vw, vh = get_virtual_screen_bounds()

        # Tính kích thước popup tùy theo độ dài văn bản
        text_len = len(text)
        pop_w = 400 if text_len > 150 else 360
        pop_h = 240 if text_len > 250 else (190 if text_len > 100 else 150)

        # Định vị popup tránh vượt ngoài màn hình
        pop_x = anchor_x
        pop_y = anchor_y

        if pop_x + pop_w > vx + vw - 12:
            pop_x = vx + vw - pop_w - 12
        if pop_y + pop_h > vy + vh - 12:
            pop_y = vy + vh - pop_h - 12
        if pop_x < vx + 10:
            pop_x = vx + 10
        if pop_y < vy + 10:
            pop_y = vy + 10

        try:
            self.popup_window = ctk.CTkToplevel(self.parent)
            self.popup_window.overrideredirect(True)
            self.popup_window.attributes("-topmost", True)
            self.popup_window.geometry(f"{pop_w}x{pop_h}+{pop_x}+{pop_y}")
            self.popup_window.configure(fg_color="#181825")

            # Phím tắt Esc để đóng popup nhanh
            self.popup_window.bind("<Escape>", lambda e: self.hide_popup())

            # Khung viền chính
            container = ctk.CTkFrame(
                self.popup_window,
                fg_color="#181825",
                border_color="#7c3aed",
                border_width=1,
                corner_radius=10
            )
            container.pack(fill="both", expand=True, padx=2, pady=2)

            # 1. Header (Có thể bấm giữ chuột để kéo di chuyển popup)
            header = ctk.CTkFrame(container, fg_color="#1e1e2e", height=32, corner_radius=8)
            header.pack(fill="x", padx=6, pady=(6, 4))

            # Cho phép kéo popup di chuyển
            def _start_drag(event):
                self._drag_start_x = event.x
                self._drag_start_y = event.y

            def _on_drag(event):
                try:
                    cur_x = self.popup_window.winfo_x()
                    cur_y = self.popup_window.winfo_y()
                    nx = cur_x + (event.x - self._drag_start_x)
                    ny = cur_y + (event.y - self._drag_start_y)
                    self.popup_window.geometry(f"+{nx}+{ny}")
                except Exception:
                    pass

            header.bind("<Button-1>", _start_drag)
            header.bind("<B1-Motion>", _on_drag)

            # Badge trạng thái ngôn ngữ
            self.lbl_badge = ctk.CTkLabel(
                header,
                text="⏳ Đang dịch...",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#38bdf8"
            )
            self.lbl_badge.pack(side="left", padx=(10, 6), pady=4)
            self.lbl_badge.bind("<Button-1>", _start_drag)
            self.lbl_badge.bind("<B1-Motion>", _on_drag)

            # Nút Đóng (✕)
            btn_close = ctk.CTkButton(
                header,
                text="✕",
                width=24,
                height=24,
                corner_radius=6,
                fg_color="transparent",
                hover_color="#ef4444",
                text_color="#94a3b8",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                command=self.hide_popup
            )
            btn_close.pack(side="right", padx=(4, 6), pady=4)

            # Nút Thử lại (Ẩn khi dịch thành công, chỉ hiện khi lỗi kết nối)
            self.btn_retry = ctk.CTkButton(
                header,
                text="🔄 Thử lại",
                width=70,
                height=24,
                corner_radius=6,
                fg_color="#ef4444",
                hover_color="#dc2626",
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                command=self._retry_action
            )

            # Nút Đọc (🔊)
            self.btn_speak = ctk.CTkButton(
                header,
                text="🔊 Đọc",
                width=60,
                height=24,
                corner_radius=6,
                fg_color="#334155",
                hover_color="#475569",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                command=self._speak_action
            )
            self.btn_speak.pack(side="right", padx=3, pady=4)

            # Nút Copy (📋)
            self.btn_copy = ctk.CTkButton(
                header,
                text="📋 Copy",
                width=60,
                height=24,
                corner_radius=6,
                fg_color="#334155",
                hover_color="#475569",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                command=self._copy_action
            )
            self.btn_copy.pack(side="right", padx=3, pady=4)

            # 2. Ô nội dung: Chỉ xuất hiện đoạn văn đã dịch
            self.txt_content = ctk.CTkTextbox(
                container,
                fg_color="#11111b",
                border_color="#313244",
                border_width=1,
                corner_radius=8,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                wrap="word",
                text_color="#f8fafc"
            )
            self.txt_content.pack(fill="both", expand=True, padx=8, pady=(2, 8))
            self.txt_content.insert("1.0", "Đang kết nối dịch văn bản...")
            self.txt_content.configure(state="disabled")

            # Khởi chạy luồng dịch ngầm (gửi kết quả qua hàng đợi an toàn)
            def _worker():
                trans_text, src_lang, tgt_lang = translate_bidirectional(text)
                try:
                    self.parent.get_msg_queue().put(
                        ("FLOATING_TRANSLATE_DONE", (trans_text, src_lang, tgt_lang))
                    )
                except Exception:
                    pass

            threading.Thread(target=_worker, daemon=True).start()

        except Exception as e:
            print(f"Lỗi mở popup dịch: {e}")

    def _on_translation_finished(self, translated_text, src_lang, tgt_lang):
        """Cập nhật nội dung dịch lên popup khi đã xử lý xong."""
        if not self.popup_window:
            return
        try:
            if not self.popup_window.winfo_exists():
                return
        except Exception:
            return

        self.last_translated = translated_text
        is_error = translated_text.startswith("[Lỗi")

        # Cập nhật Badge ngôn ngữ
        if is_error:
            badge_text = "⚠️ LỖI KẾT NỐI"
            badge_color = "#ef4444"
            # Hiện nút thử lại
            self.btn_retry.pack(side="right", padx=3, pady=4)
        else:
            self.btn_retry.pack_forget()
            if src_lang == "vi" and tgt_lang == "en":
                badge_text = "🇻🇳 VI ➔ 🇬🇧 EN"
                badge_color = "#10b981"
            elif tgt_lang == "vi":
                badge_text = f"🌐 {src_lang.upper()} ➔ 🇻🇳 VI"
                badge_color = "#10b981"
            else:
                badge_text = f"🌐 {src_lang.upper()} ➔ {tgt_lang.upper()}"
                badge_color = "#10b981"

        self.lbl_badge.configure(text=badge_text, text_color=badge_color)

        # Hiển thị đoạn văn
        self.txt_content.configure(state="normal")
        self.txt_content.delete("1.0", "end")
        if is_error:
            self.txt_content.insert(
                "1.0",
                f"{translated_text}\n\n👉 Vui lòng nhấp nút [🔄 Thử lại] ở trên để dịch lại ngay."
            )
        else:
            self.txt_content.insert("1.0", translated_text)
        self.txt_content.configure(state="disabled")

        if not is_error:
            # Lưu vào lịch sử của ứng dụng chính
            try:
                self.parent.add_history_entry(
                    source=f"Dịch ({src_lang}➔{tgt_lang})",
                    text=translated_text
                )
            except Exception:
                pass

            # Tự động sao chép nếu cấu hình auto_copy bật
            try:
                if self.parent.auto_copy_var.get():
                    self._copy_action(silent=True)
            except Exception:
                pass

    def _retry_action(self):
        """Thực hiện thử lại dịch khi gặp sự cố mạng."""
        if not self.current_text:
            return

        self.btn_retry.pack_forget()
        self.lbl_badge.configure(text="⏳ Đang thử lại...", text_color="#38bdf8")
        self.txt_content.configure(state="normal")
        self.txt_content.delete("1.0", "end")
        self.txt_content.insert("1.0", "Đang kết nối lại máy chủ dịch...")
        self.txt_content.configure(state="disabled")

        def _worker():
            trans_text, src_lang, tgt_lang = translate_bidirectional(self.current_text)
            try:
                self.parent.get_msg_queue().put(
                    ("FLOATING_TRANSLATE_DONE", (trans_text, src_lang, tgt_lang))
                )
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _speak_action(self):
        """Phát âm đoạn văn đã dịch."""
        if not self.last_translated or self.last_translated.startswith("[Lỗi"):
            return

        speak_text_async(self.last_translated)

        # Hiệu ứng đổi chữ trên nút Đọc
        orig_text = "🔊 Đọc"
        self.btn_speak.configure(text="🔊 Đang đọc...", fg_color="#7c3aed")
        if self.popup_window and self.popup_window.winfo_exists():
            self.popup_window.after(
                2000,
                lambda: self.btn_speak.configure(text=orig_text, fg_color="#334155")
                if self.popup_window and self.popup_window.winfo_exists() else None
            )

    def _copy_action(self, silent=False):
        """Sao chép đoạn văn đã dịch vào clipboard."""
        if not self.last_translated or self.last_translated.startswith("[Lỗi"):
            return

        try:
            self.parent.clipboard_clear()
            self.parent.clipboard_append(self.last_translated)
            self.parent.update()

            if not silent:
                self.btn_copy.configure(text="✓ Đã chép", fg_color="#10b981")
                if self.popup_window and self.popup_window.winfo_exists():
                    self.popup_window.after(
                        1500,
                        lambda: self.btn_copy.configure(text="📋 Copy", fg_color="#334155")
                        if self.popup_window and self.popup_window.winfo_exists() else None
                    )
        except Exception:
            pass

    def hide_popup(self):
        """Đóng popup kết quả dịch."""
        if self.popup_window:
            try:
                if self.popup_window.winfo_exists():
                    self.popup_window.destroy()
            except Exception:
                pass
            self.popup_window = None

    def cleanup(self):
        """Dọn dẹp toàn bộ toplevel khi tắt ứng dụng."""
        self.hide_icon()
        self.hide_popup()
