# Kiến trúc hiện tại

Tài liệu này mô tả các boundary và dependency rule đang được dùng bởi Haunted
Room Runner. Đây là tài liệu sống: cập nhật nó khi trách nhiệm package hoặc wiring
thực tế thay đổi.

Lý do lịch sử dẫn tới cấu trúc ban đầu được lưu tại
[`ADR-001-hauntedroom-package-boundaries.md`](adr/ADR-001-hauntedroom-package-boundaries.md).
Định hướng tách framework trong tương lai nằm tại
[`FRAMEWORK_EXTRACTION_HANDOVER.md`](planning/FRAMEWORK_EXTRACTION_HANDOVER.md) và
chưa phải kiến trúc đã được chấp nhận.

## Composition root

`tools/hauntedroom_runner.py` là composition root. Entrypoint chịu trách nhiệm:

- chuẩn bị CLI, browser profile và page;
- thực hiện startup navigation và browser guard;
- chọn action mode hoặc standby mode;
- inject direct-command table và screen-command table vào standby controller;
- quản lý shutdown của runner và browser.

Entrypoint không chứa business policy của từng flow.

## Package boundaries

```text
tools/
├── hauntedroom_runner.py       composition root
└── hauntedroom/
    ├── core/                   capability nền tảng hiện tại
    ├── actions/                model, loader và executor của action JSON
    ├── control_events/         blocker/browser control có quyền preempt flow
    ├── runner/                 command dispatch, standby, navigation, reload
    ├── flows/                  Haunted Room business flows
    │   └── automap_support/    implementation nội bộ của auto-map
    ├── screen_detect.py        nhận diện screen mang vocabulary của game
    └── settings.py             cấu hình application/game
```

`core` ở đây có nghĩa là foundational capability của codebase hiện tại, không
phải domain layer theo Clean Architecture và chưa phải public framework. Nó có
thể phụ thuộc stdlib hoặc thư viện ngoài như Playwright, NumPy và OpenCV, nhưng
không được biết business flow nào đang sử dụng nó.

### `core`

- `cli.py`: CLI và preparation cho runner hiện tại.
- `mouse.py`: click/drag primitive dùng chung.
- `runtime.py`: flow control, hotkey, wait/countdown và runtime diagnostics.
- `template.py`: load và match template.
- `terminal.py`: terminal formatting.
- `vision.py`: capture và OpenCV primitive không mang business rule.

Một số module trong `core` vẫn chứa coupling Haunted Room/application. Việc phân
loại lại chúng thuộc phase framework extraction, không làm thay đổi dependency
rule hiện tại.

### `actions`

`actions` sở hữu typed action model, parse/validation/path resolution và generic
execution của action JSON. Loader là input boundary; runner nhận action đã được
prepare. Action engine không được phụ thuộc business flow.

### `flows`

`flows` chứa policy mang ý nghĩa Haunted Room: auto-map, train, research,
artifact, EXP, hero breakthrough và start-auto. Detector, threshold, priority,
transition và asset chỉ dùng cho một flow vẫn là game business, kể cả khi chúng
có hình dạng kỹ thuật giống vision helper.

`automap.py` là coordinator/public API cho một lượt auto-map;
`automap_support/` chứa phase, action, state và detector nội bộ. Composite flow có
thể nhận dependency/callback từ command wiring thay vì import trực tiếp flow khác.

### `screen_detect.py`

Screen detection mang screen taxonomy của Haunted Room. Module này nhận diện và
trả kết quả; quyết định screen nào chạy command nào nằm ở runner wiring. Nó được
phép dùng detector game-specific hiện có khi đó là nguồn nhận diện chuẩn.

### `runner`

`runner` nối runtime với game commands:

- `commands.py`: command spec/factory;
- `default_commands.py`: game-owned registration và screen-to-command mapping;
- `standby.py`: hotkey transport, dispatch và lifecycle task;
- `navigation.py`: startup navigation policy;
- `reload.py`: dev-reload policy theo module graph hiện tại.

Registration và reload policy hiện còn game-specific. Chúng là migration target
trong framework extraction, chưa phải generic framework contract.

### `control_events`

Control event có thể tạm thời preempt normal flow. Package này được phụ thuộc
`core`, sibling module và application settings, nhưng không phụ thuộc `actions`
hoặc `flows`. Boundary này sẽ được phân loại lại thành framework capability,
game adapter hoặc business event khi extraction có đủ evidence.

## Dependency direction

```text
hauntedroom_runner.py
        │
        ├── runner ────────────────┐
        ├── actions                │
        ├── control_events         │
        └── core                   │
                                   ▼
runner ──> actions / flows / screen_detect / control_events / core
flows  ──> core (và support module thuộc cùng feature)
actions ─> core / control_events
control_events ─> core / settings
core ──X──> actions / flows / runner / entrypoint
```

Các invariant chính:

1. `core` không import tầng trên hoặc game flow.
2. `actions` không import `flows`.
3. `control_events` không import `actions` hoặc `flows`.
4. Leaf flow không import action engine hay flow khác, trừ composite dependency
   được chỉ rõ và kiểm soát.
5. Support module của auto-map không trở thành dependency ngầm của flow không
   liên quan.
6. Module tầng dưới không import ngược composition root.
7. Các invariant đã ổn định được khóa bằng
   `tests/test_hauntedroom_architecture.py`; backlog mở rộng coverage nằm trong
   `docs/refactor_audit/REFACTOR.md`, và tài liệu không thay thế test.

## Runtime wiring

Ở standby, direct hotkey và screen-driven command đều được khai báo qua command
tables trong `runner/default_commands.py`. `screen_detect.py` chỉ cung cấp screen
result; runner thực hiện dispatch. `Shift+5` lazy-load action JSON ở mỗi lần bắt
đầu. Chi tiết hotkey và CLI thuộc [`README.md`](README.md), không được duplicate
tại đây.

Dev reload giữ browser/session hiện tại và resolve lại module cần thiết trước khi
khởi chạy flow mới. Danh sách reload là application policy và hiện nằm trong
`runner/reload.py`.

## Hướng tiến hóa

Boundary hiện tại là khung tổ chức Haunted Room, không phải cam kết rằng toàn bộ
`core`, `actions` hoặc `runner` đều reusable. Khi tách framework:

- framework chỉ giữ capability không chứa Haunted Room vocabulary;
- game integration sở hữu wiring, settings, asset registry và provider guard;
- game business sở hữu screen taxonomy, detector policy, flow và state của game;
- framework không được import package Haunted Room.

Chỉ chốt contract extraction bằng một ADR mới khi boundary đã có đủ evidence và
được quyết định; không cập nhật ADR-001 để mô tả thiết kế mới.
