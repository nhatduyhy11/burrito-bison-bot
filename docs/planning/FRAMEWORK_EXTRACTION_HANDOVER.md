# Framework extraction — backlog handover

## Status

Đây là backlog cho một phase refactor lớn trong tương lai, không phải kế hoạch
thực thi ngay. Haunted Room hiện vẫn đang trong giai đoạn hoàn thiện feature;
không nên đóng cứng abstraction hoặc di chuyển hàng loạt file trước khi các flow
và state còn thiếu được hiểu rõ.

Mục tiêu dài hạn là giữ lại một automation framework có thể tái sử dụng và thay
"bộ ruột" Haunted Room bằng business package của game khác với rất ít thay đổi
ở browser/runtime/runner.

## Refactor nội bộ game có thể làm ngay

Việc chưa extract framework không chặn các refactor behavior-preserving bên trong
Haunted Room. Có thể tách các flow lớn ngay nếu boundary mới giúp phân biệt rõ:

- Immutable config theo từng flow/invocation.
- Loaded game assets/templates.
- Mutable state theo một map/flow.
- State có lifetime dài hơn như run/login/account/game-day.
- Runtime dependencies và callback do composition root truyền vào.

`AutomapFlow` là ví dụ chuẩn cho migration seam này. Boss, hero, gear, reward,
map completion, handler priority, threshold và asset của Automap vẫn là game
business. Có thể tách chúng thành package nội bộ game và giữ
`flows/automap.py` làm compatibility facade. Không chuyển các module đó vào
framework chỉ vì chúng dùng vision, polling hoặc state machine.

Trong giai đoạn chuyển tiếp, game business được phép import capability hiện tại
qua `hauntedroom.core.*`. Khi framework package được extract, các import này được
đổi sang public framework contracts hoặc được wiring tại composition root mà
không thay business behavior. Compatibility facade là API tạm thời của game,
không phải framework contract lâu dài.

Không dùng module global để nối lifetime qua dev reload. Callback như `on_win`
thuộc từng invocation; daily/first-win state thuộc game-owned state context có
scope và reset semantics rõ ràng. Có thể bắt đầu bằng in-memory run scope, nhưng
không trộn nó vào config hoặc map-scoped state.

## Mental model mục tiêu

Tách hệ thống thành ba vùng trách nhiệm:

1. **Reusable framework/capabilities**
   - Browser lifecycle, navigation và page/session setup.
   - Cancellation, pause/resume, checkpoint, timeout và flow clock.
   - Hotkey/event transport và command dispatch tổng quát.
   - Screenshot capture, diagnostics và logging hooks.
   - Vision primitives: image capture, template matching, color/component tools.
   - JSON action DSL: models, validation/parser và generic executor.
   - Generic flow registry/controller và optional developer reload mechanism.
2. **Game integration/adapters**
   - Wiring giữa framework và một game cụ thể.
   - Command/flow registration, asset registry và game settings.
   - Browser guards hoặc host-page behavior riêng của game/provider.
   - Reload policy/module list của game.
3. **Game business**
   - Screen/state taxonomy của game.
   - Boss, hero, gear, reward, map completion, train, research, EXP, v.v.
   - Threshold, region, priority, transition và policy mang ý nghĩa Haunted Room.
   - Daily rules và quyết định business dựa trên login/run state.

Dependency mong muốn:

```text
game app/composition root
        ├── registers game flows and adapters
        ├── uses reusable runner/runtime
        └── owns game business and assets

game business ───────> framework capabilities
framework ──X───────> Haunted Room modules or vocabulary
```

Một file "specific quá" nên ở game integration/business, kể cả khi nó có hình
dáng kỹ thuật giống detector, event hoặc action. Tên package không quyết định
boundary; ý nghĩa và lý do thay đổi mới quyết định boundary.

## Hai feature lớn còn thiếu cần ảnh hưởng thiết kế

### 1. Screen detector / screen-state recognition

Hệ thống cần xác định page hiện đang ở screen/state nào, sau đó switch sang action
hoặc flow tương ứng thay vì để từng flow tự đoán cục bộ. Theo definition hiện tại,
`ScreenDetector` và state-driven orchestration là business của game, không phải
capability của reusable framework:

- **Framework:** screenshot capture, template/color/component matching, generic
  polling, timeout, checkpoint và diagnostic capture. Snapshot reuse/cache chỉ
  extract vào framework nếu chứng minh được nó không phụ thuộc game.
- **Game business:** `GameScreen`, `ScreenDetector`, screen observation, danh sách
  state như login/home/map/battle/reward/popup, asset, region, threshold,
  confidence/priority, unknown/ambiguous handling, transition rule và logic switch
  action/flow tương ứng.
- **Runner:** chỉ quản lý lifecycle của top-level game flow; không biết vocabulary
  như login/home/battle/reward và không switch action theo screen.

Không đưa tên screen, detector contract hoặc transition model Haunted Room vào
core. Chỉ extract một generic detector/state interface sau này nếu có ít nhất hai
implementation thực tế chứng minh contract đó thật sự reusable.

Các câu hỏi cần chốt khi feature được implement:

- Game business detection là pull tại checkpoint hay một background observer?
- Một screenshot có được reuse cho nhiều detector để tránh capture lặp không?
- Confidence/priority xử lý thế nào khi hai screen cùng match?
- State ổn định cần bao nhiêu frame liên tiếp trước khi emit transition?
- Business flow consume current snapshot, transition event hay cả hai?
- Khi state unknown quá lâu, game policy recover thế nào và dùng framework
  diagnostics để capture/debug ra sao?

### 2. Login state và daily/run state

Cần nhận diện login/session state để flow có thể track lifecycle daily trong một
run. Cũng phải tách mechanism khỏi Haunted Room policy:

- **Framework:** state store/context theo scope, lifecycle reset, typed event,
  timestamp và optional persistence interface.
- **Game integration:** cách nhận diện logged-out/logging-in/logged-in, account
  identity nếu có, reconnect/session recovery.
- **Game business:** daily-first-win đã xử lý chưa, ngày game reset lúc nào, state
  nào giữ trong một map/process/login/account và rule nào invalidates state.

Không mặc định "daily" đồng nghĩa với process lifetime. Trước khi implement phải
chốt timezone/reset boundary, account scope và behavior khi logout/relogin hoặc
đổi account. Run-scoped in-memory state có thể là bước đầu, nhưng contract không
nên chặn persistence về sau.

## Coupling hiện tại cần xử lý trong phase refactor

- `core/cli.py` chứa URL/default/profile và wording riêng Haunted Room; phù hợp
  với app bootstrap/config hơn reusable core.
- `core/runtime.py` trộn `FlowControl`/timing generic với hotkey JavaScript,
  screenshot path, click logger và global mang tên Haunted Room.
- `runner/reload.py` biết toàn bộ dependency graph boss/gear/hero/completion; reload
  framework nên nhận game-owned reload policy/registration.
- `runner/commands.py` vừa cung cấp generic `FlowCommand` vừa wiring các flow cụ
  thể; tách contract khỏi Haunted Room command registry/composition root.
- `actions` phần lớn reusable nhưng executor/blocker còn biết popup guard và
  JavaScript global của Haunted Room. Cần hook/adapter thay vì hard dependency.
- `control_events` đang gom browser guard và visual game action dưới một tên;
  phân loại lại theo capability, adapter và business event.
- `settings.py` là game/application config, không phải framework config tổng quát.

## Cách thực hiện an toàn khi đến phase

Không bắt đầu bằng move/rename toàn bộ tree. Làm theo seam và giữ behavior:

1. Hoàn thiện hoặc làm rõ các feature/state quan trọng, nhất là screen detection
   và login/daily lifecycle. Điều này chặn việc generalize/extract contract tương
   ứng vào framework, nhưng không chặn refactor nội bộ game theo migration seam
   ở trên.
2. Ghi dependency rules bằng architecture tests trước khi di chuyển code.
3. Tách interface/contract nhỏ tại boundary hiện hữu: flow registration, reload
   policy, screen detector, state context, browser guard hooks.
4. Chuyển các primitive thực sự generic sang namespace framework và giữ adapter
   compatibility tạm thời nếu cần.
5. Chuyển Haunted Room wiring/settings/assets/policy vào game package.
6. Tạo một fake/minimal second game để chứng minh framework không còn implicit
   dependency vào Haunted Room. Không cần game đầy đủ; chỉ cần launch, detect một
   screen, chạy một flow JSON và stop/pause được.
7. Xóa compatibility layer sau khi test và entry point mới ổn định.

Ưu tiên extraction theo độ ổn định:

1. Vision primitives và flow-control/timing.
2. Generic runner contracts và command registry.
3. JSON action engine cùng extension hooks.
4. Browser lifecycle/hotkey/diagnostics.
5. Game-owned screen detector/orchestration và state store sau khi behavior thực
   tế đủ rõ; chỉ extract primitive đã chứng minh reusable.
6. Hot reload cuối cùng; đây là developer infrastructure phụ thuộc mạnh vào
   module graph sau refactor.

## Guardrails

- Big refactor phải behavior-preserving; feature change đi thành bước riêng có
  test riêng.
- Không generalize một abstraction chỉ từ một game-specific example.
- Framework không import package Haunted Room và không chứa vocabulary của game.
- Business không trực tiếp điều khiển runner internals; giao tiếp qua context,
  control/event và registered flow contracts.
- Không biến mọi detector/action thành JSON nếu code typed rõ và testable hơn.
- Tránh một `core` hoặc `runtime` mới trở thành thư mục/file miscellaneous.
- Asset path, screen name, threshold và transition policy thuộc game package.
- Preserve cooperative cancellation tại mọi wait/poll/click boundary.

## Definition of done dài hạn

- Haunted Room chạy qua public framework contracts, không dùng framework internals.
- Framework tests không cần import Haunted Room.
- Architecture test chặn dependency framework → game.
- Có minimal second-game fixture chứng minh swap business package.
- Screen recognition và action switching thuộc game business; framework chỉ giữ
  vision/runtime primitives đã chứng minh reusable.
- Login/daily state có scope và reset semantics rõ ràng, có test transition.
- JSON action engine hỗ trợ game-specific extension qua registration/hook thay vì
  hard-coded import.
- Hot reload được khai báo bởi game/application composition root.
- Tài liệu mô tả entry point, lifecycle, extension points và dependency rules.

## Ghi chú quyết định

Chưa chọn structure/package name cuối cùng. Các tên như `framework`, `automation`,
`games/hauntedroom` chỉ minh họa boundary. Hãy để screen detector, login state và
những feature còn thiếu cung cấp thêm evidence trước khi đóng structure chính
thức.
