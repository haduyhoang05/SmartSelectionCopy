# -*- coding: utf-8 -*-
"""
Smart Selection Copy - Trình xử lý Chụp màn hình Đa màn hình và OCR Đa Engine
Hỗ trợ:
1. Windows Native OCR (winocr / WinRT) - Chạy ngay trên Windows 10/11 không cần cài đặt thêm.
2. Tesseract OCR (pytesseract) - Nhận diện tiếng Việt chuyên sâu offline.
3. Chụp màn hình đa màn hình bằng GDI siêu tốc & khắc phục hoàn toàn lỗi lệch DPI.
"""

import os
import ctypes
from ctypes import wintypes
import subprocess
import tkinter as tk
from PIL import Image, ImageTk, ImageEnhance, ImageGrab
from utils import clean_text_linebreaks

# Kiểm tra thư viện winocr
HAS_WINOCR = False
try:
    import winocr
    HAS_WINOCR = True
except Exception:
    HAS_WINOCR = False

def find_tesseract_cmd():
    """Tự động quét tìm đường dẫn cài đặt tesseract.exe trên Windows."""
    try:
        subprocess.run(["tesseract", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "tesseract"
    except Exception:
        pass

    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe")
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path
    return None

def configure_tesseract():
    """Cấu hình pytesseract đường dẫn tesseract_cmd."""
    try:
        import pytesseract
        cmd = find_tesseract_cmd()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
            return True
    except Exception:
        pass
    return False

def capture_virtual_screen():
    """
    Chụp toàn bộ màn hình (kể cả hệ thống đa màn hình) bằng GDI BitBlt.
    Khắc phục triệt để lỗi ImageGrab bị fail hoặc lệch tọa độ khi dùng nhiều màn hình.
    Trả về: (Image, vx, vy, vw, vh)
    """
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    # Lấy tọa độ không gian desktop ảo (Virtual Screen)
    vx = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
    vy = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
    vw = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
    vh = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN

    if vw <= 0 or vh <= 0:
        # Fallback về màn hình đơn cơ bản nếu metrics lỗi
        vw = user32.GetSystemMetrics(0)
        vh = user32.GetSystemMetrics(1)
        vx = 0
        vy = 0

    try:
        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, vw, vh)
        gdi32.SelectObject(hdc_mem, hbmp)

        # SRCCOPY (0x00CC0020) | CAPTUREBLT (0x40000000)
        gdi32.BitBlt(hdc_mem, 0, 0, vw, vh, hdc_screen, vx, vy, 0x00CC0020 | 0x40000000)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD),
                ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = vw
        bmi.biHeight = -vh  # top-down DIB
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buffer_size = vw * vh * 4
        buf = ctypes.create_string_buffer(buffer_size)
        lines = gdi32.GetDIBits(hdc_mem, hbmp, 0, vh, buf, ctypes.byref(bmi), 0)

        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

        if lines > 0:
            img = Image.frombuffer('RGBA', (vw, vh), buf, 'raw', 'BGRA', 0, 1)
            return img.convert('RGB'), vx, vy, vw, vh
    except Exception as e:
        print(f"Lỗi chụp màn hình GDI: {e}, chuyển sang ImageGrab fallback.")

    # Fallback ImageGrab nếu GDI gặp sự cố
    try:
        fallback_img = ImageGrab.grab(all_screens=True)
        return fallback_img, vx, vy, vw, vh
    except Exception:
        fallback_img = ImageGrab.grab()
        return fallback_img, 0, 0, fallback_img.width, fallback_img.height

def preprocess_image(image):
    """Tiền xử lý ảnh để nâng cao tỷ lệ nhận diện chữ."""
    # 1. Chuyển ảnh xám
    gray = image.convert("L")
    # 2. Tăng độ tương phản (1.8x - 2.0x)
    enhancer = ImageEnhance.Contrast(gray)
    contrasted = enhancer.enhance(1.8)
    # 3. Nếu ảnh quá nhỏ (chiều cao < 80px), phóng to 2x bằng Lanczos để rõ nét chữ
    w, h = contrasted.size
    if h < 100:
        contrasted = contrasted.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
    return contrasted

def run_ocr(image, engine_pref="auto", clean_breaks=True):
    """
    Chạy nhận diện ký tự từ ảnh với cơ chế Hybrid:
    - Thử Tesseract nếu máy đã cài (tối ưu tiếng Việt).
    - Tự động chuyển đổi sang Windows Native OCR (không cần cài thêm gì) nếu Tesseract không có sẵn.
    Trả về: (text: str, engine_used: str, err: str)
    """
    if image is None:
        return "", "", "Ảnh không hợp lệ."

    processed_img = preprocess_image(image)
    text = ""
    engine_used = ""
    err = None

    # Thử Tesseract trước nếu người dùng để auto hoặc chọn tesseract
    tesseract_available = configure_tesseract()
    
    if (engine_pref in ("auto", "tesseract")) and tesseract_available:
        try:
            import pytesseract
            raw_text = pytesseract.image_to_string(processed_img, lang="vie+eng")
            if raw_text and raw_text.strip():
                text = raw_text.strip()
                engine_used = "Tesseract OCR (vie+eng)"
        except Exception as e:
            err = f"Lỗi Tesseract: {e}"

    # Nếu Tesseract chưa lấy được chữ hoặc không có sẵn, thử Windows Native OCR
    if not text and (engine_pref in ("auto", "winocr")) and HAS_WINOCR:
        try:
            # Chạy Windows Native OCR
            result = winocr.recognize_pil_sync(image, lang="en")
            raw_text = result.get("text", "")
            if raw_text and raw_text.strip():
                text = raw_text.strip()
                engine_used = "Windows Native OCR"
                err = None
        except Exception as e:
            if not err:
                err = f"Lỗi Windows Native OCR: {e}"

    # Nếu vẫn chưa được và Tesseract khả dụng nhưng ném lỗi
    if not text and not engine_used:
        if not tesseract_available and not HAS_WINOCR:
            return "", "", "Chưa có công cụ OCR nào khả dụng trên máy (Tesseract hoặc WinRT)."
        if not text:
            return "", "", err if err else "Không nhận diện được ký tự nào từ vùng đã chọn."

    # Làm sạch ngắt dòng nếu được bật
    if clean_breaks and text:
        text = clean_text_linebreaks(text)

    return text, engine_used, None


class ScreenCropper:
    """
    Cửa sổ toàn màn hình che phủ toàn bộ hệ thống màn hình (kể cả đa màn hình)
    để kéo chọn vùng quét OCR với hiệu ứng làm tối nền trực quan.
    """
    def __init__(self, parent, on_crop_callback):
        self.parent = parent
        self.on_crop_callback = on_crop_callback

        # 1. Chụp lại toàn bộ màn hình trước khi hiển thị khung chọn
        self.screenshot, self.vx, self.vy, self.vw, self.vh = capture_virtual_screen()

        # Tạo ảnh tối cho nền
        enhancer = ImageEnhance.Brightness(self.screenshot)
        self.screenshot_dark = enhancer.enhance(0.45)

        # 2. Tạo cửa sổ đè toàn bộ màn hình ảo
        self.root = tk.Toplevel(parent)
        self.root.overrideredirect(True)
        self.root.geometry(f"{self.vw}x{self.vh}+{self.vx}+{self.vy}")
        self.root.attributes("-topmost", True)
        self.root.focus_force()

        # Canvas chuẩn bị ảnh
        self.photo_dark = ImageTk.PhotoImage(self.screenshot_dark)
        self.canvas = tk.Canvas(
            self.root,
            width=self.vw,
            height=self.vh,
            bd=0,
            highlightthickness=0,
            cursor="cross"
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self.photo_dark, anchor="nw")

        # Hướng dẫn trên màn hình
        self.guide_text_id = self.canvas.create_text(
            self.vw // 2, 40,
            text="Nhấn giữ chuột trái và kéo chọn vùng chữ. Nhấn ESC hoặc Chuột phải để hủy.",
            fill="#ffffff",
            font=("Segoe UI", 13, "bold"),
            anchor="center"
        )

        self.start_x = 0
        self.start_y = 0
        self.rect_id = None
        self.dim_label_id = None
        self.photo_crop = None
        self.image_on_top_id = None

        # Liên kết sự kiện
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<ButtonPress-3>", lambda e: self._cancel())  # Chuột phải hủy
        self.root.bind("<Escape>", lambda e: self._cancel())

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="#89b4fa", width=2, dash=(4, 4)
        )
        self.dim_label_id = self.canvas.create_text(
            self.start_x, self.start_y - 15,
            text="", fill="#a6e3a1", font=("Segoe UI", 10, "bold"), anchor="sw"
        )

    def _on_drag(self, event):
        cur_x = event.x
        cur_y = event.y

        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

        x1, x2 = min(self.start_x, cur_x), max(self.start_x, cur_x)
        y1, y2 = min(self.start_y, cur_y), max(self.start_y, cur_y)
        w = x2 - x1
        h = y2 - y1

        if self.dim_label_id:
            self.canvas.coords(self.dim_label_id, x1, max(20, y1 - 8))
            self.canvas.itemconfig(self.dim_label_id, text=f"{w} x {h} px")

        # Làm sáng vùng chọn
        if w > 2 and h > 2:
            try:
                cropped = self.screenshot.crop((x1, y1, x2, y2))
                self.photo_crop = ImageTk.PhotoImage(cropped)
                if self.image_on_top_id:
                    self.canvas.delete(self.image_on_top_id)
                self.image_on_top_id = self.canvas.create_image(
                    x1, y1, image=self.photo_crop, anchor="nw"
                )
                self.canvas.tag_raise(self.rect_id)
                if self.dim_label_id:
                    self.canvas.tag_raise(self.dim_label_id)
            except Exception:
                pass

    def _on_release(self, event):
        end_x = event.x
        end_y = event.y

        self.root.destroy()

        x1, x2 = min(self.start_x, end_x), max(self.start_x, end_x)
        y1, y2 = min(self.start_y, end_y), max(self.start_y, end_y)

        if (x2 - x1) > 6 and (y2 - y1) > 6:
            cropped_image = self.screenshot.crop((x1, y1, x2, y2))
            self.on_crop_callback(cropped_image)
        else:
            self.on_crop_callback(None)

    def _cancel(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        self.on_crop_callback(None)
