# -*- coding: utf-8 -*-
"""
Smart Selection Copy & OCR - Giao diện người dùng hiện đại CustomTkinter
Thiết kế: Windows 11 Fluent / Catppuccin Dark Mode
"""

import os
import sys
import time
import queue
import threading
from tkinter import messagebox
import customtkinter as ctk

from utils import clean_text_linebreaks, clean_whitespace, translate_text, speak_text_async
from config import save_config, load_history, save_history
from floating_widget import FloatingTranslateManager

# Cài đặt giao diện CustomTkinter chuẩn Dark Mode
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SelectionAppUI(ctk.CTk):
    def __init__(self, config, on_close_callback=None, on_ocr_callback=None):
        super().__init__()
        self.config_data = config
        self.on_close_callback = on_close_callback
        self.on_ocr_callback = on_ocr_callback
        self.msg_queue = queue.Queue()

        # Bảng màu chủ đề cao cấp (Fluent Catppuccin Mocha)
        self.palette = {
            "window_bg": "#181825",
            "card_bg": "#1e1e2e",
            "card_border": "#313244",
            "textbox_bg": "#11111b",
            "accent_blue": "#3b82f6",
            "accent_blue_hover": "#2563eb",
            "accent_purple": "#8b5cf6",
            "accent_purple_hover": "#7c3aed",
            "accent_green": "#10b981",
            "accent_green_hover": "#059669",
            "accent_red": "#ef4444",
            "accent_red_hover": "#dc2626",
            "btn_neutral": "#334155",
            "btn_neutral_hover": "#475569",
            "text_main": "#f8fafc",
            "text_sub": "#94a3b8",
            "badge_uia": "#0284c7",
            "badge_ocr": "#7c3aed",
            "badge_trans": "#059669"
        }

        # Cấu hình cửa sổ chính
        self.title("Smart Selection Copy & OCR")
        geometry = self.config_data.get("window_geometry", "600x640")
        self.geometry(geometry)
        self.minsize(360, 420)
        self.configure(fg_color=self.palette["window_bg"])

        # Trạng thái responsive
        self.is_compact_width = None
        self.is_compact_height = None
        self.history_labels = []

        # Cài đặt biểu tượng icon
        self._set_window_icon()

        # Biến trạng thái
        self.always_on_top_var = ctk.BooleanVar(value=self.config_data.get("always_on_top", True))
        self.auto_capture_var = ctk.BooleanVar(value=self.config_data.get("auto_capture", True))
        self.auto_copy_var = ctk.BooleanVar(value=self.config_data.get("auto_copy", False))
        self.auto_translate_var = ctk.BooleanVar(value=self.config_data.get("auto_translate", False))
        self.append_mode_var = ctk.BooleanVar(value=self.config_data.get("append_mode", False))
        self.clean_linebreaks_var = ctk.BooleanVar(value=self.config_data.get("clean_linebreaks", True))
        self.minimize_to_tray_var = ctk.BooleanVar(value=self.config_data.get("minimize_to_tray", True))
        self.floating_translate_var = ctk.BooleanVar(value=self.config_data.get("floating_translate_enabled", True))
        self.ocr_engine_var = ctk.StringVar(value=self.config_data.get("ocr_engine", "auto"))

        # Trình quản lý biểu tượng dịch nổi và popup
        self.floating_manager = FloatingTranslateManager(self)

        # Lưu bản gốc gần nhất trước khi dịch
        self.last_original_text = ""

        # Dữ liệu lịch sử
        self.history_items = load_history()

        # Xây dựng giao diện
        self._build_ui()

        # Áp dụng Topmost
        self.wm_attributes("-topmost", self.always_on_top_var.get())

        # Lắng nghe sự kiện co giãn cửa sổ để tự thích ứng responsive
        self.bind("<Configure>", self._on_window_configure)

        # Bắt sự kiện đóng cửa sổ
        self.protocol("WM_DELETE_WINDOW", self._on_close_requested)

        # Lắng nghe hàng đợi thông điệp siêu tốc (20ms)
        self.after(20, self._poll_queue)

    def _set_window_icon(self):
        candidates = [
            os.path.join(getattr(sys, "_MEIPASS", ""), "assets", "app_icon.ico"),
            os.path.join(os.path.dirname(__file__), "assets", "app_icon.ico"),
            "assets/app_icon.ico",
            "app_icon.ico"
        ]
        for ico in candidates:
            if ico and os.path.exists(ico):
                try:
                    self.iconbitmap(ico)
                    break
                except Exception:
                    pass

    def _build_ui(self):
        # 1. Header trên cùng
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(side="top", fill="x", padx=16, pady=(12, 6))

        left_header = ctk.CTkFrame(header_frame, fg_color="transparent")
        left_header.pack(side="left")

        title_lbl = ctk.CTkLabel(
            left_header,
            text="⚡ SMART COPY & OCR",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#38bdf8"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            left_header,
            text="Bắt bôi đen chuột • Quét chữ màn hình • Tự động dịch",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=self.palette["text_sub"]
        )
        sub_lbl.pack(anchor="w")

        # Nút switch ghim trên cùng
        self.sw_topmost = ctk.CTkSwitch(
            header_frame,
            text="Luôn trên cùng",
            variable=self.always_on_top_var,
            onvalue=True,
            offvalue=False,
            command=self._toggle_always_on_top,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            progress_color=self.palette["accent_blue"]
        )
        self.sw_topmost.pack(side="right")

        # 2. Thanh trạng thái dưới cùng (Pack trước để luôn hiện)
        self.status_bar = ctk.CTkFrame(self, fg_color=self.palette["card_bg"], height=30, corner_radius=0)
        self.status_bar.pack(side="bottom", fill="x")

        self.status_dot = ctk.CTkLabel(
            self.status_bar,
            text="●",
            text_color="#10b981",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        )
        self.status_dot.pack(side="left", padx=(12, 4))

        self.status_lbl = ctk.CTkLabel(
            self.status_bar,
            text="Sẵn sàng. Bôi đen văn bản hoặc bấm Alt + Q để quét OCR.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=self.palette["text_sub"],
            anchor="w"
        )
        self.status_lbl.pack(side="left", fill="x", expand=True)

        self.counter_lbl = ctk.CTkLabel(
            self.status_bar,
            text="0 ký tự | 0 từ",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=self.palette["text_sub"]
        )
        self.counter_lbl.pack(side="right", padx=12)

        # 3. Tab Navigation (CTkTabview)
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=self.palette["card_bg"],
            segmented_button_fg_color="#181825",
            segmented_button_selected_color=self.palette["accent_blue"],
            segmented_button_selected_hover_color=self.palette["accent_blue_hover"],
            corner_radius=10
        )
        self.tabview.pack(fill="both", expand=True, padx=14, pady=(2, 8))

        self.tab_main = self.tabview.add("📄 Soạn thảo & Quét")
        self.tab_history = self.tabview.add("🕒 Lịch sử trích xuất")
        self.tab_settings = self.tabview.add("⚙️ Cài đặt")

        self._build_main_tab()
        self._build_history_tab()
        self._build_settings_tab()

    def _build_main_tab(self):
        # 1. Hàng công tắc nhanh (Switches)
        self.switches_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        self.switches_frame.pack(side="top", fill="x", padx=4, pady=(4, 6))

        sw_font = ctk.CTkFont(family="Segoe UI", size=11)

        self.sw_auto_capture = ctk.CTkSwitch(
            self.switches_frame, text="Tự bắt UIA", variable=self.auto_capture_var,
            font=sw_font, progress_color=self.palette["accent_blue"], command=self._on_auto_capture_toggle
        )
        self.sw_auto_copy = ctk.CTkSwitch(
            self.switches_frame, text="Tự Copy", variable=self.auto_copy_var,
            font=sw_font, progress_color=self.palette["accent_green"], command=self._save_quick_settings
        )
        self.sw_auto_translate = ctk.CTkSwitch(
            self.switches_frame, text="Tự Dịch", variable=self.auto_translate_var,
            font=sw_font, progress_color=self.palette["accent_purple"], command=self._save_quick_settings
        )
        self.sw_append_mode = ctk.CTkSwitch(
            self.switches_frame, text="Nối tiếp", variable=self.append_mode_var,
            font=sw_font, progress_color=self.palette["accent_blue"], command=self._save_quick_settings
        )

        # 2. Hai nút hành động lớn (Quét màn hình & Dịch sang tiếng Việt)
        self.action_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        self.action_frame.pack(side="top", fill="x", padx=4, pady=(0, 6))
        self.action_frame.columnconfigure((0, 1), weight=1)

        btn_font = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")

        self.btn_ocr_big = ctk.CTkButton(
            self.action_frame,
            text="📷 QUÉT MÀN HÌNH (Alt + Q)",
            font=btn_font,
            fg_color=self.palette["accent_blue"],
            hover_color=self.palette["accent_blue_hover"],
            height=38,
            corner_radius=8,
            command=self._trigger_ocr
        )
        self.btn_ocr_big.grid(row=0, column=0, sticky="ew", padx=(0, 3))

        self.btn_translate_big = ctk.CTkButton(
            self.action_frame,
            text="🌐 DỊCH SANG TIẾNG VIỆT",
            font=btn_font,
            fg_color=self.palette["accent_purple"],
            hover_color=self.palette["accent_purple_hover"],
            height=38,
            corner_radius=8,
            command=lambda: self._translate_action("vi")
        )
        self.btn_translate_big.grid(row=0, column=1, sticky="ew", padx=(3, 0))

        # 3. Thanh công cụ tiện ích dưới (Pack side="bottom" trước textbox)
        self.tools_frame = ctk.CTkFrame(self.tab_main, fg_color="transparent")
        self.tools_frame.pack(side="bottom", fill="x", padx=4, pady=(4, 2))

        sub_btn_font = ctk.CTkFont(family="Segoe UI", size=10, weight="bold")

        self.btn_copy = ctk.CTkButton(
            self.tools_frame, text="📋 Sao chép", font=sub_btn_font,
            fg_color=self.palette["accent_green"], hover_color=self.palette["accent_green_hover"],
            text_color="#ffffff", height=30, corner_radius=6, command=self._copy_to_clipboard
        )
        self.btn_trans_en = ctk.CTkButton(
            self.tools_frame, text="🌐 Dịch Anh", font=sub_btn_font,
            fg_color=self.palette["btn_neutral"], hover_color=self.palette["btn_neutral_hover"],
            text_color=self.palette["text_main"], height=30, corner_radius=6,
            command=lambda: self._translate_action("en")
        )
        self.btn_restore = ctk.CTkButton(
            self.tools_frame, text="↩️ Bản gốc", font=sub_btn_font,
            fg_color=self.palette["btn_neutral"], hover_color=self.palette["btn_neutral_hover"],
            text_color=self.palette["text_main"], height=30, corner_radius=6,
            command=self._restore_original_text
        )
        self.btn_clean = ctk.CTkButton(
            self.tools_frame, text="🧹 Gộp dòng", font=sub_btn_font,
            fg_color=self.palette["btn_neutral"], hover_color=self.palette["btn_neutral_hover"],
            text_color=self.palette["text_main"], height=30, corner_radius=6,
            command=self._clean_lines_action
        )
        self.btn_speak = ctk.CTkButton(
            self.tools_frame, text="🔊 Phát âm", font=sub_btn_font,
            fg_color=self.palette["btn_neutral"], hover_color=self.palette["btn_neutral_hover"],
            text_color=self.palette["text_main"], height=30, corner_radius=6,
            command=self._speak_action
        )
        self.btn_clear = ctk.CTkButton(
            self.tools_frame, text="🗑️ Xóa", font=sub_btn_font,
            fg_color=self.palette["accent_red"], hover_color=self.palette["accent_red_hover"],
            text_color="#ffffff", height=30, corner_radius=6, command=self._clear_text
        )

        # 4. Hộp văn bản trung tâm (CTkTextbox)
        self.text_box = ctk.CTkTextbox(
            self.tab_main,
            fg_color=self.palette["textbox_bg"],
            text_color=self.palette["text_main"],
            border_color=self.palette["card_border"],
            border_width=1,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            wrap="word"
        )
        self.text_box.pack(fill="both", expand=True, padx=4, pady=(2, 4))

        self.text_box.bind("<KeyRelease>", lambda e: self._update_counter())
        self.text_box.bind("<Control-a>", self._select_all)
        self.text_box.bind("<Control-A>", self._select_all)

        # Áp dụng bố cục thích ứng responsive ban đầu
        self._apply_responsive_layout(self.winfo_width() < 530)

    def _apply_responsive_layout(self, is_narrow):
        """Tự động thay đổi layout công tắc và nút bấm khi co giãn cửa sổ."""
        # 1. Bố cục công tắc (Switches)
        for sw in (self.sw_auto_capture, self.sw_auto_copy, self.sw_auto_translate, self.sw_append_mode):
            sw.grid_forget()

        if is_narrow:
            # Thu nhỏ: 2 hàng x 2 cột
            self.switches_frame.columnconfigure((0, 1), weight=1)
            self.switches_frame.columnconfigure((2, 3), weight=0)
            self.sw_auto_capture.grid(row=0, column=0, sticky="w", padx=4, pady=2)
            self.sw_auto_copy.grid(row=0, column=1, sticky="w", padx=4, pady=2)
            self.sw_auto_translate.grid(row=1, column=0, sticky="w", padx=4, pady=2)
            self.sw_append_mode.grid(row=1, column=1, sticky="w", padx=4, pady=2)

            self.btn_ocr_big.configure(text="📷 Quét (Alt+Q)")
            self.btn_translate_big.configure(text="🌐 Dịch VN")
            self.sw_topmost.configure(text="Ghim")
        else:
            # Mở rộng: 1 hàng x 4 cột
            self.switches_frame.columnconfigure((0, 1, 2, 3), weight=1)
            self.sw_auto_capture.grid(row=0, column=0, sticky="w", padx=4, pady=2)
            self.sw_auto_copy.grid(row=0, column=1, sticky="w", padx=4, pady=2)
            self.sw_auto_translate.grid(row=0, column=2, sticky="w", padx=4, pady=2)
            self.sw_append_mode.grid(row=0, column=3, sticky="w", padx=4, pady=2)

            self.btn_ocr_big.configure(text="📷 QUÉT MÀN HÌNH (Alt + Q)")
            self.btn_translate_big.configure(text="🌐 DỊCH SANG TIẾNG VIỆT")
            self.sw_topmost.configure(text="Luôn trên cùng")

        # 2. Thanh công cụ tiện ích dưới (Tools)
        tool_buttons = [self.btn_copy, self.btn_trans_en, self.btn_restore, self.btn_clean, self.btn_speak, self.btn_clear]
        for btn in tool_buttons:
            btn.grid_forget()

        if is_narrow:
            # Thu nhỏ: 2 hàng x 3 cột (các nút tự co giãn đều đặn)
            self.tools_frame.columnconfigure((0, 1, 2), weight=1)
            self.tools_frame.columnconfigure((3, 4, 5), weight=0)
            self.btn_copy.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
            self.btn_trans_en.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
            self.btn_restore.grid(row=0, column=2, sticky="ew", padx=2, pady=2)
            self.btn_clean.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
            self.btn_speak.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
            self.btn_clear.grid(row=1, column=2, sticky="ew", padx=2, pady=2)
        else:
            # Mở rộng: 1 hàng x 6 cột
            self.tools_frame.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
            for col_idx, btn in enumerate(tool_buttons):
                btn.grid(row=0, column=col_idx, sticky="ew", padx=2, pady=2)

    def _on_window_configure(self, event):
        """Xử lý sự kiện thay đổi kích thước cửa sổ linh hoạt."""
        if event.widget != self:
            return

        w = event.width
        h = event.height
        is_narrow = (w < 530)
        is_short = (h < 560)

        if is_narrow != self.is_compact_width:
            self.is_compact_width = is_narrow
            self._apply_responsive_layout(is_narrow)

        if is_short != self.is_compact_height:
            self.is_compact_height = is_short
            h_btn = 34 if is_short else 40
            self.btn_ocr_big.configure(height=h_btn)
            self.btn_translate_big.configure(height=h_btn)

        # Cập nhật ngắt dòng linh hoạt cho các thẻ trong lịch sử
        new_wl = max(180, w - 90)
        for lbl in self.history_labels:
            try:
                lbl.configure(wraplength=new_wl)
            except Exception:
                pass

    def _build_history_tab(self):
        top_hist = ctk.CTkFrame(self.tab_history, fg_color="transparent")
        top_hist.pack(side="top", fill="x", padx=4, pady=(4, 8))

        ctk.CTkLabel(
            top_hist,
            text="Các đoạn văn bản đã trích xuất gần nhất:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=self.palette["text_main"]
        ).pack(side="left")

        ctk.CTkButton(
            top_hist,
            text="🗑️ Xóa toàn bộ lịch sử",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=self.palette["accent_red"],
            hover_color=self.palette["accent_red_hover"],
            height=28,
            corner_radius=6,
            command=self._clear_all_history
        ).pack(side="right")

        # Container cuộn danh sách thẻ lịch sử
        self.history_scroll = ctk.CTkScrollableFrame(
            self.tab_history,
            fg_color="transparent"
        )
        self.history_scroll.pack(fill="both", expand=True, padx=2, pady=2)

        self._refresh_history_ui()

    def _build_settings_tab(self):
        container = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=8, pady=4)

        sec_font = ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        sub_font = ctk.CTkFont(family="Segoe UI", size=11)

        # 1. OCR Engine
        ctk.CTkLabel(container, text="Bộ máy nhận diện OCR (Engine):", font=sec_font, text_color="#38bdf8").pack(anchor="w", pady=(8, 4))
        
        ctk.CTkRadioButton(
            container, text="Tự động (Ưu tiên Tesseract nếu có, tự động dùng Windows OCR dự phòng)",
            variable=self.ocr_engine_var, value="auto", font=sub_font,
            fg_color=self.palette["accent_blue"]
        ).pack(anchor="w", pady=4)

        ctk.CTkRadioButton(
            container, text="Windows Native OCR (Tích hợp sẵn Windows 10/11, siêu nhanh, không cần cài đặt)",
            variable=self.ocr_engine_var, value="winocr", font=sub_font,
            fg_color=self.palette["accent_blue"]
        ).pack(anchor="w", pady=4)

        ctk.CTkRadioButton(
            container, text="Tesseract OCR (Yêu cầu đã cài đặt phần mềm tesseract.exe ngoài)",
            variable=self.ocr_engine_var, value="tesseract", font=sub_font,
            fg_color=self.palette["accent_blue"]
        ).pack(anchor="w", pady=4)

        # Divider
        ctk.CTkFrame(container, height=1, fg_color=self.palette["card_border"]).pack(fill="x", pady=14)

        # 2. Phím tắt toàn cục
        ctk.CTkLabel(container, text="Phím tắt kích hoạt OCR:", font=sec_font, text_color="#38bdf8").pack(anchor="w", pady=(0, 4))
        
        hotkey_row = ctk.CTkFrame(container, fg_color="transparent")
        hotkey_row.pack(anchor="w", fill="x", pady=2)

        self.entry_hotkey = ctk.CTkEntry(
            hotkey_row,
            width=160,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=self.palette["textbox_bg"],
            border_color=self.palette["card_border"]
        )
        self.entry_hotkey.insert(0, self.config_data.get("hotkey_ocr", "<alt>+q"))
        self.entry_hotkey.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            hotkey_row,
            text="(Mặc định: <alt>+q. Nhấn phím này từ bất kỳ đâu để quét OCR)",
            font=sub_font,
            text_color=self.palette["text_sub"]
        ).pack(side="left")

        # Divider
        ctk.CTkFrame(container, height=1, fg_color=self.palette["card_border"]).pack(fill="x", pady=14)

        # 3. Tùy chọn hoạt động
        ctk.CTkLabel(container, text="Tùy chọn hoạt động:", font=sec_font, text_color="#38bdf8").pack(anchor="w", pady=(0, 4))

        ctk.CTkSwitch(
            container, text="Tự động gộp dòng khi quét OCR (Xóa ngắt dòng giữa câu)",
            variable=self.clean_linebreaks_var, font=sub_font, progress_color=self.palette["accent_blue"]
        ).pack(anchor="w", pady=6)

        ctk.CTkSwitch(
            container, text="Tự động dịch sang Tiếng Việt ngay khi vừa trích xuất chữ",
            variable=self.auto_translate_var, font=sub_font, progress_color=self.palette["accent_purple"]
        ).pack(anchor="w", pady=6)

        ctk.CTkSwitch(
            container, text="Thu nhỏ xuống khay hệ thống (System Tray) khi bấm nút Đóng [X]",
            variable=self.minimize_to_tray_var, font=sub_font, progress_color=self.palette["accent_blue"]
        ).pack(anchor="w", pady=6)

        ctk.CTkSwitch(
            container, text="Hiện biểu tượng dịch nổi 🌐 (Floating Icon) khi tắt/ẩn cửa sổ",
            variable=self.floating_translate_var, font=sub_font, progress_color=self.palette["accent_purple"]
        ).pack(anchor="w", pady=6)

        # Nút lưu cài đặt
        ctk.CTkButton(
            container,
            text="💾 LƯU TOÀN BỘ CÀI ĐẶT",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=self.palette["accent_green"],
            hover_color=self.palette["accent_green_hover"],
            height=40,
            corner_radius=8,
            command=self._save_all_settings
        ).pack(fill="x", pady=(20, 10))

    def _select_all(self, event=None):
        self.text_box.tag_add("sel", "1.0", "end")
        self.text_box.mark_set("insert", "1.0")
        self.text_box.see("insert")
        return "break"

    def _update_counter(self):
        text = self.text_box.get("1.0", "end-1c")
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        self.counter_lbl.configure(text=f"{chars} ký tự | {words} từ")

    def _toggle_always_on_top(self):
        is_top = self.always_on_top_var.get()
        self.wm_attributes("-topmost", is_top)
        self._save_quick_settings()

    def _on_auto_capture_toggle(self):
        self._save_quick_settings()
        if self.auto_capture_var.get():
            self.set_status("Đã bật tự động bắt văn bản bôi đen UIA.", "#10b981")
        else:
            self.set_status("Đã tạm dừng tự động bắt UIA. Bạn vẫn quét OCR bình thường.", "#f59e0b")

    def set_reader(self, reader):
        """Liên kết SelectionReader với UI."""
        self.reader = reader

    def _save_quick_settings(self):
        self.config_data["always_on_top"] = self.always_on_top_var.get()
        self.config_data["auto_capture"] = self.auto_capture_var.get()
        self.config_data["auto_copy"] = self.auto_copy_var.get()
        self.config_data["auto_translate"] = self.auto_translate_var.get()
        self.config_data["append_mode"] = self.append_mode_var.get()
        save_config(self.config_data)
        if hasattr(self, "reader") and self.reader:
            self.reader.set_auto_copy(self.auto_copy_var.get())

    def _save_all_settings(self):
        self.config_data["always_on_top"] = self.always_on_top_var.get()
        self.config_data["auto_capture"] = self.auto_capture_var.get()
        self.config_data["auto_copy"] = self.auto_copy_var.get()
        self.config_data["auto_translate"] = self.auto_translate_var.get()
        self.config_data["append_mode"] = self.append_mode_var.get()
        self.config_data["clean_linebreaks"] = self.clean_linebreaks_var.get()
        self.config_data["minimize_to_tray"] = self.minimize_to_tray_var.get()
        self.config_data["floating_translate_enabled"] = self.floating_translate_var.get()
        self.config_data["ocr_engine"] = self.ocr_engine_var.get()
        self.config_data["hotkey_ocr"] = self.entry_hotkey.get().strip() or "<alt>+q"
        save_config(self.config_data)
        if hasattr(self, "reader") and self.reader:
            self.reader.set_auto_copy(self.auto_copy_var.get())
        self.set_status("Đã lưu cấu hình thành công!", "#10b981")
        messagebox.showinfo("Cài đặt", "Đã lưu cài đặt thành công!")

    def add_history_entry(self, source, text):
        """Thêm một mục vào danh sách lịch sử và làm mới UI."""
        if not text or not text.strip():
            return
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "source": source,
            "text": text.strip()
        }
        self.history_items.insert(0, entry)
        limit = self.config_data.get("history_limit", 50)
        self.history_items = self.history_items[:limit]
        save_history(self.history_items, limit)
        self._refresh_history_ui()

    def set_status(self, message, dot_color="#10b981"):
        self.status_dot.configure(text_color=dot_color)
        self.status_lbl.configure(text=message)

    def update_text(self, new_text, source="UIA", info=""):
        if not new_text or not new_text.strip():
            return

        new_text = new_text.strip()
        self.last_original_text = new_text

        # Nối tiếp hoặc Ghi đè
        if self.append_mode_var.get():
            current = self.text_box.get("1.0", "end-1c")
            if current.strip():
                combined = current + "\n\n" + new_text
            else:
                combined = new_text
            self.text_box.delete("1.0", "end")
            self.text_box.insert("1.0", combined)
        else:
            self.text_box.delete("1.0", "end")
            self.text_box.insert("1.0", new_text)

        self._update_counter()

        # Lưu lịch sử
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "source": source,
            "text": new_text
        }
        self.history_items.insert(0, entry)
        limit = self.config_data.get("history_limit", 50)
        self.history_items = self.history_items[:limit]
        save_history(self.history_items, limit)
        self._refresh_history_ui()

        # Tự động copy nếu bật
        if self.auto_copy_var.get():
            self._copy_to_clipboard(silent=True)
            self.set_status(f"Đã trích xuất ({source}) & tự động chép vào Clipboard! {info}", "#10b981")
        else:
            self.set_status(f"Trích xuất thành công ({source})! {info}", "#10b981")

        # Tự động dịch sang Tiếng Việt nếu bật
        if self.auto_translate_var.get() and not source.startswith("Dịch"):
            self.after(150, lambda: self._translate_action("vi", is_auto=True))

    def _copy_to_clipboard(self, silent=False):
        text = self.text_box.get("1.0", "end-1c")
        if text.strip():
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            if not silent:
                self.set_status("Đã sao chép nội dung vào bộ nhớ tạm!", "#10b981")
        else:
            if not silent:
                self.set_status("Không có nội dung để sao chép.", "#f59e0b")

    def _clear_text(self):
        self.text_box.delete("1.0", "end")
        self._update_counter()
        self.set_status("Đã xóa sạch ô văn bản.", self.palette["text_sub"])

    def _translate_action(self, target_lang="vi", is_auto=False):
        text = self.text_box.get("1.0", "end-1c").strip()
        if not text:
            if not is_auto:
                self.set_status("Vui lòng nhập hoặc bắt chữ trước khi dịch.", "#f59e0b")
            return

        self.last_original_text = text
        lang_name = "Tiếng Việt" if target_lang == "vi" else "Tiếng Anh"
        self.set_status(f"Đang dịch sang {lang_name}...", "#38bdf8")

        def worker():
            trans = translate_text(text, target_lang=target_lang)
            self.msg_queue.put(("TRANSLATE_RESULT", (trans, target_lang, is_auto)))

        threading.Thread(target=worker, daemon=True).start()

    def _restore_original_text(self):
        if self.last_original_text and self.last_original_text.strip():
            self.text_box.delete("1.0", "end")
            self.text_box.insert("1.0", self.last_original_text)
            self._update_counter()
            self.set_status("Đã khôi phục văn bản gốc.", "#10b981")
        else:
            self.set_status("Chưa có văn bản gốc được lưu trước lần dịch này.", "#f59e0b")

    def _clean_lines_action(self):
        text = self.text_box.get("1.0", "end-1c")
        if text.strip():
            cleaned = clean_text_linebreaks(text)
            self.text_box.delete("1.0", "end")
            self.text_box.insert("1.0", cleaned)
            self._update_counter()
            self.set_status("Đã chuẩn hóa và gộp dòng văn bản.", "#10b981")

    def _speak_action(self):
        text = self.text_box.get("1.0", "end-1c").strip()
        if text:
            self.set_status("Đang phát âm văn bản...", "#38bdf8")
            speak_text_async(text)

    def _trigger_ocr(self):
        if self.on_ocr_callback:
            self.on_ocr_callback()

    # Quản lý Lịch sử (Hiển thị dạng thẻ Card hiện đại)
    def _refresh_history_ui(self):
        # Xóa các widget con cũ và reset danh sách labels
        self.history_labels.clear()
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        if not self.history_items:
            empty_frame = ctk.CTkFrame(self.history_scroll, fg_color="transparent")
            empty_frame.pack(fill="both", expand=True, pady=40)
            ctk.CTkLabel(
                empty_frame,
                text="Chưa có dữ liệu trích xuất nào.\nHãy bôi đen chữ hoặc bấm Alt+Q để quét OCR!",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=self.palette["text_sub"]
            ).pack()
            return

        for idx, entry in enumerate(self.history_items):
            self._create_history_card(idx, entry)

    def _create_history_card(self, idx, entry):
        source = entry.get("source", "UIA")
        text = entry.get("text", "")
        time_str = entry.get("time", "")

        card = ctk.CTkFrame(
            self.history_scroll,
            fg_color=self.palette["textbox_bg"],
            border_color=self.palette["card_border"],
            border_width=1,
            corner_radius=8
        )
        card.pack(fill="x", pady=4, padx=2)

        # Header của Card
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 4))

        # Màu badge theo nguồn
        badge_color = self.palette["badge_uia"]
        if "OCR" in source:
            badge_color = self.palette["badge_ocr"]
        elif "Dịch" in source:
            badge_color = self.palette["badge_trans"]

        badge = ctk.CTkLabel(
            header,
            text=f" {source} ",
            fg_color=badge_color,
            text_color="#ffffff",
            corner_radius=4,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold")
        )
        badge.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            header,
            text=time_str,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=self.palette["text_sub"]
        ).pack(side="left")

        # Nút thao tác trên thẻ
        btn_font = ctk.CTkFont(family="Segoe UI", size=10, weight="bold")

        ctk.CTkButton(
            header, text="❌", width=24, height=22, font=btn_font,
            fg_color="transparent", hover_color=self.palette["accent_red"],
            text_color=self.palette["text_sub"], command=lambda i=idx: self._delete_history_item(i)
        ).pack(side="right", padx=(3, 0))

        ctk.CTkButton(
            header, text="📋 Copy", width=55, height=22, font=btn_font,
            fg_color=self.palette["btn_neutral"], hover_color=self.palette["btn_neutral_hover"],
            command=lambda t=text: self._copy_text_direct(t)
        ).pack(side="right", padx=3)

        ctk.CTkButton(
            header, text="⬆️ Dán", width=50, height=22, font=btn_font,
            fg_color=self.palette["accent_blue"], hover_color=self.palette["accent_blue_hover"],
            command=lambda t=text: self._load_history_text(t)
        ).pack(side="right", padx=3)

        # Nội dung trích đoạn với wraplength linh hoạt theo độ rộng cửa sổ
        preview_text = text.replace("\n", " ").strip()
        if len(preview_text) > 140:
            preview_text = preview_text[:140] + "..."

        curr_width = self.winfo_width() if self.winfo_width() > 100 else 600
        content_lbl = ctk.CTkLabel(
            card,
            text=preview_text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=self.palette["text_main"],
            anchor="w",
            justify="left",
            wraplength=max(180, curr_width - 90)
        )
        content_lbl.pack(fill="x", padx=10, pady=(0, 8))
        self.history_labels.append(content_lbl)

    def _copy_text_direct(self, text):
        if text.strip():
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            self.set_status("Đã sao chép nội dung thẻ vào bộ nhớ tạm!", "#10b981")

    def _load_history_text(self, text):
        self.tabview.set("📄 Soạn thảo & Quét")
        self.update_text(text, source="Lịch sử")

    def _delete_history_item(self, idx):
        if 0 <= idx < len(self.history_items):
            self.history_items.pop(idx)
            save_history(self.history_items)
            self._refresh_history_ui()
            self.set_status("Đã xóa mục khỏi lịch sử.", self.palette["text_sub"])

    def _clear_all_history(self):
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa toàn bộ lịch sử không?"):
            self.history_items.clear()
            save_history(self.history_items)
            self._refresh_history_ui()
            self.set_status("Đã xóa sạch toàn bộ lịch sử.", self.palette["text_sub"])

    def _poll_queue(self):
        try:
            while True:
                task_type, data = self.msg_queue.get_nowait()
                self._handle_queue_msg(task_type, data)
        except queue.Empty:
            pass
        finally:
            self.after(20, self._poll_queue)

    def _handle_queue_msg(self, task_type, data):
        if task_type == "UIA_EVENT":
            # Hỗ trợ nhận diện (text, is_protected, bounds)
            text = data[0] if len(data) > 0 else ""
            is_protected = data[1] if len(data) > 1 else False
            bounds = data[2] if len(data) > 2 else None

            if not self.auto_capture_var.get():
                return

            is_hidden = not self.winfo_viewable() or self.state() in ("withdrawn", "iconic")

            if text and text.strip():
                # Khi tắt/ẩn cửa sổ tool, nếu bật tính năng thì xuất hiện icon dịch nổi
                if is_hidden and self.floating_translate_var.get():
                    self.floating_manager.show_icon(text, bounds)
                    # Cập nhật ô văn bản và lịch sử chạy ngầm
                    self.update_text(text, source="UIA")
                else:
                    self.update_text(text, source="UIA")
            elif is_protected:
                if not is_hidden:
                    self.set_status("Ứng dụng này chặn đọc trực tiếp. Nhấn Alt + Q để quét OCR.", "#f59e0b")

        elif task_type == "OCR_RESULT":
            text, engine_used, error = data
            if error:
                self.set_status(f"Lỗi: {error}", "#ef4444")
            elif text and text.strip():
                self.update_text(text, source="OCR", info=f"({engine_used})")
            else:
                self.set_status("Không nhận diện được chữ nào từ vùng đã chọn.", "#f59e0b")

        elif task_type == "TRANSLATE_RESULT":
            translated, target_lang, is_auto = data
            if translated and not translated.startswith("[Lỗi"):
                self.text_box.delete("1.0", "end")
                self.text_box.insert("1.0", translated)
                self._update_counter()
                lang_name = "Tiếng Việt" if target_lang == "vi" else "Tiếng Anh"
                self.set_status(f"Đã dịch sang {lang_name}! (Bấm '↩️ Bản gốc' để xem lại)", "#10b981")
                # Thêm vào lịch sử
                entry = {
                    "time": time.strftime("%H:%M:%S"),
                    "source": f"Dịch ({target_lang})",
                    "text": translated
                }
                self.history_items.insert(0, entry)
                save_history(self.history_items)
                self._refresh_history_ui()
                if self.auto_copy_var.get():
                    self._copy_to_clipboard(silent=True)
            else:
                self.set_status(f"{translated}", "#ef4444")

        elif task_type == "FLOATING_TRANSLATE_DONE":
            trans_text, src_lang, tgt_lang = data
            self.floating_manager._on_translation_finished(trans_text, src_lang, tgt_lang)

    def get_msg_queue(self):
        return self.msg_queue

    def _on_close_requested(self):
        if self.minimize_to_tray_var.get():
            self.withdraw()
            self.set_status("Đã thu nhỏ xuống Khay hệ thống.", self.palette["text_sub"])
        else:
            self._exit_app()

    def _exit_app(self):
        try:
            self.floating_manager.cleanup()
        except Exception:
            pass

        try:
            self.config_data["window_geometry"] = self.geometry()
            save_config(self.config_data)
        except Exception:
            pass

        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()
