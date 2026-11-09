# BUNDLE_RESEARCH — Đào code/config/proto từ bundle game

> **Chỉ đọc khi cần đọc code client** (logic battle/UI, bảng config, proto packet,
> field `fN` chưa có tên). Bot chạy không cần doc này.

## 1. Bundle game

- Game = Cocos Creator 2.x, entry `https://hauntedroomvnh5.joynetgame.com/`. Chuỗi tải:
  `h5SB_4399_sea_vn.js` → `manifest.<ClientVer>.js` → `main.<hash>.js` (loader) →
  code game ở **`assets/main/index.<hash>.js` (~24MB)**. Các sub-bundle
  `assets/{battle,hangup,login,resources}/index.*.js` chỉ là stub (~284B), toàn bộ
  code nằm trong `main`. Module truy cập qua `window.__require(<Tên>)`.
- Bundle dạng browserify: `window.__require=function e(t,o,i){…}({Name:[fn,deps],…},{},[entries])`;
  mỗi module game mở bằng `cc._RF.push(t,"<uuid>","<Name>")`.
- Minify giữ nguyên **tên class / method / field / message proto** → grep tên là đủ
  lần ra logic.
- Hash bundle (`index.<hash>.js`) và config (`config.<ver>.bin`) đổi theo đợt deploy —
  luôn lấy URL từ resource của page vừa boot, không hardcode.

### Tải + tách module

[`scripts/bundle/fetch_bundle.py`](../../scripts/bundle/fetch_bundle.py):

```bash
uv run python scripts/bundle/fetch_bundle.py            # boot game, tải bundle mới nhất
uv run python scripts/bundle/fetch_bundle.py --bundle <file.js>   # tách file đã có
```

→ `.tmp/bundle/main.<hash>/`: bundle gốc, `modules/<Name>.js` (1 file / module,
`_lib/` cho module id số = lib npm), `index.json` (`{name: {file, deps, size}}`).
Tách bằng cách eval bundle trong page trắng với loader thay bằng stub capture —
ranh giới module do JS engine quyết, không regex. Grep trên `modules/` thay vì file
24MB (trên file gốc: dùng Python `str.find`; `grep -oE ".{3000}X"` chạy quá 2 phút).

## 2. Bảng config `*LO`

- Bảng nén QuickLZ + stream custom, KHÔNG tự parse — dùng runtime game:
  `window.__require("<T>LO").<T>LO.get(id)`. Liệt kê tên bảng: file `modules/*LO.js`
  (~476 bảng) hoặc regex `\b[A-Z]\w*LO\b` trên text bundle.
- Bảng lazy: sau khi `config.<ver>.bin` tải, LO giữ `_buffer`/`_count`; parse khi gọi
  `get()` hoặc getter `store` (`tryToInit`). Store là `Dictionary`: duyệt key bằng
  `Object.values(LO.store._keyList)` + `LO.get(key)`, KHÔNG phải `Object.keys(store)`.
- [2026-11-09] Boot không login, ở màn login đã tải `remoteConfig/sea/config.<ver>.bin`
  và các LO có `_buffer` → đọc được config không cần login. Nếu sau này store rỗng
  (chỉ có `preload_config.<ver>.bin`), tự nạp trong page: fetch `config.<ver>.bin`
  (URL = `preload_config.<ver>.bin` đổi tên) → `QuickLZ.decompress(buf)` →
  `new BinaryReader().init(data)` → `new ConfigParser().writeBinaryDataWhenRead(reader)`
  (đều qua `window.__require`).
- Schema cột: `parseData=function(t){var o=new e;return o._id=t.readInt(),…}` trong
  `modules/<T>LO.js` — thứ tự `readInt/readString/…` = thứ tự cột.

## 3. Schema proto (cmd → message → field)

Pattern trong bundle:

- `XxxProxy`: `this._m=<module>,…registerModuleName(this._m,"XxxProxy")` rồi
  `this._s.register(this._m, <cmd>, "<Name>", s.<Name>_<NS>_<C2S|S2C>,
  n.<NS>Define.<Name>_<NS>_<dir>_Def | null, this.<Name>Response|Push)` — handler đuôi
  `Response` = reply, `Push` = server push, không handler = request/sub-struct.
  Request gửi: `prototype.<Name>Request=function(e,t){this._s.send(this._m,<cmd>,…)}`.
- `<Msg>_Def=function(){var e=new c.Dictionary;return e.add(<no>,{n:"<field>",
  ft:PFType.<Optional|Repeated|Map>, wt, bt:PBType.<type>, refCls:a.<SubMsg>}),…,e}`
  — nằm trong `modules/<NS>Define.js`.
- ~117 `*Proxy` module; module id ví dụ: `PlayerInfoProxy` `_m=13` (`0x0d`),
  `MiningProxy` `_m=72` (`0x48`).

## 4. Trace UI → data (cách làm)

1. Từ hành động UI grep handler trong class view/panel (`onBtn<X>Tap`…) → module
   (`<X>Module`) → bảng config (`<X>LO.get(id)`) hoặc dict runtime.
2. Lần ngược nguồn dict: tìm chỗ điền dict, thường trong callback
   `<X>Proxy.<Name>Request`.
3. Proxy → cmd (`send(this._m,<cmd>)`) → Def response → đối chiếu frame thật trong
   socket log + screenshot game.

Nút UI không sinh request ⇔ data render từ config client hoặc dict đã có từ request trước.

## 5. Evidence

- 2026-11-09: bundle `assets/main/index.1377a.js`, config `config.65380.bin`;
  `fetch_bundle.py` tách 4819 module (4458 có tên). Pattern `parseData`, `_Def`,
  `registerModuleName` ở §2–3 đã grep lại trên bản này.
