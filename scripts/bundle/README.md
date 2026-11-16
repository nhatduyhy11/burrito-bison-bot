# Bundle research — đào code/config/proto từ bundle game

> Chỉ đọc khi cần đọc code client (logic battle/UI, bảng config, proto packet,
> field `fN` chưa có tên). Bot chạy không cần doc này.

## Tải + tách module

```bash
uv run python scripts/bundle/fetch_bundle.py                      # boot game, tải bundle mới nhất
uv run python scripts/bundle/fetch_bundle.py --bundle <file.js>   # tách file đã có
```

→ `.tmp/bundle/main.<hash>/`: bundle gốc, `modules/<Name>.js` (1 file / module,
`_lib/` cho module id số = lib npm), `index.json` (`{name: {file, deps, size}}`).

- Game là Cocos Creator 2.x, toàn bộ code nằm trong `assets/main/index.<hash>.js`
  (~24MB). Các sub-bundle `assets/{battle,hangup,login,resources}/index.*.js` chỉ là
  stub (~284B). Module truy cập qua `window.__require(<Tên>)`.
- Minify giữ nguyên tên class / method / field / message proto → grep tên là đủ.
  Grep trên `modules/`, không grep file 24MB (`grep -oE ".{3000}X"` chạy quá 2 phút).
- Hash bundle và `config.<ver>.bin` đổi theo đợt deploy — luôn lấy URL từ page vừa
  boot, không hardcode.

## Bảng config `*LO`

- Nén QuickLZ + stream custom, KHÔNG tự parse — dùng runtime game:
  `window.__require("<T>LO").<T>LO.get(id)`. Liệt kê tên bảng: `modules/*LO.js`
  (~476 bảng) hoặc regex `\b[A-Z]\w*LO\b` trên text bundle.
- Bảng lazy: parse khi gọi `get()` hoặc getter `store`. Store là `Dictionary`: duyệt
  bằng `Object.values(LO.store._keyList)` + `LO.get(key)`, KHÔNG phải `Object.keys(store)`.
- Ở màn login (chưa đăng nhập) đã tải `config.<ver>.bin` → đọc config không cần login.
  Nếu store rỗng, tự nạp trong page: fetch `config.<ver>.bin` (= URL
  `preload_config.<ver>.bin` đổi tên) → `QuickLZ.decompress(buf)` →
  `new BinaryReader().init(data)` → `new ConfigParser().writeBinaryDataWhenRead(reader)`
  (đều qua `window.__require`).
- Schema cột: `parseData` trong `modules/<T>LO.js` — thứ tự `readInt/readString/…`
  = thứ tự cột.

## Schema proto (cmd → message → field)

- `modules/<X>Proxy.js`: `this._m=<module>` rồi
  `this._s.register(this._m, <cmd>, "<Name>", …, <NS>Define.<Name>_<NS>_<dir>_Def | null, handler)`
  — handler đuôi `Response` = reply, `Push` = server push, không handler =
  request/sub-struct. Request gửi: `this._s.send(this._m, <cmd>, …)`.
- `modules/<NS>Define.js`: `<Msg>_Def` gồm các
  `e.add(<no>, {n:"<field>", ft:PFType.<Optional|Repeated|Map>, wt, bt:PBType.<type>, refCls})`.

## Trace UI → data

1. Handler trong view/panel (`onBtn<X>Tap`…) → `<X>Module` → `<X>LO.get(id)` hoặc dict runtime.
2. Dict runtime: tìm chỗ điền, thường trong callback `<X>Proxy.<Name>Request`.
3. Proxy → cmd → Def response → đối chiếu frame thật trong socket log + screenshot.

Nút UI không sinh request ⇔ data từ config client hoặc dict đã có từ request trước.
