# Haunted Room Runner

Mã nguồn Burrito Bison cũ được giữ làm tài liệu tham khảo độc lập tại
[`ref_cv/`](ref_cv/README.md); runner và test ở root hiện chỉ dành cho Haunted Room.

Runner Playwright dùng OpenCV template matching để tìm và click các nút trong Haunted Room. Script dùng browser context của Playwright, không điều khiển chuột ở cấp hệ điều hành.

## Yêu cầu

- Có [`uv`](https://docs.astral.sh/uv/) trong `PATH`.
- Đã cài Google Chrome trên Windows hoặc macOS.
- Chạy lệnh từ thư mục gốc của repo.

Playwright được khai báo trong `pyproject.toml` và khóa phiên bản trong `uv.lock`. Cài hoặc đồng bộ toàn bộ dependency bằng:

```shell
uv sync
```

Khi cần thêm Playwright vào một project `uv` mới, lệnh tương đương phù hợp với `pip install playwright` là `uv add playwright`; lệnh này cập nhật cả `pyproject.toml` và `uv.lock`. Browser mặc định là Chrome cài trên máy và được Playwright tự tìm theo hệ điều hành, không dùng đường dẫn hardcoded.

## Lệnh chạy

Mở runner với action mặc định. Với `ACTION_LOOP_COUNT = 0`, runner vào chế độ standby:

```shell
uv run python tools/hauntedroom_runner.py
```

Khi đang phát triển auto-map, bật hot-reload để giữ nguyên browser và session:

```powershell
uv run python tools/hauntedroom_runner.py --dev-reload
```

Sau khi sửa `hauntedroom/flows/automap.py`, `hauntedroom/core/vision.py` hoặc template PNG, bấm `Shift+0` để dừng flow cũ rồi `Shift+2` để reload và chạy code mới. Nếu reload lỗi syntax/import, runner vẫn mở và ở trạng thái idle để sửa file rồi thử lại.

Với `ACTION_LOOP_COUNT = 0`, standby đã tự giữ browser mở cho tới khi bấm `Ctrl+C`, vì vậy không cần thêm `--keep-open` vào lệnh hot-reload. `--keep-open` chỉ có tác dụng khi cấu hình `ACTION_LOOP_COUNT` lớn hơn `0`.

Khi cấu hình `ACTION_LOOP_COUNT` lớn hơn `0`, giữ browser mở sau khi chạy xong:

```shell
uv run python tools/hauntedroom_runner.py --keep-open
```

Chạy một file action khác:

```shell
uv run python tools/hauntedroom_runner.py --actions tools/my_actions.json
```

Các tùy chọn thường dùng:

- `--browser chrome`: dùng Google Chrome; đây là mặc định và hoạt động trên Windows/macOS.
- `--browser msedge`: dùng Microsoft Edge đã cài trên máy.
- `--browser chromium`: dùng Chromium do Playwright quản lý; browser binary phải được cài riêng.
- `--headless`: chạy không hiển thị cửa sổ browser.
- `--width` và `--height`: thay đổi viewport; mặc định hiện tại là `640x720`.
- `--profile`: thay đổi thư mục browser profile.
- `--url`: thay đổi URL đích.
- `--dev-reload`: reload module auto-map và vision mỗi lần bắt đầu `Shift+2`; dùng cho vòng lặp debug `Shift+0` → sửa code/template → `Shift+2`.
- `--keep-open`: chỉ giữ browser sau khi action hoàn tất khi `ACTION_LOOP_COUNT > 0`; không cần trong standby mặc định.

Xem toàn bộ tùy chọn:

```shell
uv run python tools/hauntedroom_runner.py --help
```

## Action file

File action là một JSON array. Runner chạy tuần tự toàn bộ array rồi lặp lại theo `ACTION_LOOP_COUNT` trong `tools/hauntedroom/core/runtime.py`.

Khi `ACTION_LOOP_COUNT = 0`, runner load action rồi vào chế độ standby:

- `Shift+1`: chạy flow enter-exit room liên tục.
- `Shift+2`: chạy riêng flow auto-map sau khi đã vào map và bấm `start_battle` thủ công. Priority là interrupt `automap/lv_spin.png` trước, sau đó check terminal `automap/map_end.png` tối đa mỗi 5 giây, phát hiện thanh HP boss trong vùng critical, rồi bảo vệ cửa, `automap/lv_up.png`, và `automap/built.png`. Boss được nhận diện bằng các cạnh sọc dọc của `boss/boss_hp_bar.png` ở đúng kích thước boss, không phụ thuộc màu. Khi boss vào vùng, bot click `exit_click.png` đúng một lần rồi dừng auto-map để người dùng xử lý boss thủ công. Với công trình, bot chọn marker có x lớn nhất (nếu trùng x thì y lớn nhất), rồi chọn từ trên xuống tùy chọn đầu tiên có giá màu trắng và bỏ qua giá màu đỏ. Nếu thấy `lv_spin` thì click lệch trái 70 px từ tâm match; `lv_spin` cũng được check lại ngay sau khi click `lv_up` và trước confirm. Bấm `Shift+0` để dừng flow trong phase hiện tại.
- `Shift+8`: lưu screenshot live của viewport hiện tại vào `.tmp/hauntedroom-captures/` rồi tiếp tục trạng thái hiện tại. Nếu runner đang idle thì vẫn idle; nếu flow đang chạy thì flow vẫn chạy.
- `Shift+9`: dùng threshold riêng `0.6` và chỉ match scale `1.0`. Runner thử tìm badge `rooms/misc/research_available.png` tối đa 4 lần, cách nhau 600 ms; nếu thấy thì chờ 600 ms và click góc dưới-trái để mở mục nghiên cứu. Sau đó runner click center `research_active.png`. Khi active miss 4 lần, flow quay lại tìm available; chỉ về idle khi available cũng miss đủ 4 lần.
- `Shift+0`: dừng mềm flow hiện tại và quay lại standby; browser vẫn mở.
- `Shift+3` đến `Shift+7`: được dành sẵn cho các flow bổ sung và hiện chỉ in thông báo chưa cấu hình.
- `Ctrl+C` trong terminal: đóng runner và browser.

Hotkey dùng vị trí phím vật lý (`Digit0` đến `Digit9`), hoạt động trên Windows/macOS và chỉ điều khiển trang browser đang focus. Khi một flow đang chạy, runner không nhận flow khác cho tới khi flow đó hoàn tất hoặc được dừng bằng `Shift+0`; riêng `Shift+8` chỉ chụp screenshot nên không bị chặn.

Bốn action hiện được hỗ trợ. Flow dùng `clear_blockers` tại các checkpoint có thể xuất hiện popup:

```json
[
  { "type": "clear_blockers", "templates_dir": "rooms/blocker", "until_template": "rooms/start_home.png" },
  { "type": "click_template", "template": "rooms/start_home.png", "note": "Start HOME" },
  { "type": "click_template", "template": "rooms/start_battle.png", "note": "Start Battle" }
]
```

- `click_template`: chụp viewport và dùng OpenCV tìm template liên tục. Khi score đạt threshold, runner chờ `delay_ms` rồi click tâm template.
- `clear_blockers`: match các file PNG trong `templates_dir` theo thứ tự `priority`. Runner click blocker đầu tiên đạt threshold rồi quét lại từ đầu. Khi thấy `until_template` và không còn blocker, runner chuyển sang action kế tiếp mà không click `until_template`.
- `click`: bắt buộc có `x`, `y`; `button` và `note` là tùy chọn.
- `wait`: bắt buộc có `ms`; `note` là tùy chọn.

Đường dẫn `template` được tính tương đối từ file action JSON. Các tùy chọn của `click_template`:

- `threshold`: mặc định `0.9`.
- `timeout_ms`: thời gian tối đa chờ ảnh, mặc định `30000`.
- `poll_ms`: khoảng nghỉ giữa các lần detect, mặc định `600`.
- `delay_ms`: thời gian chờ trước mỗi click, gồm cả click đầu sau detect và các click liên tiếp; mặc định `500`.
- `click_count`: số lần click template sau khi detect, mặc định `1`.
- `button`: mặc định `left`.
- `skip_if_template`: template báo action hiện tại đã không còn cần thiết; nếu template này đạt cùng `threshold`, runner bỏ qua click hiện tại và chuyển sang action kế tiếp.

`clear_blockers` hỗ trợ `click_positions` để đổi điểm click theo tên file. Vị trí mặc định là `center`; `top_middle` click chính giữa cạnh trên của vùng match:

```json
{ "click_positions": { "overlay_newbie.png": "top_middle" } }
```

Thứ tự kiểm tra blocker được cấu hình bằng tên file trong `priority`. Các PNG không được liệt kê sẽ được nối vào cuối theo thứ tự tên file:

```json
{
  "priority": [
    "lubu_close.png",
    "overlay_close.png",
    "overlay_close_2.png",
    "overlay_newbie.png"
  ]
}
```

Không có thời gian load cố định trước flow. Template đầu tiên đóng vai trò điều kiện báo game đã load.

Flow cũng chạy `clear_blockers` sau khi click `start_home` và trước khi click `start_battle`, vì blocker có thể xuất hiện trong lúc chuyển giữa hai màn hình này.

File mặc định là `tools/hauntedroom_actions.sample.json`.

## Log và ghi tọa độ

Mỗi vòng lặp có log bắt đầu và hoàn tất:

```text
loop 1/10 start
...
loop 1/10 finish
```

Các thao tác click thủ công trong browser được in ra terminal dưới dạng JSON để có thể chép vào action file. Click do runner tự gửi sẽ không bị ghi lại.

Wait dài có countdown; ngưỡng countdown và số vòng lặp được cấu hình trong `tools/hauntedroom/core/runtime.py`.

## Browser profile

Profile mặc định nằm tại `.tmp/hauntedroom-profile`. Cookies, localStorage, IndexedDB và session game được giữ lại giữa các lần chạy.

Chỉ một browser instance được dùng profile này tại cùng thời điểm. Nếu một lần chạy với `--keep-open` vẫn còn hoạt động, lần chạy tiếp theo có thể báo profile đang được sử dụng.

Xóa profile sẽ reset session và có thể làm game quay lại luồng guest/intro.

## Giới hạn hiện tại

- Template matching thử hai scale cố định `1.0` và `0.67`, sau đó dùng kết quả có score cao hơn.
- Viewport nên được giữ cố định ở kích thước dùng khi chụp template.
- Khi hết `timeout_ms` lần đầu, runner ghi `timeout count=1/2`, bỏ phần action còn lại của loop hiện tại và thử lại từ đầu ở loop kế tiếp.
- Hai loop timeout liên tiếp sẽ dừng runner. Một loop hoàn tất không timeout sẽ reset bộ đếm về `0`.
- Mỗi lần timeout, runner lưu screenshot cuối vào `.tmp/hauntedroom-timeouts/` và in đường dẫn file trong terminal.
