# Nghiên cứu giải pháp RapidOCR cho Game Automation (Haunted Room)

Tài liệu này tập trung giải đáp các thắc mắc về kỹ thuật, chi phí tài nguyên, kiến trúc hệ thống và khả năng thực tế của **RapidOCR** trong việc thay thế template matching chữ tiếng Anh, Trung, Việt.

---

## 1. Chi phí chạy (Running Cost: CPU, RAM, Disk)

RapidOCR cực kỳ tối ưu vì chạy trực tiếp trên **ONNX Runtime** (viết bằng C++), loại bỏ hoàn toàn các framework nặng như PyTorch hay PaddlePaddle.

*   **Dung lượng ổ đĩa (Disk Size):**
    *   Thư viện cài đặt (`pip install rapidocr_onnxruntime` + `onnxruntime`) nặng khoảng **80MB - 100MB**.
    *   Các file model ONNX (đã được tích hợp sẵn hoặc tự động tải về trong lần chạy đầu tiên) chỉ nặng khoảng **15MB - 30MB** (gồm cả Det và Rec model).
*   **Bộ nhớ RAM tiêu thụ (RAM Usage):**
    *   Khi khởi tạo một đối tượng `RapidOCR`, lượng RAM tăng thêm chỉ khoảng **30MB - 50MB**. Đây là con số rất nhỏ so với các OCR dựa trên Deep Learning thông thường (thường ngốn từ 500MB đến hơn 1GB RAM).
*   **Hiệu năng CPU (CPU Overhead):**
    *   **Ảnh chụp toàn màn hình (ví dụ 640x720):** Tốn khoảng **150ms - 300ms** trên một nhân CPU trung bình.
    *   **Ảnh cắt nhỏ (ROI - ví dụ vùng chữ tên Hero 150x40):** Chỉ tốn **10ms - 30ms** cho mỗi lần chạy.
    *   ONNX Runtime hỗ trợ đa luồng (multi-threading) cực tốt ở tầng C++, do đó việc xử lý các vùng crop nhỏ hầu như không gây nghẽn CPU hoặc ảnh hưởng đến trải nghiệm game.

---

## 2. Thiết kế kiến trúc khi chạy nhiều Playwright Instance

Khi chạy đồng thời nhiều tab/instance Playwright (Multi-instance), việc tổ chức module OCR rất quan trọng để tránh nghẽn CPU và lãng phí RAM.

### Phương án A: Khởi tạo cục bộ (Local Instance) cho mỗi Worker
Mỗi tiến trình bot (hoặc mỗi worker điều khiển Playwright) tự khởi tạo một đối tượng `RapidOCR()` riêng.

*   **Đặc điểm:**
    *   Mỗi worker tốn thêm ~50MB RAM. Nếu chạy 10 instances song song, tổng RAM tiêu hao cho OCR là ~500MB (rất khả thi trên PC/Server thông thường).
    *   Nếu các worker chạy dưới dạng các **tiến trình độc lập (Multiprocessing hoặc các tiến trình OS riêng biệt)**, CPU sẽ tận dụng được tối đa đa nhân mà không bị ảnh hưởng bởi Python GIL (Global Interpreter Lock).
*   **Khi nào dùng:** Số lượng instance chạy đồng thời ít (dưới 4 instances) hoặc các instance chạy ở các tiến trình Python hoàn toàn độc lập.

### Phương án B: Tách thành Subproject / Microservice độc lập (Khuyên Dùng khi scale lớn)
Tách OCR thành một dịch vụ Web API siêu nhẹ (sử dụng FastAPI + Uvicorn) chạy trên cổng `localhost:8000`. Các worker Playwright chỉ việc gửi ảnh crop dưới dạng bytes qua HTTP POST hoặc gRPC và nhận về kết quả JSON.

*   **Đặc điểm:**
    *   **Tiết kiệm RAM:** Chỉ load model ONNX đúng 1 lần vào RAM duy nhất (chỉ tốn 50MB RAM cho toàn hệ thống).
    *   **Tránh nghẽn CPU:** Dịch vụ API có thể quản lý luồng xử lý hàng đợi (Queue), xử lý bất đồng bộ (Async) và tận dụng ONNX Runtime thread pool để điều phối CPU tối ưu nhất.
    *   **Dễ dàng bảo trì:** Bot runner không cần cài đặt các thư viện OCR hay ONNX, giúp runner nhẹ hơn. Nếu cần nâng cấp model OCR, chỉ cần cập nhật ở server OCR mà không cần sửa code của từng bot.
*   **Khi nào dùng:** Khi chạy từ 4 instances Playwright trở lên hoặc chạy phân tán trên nhiều máy.

---

## 3. Độ phức tạp và lượng code cần implement

Để kiểm tra nhanh (Quick Test) hoặc đưa vào vận hành thực tế, lượng code viết rất ngắn và đơn giản.

*   **Độ phức tạp:** Thấp. Không cần cấu hình phức tạp hay cài đặt thêm phần mềm bên ngoài (như Tesseract OCR yêu cầu cài EXE/Binary vào hệ thống). Chỉ cần thư viện Python.
*   **Các bước triển khai:**
    1.  Cài đặt thư viện: `pip install rapidocr_onnxruntime`
    2.  Đọc ảnh/crop ảnh bằng OpenCV nhị phân hoặc màu.
    3.  Truyền ảnh vào engine và nhận kết quả dạng chuỗi văn bản.

---

## 4. Khả năng nhận diện thực tế (Chữ tiếng Việt, tiếng Trung, tên Hero)

RapidOCR kế thừa bộ model từ **PaddleOCR** (được đánh giá là một trong những bộ OCR mã nguồn mở tốt nhất hiện nay cho chữ dạng cảnh vật và UI).

*   **Tên Hero tiếng Việt/Anh/Trung (ví dụ: "Hắc Lữ Bố", "Hanuman", "Vua Pháp Sư"):**
    *   Khả năng nhận diện cực tốt nhờ mô hình nhận diện ký tự tiếng Trung và tiếng Việt có dấu.
    *   Khi cắt đúng vùng tên Hero trên thẻ bài, ảnh không bị nhiễu nền, OCR có thể đạt độ chính xác **>98%**.
*   **Khắc phục lỗi phông chữ / sai lệch nhỏ:**
    *   Thay vì so khớp tuyệt đối như template matching (`==`), khi dùng OCR ta sẽ dùng so khớp chuỗi mềm (Fuzzy String Matching) hoặc tìm kiếm từ khóa con.
    *   *Ví dụ:* Nếu OCR đọc ra `"Hắc Lữ Bố"` hoặc do font game cách điệu bị đọc lệch nhẹ thành `"Hắc Lử Bố"`, đoạn code kiểm tra `"lữ bố" in text.lower()` hoặc dùng thư viện `difflib` để so sánh độ tương đồng vẫn sẽ nhận diện đúng 100% mục tiêu.

---

## 5. Hướng dẫn Test Nhanh (Quick Test Setup)

Để chạy thử nghiệm trên máy của bạn ngay lập tức, bạn chỉ cần thực hiện 2 bước đơn giản sau:

### Bước 1: Cài đặt môi trường
Mở Terminal tại thư viện ảo của dự án và chạy:
```bash
pip install rapidocr_onnxruntime
```

### Bước 2: Chạy Script Test trực tiếp bằng Python
Dưới đây là mã nguồn của một script kiểm tra độc lập (bạn có thể lưu thành `test_ocr.py` ngoài thư mục dự án để chạy thử):

```python
import cv2
from rapidocr_onnxruntime import RapidOCR

# 1. Khởi tạo engine OCR (chỉ chạy 1 lần)
engine = RapidOCR()

# 2. Đọc ảnh screenshot game (hoặc ảnh crop sẵn tên Hero)
# Thay bằng đường dẫn ảnh thực tế của bạn
image_path = "path/to/hero_card_screenshot.png"
img = cv2.imread(image_path)

if img is None:
    print(f"Không thể đọc file ảnh: {image_path}")
else:
    # 3. Chạy OCR trực tiếp trên ảnh (hoặc crop vùng cần test)
    # Ví dụ crop: img_crop = img[y1:y2, x1:x2]
    results, elapse = engine(img)
    
    # 4. In kết quả nhận diện ra console
    print(f"Thời gian xử lý: {elapse} giây")
    if results:
        for idx, line in enumerate(results):
            # line format: [ [ [x1, y1], [x2, y2], [x3, y3], [x4, y4] ], text, confidence ]
            box, text, score = line
            print(f"Ký tự {idx + 1}: '{text}' (Độ tin cậy: {score:.2f})")
    else:
        print("Không phát hiện chữ nào trong ảnh.")
```
