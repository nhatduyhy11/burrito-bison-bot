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

Giữ toàn bộ cấu hình dùng chung của automap:

```python
@dataclass
class AutomapConfig:
    threshold: float = 0.8
    debug: bool = False
    # template paths, polling intervals, feature flags, ...


automap_config = AutomapConfig()
```

Nếu ứng dụng chỉ dùng một bộ config cho toàn process, các module có thể đọc trực tiếp config này. Không cần truyền từng giá trị qua nhiều tầng function.

Nên import module:

```python
from hauntedroom.flows.automap_support import config
```

Không nên copy một giá trị global vào namespace của module sử dụng:

```python
from hauntedroom.flows.automap_support.config import AUTOMAP_TEMPLATE_THRESHOLD
```

Import module giúp việc thay config trong test hoặc reload nhất quán hơn.

Global config phù hợp nếu không cần chạy đồng thời hai `AutomapFlow` với hai cấu hình khác nhau. Nếu sau này xuất hiện yêu cầu đó, có thể chuyển sang config theo instance mà không cần trộn config với runtime state.

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

Mỗi `AutomapFlow` tạo một `AutomapState` mới. Không để các field này trong global config vì state của lần chạy trước có thể rò sang lần chạy sau.

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
    def load(cls) -> "AutomapTemplates":
        cfg = config.automap_config
        return cls(
            lv_up=load_template(cfg.lv_up_template_path),
            built=load_template(cfg.built_template_path),
            boss_hp=load_template(cfg.boss_hp_template_path),
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


async def run_automap_flow(page, stop_event=None, *, on_win=None) -> bool:
    return await AutomapFlow(page, stop_event, on_win=on_win).run()
```

Nên re-export `AutomapConfig` và `AutomapFlow` từ file này vì các test hiện đang import trực tiếp từ `hauntedroom.flows.automap`.

## Ranh giới dependency

Phân loại đề xuất:

- Cấu hình và feature flag dùng chung: đọc từ `config.automap_config`.
- Template đã load: nằm trong `AutomapTemplates`.
- State thay đổi trong trận: nằm trong `AutomapState` của flow.
- `page` và `stop_event`: thuộc runtime của flow.
- Callback như `on_win`: truyền theo lần chạy, không đặt global.
- Hàm cần mock như capture/click/time: có thể giữ dependency injection khi thực sự giúp test, không cần truyền mọi constant/config value.

`on_win` không nên nằm trong global config vì callback do caller tạo ra và có lifetime theo từng lần chạy. Đặt global có nguy cơ giữ callback cũ cho lần chạy tiếp theo.

## Thứ tự refactor an toàn

1. Extract `config.py`, giữ re-export/API cũ.
2. Extract `AutomapState`.
3. Extract `AutomapTemplates` và cho phép inject templates trong test.
4. Move `AutomapFlow` sang `automap_support/flow.py`, vẫn re-export từ `automap.py`.
5. Chuyển adapter map completion vào `map_completion.py`.
6. Cập nhật architecture allowlist và patch target trong test.
7. Chạy toàn bộ test automap, hero selection và runner reload.

## Kết luận

Với kiến trúc hiện tại, dùng một global `AutomapConfig` và import config trực tiếp tại nơi cần dùng là lựa chọn thực dụng, miễn là ứng dụng chỉ có một cấu hình automap cho toàn process.

Không nên dùng config làm nơi chứa mutable runtime state. Điểm cân bằng phù hợp là:

```text
global AutomapConfig
        ↓
AutomapFlow ── owns ──> AutomapState
        │
        └─────────────> AutomapTemplates
```

Cách tách này giảm đáng kể argument truyền lòng vòng, giữ dependency đủ rõ và đưa `automap.py` về đúng vai trò public facade.
