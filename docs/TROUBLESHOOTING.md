# Troubleshooting

Tài liệu này tập trung vào các lỗi môi trường và runtime của Haunted Room runner.
Hướng dẫn sử dụng chính nằm trong [README.md](README.md).

## Cả ba lần startup navigation đều timeout

### Triệu chứng

Browser đứng ở `about:blank`, terminal in đủ hai dòng retry rồi kết thúc bằng:

```text
Page.goto: Timeout 15000ms exceeded
Call log:
  - navigating to "https://hauntedroomvnh5.joynetgame.com/", waiting until "commit"
```

Dòng `navigating to ...` xác nhận Playwright đã nhận đúng URL. Thanh địa chỉ vẫn có
thể là `about:blank` vì server chưa trả response để navigation đạt mốc `commit`;
Playwright điều hướng trực tiếp và không nhập URL bằng bàn phím.

### Nguyên nhân đã gặp

Cache hoặc network state trong persistent profile có thể bị hỏng sau nhiều lần
browser bị dừng giữa chừng. Khi đó request chính có thể kết thúc bằng
`net::ERR_ABORTED`, dù domain vẫn resolve, `curl` trả HTTP 200 và cùng đoạn
Playwright chạy được với một profile sạch.

Retry bằng tab mới không giải quyết được vì mọi tab vẫn dùng chung browser context,
network service và profile. Lệnh CDP `Network.clearBrowserCache` cũng có thể treo
nếu chính network service đang lỗi.

### Khoanh vùng bằng profile sạch

Chạy runner với một profile tạm mới:

```powershell
uv run python tools/hauntedroom_runner.py --profile .tmp/hauntedroom-profile-clean --dev-reload
```

Nếu profile mới vào được nhưng profile mặc định vẫn timeout, lỗi nằm ở state của
profile mặc định. Profile mới không có session cũ nên có thể yêu cầu đăng nhập lại;
nó chỉ dùng để chẩn đoán.

### Phục hồi an toàn

1. Đóng runner và bảo đảm không còn Chrome process nào dùng
   `.tmp/hauntedroom-profile`.
2. Di chuyển, thay vì xóa ngay, các thư mục có thể được Chrome tạo lại sang một
   thư mục backup:

   - `Default/Cache`
   - `Default/Code Cache`
   - `Default/GPUCache`
   - `Default/Service Worker`
   - `Default/Shared Dictionary`
   - Các file `Default/Network/*.tmp`
3. Không xóa `Default/Network/Cookies`, `Local Storage`, `IndexedDB` hoặc toàn bộ
   profile; các mục này chứa session và trạng thái đăng nhập.
4. Chạy lại runner. Chrome sẽ tạo lại cache cần thiết.
5. Chỉ xóa backup sau khi đã xác nhận game và phiên đăng nhập hoạt động bình thường.

Việc phục hồi phải diễn ra sau khi browser context đã đóng. Không di chuyển hoặc
xóa file của một profile đang được Chrome sử dụng.

### Hướng tự động hóa

Runner hiện chỉ retry navigation bằng page mới. Có thể bổ sung recovery ở cấp
browser: sau khi hết toàn bộ navigation attempt, đóng browser context, backup riêng
các cache path nêu trên, relaunch context và thử thêm một lần. Recovery phải giữ
nguyên cookies, local storage, IndexedDB và có backup để hoàn tác.
