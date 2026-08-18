# Audit `automap.py`

## Hiện trạng

`tools/hauntedroom/flows/automap.py` đang dài khoảng 500 dòng. Vấn đề chính không chỉ là số dòng mà là `AutomapFlow` đang giữ nhiều trách nhiệm cùng lúc:

- Khai báo đường dẫn và default config.
- Load toàn bộ image template.
- Giữ mutable state của một trận.
- Làm adapter gọi các action trong `automap_support`.
- Điều phối handler theo priority.
- Xử lý lifecycle hoàn thành map.
- Duy trì `FIRST_WIN_DONE` xuyên qua dev reload.

Project đã có `automap_support`, vì vậy nên tiếp tục dùng package này thay vì tách mỗi method thành một file riêng.

## Breakdown đề xuất

```text
flows/
├── automap.py                         # public facade
└── automap_support/
    ├── config.py                      # paths, constants, AutomapConfig
    ├── state.py                       # mutable state của một lần chạy
    ├── templates.py                   # load và giữ image templates
    ├── flow.py                        # AutomapFlow và priority scheduler
    ├── map_completion.py              # map-end/win lifecycle
    ├── boss_flow.py
    ├── upgrade_action.py
    └── ...
```

### `config.py`

Giữ cấu hình game-specific của automap. Config phải immutable và được tạo theo
từng invocation/flow; không tạo global singleton để tránh đóng cứng giả định chỉ
có một Automap config trong process:

```python
@dataclass(frozen=True)
class AutomapConfig:
    threshold: float = 0.8
    debug: bool = False
    # template paths, polling intervals, feature flags, ...
```

`run_automap_flow()` build một `AutomapConfig`, sau đó truyền object đó vào
`AutomapTemplates.load(config)` và `AutomapFlow`. Cách này giữ dependency rõ,
cho phép test hoặc chạy đồng thời nhiều instance với config khác nhau, và tránh
phụ thuộc vào module state khi dev reload.

`AutomapConfig` chỉ chứa dữ liệu cấu hình như asset path, threshold, interval và
feature flag. Không đặt `page`, `stop_event`, callback `on_win`, loaded image hoặc
mutable runtime state trong config.

### `state.py`

State thay đổi trong một trận không thuộc config:

```python
@dataclass
class AutomapState:
    last_map_end_check: float | None = None
    map_completed: bool = False
    win_recorded: bool = False
    total_win: int | None = None
    final_boss_pet_deployed: bool = False
    boss_detection_logged: bool = False
    initial_gear_unlocked: bool = False
    initial_gear_attempted: bool = False
    initial_gear_placed: bool = False
```

Mỗi `AutomapFlow` tạo một `AutomapState` mới. Không để các field này trong config
vì state của lần chạy trước có thể rò sang lần chạy sau.

State có lifetime dài hơn một map phải nằm ở context riêng do game composition
root/runner sở hữu. Ví dụ `daily_first_win_done` có thể có scope theo run, login,
account hoặc game-day; không giữ bằng module global qua dev reload. Trước khi có
daily state store hoàn chỉnh, dùng một run-scoped context tối thiểu nhưng giữ API
đủ để bổ sung reset/persistence sau này.

### `templates.py`

Tách việc load resource khỏi constructor của flow:

```python
@dataclass
class AutomapTemplates:
    lv_up: np.ndarray
    built: np.ndarray
    boss_hp: np.ndarray
    # ...

    @classmethod
    def load(cls, config: AutomapConfig) -> "AutomapTemplates":
        return cls(
            lv_up=load_template(config.lv_up_template_path),
            built=load_template(config.built_template_path),
            boss_hp=load_template(config.boss_hp_template_path),
        )
```

Việc này làm `AutomapFlow.__init__` ngắn hơn và cho phép test truyền fake templates mà không phải patch `load_template` trên toàn module.

### `flow.py`

`AutomapFlow` chỉ nên chịu trách nhiệm orchestration:

- Capture frame.
- Convert grayscale.
- Chạy handler theo priority.
- Chờ poll/recheck interval.
- Quyết định khi nào flow kết thúc.

Priority order hiện tại nên tiếp tục được thể hiện rõ bằng một tuple tĩnh:

```python
handlers = (
    self.handle_level_spin_interrupt,
    self.handle_map_end,
    self.handle_initial_gear,
    self.handle_boss_critical,
    self.handle_level_up,
    self.handle_build_structure,
    self.handle_hero_levelup,
)
```

Chưa cần tạo event bus hoặc framework handler tổng quát; danh sách tĩnh dễ đọc và phù hợp với quy mô hiện tại.

### `map_completion.py`

`handle_map_end()` và `finish_map_from_home()` là một cụm chức năng độc lập. Nên gom các phần sau vào `map_completion.py` hiện có:

- Rate-limit việc detect map end.
- Detect `map_end` template.
- Click về home.
- Xử lý reward/daily first win/blocker.
- Cập nhật win state.

## Public facade

Giữ `flows/automap.py` làm API ổn định:

```python
from hauntedroom.flows.automap_support.flow import AutomapFlow
from hauntedroom.flows.automap_support.config import AutomapConfig
from hauntedroom.flows.automap_support.state import AutomapState
from hauntedroom.flows.automap_support.templates import AutomapTemplates


async def run_automap_flow(page, stop_event=None, *, on_win=None) -> bool:
    config = AutomapConfig()
    templates = AutomapTemplates.load(config)
    return await AutomapFlow(
        page,
        stop_event,
        config=config,
        templates=templates,
        state=AutomapState(),
        on_win=on_win,
    ).run()
```

Nên re-export `AutomapConfig` và `AutomapFlow` từ file này vì các test hiện đang import trực tiếp từ `hauntedroom.flows.automap`.

## Ranh giới dependency

Phân loại đề xuất:

- Cấu hình và feature flag: nằm trong immutable `AutomapConfig` theo flow.
- Template đã load: nằm trong `AutomapTemplates`.
- State thay đổi trong trận: nằm trong `AutomapState` của flow.
- Daily/login/account state: nằm trong game-owned context có scope và reset
  semantics riêng, không nằm trong module global.
- `page` và `stop_event`: thuộc runtime của flow.
- Callback như `on_win`: truyền theo lần chạy, không đặt global.
- Hàm cần mock như capture/click/time: có thể giữ dependency injection khi thực sự giúp test, không cần truyền mọi constant/config value.

`on_win` không nên nằm trong global config vì callback do caller tạo ra và có lifetime theo từng lần chạy. Đặt global có nguy cơ giữ callback cũ cho lần chạy tiếp theo.

## Thứ tự refactor an toàn

1. Extract immutable, per-flow `AutomapConfig`, giữ re-export/API cũ.
2. Extract map-scoped `AutomapState`.
3. Extract `AutomapTemplates` và cho phép inject templates trong test.
4. Đưa `on_win` ra khỏi config; thay `FIRST_WIN_DONE` module global bằng
   game-owned run/daily context tối thiểu.
5. Move `AutomapFlow` sang `automap_support/flow.py`, vẫn re-export từ `automap.py`.
6. Chuyển adapter map completion vào `map_completion.py`.
7. Cập nhật architecture allowlist và patch target trong test.
8. Chạy toàn bộ test automap, hero selection và runner reload.

## Kết luận

Automap là Haunted Room game business, không phải reusable framework. Refactor
trước mắt nên tạo boundary để sau này chuyển nguyên package sang
`games/hauntedroom` và chỉ đổi import capability/composition wiring, không phải
viết lại business logic.

Điểm cân bằng phù hợp là:

```text
game composition root
        ├── creates ──> AutomapConfig (per flow, immutable)
        ├── owns ─────> Daily/Run State
        └── invokes ──> AutomapFlow
                           ├── owns ──> AutomapState (per map)
                           └─────────> AutomapTemplates (game assets)
```

Cách tách này đưa `automap.py` về đúng vai trò compatibility facade. Static
handler priority và toàn bộ boss/hero/gear/reward/map-completion policy tiếp tục
thuộc game package. Framework sau này chỉ cung cấp vision, capture, timing,
cancellation, diagnostics và runner contracts.
