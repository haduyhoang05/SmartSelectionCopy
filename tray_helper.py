# -*- coding: utf-8 -*-
"""
Smart Selection Copy - Hỗ trợ Khay hệ thống (System Tray)
Sử dụng pystray và Pillow để chạy ngầm trên Windows Taskbar.
"""
import os
import sys
import threading
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

def get_or_create_icon():
    """Tạo hoặc lấy icon ứng dụng."""
    candidates = [
        os.path.join(getattr(sys, "_MEIPASS", ""), "assets", "app_icon.png"),
        os.path.join(os.path.dirname(__file__), "assets", "app_icon.png"),
        "assets/app_icon.png",
        "app_icon.png"
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return Image.open(path)
            except Exception:
                pass

    # Tự tạo icon vẽ bằng Pillow nếu không có file
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill='#89b4fa')
    draw.rectangle((18, 16, 46, 50), fill='#1e1e2e')
    draw.line((22, 26, 42, 26), fill='#a6e3a1', width=3)
    draw.line((22, 34, 42, 34), fill='#cdd6f4', width=3)
    draw.line((22, 42, 36, 42), fill='#fab387', width=3)
    return img

class SystemTrayManager:
    def __init__(self, on_show, on_ocr, on_exit):
        """
        :param on_show: Hàm callback hiện lại cửa sổ chính
        :param on_ocr: Hàm callback kích hoạt quét OCR
        :param on_exit: Hàm callback tắt ứng dụng hoàn toàn
        """
        self.on_show = on_show
        self.on_ocr = on_ocr
        self.on_exit = on_exit
        self.icon = None
        self.thread = None

    def start(self):
        """Khởi chạy biểu tượng khay hệ thống trong luồng riêng."""
        image = get_or_create_icon()
        menu = (
            item('Mở Smart Selection Copy', self._on_show_clicked, default=True),
            item('📷 Quét màn hình OCR (Alt+Q)', self._on_ocr_clicked),
            item('Thoát hoàn toàn', self._on_exit_clicked)
        )
        self.icon = pystray.Icon(
            "SmartSelectionCopy",
            image,
            "Smart Selection Copy (Bắt bôi đen & OCR)",
            menu
        )
        self.thread = threading.Thread(target=self.icon.run, daemon=True)
        self.thread.start()

    def _on_show_clicked(self, icon, item):
        if self.on_show:
            self.on_show()

    def _on_ocr_clicked(self, icon, item):
        if self.on_ocr:
            self.on_ocr()

    def _on_exit_clicked(self, icon, item):
        self.stop()
        if self.on_exit:
            self.on_exit()

    def stop(self):
        """Dừng khay hệ thống."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
