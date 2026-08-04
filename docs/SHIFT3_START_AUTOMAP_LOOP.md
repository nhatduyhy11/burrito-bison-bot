# Flow `Shift+3`: start-auto loop

Khi runner idle, `Shift+3` bắt đầu chạy nhiều map liên tiếp. Trong lúc flow đang
chạy, bấm lại `Shift+3` để pause và bấm lần nữa để resume đúng state hiện tại;
flow không restart từ đầu. Khi đang chạy hoặc pause, `Shift+0` dừng hẳn flow.
Ngoài ra flow kết thúc khi detector xác định map thất bại.

Mỗi vòng chạy theo thứ tự:

1. Tái sử dụng các action của flow `Shift+1` từ đầu tới hết action click
   `start_battle.png`; các action exit không được chạy. Entry actions được thử
   tối đa 2 lần khi timeout và dừng ngay sau lần đầu tiên hoàn thành thành công.
2. Chạy trọn một lượt auto-map giống `Shift+2`.
3. Kiểm tra map có thất bại hay không.
4. Nếu chưa thất bại, chờ 2 giây rồi bắt đầu vòng tiếp theo.

Flow giữ `win_count` trong suốt một lần chạy Shift+3. Khi auto-map nhận diện
`win_reward.png` lần đầu tiên trong màn reward của một map, `win_count` tăng 1;
các reward còn lại trong cùng màn không làm tăng thêm count.
Ngay trước log hoàn thành auto-map, flow in tổng hiện tại theo format
`>>> [total_win] win`.

Nếu hai loop đầu tiên kết thúc mà `win_count` vẫn bằng 0, loop thứ 3 bật chế độ
handoff. Ngay khi detector thấy thanh HP của bất kỳ boss nào (mini-boss hoặc
final boss), bot click nút pause, dừng start-auto loop và trả quyền xử lý cho
người dùng. Nếu đã có ít nhất một win thì loop thứ 3 tiếp tục auto-map bình
thường.

Trước log cooldown giữa hai map có một dòng gạch ngang để phân cách log của hai
loop.

Detector thất bại hiện là placeholder `map_was_lost()` và luôn trả về `False`.
Vì vậy flow hiện chỉ kết thúc khi bị dừng, auto-map không hoàn tất, hoặc có lỗi.

Khi bật `--dev-reload`, cả `Shift+2` và `Shift+3` đều reload implementation
auto-map trước khi bắt đầu flow.
