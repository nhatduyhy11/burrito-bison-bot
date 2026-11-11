# vendor

Thư viện bên thứ ba dùng trực tiếp trong trang `/__sim/*` (không CDN, không build: sandbox chặn
mọi request ngoài `127.0.0.1:8090`). Nạp bằng `<script>` thường, mỗi file gắn một global.

| File | Nguồn (npm) | Version | Global | License |
|---|---|---|---|---|
| `preact.umd.js` | `preact/dist/preact.umd.js` | 10.29.8 | `preact` | [MIT](LICENSE-preact) |
| `preact-hooks.umd.js` | `preact/hooks/dist/hooks.umd.js` | 10.29.8 | `preactHooks` (cần `preact` nạp trước) | [MIT](LICENSE-preact) |
| `htm.umd.js` | `htm/dist/htm.umd.js` | 3.1.1 | `htm` | [Apache-2.0](LICENSE-htm) |

Copy nguyên file từ `npm pack preact@10.29.8 htm@3.1.1`, chỉ bỏ dòng `//# sourceMappingURL`
(không kèm file `.map`). Preact 11 chỉ có bản ES module nên giữ 10.x. Nâng version thì chép lại
đúng 3 file trên và sửa bảng này.
