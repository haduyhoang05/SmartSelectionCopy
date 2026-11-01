# -*- coding: utf-8 -*-
"""
Smart Selection Copy - Bộ công cụ tiện ích (Dịch thuật, Chuẩn hóa văn bản, Text-to-Speech)
"""
import re
import json
import threading
import urllib.request
import urllib.parse

def clean_text_linebreaks(text):
    """
    Chuẩn hóa văn bản OCR:
    Nối các dòng bị ngắt ngẫu nhiên giữa câu, giữ lại ngắt dòng thực sự (2 dấu xuống dòng hoặc sau dấu chấm).
    """
    if not text:
        return ""
    
    lines = text.splitlines()
    merged = []
    current_para = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_para:
                merged.append(" ".join(current_para))
                current_para = []
            merged.append("")
        else:
            current_para.append(stripped)
            # Nếu dòng kết thúc bằng dấu câu kết đoạn (. ! ? : ")
            if stripped[-1] in ".!?:\"'":
                merged.append(" ".join(current_para))
                current_para = []
                
    if current_para:
        merged.append(" ".join(current_para))
        
    result = "\n".join(merged)
    # Loại bỏ khoảng trắng thừa
    result = re.sub(r"[ \t]+", " ", result)
    # Loại bỏ nhiều dòng trống liên tiếp
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()

def clean_whitespace(text):
    """Xóa bỏ các khoảng trắng thừa đầu dòng, cuối dòng và khoảng trắng kép."""
    if not text:
        return ""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(lines).strip()

def translate_text(text, target_lang="vi", timeout=5):
    """
    Dịch văn bản tự động sang ngôn ngữ đích (mặc định Tiếng Việt)
    Sử dụng Google Translate API công khai nhẹ nhàng, không cần API Key.
    """
    if not text or not text.strip():
        return ""
    
    clean_input = text.strip()
    # Giới hạn độ dài để tránh vượt quá URL query limit
    if len(clean_input) > 2000:
        clean_input = clean_input[:2000]
        
    encoded_text = urllib.parse.quote(clean_input)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={encoded_text}"
    
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    
    try:
        import unicodedata
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw_data = response.read().decode("utf-8")
            data = json.loads(raw_data)
            translated_parts = [part[0] for part in data[0] if part and part[0]]
            combined = "".join(translated_parts)
            return unicodedata.normalize("NFC", combined)
    except Exception as e:
        return f"[Lỗi dịch thuật: {e}]"

def speak_text_async(text):
    """
    Phát âm văn bản trong luồng riêng sử dụng Microsoft SAPI SpVoice tích hợp sẵn trên Windows.
    """
    if not text or not text.strip():
        return
        
    def _speak_worker():
        try:
            import comtypes
            import comtypes.client
            comtypes.CoInitialize()
            voice = comtypes.client.CreateObject("SAPI.SpVoice")
            voice.Speak(text[:500])  # Giới hạn 500 ký tự để không bị kẹt giọng nói
            comtypes.CoUninitialize()
        except Exception:
            pass

    t = threading.Thread(target=_speak_worker, daemon=True)
    t.start()
