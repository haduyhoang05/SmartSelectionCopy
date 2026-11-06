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

VIETNAMESE_CHARS_RE = re.compile(
    r'[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]',
    re.IGNORECASE
)

def query_translate_api_robust(text, sl="auto", tl="vi", timeout=6):
    """
    Truy vấn dịch thuật với đa cổng dự phòng (Multi-endpoint Failover):
    1. clients5.google.com (Cổng mở rộng của Chrome - siêu nhanh và nhẹ)
    2. translate.googleapis.com (Cổng GTX truyền thống)
    3. translate.google.com (Cổng web fallback)
    """
    clean = text.strip()[:2500]
    enc = urllib.parse.quote(clean)

    endpoints = [
        f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl={sl}&tl={tl}&q={enc}",
        f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl={tl}&dt=t&q={enc}",
        f"https://translate.google.com/translate_a/single?client=at&sl={sl}&tl={tl}&dt=t&q={enc}"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    last_err = None
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_data = resp.read().decode("utf-8")
                data = json.loads(raw_data)

                # Cấu trúc từ clients5: [['bản_dịch', 'ngôn_ngữ_phát_hiện']] hoặc ['bản_dịch', 'lang']
                if isinstance(data, list) and len(data) > 0:
                    first = data[0]
                    if isinstance(first, list):
                        if len(first) > 0 and isinstance(first[0], str) and len(first) <= 2:
                            det = first[1] if len(first) > 1 and isinstance(first[1], str) else sl
                            return first[0], det
                        elif len(first) > 0 and isinstance(first[0], list):
                            # GTX format
                            parts = [p[0] for p in first if p and p[0]]
                            det = data[2] if len(data) > 2 and isinstance(data[2], str) else sl
                            return "".join(parts), det
                    elif isinstance(first, str):
                        det = data[1] if len(data) > 1 and isinstance(data[1], str) else sl
                        return first, det
        except Exception as e:
            last_err = e
            continue

    raise last_err or Exception("Không thể kết nối đến tất cả máy chủ dịch")

def translate_text(text, target_lang="vi", timeout=6):
    """
    Dịch văn bản tự động sang ngôn ngữ đích (mặc định Tiếng Việt).
    Tự động chuyển cổng dự phòng nếu gặp sự cố mạng.
    """
    if not text or not text.strip():
        return ""

    try:
        import unicodedata
        trans, _ = query_translate_api_robust(text, sl="auto", tl=target_lang, timeout=timeout)
        return unicodedata.normalize("NFC", trans)
    except Exception as e:
        return f"[Lỗi dịch thuật: {e}]"

def translate_bidirectional(text, timeout=6):
    """
    Dịch 2 chiều thông minh (EN <-> VI):
    - Tự động nhận diện Tiếng Việt -> Dịch sang Tiếng Anh
    - Tự động nhận diện Tiếng Anh (hoặc ngôn ngữ khác) -> Dịch sang Tiếng Việt
    - Dự phòng 3 máy chủ Edge CDN của Google để loại bỏ hoàn toàn hiện tượng timed out.
    Trả về: (translated_text, source_lang, target_lang)
    """
    if not text or not text.strip():
        return "", "", ""

    clean_input = text.strip()
    is_vietnamese = bool(VIETNAMESE_CHARS_RE.search(clean_input))

    try:
        import unicodedata
        if is_vietnamese:
            # Chắc chắn là Tiếng Việt có dấu -> Dịch sang Tiếng Anh
            trans, _ = query_translate_api_robust(clean_input, sl="vi", tl="en", timeout=timeout)
            return unicodedata.normalize("NFC", trans), "vi", "en"
        else:
            # Chưa rõ ngôn ngữ -> Dịch sang tiếng Việt trước
            trans, det = query_translate_api_robust(clean_input, sl="auto", tl="vi", timeout=timeout)
            if det == "vi":
                # Tiếng Việt không dấu -> Dịch sang Tiếng Anh
                trans_en, _ = query_translate_api_robust(clean_input, sl="vi", tl="en", timeout=timeout)
                return unicodedata.normalize("NFC", trans_en), "vi", "en"
            else:
                return unicodedata.normalize("NFC", trans), det, "vi"
    except Exception as e:
        return f"[Lỗi dịch thuật: {e}]", "err", "err"

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
