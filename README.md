# Trình Bắt Văn Bản Bôi Đen & OCR Đa Năng (Smart Selection Copy & OCR)

Ứng dụng Windows hiện đại giúp tự động trích xuất văn bản đang được người dùng bôi đen (lựa chọn) trên bất kỳ ứng dụng nào khác (trình duyệt, Word, Excel, PDF, Google Docs...) hoặc chụp kéo chọn màn hình quét OCR siêu nhanh, hỗ trợ đầy đủ các tiện ích như tự động copy, dịch thuật, nối tiếp nội dung, đọc văn bản và lưu trữ lịch sử.

---

## 🌟 Các Tính Năng Nổi Bật

### 1. Cơ Chế Bắt Chữ Siêu Nhạy & Không Báo Lỗi Giả (Enhanced UIA)
* **Khắc phục hoàn toàn False-Positive**: Thuật toán phát hiện bôi đen thông minh phân biệt chính xác thao tác click chuột thường, rung tay và thao tác bôi đen thật sự. Không còn hiện cảnh báo hay nút cam khó chịu khi click chuột ra ngoài.
* **Hỗ trợ đa dạng Pattern**: Hỗ trợ đồng thời `TextPattern` và `TextPattern2` của Windows UI Automation.

### 2. Hybrid OCR Đa Engine (Windows Native OCR + Tesseract)
* **Không bắt buộc cài Tesseract**: Tích hợp sẵn **Windows Native OCR** (`Windows.Media.Ocr`), chạy mượt mà ngay trên Windows 10/11 mà không cần cài thêm phần mềm ngoài.
* **Tự động chuyển đổi thông minh (Auto Fallback)**: Nếu máy đã cài Tesseract với gói tiếng Việt, hệ thống sẽ ưu tiên Tesseract để nhận diện chuẩn dấu tiếng Việt; nếu không có, hệ thống tự động chuyển sang Windows Native OCR.
* **Hỗ trợ Đa Màn Hình & Tỉ lệ Thu Phóng (DPI Awareness)**: Công nghệ chụp ảnh desktop ảo bằng GDI trực tiếp khắc phục hoàn toàn lỗi lệch khung cắt trên hệ thống nhiều màn hình và các màn hình có tỉ lệ Scale (125%, 150%, 200%).
* **Tự động gộp dòng (Line Merge)**: Xóa các dấu xuống dòng gãy ngẫu nhiên giữa câu do OCR gây ra, giữ nguyên bố cục đoạn văn bản chuẩn.

### 3. Phím Tắt Toàn Cục & Khay Hệ Thống (Productivity & System Tray)
* **Kích hoạt tức thì**: Nhấn phím tắt **`Alt + Q`** ở bất kỳ đâu trên Windows để kích hoạt công cụ kéo chọn chụp và quét OCR màn hình.
* **Chạy ngầm dưới Khay hệ thống**: Khi bấm nút Đóng `[X]`, ứng dụng tự động thu nhỏ xuống System Tray thay vì tắt hẳn. Bạn có thể mở lại nhanh hoặc nhấp chuột phải chọn menu thao tác.

### 4. Thanh Công Cụ Tiện Ích Trực Tiếp (Quick Productivity Tools)
* **🌐 Dịch sang Tiếng Việt**: Nút bấm lớn màu tím nổi bật ngay cạnh nút Quét OCR.
* **[ ] Tự động Dịch**: Tùy chọn tự động dịch sang Tiếng Việt ngay khi vừa bắt/quét chữ tiếng nước ngoài.
* **📋 Sao chép (Copy)**: Chép nội dung vào Clipboard chỉ với 1 click.
* **🌐 Dịch sang Anh & ↩️ Bản gốc**: Dịch sang tiếng Anh hoặc xem lại bản gốc trước khi dịch.
* **🧹 Gộp dòng**: Chuẩn hóa văn bản, xóa ngắt dòng và khoảng trắng thừa.
* **🔊 Phát âm (TTS)**: Đọc văn bản tiếng Anh/Việt qua Microsoft Speech SAPI mà không gây đơ giao diện.
* **Tùy chọn nhanh**:
  - `Luôn trên cùng` (Always on top)
  - `Tự động bắt UIA` (Auto capture)
  - `Tự động Copy` (Auto-copy vào clipboard ngay khi bôi đen hoặc quét OCR)
  - `Tự động Dịch` (Auto-translate)
  - `Nối tiếp` (Append mode: thêm nội dung mới vào sau nội dung cũ thay vì ghi đè)

### 5. Quản Lý Lịch Sử Trích Xuất (History Management)
* Tự động lưu trữ danh sách các lần bôi đen và quét OCR gần nhất (kèm mốc thời gian, nguồn trích xuất).
* Dễ dàng xem lại, sao chép hoặc dán ngược trở lại ô soạn thảo chính.

---

## 📁 Cấu Trúc Dự Án (Project Structure)

```text
CCC/
├── assets/                     # Tài nguyên biểu tượng ứng dụng
│   ├── app_icon.ico            # File icon Windows
│   └── app_icon.png            # File ảnh icon PNG
├── dist/                       # Sản phẩm đã đóng gói
│   ├── SmartSelectionCopy/     # Thư mục ứng dụng chạy độc lập
│   │   └── SmartSelectionCopy.exe
│   └── SmartSelectionCopy.zip  # Bản nén sẵn sàng chia sẻ
├── config.py                   # Quản lý lưu/tải cài đặt (config.json) & lịch sử
├── main.py                     # Điểm khởi chạy chính của ứng dụng
├── ocr_helper.py               # Chụp màn hình GDI & Hybrid OCR đa engine
├── selection_reader.py         # Lắng nghe thao tác chuột/phím & bắt văn bản UIA
├── tray_helper.py              # Quản lý biểu tượng khay hệ thống (System Tray)
├── ui.py                       # Giao diện Tkinter hiện đại, đa tab, dark mode
├── utils.py                    # Tiện ích: Dịch thuật, TTS, chuẩn hóa văn bản
├── build_exe.py                # Script tự động đóng gói PyInstaller & dọn rác
├── requirements.txt            # Danh sách thư viện phụ thuộc
├── .gitignore                  # Quy định bỏ qua các file tạm/cache
└── README.md                   # Tài liệu hướng dẫn sử dụng chi tiết
```

---

## 🛠️ Hướng Dẫn Cài Đặt & Sử Dụng

### 1. Yêu cầu hệ thống
* Hệ điều hành: **Windows 10 / 11**
* Python: Phiên bản **Python 3.8 trở lên**

### 2. Cài đặt thư viện phụ thuộc
```bash
pip install -r requirements.txt
```

### 3. Chạy ứng dụng từ mã nguồn Python
```bash
python main.py
```

### 4. Chạy trực tiếp file thực thi .exe
* Bạn chỉ cần vào thư mục `dist\SmartSelectionCopy\` và nhấp đúp vào **`SmartSelectionCopy.exe`** để sử dụng ngay mà không cần cài đặt Python.

### 5. Đóng gói lại khi có chỉnh sửa mã nguồn
```bash
python build_exe.py
```
*(Script sẽ tự động build, dọn dẹp các thư mục rác như `build/`, `.spec` và tạo file nén zip trong `dist/`)*

---

## ⌨️ Phím Tắt Nhanh
* **`Alt + Q`**: Chụp và quét OCR màn hình từ bất kỳ đâu.
* **`ESC`** hoặc **Chuột phải**: Hủy bỏ thao tác kéo chọn quét OCR màn hình.
* **`Ctrl + A`**: Chọn toàn bộ văn bản trong ô soạn thảo.
