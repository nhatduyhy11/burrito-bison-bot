    Refactor luồng khởi tạo Train (Train Entry Flow) để xử

lý triệt để trường hợp có phần thưởng xuất hiện trước khi
vào trận:

    ### 1. Bối cảnh & Vấn đề:
    Khi bắt đầu vào Train, ngoài nút bắt đầu thông thường

thì có thể xuất hiện chuỗi nhận thưởng mốc hoặc popup thu
thập quà che màn hình. Hiện tại bot chỉ chờ 1 nút cố định
nên dễ bị kẹt hoặc bỏ sót.

    ### 2. Yêu cầu luồng xử lý (Flow Logic):
    - **Phase 1: Dọn sạch dải nút đáy ở màn hình Train

(Lobby Cleansing)\*\*: - Quét toàn bộ dải đáy màn hình để tìm các nút vàng
(nhận thưởng mốc, xác nhận popup quà, nút bắt đầu train -
kể cả khi nút bị mờ do popup che). - Lặp lại thao tác click cho đến khi dải đáy hoàn
toàn sạch nút vàng.

    - **Phase 2: Chuyển tiếp sang màn hình Chọn tướng (Hero

Select)\*\*: - Tách pha Hero Select thành một bước/phase riêng
biệt độc lập với màn hình Train bên ngoài (để thuận tiện
mở rộng logic sau này). - Đợi màn hình Hero Select xuất hiện (xác thực bằng
banner/dấu hiệu nhận diện không phụ thuộc ngôn ngữ). - Tìm và click nút vàng Battle để xác nhận đội hình
vào trận.

    - **Pha tiếp theo (Battle & Card Selection)**:
      - Sau khi bấm nút Battle ở màn hình Hero Select, giữ

nguyên toàn bộ flow chọn thẻ bài và vào trận như cũ.

    ### 3. Yêu cầu kỹ thuật:
    - Nhận diện hoàn toàn **độc lập ngôn ngữ** (Locale-

agnostic): dùng nhận diện màu HSV / hình ảnh không chữ
thay vì template text tiếng Việt ("Khiêu chiến"). - Bổ sung unit tests bao phủ các case: có nút nhận
thưởng trước, nút bị tối do popup che, và flow vào thẳng
hero select.
