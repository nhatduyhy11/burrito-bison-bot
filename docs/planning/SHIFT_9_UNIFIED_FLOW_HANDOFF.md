# Handoff: Unified `Shift+9` Flow

## Mục tiêu

Gộp ba command hiện tại thành một command `Shift+9`:

- `Shift+5`: collect hero EXP.
- `Shift+6`: hero breakthrough.
- `Shift+9`: research.

`Shift+9` mới là wrapper mỏng. Khi bắt đầu, wrapper chụp màn hình đúng một lần,
xác định screen hiện tại, rồi dispatch sang flow tương ứng. Từ thời điểm đó child
flow chạy như hiện tại cho đến khi hoàn thành hoặc bị stop.

```text
Shift+9
  -> capture once
  -> classify current screen
     -> hero EXP screen       -> run_exp_available_flow
     -> hero breakthrough     -> run_hero_up_available_flow
     -> research screen       -> run_research_flow
     -> unknown/ambiguous     -> log and return idle
```

## Quyết định đã chốt

- Chỉ classify ở đầu wrapper; không capture lại để chọn flow khác.
- Không tự điều hướng giữa ba screen và không chuyển child flow giữa chừng.
- Tái sử dụng ba flow hiện tại; wrapper chỉ chịu trách nhiệm nhận diện và route.
- Screen detector phải nhận diện **loại screen**, không dựa riêng vào trạng thái
  "available". Ví dụ screen EXP không có badge hoặc hero không có dấu `!` vẫn
  phải được route đúng để child flow tự quyết định kết thúc.
- Nếu không nhận diện được duy nhất một screen, không chạy fallback flow. Ghi log
  kết quả detector và trả runner về idle.
- `Shift+5` và `Shift+6` được bỏ khỏi command table/menu; `Shift+9` là entrypoint
  duy nhất cho cả ba flow.

## Phạm vi triển khai

1. Thêm screen classifier nhận một frame và trả về một trong `exp`,
   `hero_breakthrough`, `research`, hoặc `unknown`.
2. Thêm wrapper flow cho `Shift+9`; wrapper capture một frame, classify, rồi
   `await` đúng child flow.
3. Đổi resolver/reload policy để dev reload nạp wrapper cùng các detector/child
   flow liên quan.
4. Xóa command mapping riêng cho phím `5` và `6`; cập nhật menu và tài liệu hotkey.
5. Giữ nguyên stop-event và giá trị trả về của child flow.

Tên module là quyết định triển khai; ưu tiên một module thể hiện đúng vai trò
wrapper thay vì nhét routing vào `runner/commands.py`.

## Testing cần có

- Mỗi fixture của ba screen route đúng child flow và chỉ gọi một child flow.
- Wrapper chỉ capture/classify một lần, kể cả khi child flow thay đổi UI sau đó.
- Screen hợp lệ nhưng không có action available vẫn route đúng loại screen.
- `unknown` hoặc nhiều detector cùng match không gọi child flow và về idle an toàn.
- Stop-event và kết quả `True`/`False` được truyền qua wrapper không đổi.
- Command table chỉ còn `Shift+9` cho nhóm chức năng này; dev reload vẫn hoạt động.

## Ngoài phạm vi

- Tự mở screen EXP, breakthrough hoặc research từ screen khác.
- Chạy tuần tự cả ba child flow trong một lần bấm.
- Theo dõi screen để tự chuyển flow trong lúc child flow đang chạy.
- Refactor business logic bên trong ba child flow nếu không cần cho routing.

## Tiêu chí hoàn thành

Từ bất kỳ một trong ba screen được hỗ trợ, bấm `Shift+9` sẽ chọn đúng flow dựa
trên capture ban đầu và giữ nguyên flow đó đến khi kết thúc. Phím `Shift+5` và
`Shift+6` không còn khởi chạy command riêng.
