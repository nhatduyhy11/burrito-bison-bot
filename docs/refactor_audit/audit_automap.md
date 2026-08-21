# Audit `automap.py`

## Hiện trạng cần xử lý

`tools/hauntedroom/flows/automap.py` vẫn giữ các trách nhiệm chưa thuộc về một
public facade:

- Định nghĩa `AutomapFlow` và toàn bộ priority scheduler.
- Làm adapter cho boss, hero, gear, upgrade và map completion.
- Rate-limit map-end, detect map-end, gọi completion flow và cập nhật win state.

Các boundary còn chưa sạch:

- `handle_map_end()` và `finish_map_from_home()` vẫn làm flow orchestration phụ
  thuộc trực tiếp vào policy completion.
- Architecture allowlist vẫn phản ánh facade lớn thay vì boundary đích.

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

`on_win` đã là dependency theo invocation: facade truyền callback trực tiếp
vào `AutomapFlow`, rồi flow truyền tiếp vào map-completion context.
`AutomapConfig` chỉ còn configuration data.

## Template loading

`AutomapFlow` chỉ nhận `AutomapTemplates` đã load; constructor không còn
fallback resource loading. Facade `run_automap_flow()` là composition root load
template cho mỗi invocation.

Test trực tiếp flow dùng factory tạo `AutomapTemplates` fake và inject rõ ràng.
Test loader patch symbol tại `automap_support.templates`, không patch facade.
Hero templates cũng đi qua cùng injection seam với các template còn lại.

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

1. Chuyển `AutomapFlow` sang `automap_support/flow.py`, giữ re-export từ
   `automap.py`.
2. Chuyển map-end/completion adapter sang `map_completion.py`.
3. Cập nhật architecture allowlist theo owner mới.
4. Chạy test automap, hero selection, runner và dev reload.

## Ranh giới không nên mở rộng

Automap là Haunted Room game business, không phải reusable framework. Boss,
hero, gear, reward và map-completion policy tiếp tục thuộc game package. Không
tạo event framework hoặc generic flow abstraction chỉ để giảm số dòng của
`automap.py`.
