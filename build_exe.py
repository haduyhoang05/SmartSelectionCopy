# -*- coding: utf-8 -*-
"""
Smart Selection Copy - Script Đóng gói ứng dụng sang file thực thi .exe
Sử dụng PyInstaller
"""

import os
import sys
import shutil
import zipfile
import subprocess

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def build():
    print("Bắt đầu quy trình đóng gói ứng dụng Smart Selection Copy...")

    # Đảm bảo thư mục assets và file icon tồn tại
    os.makedirs("assets", exist_ok=True)
    ico_path = os.path.join("assets", "app_icon.ico")
    png_path = os.path.join("assets", "app_icon.png")

    if not os.path.exists(ico_path) or not os.path.exists(png_path):
        from PIL import Image, ImageDraw
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((4, 4, 60, 60), fill='#89b4fa')
        draw.rectangle((18, 16, 46, 50), fill='#1e1e2e')
        draw.line((22, 26, 42, 26), fill='#a6e3a1', width=3)
        draw.line((22, 34, 42, 34), fill='#cdd6f4', width=3)
        draw.line((22, 42, 36, 42), fill='#fab387', width=3)
        img.save(ico_path, format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
        img.save(png_path, format='PNG')

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=SmartSelectionCopy",
        "--windowed",
        "--noconfirm",
        "--clean",
        f"--icon={ico_path}",
        f"--add-data=assets;assets",
        "--hidden-import=pystray",
        "--hidden-import=pynput",
        "--hidden-import=pynput.keyboard",
        "--hidden-import=pynput.mouse",
        "--hidden-import=uiautomation",
        "--hidden-import=comtypes",
        "--hidden-import=comtypes.client",
        "--hidden-import=floating_widget",
        "--hidden-import=winocr",
        "--hidden-import=winrt",
        "--hidden-import=winrt.windows.media.ocr",
        "--hidden-import=winrt.windows.globalization",
        "--hidden-import=winrt.windows.graphics.imaging",
        "--hidden-import=winrt.windows.storage.streams",
        "--hidden-import=winrt.windows.foundation",
        "--collect-all=customtkinter",
        "--collect-all=darkdetect",
        "main.py"
    ]

    print("Đang thực thi PyInstaller:")
    print(" ".join(cmd))
    result = subprocess.run(cmd)

    if result.returncode == 0:
        # Tự động dọn dẹp thư mục tạm build/ và file .spec để giữ thư mục dự án sạch sẽ
        print("\nĐang dọn dẹp các file trung gian và file tạm...")
        if os.path.exists("build"):
            shutil.rmtree("build", ignore_errors=True)
        if os.path.exists("SmartSelectionCopy.spec"):
            try:
                os.remove("SmartSelectionCopy.spec")
            except Exception:
                pass

        # Nén thư mục dist/SmartSelectionCopy thành file zip
        zip_path = os.path.join("dist", "SmartSelectionCopy.zip")
        source_dir = os.path.join("dist", "SmartSelectionCopy")
        print("Đang nén bản phân phối thành file zip...")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, source_dir)
                    zipf.write(full_path, rel_path)

        print("\n=======================================================")
        print("✓ ĐÓNG GÓI THÀNH CÔNG VÀ ĐÃ DỌN DẸP SẠCH SẼ!")
        print("1. Thư mục chạy: dist\\SmartSelectionCopy\\SmartSelectionCopy.exe")
        print("2. Bản nén chia sẻ: dist\\SmartSelectionCopy.zip")
        print("=======================================================")
    else:
        print("\n❌ Quá trình đóng gói gặp lỗi!")

if __name__ == "__main__":
    build()
