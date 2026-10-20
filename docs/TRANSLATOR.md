# Dịch game CN sang tiếng Việt

Translator dùng Playwright chụp game, RapidOCR đọc chữ,
khôi phục chữ gần khớp từ các lệnh vẽ canvas, rồi hiển thị bản dịch tại vùng chữ.
Mặc định dịch qua Google web, có cache và model offline Trung → Anh → Việt dự phòng.
Glossary sửa thuật ngữ UI/tên game thông dụng; các câu còn lại dùng máy dịch thật.

## Chạy trên Windows hoặc macOS

Cần Python, `uv` và Chrome. Nếu bạn đang dùng runner với profile CN, chạy:

```shell
uv run --extra translator python tools/hauntedroom_runner.py --dev-reload --profile .tmp/pcn --cn --translate
```

Dịch **tự bật ngay trong cửa sổ game của runner**, không cần mở thêm chương trình.
Click vào game rồi nhấn **Shift+D** để tắt; nhấn lại để bật. Các hotkey bot cũ vẫn
hoạt động. Ảnh dùng cho nhận diện bot tự loại lớp chữ dịch để không làm sai template.
Đóng runner đang dùng `.tmp/pcn` trước khi chạy lại lệnh trên.

Trên máy hiện tại model đã setup. Nếu cài trên máy mới, chạy một lần:

```shell
uv sync --extra translator
uv run --extra translator python tools/setup_translator.py
```

Setup tải hai model Argos 1.9, khoảng 142 MB tổng dung lượng download, vào
`.tmp/translator-models`. Sau khi tải xong có thể chạy hoàn toàn offline:

```shell
uv run --extra translator python tools/hauntedroom_runner.py --dev-reload --profile .tmp/pcn --cn --translate-offline
```

Nếu chỉ muốn dịch và chơi tay, không dùng bot, có thể chạy riêng:

```shell
uv run --extra translator python tools/game_translator.py
```

- `Shift+D`: bật/tắt bản dịch khi tab game đang focus.
- `Ctrl+C` ở terminal: đóng translator/browser.
- Với chương trình riêng, profile mặc định `.tmp/translator-profile` giữ phiên game; không mở hai process
  cùng profile. Dùng `--profile .tmp/translator-other` để tạo phiên riêng.
- Nếu không có Chrome: `uv run playwright install chromium`, rồi thêm
  `--browser chromium`.
- Sửa thuật ngữ trong `tools/translator_glossary.json` rồi khởi động lại.
- `.tmp/translator-result/latest.json` chứa OCR, text gốc sau khôi phục, bản dịch,
  nguồn dịch, vùng bị loại vì đã đổi và timing.

Google web là endpoint không chính thức, có thể thay đổi/rate-limit. Chỉ các chuỗi
chữ OCR chưa có cache/glossary được gửi ra ngoài; ảnh được OCR trên máy. Khi web MT
lỗi, chương trình dùng offline và chờ 60 giây trước khi thử web lại. `--translate-offline`
(runner) hoặc `--offline` (chương trình riêng)
không gửi text cho dịch online, nhưng bản thân game vẫn cần mạng.

## Kiểm chứng tự động

```shell
uv run --extra translator python tools/game_translator.py --headless --demo --profile .tmp/translator-demo
uv run --extra translator python tools/verify_translator.py
uv run python -m unittest tests.test_game_translator -v
```

Demo mở game CN, dịch entry, vào cốt truyện, bỏ qua, dịch màn hình chuẩn bị,
thử wheel invalidation và bật/tắt, rồi click sẵn sàng để chụp bước tutorial tiếp.
Demo dùng tọa độ theo viewport 640×720 đã kiểm tra; đây không phải bot tự vượt
mọi tutorial. Dùng profile mới khi cần tái hiện từ đầu.

Ảnh `*-source.png`, `*-translated.png` và `report.json` nằm ở thư mục `--output`
(mặc định `.tmp/translator-result`). Assertion không chỉ kiểm tra file ảnh:
phải có vùng OCR/dịch được render, overlay không nhận pointer, input xóa overlay,
toggle off không xử lý và toggle on hiển thị trở lại.

Unit test kiểm tra frame lỗi vẫn được retry, frame thành công giữ nguyên không
chạy OCR lại, input trong lúc xử lý làm bỏ kết quả, pixel vùng chữ đổi bị loại,
animation ngoài vùng chữ không làm mất nhãn và khôi phục text không chọn mơ hồ.

`verify_translator.py` là fixture canvas riêng, phân biệt với demo game thật:
render mô tả nhiều dòng, cuộn sang hai câu mới, dùng OCR/MT thật, kiểm tra cache,
click-through và inference offline. Kết quả ở `.tmp/translator-regression`.
Hai câu mới không có trong glossary đã dịch ra:

- “Nâng cấp kỹ năng có thể tăng sát thương.”
- “Bấm vào nút để quay lại trang trước.”

Lần kiểm chứng Windows 2026-10-20: demo server CN đã qua entry → cốt truyện →
chuẩn bị trận → tutorial, có bản dịch hiển thị ở từng bước. Bộ test repo:
371 test chạy thành công, 4 skipped. Ảnh game thật và timing:
`.tmp/translator-final-result/report.json`, các file `*-translated.png` cùng thư mục.
Các số liệu là mẫu kiểm chứng, không phải SLA hay benchmark trên macOS.

## Giới hạn đã biết

- Đã chạy thực tế trên Windows; code không dùng Win32 hay desktop screenshot.
  macOS dùng cùng API Playwright/CPU OCR/MT, **chưa kiểm thử trên máy Mac thật**.
- Đây là dịch màn hình sau một khoảng trễ, chưa đạt mục tiêu 100–300 ms.
  Full-frame OCR, mạng và lần đầu dịch câu mới có thể mất vài giây.
- OCR vẫn có thể sai chữ nhỏ/cách điệu; tên riêng và câu dịch qua tiếng Anh có
  thể sai nghĩa. Glossary không bao phủ mọi tướng/kỹ năng.
- Khi chữ đang chuyển động, nhãn có thể bị bỏ cho tới khi vùng chữ ổn định.
  Overlay có thể dài hơn dòng gốc; Shift+D để xem nguyên bản.
- Hook 2D chỉ dùng hỗ trợ khôi phục OCR, không lấy mọi chuỗi đã hook làm chữ đang
  hiển thị. Worker/bitmap fonts có thể không hook được; OCR vẫn hoạt động.
- Trong runner, bật bằng `--translate`; Shift+D hoạt động cùng các hotkey bot.
  Không mở chương trình translator riêng trên profile đang bị runner khác giữ.

Nguồn kỹ thuật: [Playwright screenshot](https://playwright.dev/python/docs/screenshots),
[CTranslate2](https://opennmt.net/CTranslate2/translation.html),
[Argos package format](https://argos-translate.readthedocs.io/en/stable/source/argostranslate.html).
