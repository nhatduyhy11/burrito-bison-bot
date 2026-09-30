# Framework extraction — handover (cấu trúc 3 tầng)

Kiến trúc hiện hành mô tả tại [`ARCHITECTURE.md`](../ARCHITECTURE.md). Tài liệu
này định nghĩa cấu trúc đích cho việc tách framework, và thay thế mental-model
"framework / game integration / game business" ba vùng của bản trước trong
chính file này. Vẫn chưa supersede
[`ADR-001`](../adr/ADR-001-hauntedroom-package-boundaries.md) — ADR mới chỉ
được viết khi boundary framework/game được chấp nhận chính thức.

## Status

- Cấu trúc 3 tầng bên dưới đã chốt làm hướng đi (2026-09-30).
- Điều kiện tiền đề của handover cũ đã đạt: `ref_cv/` (Burrito Bison) là game
  thứ hai, đủ evidence để chốt seam transport và bắt đầu extraction.
- Thứ tự thực thi là phase 1–5 ở cuối tài liệu. Phase 2 trùng với
  [`refactor_actions_flows_boundary.md`](refactor_actions_flows_boundary.md)
  đang chờ chạy — không song song.

## Tầng framework — mỏng

Nguyên tắc: framework chỉ là wrap của thư viện + capability runtime generic.
Không game vocabulary, không orchestration business, không biết flow nào.

```text
framework/
├── transport/               # 2 port duy nhất: capture, input
│   │                          capture → frame: np.ndarray
│   │                          input: click / drag / key
│   └── backends/
│       └── playwright/      # page lifecycle, profile, JS injection, browser guard
├── vision/                  # primitive thuần: frame in → match out, sync, không I/O
├── runtime/                 # flow control generic: checkpoint, timeout, timing,
│                            #   cancellation, diagnostics screenshot policy
├── actions/                 # JSON DSL engine — module optional
├── runner/                  # standby loop, hotkey transport, command registry contract
└── devtools/                # hot reload, debug capture tools

dependency: runner → actions → runtime → transport ports; vision pure, đứng riêng
```

- **Transport là seam duy nhất để swap backend.** Playwright là một backend
  impl, không phải "lớp browser của framework". Backend sau này: macro
  BlueStacks, OS window (win/mac/linux) — mỗi cái tự impl 2 port + adapter
  launch/navigation riêng, framework không đổi dòng nào.
- Port nói **raw pixel**. Phép dịch content-offset và scale về tọa độ game là
  việc của game app (BlueStacks sẽ có resolution/scale khác).
- Hot reload là devtool, không phải contract cho business phụ thuộc.
- JSON action engine giữ dạng optional; không để nó kéo framework dày lên.

## Tầng game — buz_vision < buz_action < flow

```text
games/hauntedroom/
├── vision/                  # BUZ_VISION — pure, sync, frame → typed result
│   ├── assets/              #   pattern template runtime dùng
│   ├── screens.py, train.py, hero_select.py, boss.py, ...
│   └── test_*.py + captures/     # unit test detector + ảnh test, nằm cạnh
├── actions/                 # BUZ_ACTION — async; cầm page + vision + framework.runtime
│   └── test_*.py            #   unit test với fake capture; wait/retry/click,
│                            #   recovery của lobby sống ở đây
├── flows/                   # composition: mode, loop, run_state
│   └── test_*.py
└── app/                     # wiring: command table, reload list, settings,
                             #   navigation/URL policy, asset registry
```

**Luật bất biến: bất đồng bộ chỉ bắt đầu ở buz_action.** Detector cần
"chờ đến khi X" là buz_action, không phải vision. Nhờ đó unit test buz_vision
là pure-function test với ảnh fixture — không mock page, không async.

- Tổ chức theo tier-dir (không phải feature-dir) để arch test khóa chiều
  `flows → actions → vision` bằng đúng 3 rule. Feature chỉ là tiền tố file.
- Recovery là buz_action của lobby; detector là buz_vision; flow chỉ ráp phase.
- Framework tests không bao giờ import game package.
- `tests/` ở repo root chỉ còn test dạng cấu trúc lớn: arch dependency test và
  e2e live.

## Quy ước test & asset

- Asset path đi qua **một registry duy nhất mỗi game** (`app/assets.py`).
  Cấm `Path(__file__).resolve().parents[n]` rải rác — arch test chặn.
- Pattern asset và ảnh test gộp theo feature trong tier `vision/`; unit test
  actions dùng lại captures đó qua fake capture.
- Runtime diagnostics (`.tmp/`) không bao giờ nằm trong tests/. Ảnh test trong
  repo chỉ nhận ảnh đã curate (promote thủ công).
- `LIVE_SCREENSHOT_DIR` hiện ghi thẳng vào `tests/fixtures/` — bỏ ngay phase 1.
- Pytest config (rootdir, importmode, đường dẫn asset) chốt từ commit đầu của
  `games/` để không sinh ra hệ `parents[n]` thứ hai.

## Mapping hiện tại → đích

| Hiện tại | Đi đâu |
| --- | --- |
| `core/mouse.py`, capture trong `core/vision.py`, `browser_hook.py` | framework transport + playwright backend |
| `core/template_matching.py`, `template_detection.py` | framework vision |
| `core/runtime.py` nửa generic (checkpoint/timeout/timing) | framework runtime |
| `core/runtime.py` nửa boss-pause + `LIVE_SCREENSHOT_DIR` | game app / framework diag policy |
| `vision/buttons.py` (cơ chế tìm button) | framework vision, color/geometry thành tham số |
| `flows/*/detection.py`, `automap_support/vision/`, `train_select.py` | game `vision/` |
| `train_support/entry.py`, `exit_flow.py`, wait-and-click | game `actions/` |
| `autotrain.py`, `start_auto.py`, `new_account.py` | game `flows/` |
| `runner/standby.py`, `commands.py` (contract) | framework runner |
| `default_commands.py`, `reload.py`, `cli.py` URL | game `app/` |
| `screen_detect.py` vòng scoring anchors | generic → framework vision; `ScreenName` + spec → game `vision/screens.py` |

Gần như toàn bộ là rename/split — không rewrite. Phần viết mới duy nhất là 2
interface transport port.

## Vấn đề còn mở (giữ từ bản trước, rút gọn)

1. **Screen-state recognition**: pull tại checkpoint hay background observer;
   reuse snapshot giữa nhiều detector; confidence khi 2 screen cùng match; bao
   nhiêu frame liên tiếp trước khi emit transition; unknown quá lâu thì recover
   thế nào. Thuộc game `vision/screens.py` + `flows/`; framework chỉ giữ
   polling/timeout primitive.
2. **Login / daily-run state**: scope state (invocation/run/login/account/
   game-day), reset boundary, timezone, hành vi khi relogin. Callback như
   `on_win` thuộc từng invocation; daily/first-win state thuộc game-owned state
   context có reset semantics rõ ràng. Framework chỉ giữ state store generic;
   daily policy là game.

## Phase thực hiện

1. **Transport port + asset registry**: định nghĩa 2 port; playwright chuyển
   thành backend impl đầu tiên; mỗi game một `assets.py`; bỏ
   `LIVE_SCREENSHOT_DIR` khỏi `tests/`; chốt pytest config.
2. **Chạy nốt actions↔flows boundary** (C1a→C3 của
   [`refactor_actions_flows_boundary.md`](refactor_actions_flows_boundary.md))
   — pattern phase thuần thành convention chung.
3. **Tách runtime và screen_detect**: `core/runtime.py` split generic/game;
   vòng scoring của `screen_detect` generic hóa; spec table về game.
4. **Physical move** sang `framework/` + `games/hauntedroom/` — mechanical vì
   imports đã kỷ luật; rewrite arch test theo cấu trúc đích, bỏ allowlist cũ.
5. **Port Burrito Bison** (`ref_cv`) lên framework — minimal: capture, một
   template match, một flow, stop/pause. Đây là proof-of-extraction; coi là
   một phần của công việc, không phải "việc sau".

## Guardrails

- Framework không import game, không chứa game vocabulary.
- Framework mỏng: 2 port là đủ cho đến khi backend thứ hai thật sự cần thêm.
- Không promote abstraction từ một ví dụ duy nhất; vision primitive chỉ
  promote khi ≥2 ngữ cảnh dùng.
- buz_vision pure — vi phạm là bug kiến trúc, không phải style.
- Behavior-preserving trong từng phase; mỗi phase commit độc lập, suite xanh.

## Điều kiện hoàn thành

- Framework tests không import hauntedroom; arch test chặn dependency 2 chiều.
- Không còn `parents[n]` asset magic ngoài registry.
- `ref_cv` chạy minimal trên framework.
- `tests/` repo chỉ còn arch + e2e.

## Ghi chú quyết định

Tên `framework/`, `games/` chỉ minh họa boundary; có thể đổi khi physical move,
miễn giữ đúng ranh giới tầng. Screen-state và login-state (hai vấn đề mở trên)
phải được giải quyết trong tầng game trước khi physical move (phase 4) đóng
cứng contract tương ứng.
