# vendor

Thư viện bên thứ ba dùng trực tiếp trong trang `/__sim/*` (không CDN, không build: sandbox chặn
mọi request ngoài `127.0.0.1:8090`). Bản ES module, nạp bằng `import`; tên package (`preact`,
`preact/hooks`, `htm`) được map tới file ở đây bằng `<script type="importmap">` trong trang
(xem `web/setup.html`).

| File | Nguồn (npm) | Version | Import map | License |
|---|---|---|---|---|
| `preact.module.js` | `preact/dist/preact.module.js` | 10.29.8 | `preact` | [MIT](LICENSE-preact) |
| `preact-hooks.module.js` | `preact/hooks/dist/hooks.module.js` | 10.29.8 | `preact/hooks` (import `"preact"`) | [MIT](LICENSE-preact) |
| `htm.module.js` | `htm/dist/htm.module.js` | 3.1.1 | `htm` | [Apache-2.0](LICENSE-htm) |

Copy nguyên file từ `npm pack preact@10.29.8 htm@3.1.1`, chỉ bỏ dòng `//# sourceMappingURL`
(không kèm file `.map`). Giữ Preact 10.x (11 còn quá mới). Nâng version thì chép lại đúng 3 file
trên và sửa bảng này.
