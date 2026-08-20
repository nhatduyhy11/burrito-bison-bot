# Audit `automap.py`

## Hiện trạng cần xử lý

`tools/hauntedroom/flows/automap.py` vẫn giữ các trách nhiệm chưa thuộc về một
public facade:

- Định nghĩa `AutomapFlow` và toàn bộ priority scheduler.
- Làm adapter cho boss, hero, gear, upgrade và map completion.
- Tự load `AutomapTemplates` trong constructor khi caller không inject.
- Giữ callback runtime `on_win` bên trong `AutomapConfig`.
- Rate-limit map-end, detect map-end, gọi completion flow và cập nhật win state.

Các boundary còn chưa sạch:

- `AutomapConfig` đang trộn configuration data với callback runtime `on_win`.
- `AutomapFlow.__init__` vừa nhận loaded templates vừa có thể tự load chúng, nên
  composition root chưa phải owner duy nhất của resource loading.
- Test vẫn patch `hauntedroom.flows.automap.load_template`, giữ facade phụ thuộc
  vào implementation detail của template loading.
- `handle_map_end()` và `finish_map_from_home()` vẫn làm flow orchestration phụ
  thuộc trực tiếp vào policy completion.

## Kiến trúc đích

```text
game composition root / runner
        ├── owns ─────> Daily/Run State
        ├── creates ──> AutomapConfig
        ├── loads ────> AutomapTemplates
        └── invokes ──> AutomapFlow
                           ├── owns ──> AutomapState (per map)
                           └── calls ─> MapCompletion

flows/
├── automap.py                         # compatibility facade
└── automap_support/
    ├── flow.py                        # AutomapFlow và priority scheduler
    ├── map_completion.py              # map-end/win lifecycle adapter
    └── ...
```

`flows/automap.py` chỉ nên re-export public API và tạo dependency cho một lần
chạy:

```python
from hauntedroom.flows.automap_support.flow import AutomapFlow


async def run_automap_flow(page, stop_event=None, *, on_win=None) -> bool:
    config = AutomapConfig()
    templates = AutomapTemplates.load(config)
    state = AutomapState()
    return await AutomapFlow(
        page,
        stop_event,
        config=config,
        templates=templates,
        state=state,
        on_win=on_win,
        run_context=game_owned_run_context,
    ).run()
```

Ví dụ trên chỉ mô tả dependency boundary. Composition root thực tế phải truyền
`run_context`; facade không được tạo context mới cho từng map nếu state cần tồn
tại qua nhiều map.

## Daily/run state và callback

Daily/run state đã được chuyển sang `AutomapRunContext` với field
`daily_first_win_done`. Runner tạo context mới cho mỗi command invocation:

- One-map và train dùng context riêng cho lượt command đó.
- Start-auto truyền cùng một context qua mọi lần gọi `run_automap_flow()`.
- Context reset khi command kết thúc và command mới được khởi chạy; hiện không
  restore qua lần khởi động lại bot.

`AutomapState` giờ chỉ giữ state theo một map. Module global `FIRST_WIN_DONE` đã
được xóa; completion outcome cập nhật trực tiếp context được inject.

`on_win` là dependency theo invocation. Truyền callback trực tiếp vào
`AutomapFlow` hoặc map-completion context, không đặt trong `AutomapConfig`.

## Template loading

`AutomapFlow` chỉ nhận `AutomapTemplates` đã load. Bỏ fallback
`AutomapTemplates.load()` khỏi constructor sau khi chuyển toàn bộ caller sang
composition root.

Test cần một factory/fixture tạo `AutomapTemplates` fake và inject trực tiếp.
Test riêng cho loader patch tại nơi symbol được dùng trong
`automap_support.templates`, không patch facade. Loader của hero templates cũng
nên đi qua cùng injection seam nếu test cần kiểm soát toàn bộ resource loading.

## `flow.py`

Chuyển `AutomapFlow` và `SituationHandler` sang `automap_support/flow.py`.
`AutomapFlow` chỉ điều phối:

- Capture và grayscale frame.
- Chạy handler theo priority.
- Chờ poll/recheck interval.
- Kết thúc khi map complete hoặc flow bị stop.

Priority order tiếp tục dùng tuple tĩnh:

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

Không cần event bus hoặc framework handler tổng quát.

## `map_completion.py`

Gom lifecycle map-end vào boundary này:

- Rate-limit việc detect map end.
- Detect và click `map_end`.
- Xử lý reward, daily first win và blocker.
- Gọi `on_win`.
- Cập nhật map state và run/daily context.

`AutomapFlow` chỉ gọi adapter và nhận outcome đủ để quyết định tiếp tục hay kết
thúc; không tự đồng bộ từng field completion hoặc module global.

## Thứ tự refactor còn lại

1. Đưa `on_win` ra khỏi `AutomapConfig` và truyền như dependency theo invocation.
2. Bỏ template-loading fallback khỏi `AutomapFlow.__init__`; chuyển caller/test
   sang inject `AutomapTemplates`.
3. Chuyển `AutomapFlow` sang `automap_support/flow.py`, giữ re-export từ
   `automap.py`.
4. Chuyển map-end/completion adapter sang `map_completion.py`.
5. Cập nhật architecture allowlist và test patch targets theo owner mới.
6. Chạy test automap, hero selection, runner và dev reload.

## Ranh giới không nên mở rộng

Automap là Haunted Room game business, không phải reusable framework. Boss,
hero, gear, reward và map-completion policy tiếp tục thuộc game package. Không
tạo event framework hoặc generic flow abstraction chỉ để giảm số dòng của
`automap.py`.
