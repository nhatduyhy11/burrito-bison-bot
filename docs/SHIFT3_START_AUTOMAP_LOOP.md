# Flow `Shift+3`: start-auto loop

`Shift+3` chạy nhiều map liên tiếp cho tới khi người dùng bấm `Shift+0` hoặc
detector xác định map thất bại.

Mỗi vòng chạy theo thứ tự:

1. Tái sử dụng các action của flow `Shift+1` từ đầu tới hết action click
   `start_battle.png`; các action exit không được chạy.
2. Chạy trọn một lượt auto-map giống `Shift+2`.
3. Kiểm tra map có thất bại hay không.
4. Nếu chưa thất bại, chờ 2 giây rồi bắt đầu vòng tiếp theo.

Detector thất bại hiện là placeholder `map_was_lost()` và luôn trả về `False`.
Vì vậy flow hiện chỉ kết thúc khi bị dừng, auto-map không hoàn tất, hoặc có lỗi.

Khi bật `--dev-reload`, cả `Shift+2` và `Shift+3` đều reload implementation
auto-map trước khi bắt đầu flow.
