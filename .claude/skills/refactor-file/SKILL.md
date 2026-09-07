---
name: refactor-file
description: >-
  Audit một file Python quá lớn và đề xuất plan tách thành các module con vừa đủ.
  Dùng khi user muốn refactor / breakdown / split một file (thường là file 200+
  dòng trong snapshot của docs/refactor_audit/REFACTOR.md), truyền target file
  làm args. Skill phân tích trách nhiệm, đề xuất tên file con + ước lượng line
  count theo heuristic 100–<200 dòng (không quá 300), gộp mảnh quá nhỏ, tôn trọng
  dependency rule trong docs/ARCHITECTURE.md, rồi thực thi sau khi user duyệt plan.
---

# Refactor file: tách file lớn thành module con vừa đủ

Mục tiêu: nhận một target file, đưa ra **plan audit** breakdown thành các file nhỏ
hơn, rồi thực thi sau khi user duyệt. Đây là project cá nhân — tách vừa đủ để dễ
đọc/review, **không** chia nhỏ tới mức atomic.

Target file lấy từ args. Nếu user không chỉ rõ, hỏi lại 1 câu; hoặc gợi ý chọn từ
snapshot line count trong `docs/refactor_audit/REFACTOR.md`.

## Heuristic sizing (bắt buộc tuân thủ)

- File con lý tưởng: **100 – dưới 200 dòng**.
- Được phép lố, nhưng **không quá 300 dòng**. Nếu một nhóm trách nhiệm > 300 dòng
  → phải tách tiếp thành 2 nhóm con.
- **Quá nhỏ thì đừng tách riêng.** Một mảnh < ~60–80 dòng và không có lý do
  boundary rõ ràng → gộp vào file con họ hàng gần nhất thay vì tạo file riêng.
- Ưu tiên số lượng file con **ít mà mỗi file cân**, hơn là nhiều file vụn.
  Đừng chia chỉ để chạm mốc dòng.
- Line count chỉ là tín hiệu. Boundary theo **trách nhiệm** mới là tiêu chí chính
  (xem `docs/refactor_audit/REFACTOR.md`: line count không tự động đồng nghĩa với
  over-responsibility).

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

- Đọc `docs/ARCHITECTURE.md`. Xác định target file thuộc boundary nào
  (`core` / `actions` / `control_events` / `runner` / `flows` / `screen_detect`).
- Plan tách **không được** vi phạm dependency rule (mục "Dependency direction" +
  các invariant). Ví dụ: không tạo file con trong `actions/` mà import `flows/`;
  `core` không import tầng trên.
- Nếu file là coordinator/public API (kiểu `automap.py`), giữ lại một file
  **coordinator mỏng** làm entrypoint public, đẩy phase/detail xuống package con
  (kiểu `automap_support/`). Không đổi public import path mà không nêu rõ.
- Kiểm tra `tests/test_hauntedroom_architecture.py` để không phá guardrail import.

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
- test nào có thể phải sửa (đường dẫn import trong `tests/`).

Nếu đang ở plan mode, đóng gói phần này qua ExitPlanMode. Nếu không, hỏi user xác
nhận trước khi sửa file. **Không tự thực thi khi chưa được duyệt.**

### 6. Thực thi (sau khi duyệt)

- Tạo các file con, di chuyển code, cập nhật import ở file gốc và mọi call site.
- Giữ public API ổn định: nếu file gốc từng được import trực tiếp, giữ nó (hoặc
  `__init__.py`) re-export để không phải sửa hàng loạt import bên ngoài.
- Mỗi bước đủ nhỏ để rollback độc lập.

### 7. Verify

- Chạy baseline từ repository root:

  ```shell
  uv run --with pytest pytest -q
  ```

- So với baseline trong `docs/refactor_audit/REFACTOR.md`
  (hiện `316 passed, 4 skipped, 103 subtests passed`). Không được giảm.
- Nếu file gốc từng nằm trong "Snapshot line count" của REFACTOR.md, cập nhật
  snapshot đó: xóa/sửa entry cũ, thêm file con mới nếu ≥ 200 dòng. Tuân quy tắc
  duy trì file của REFACTOR.md (không changelog, chỉ current state).

## Nhắc

- Đây là refactor cơ học giữ nguyên hành vi — **không** đổi logic/contract nhân
  tiện. Nếu thấy bug thật, báo riêng, đừng sửa lẫn vào.
- Nếu sau khi phân tích thấy file **không đáng tách** (đã cân, hoặc tách ra chỉ
  tạo file vụn), nói thẳng điều đó thay vì cố tách cho có.
