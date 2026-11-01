# -*- coding: utf-8 -*-
"""
Smart Selection Copy - Quản lý cấu hình và lưu trữ
"""
import os
import json

CONFIG_FILE = "config.json"
HISTORY_FILE = "history.json"

DEFAULT_CONFIG = {
    "always_on_top": True,
    "auto_capture": True,
    "auto_copy": False,
    "auto_translate": False,
    "append_mode": False,
    "clean_linebreaks": True,
    "minimize_to_tray": True,
    "hotkey_ocr": "<alt>+q",
    "ocr_engine": "auto",  # "auto", "winocr", "tesseract"
    "history_limit": 50,
    "window_geometry": "580x620"
}

def load_config():
    """Tải cấu hình từ file config.json."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                return config
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Lưu cấu hình vào file config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Lỗi lưu cấu hình: {e}")

def load_history():
    """Tải lịch sử bôi đen/OCR từ history.json."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_history(history_list, limit=50):
    """Lưu danh sách lịch sử."""
    try:
        truncated = history_list[:limit]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(truncated, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Lỗi lưu lịch sử: {e}")
