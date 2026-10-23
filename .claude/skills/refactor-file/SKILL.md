---
name: refactor-file
description: >-
  Audit một file Python quá lớn và đề xuất plan tách thành các module con vừa đủ.
  Dùng khi user muốn refactor / breakdown / split một file, truyền target file
  làm args. Skill phân tích trách nhiệm, đề xuất tên file con + ước lượng line
  count theo heuristic 100–<200 dòng (không quá 300), gộp mảnh quá nhỏ, tôn trọng
  dependency direction hiện có, rồi thực thi sau khi user duyệt plan.
---

# Refactor file: tách file lớn thành module con vừa đủ

Mục tiêu: nhận một target file, đưa ra **plan audit** breakdown thành các file nhỏ
hơn, rồi thực thi sau khi user duyệt. Đây là project cá nhân — tách vừa đủ để dễ
đọc/review, **không** chia nhỏ tới mức atomic.

Target file lấy từ args. Nếu user không chỉ rõ, hỏi lại 1 câu.

## Heuristic sizing (bắt buộc tuân thủ)

- File con lý tưởng: **100 – dưới 200 dòng**.
- Được phép lố, nhưng **không quá 300 dòng**. Nếu một nhóm trách nhiệm > 300 dòng
  → phải tách tiếp thành 2 nhóm con.
- **Quá nhỏ thì đừng tách riêng.** Một mảnh < ~60–80 dòng và không có lý do
  boundary rõ ràng → gộp vào file con họ hàng gần nhất thay vì tạo file riêng.
- Ưu tiên số lượng file con **ít mà mỗi file cân**, hơn là nhiều file vụn.
  Đừng chia chỉ để chạm mốc dòng.
- Line count chỉ là tín hiệu. Boundary theo **trách nhiệm** mới là tiêu chí chính —
  line count không tự động đồng nghĩa với over-responsibility.

## Quy trình

### 1. Đọc & đo

- Read toàn bộ target file, đếm số dòng.
- Liệt kê các top-level symbol (class, function, constant block) kèm khoảng dòng
  của mỗi cái, để biết khối lượng thực của từng phần.

### 2. Nhóm theo trách nhiệm

Gom code thành các cluster theo trách nhiệm, không theo thứ tự vật lý. Với mỗi
cluster ghi:

- symbol nào thuộc về nó;
- ước lượng line count (gồm import/whitespace cần thiết);
- lý do nó là một boundary (được ai gọi, phụ thuộc gì).

Chú ý coupling: symbol dùng chung state/helper nội bộ nên ở cùng file; đừng cắt
đôi một đơn vị dính chặt chỉ vì line count.

### 3. Đối chiếu kiến trúc

- Xác định target file thuộc tầng nào trong package, và hướng import hiện có
  (tầng dưới không import tầng trên).
- Plan tách **không được** vi phạm dependency direction hiện có.
- Nếu file là coordinator/public API, giữ lại một file **coordinator mỏng** làm
  entrypoint public, đẩy phase/detail xuống package con. Không đổi public import
  path mà không nêu rõ.

### 4. Đề xuất tên file con

Đặt tên theo trách nhiệm, ngắn, snake_case, hợp giọng module lân cận trong cùng
package. Tránh tên chung chung (`utils.py`, `helpers.py`, `misc.py`) trừ khi thật
sự không có tên trách nhiệm rõ hơn. Nếu tách thành package, đề xuất layout
`dir/__init__.py` (re-export public API) + các file con.

### 5. Trình plan cho user duyệt

Xuất bảng breakdown:

| File con (đề xuất) | Trách nhiệm | Symbol chuyển vào | ~Dòng |
|---|---|---|---|

Kèm:

- file coordinator/entrypoint còn lại sau khi tách (và ~dòng);
- các import/`__init__` re-export cần thêm để giữ nguyên public API;
- rủi ro circular import và cách xử lý;
- test/call site nào có thể phải sửa theo import path mới.

Nếu đang ở plan mode, đóng gói phần này qua ExitPlanMode. Nếu không, hỏi user xác
nhận trước khi sửa file. **Không tự thực thi khi chưa được duyệt.**

### 6. Thực thi (sau khi duyệt)

- Tạo các file con, di chuyển code, cập nhật import ở file gốc và mọi call site.
- Giữ public API ổn định: nếu file gốc từng được import trực tiếp, giữ nó (hoặc
  `__init__.py`) re-export để không phải sửa hàng loạt import bên ngoài.
- Mỗi bước đủ nhỏ để rollback độc lập.

### 7. Verify

- Nếu repo còn test suite: chạy baseline từ repository root và so trước/sau,
  **không được giảm**.
- Nếu không: `uv run python -m py_compile` từng file đổi, và smoke-test entrypoint
  (ví dụ `--help`) để chắc import không gãy.

## Nhắc

- Đây là refactor cơ học giữ nguyên hành vi — **không** đổi logic/contract nhân
  tiện. Nếu thấy bug thật, báo riêng, đừng sửa lẫn vào.
- Nếu sau khi phân tích thấy file **không đáng tách** (đã cân, hoặc tách ra chỉ
  tạo file vụn), nói thẳng điều đó thay vì cố tách cho có.
