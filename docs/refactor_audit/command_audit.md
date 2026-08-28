# Audit `runner/commands.py`

Các file liên quan được audit:

- `tools/hauntedroom/runner/commands.py` (406 dòng - Đối tượng audit chính)
- `tools/hauntedroom/runner/default_commands.py` (31 dòng - Consumer và registry mapping)
- `tools/hauntedroom/runner/reload.py` (227 dòng - Hot-reload dependency provider)
- `tests/runner/test_commands.py` (157 dòng - Unit/Policy tests)

---

## 1. Trả lời trực diện: Tại sao `test_commands.py` rất ngắn gọn mà `commands.py` lại khá dài (406 dòng)?

### Sự bất cân xứng về trách nhiệm (Responsibility Asymmetry)

1. **`test_commands.py` ngắn (~157 dòng) vì:**
   - **Chỉ kiểm tra Metadata Contract**: Test chỉ xác nhận danh sách hotkey (`t`, `5`, `9`), mapping màn hình (`ScreenName`), và các cờ cấu hình (`control_factory`, `stops_on_repeat_screen_hotkey`).
   - **Chỉ mock một vài flow đại diện**: Test chỉ mock `reload_policy` và assert execution logic cho 3 flow tiêu biểu (`newbie_block`, `json_actions` [Shift+5], và `spawn_exit_lvup` [Shift+9]).
   - **Không chứa business logic hay template definitions**: Test không cần khởi tạo thực tế 12 flow, không chứa đường dẫn template ảnh (`rooms/*.png`) hay tọa độ pixel.

2. **`commands.py` dài (406 dòng) vì đang là một "God Factory" gánh 4 tầng trách nhiệm khác nhau:**
   - **Tầng 1: Hardcoded Action Sequences & Macro Definitions (Dòng 23–100, ~80 dòng)**
     Chứa trực tiếp đường dẫn asset `ROOMS_DIR`, `BLOCKER_PRIORITY`, cùng các hàm build chuỗi action phức tạp (`build_start_battle_actions`, `build_spawn_exit_lvup_actions`, `build_newbie_block_actions`).
   - **Tầng 2: Data Models & Typings (Dòng 20–22, 102–117, ~20 dòng)**
     Định nghĩa `ResolvedFlow`, `FlowCommand`, và các Type Alias (`FlowStarter`, `FlowResolver`, `ControlFactory`).
   - **Tầng 3: 12 Local Resolver Closures với Boilerplate lặp lại (Dòng 120–320, ~200 dòng)**
     Mỗi flow tự khai báo một hàm `resolve_*` lồng bên trong một `async def run(...)` với logic bọc flow gần như sao chép y hệt nhau.
   - **Tầng 4: Factory & Registry Instantiation (Dòng 321–405, ~85 dòng)**
     Khởi tạo và cấu hình `dict[str, FlowCommand]`.

---

## 2. Chi tiết các vấn đề kiến trúc & Code Smells trong `commands.py`

### Vấn đề 1: Vi phạm Single Responsibility Principle (SRP) & Layer Boundaries
- **Hiện trạng**: Tầng `runner` theo quy định kiến trúc (`docs/ARCHITECTURE.md`) chỉ có nhiệm vụ dispatching, standby handling, và wiring command. Tuy nhiên, `commands.py` lại trực tiếp chứa:
  - Tọa độ UI game hardcoded (`NEWBIE_BLOCKER_DISMISS_CLICK`).
  - Đường dẫn template ảnh (`ROOMS_DIR / "start_home.png"`, `"exit_click.png"`, ...).
  - Danh sách thứ tự ưu tiên blocker (`BLOCKER_PRIORITY = ("lubu_close.png", ...)`).
  - Macro hành động kết hợp nhiều step (battle entry, spawn exit level up).
- **Hệ quả**: Khi thay đổi tọa độ, template ảnh hoặc macro game, lập trình viên phải sửa file thuộc tầng `runner` thay vì tầng `actions` hay `flows`.

### Vấn đề 2: Boilerplate lặp lại trầm trọng trong các Flow Resolvers
Trong hàm `build_flow_commands`, 12 hàm `resolve_*` có thể chia thành 3 nhóm lặp mã:

1. **Nhóm Simple Leaf Flows (5 flow lặp 100% code)**:
   - `resolve_research`, `resolve_artifact`, `resolve_diamond_collection`, `resolve_exp_available`, `resolve_hero_up_available`.
   - Mỗi hàm đều có đúng cấu trúc:
     ```python
     def resolve_xyz(actions, dev_reload, _actions_path):
         xyz_flow = reload_policy.get_xyz_flow(dev_reload)
         async def run(page, stop_event, _debug: bool):
             return await xyz_flow(page, stop_event)
         return ResolvedFlow(actions, run)
     ```
     Đoạn mã này lặp lại 5 lần, tốn hơn 60 dòng chỉ để forward `(page, stop_event)`.

2. **Nhóm Automap/Stateful Flows (4 flow lặp `MapRunState`)**:
   - `resolve_automap`, `resolve_train`, `resolve_new_account`, `resolve_start_auto`.
   - Mỗi hàm đều tự khởi tạo `run_state = MapRunState()` và wrap các tham số `(page, stop_event, debug, run_state=run_state)` hoặc inject `automap_runtime.automap_flow`.

3. **Nhóm Macro/Action-Runner Flows (3 flow lặp `action_runner`)**:
   - `resolve_newbie_block`, `resolve_spawn_exit_lvup`, `resolve_json_actions`.
   - Lặp lại cấu trúc gọi `action_runner(page, actions, loop_count=..., stop_event=stop_event, ...)`.

### Vấn đề 3: Closure lồng 3 cấp gây khó khăn khi Test độc lập
- Cấu trúc: `build_flow_commands(...)` (Cấp 1) $\rightarrow$ `resolve_xyz(...)` (Cấp 2) $\rightarrow$ `async def run(...)` (Cấp 3).
- **Hệ quả**: Không thể unit test một flow resolver riêng lẻ mà bắt buộc phải chạy qua toàn bộ hàm factory lớn `build_flow_commands`, phụ thuộc vào việc inject toàn bộ `reload_policy`.

---

## 3. Bản đồ cấu trúc sau khi Breakdown (Target Architecture)

Tách `commands.py` thành các thành phần chuyên biệt theo đúng vai trò:

```text
tools/hauntedroom/
├── actions/
│   └── macros.py               <-- [MỚI] Chứa build_start_battle_actions,
│                                        build_spawn_exit_lvup_actions,
│                                        build_newbie_block_actions,
│                                        ROOMS_DIR, BLOCKER_PRIORITY
└── runner/
    ├── models.py               <-- [MỚI] Chứa ResolvedFlow, FlowCommand,
    │                                    FlowStarter, FlowResolver, ControlFactory
    ├── resolvers.py            <-- [MỚI] Chứa các Generic Resolver Helpers
    │                                    (loại bỏ boilerplate lặp lại)
    ├── commands.py             <-- [REFACTOR] Chỉ còn declarative registry (~60 dòng)
    └── default_commands.py     <-- Giữ nguyên consumer mapping
```

---

## 4. Hướng breakdown và kế hoạch thực hiện từng bước (Actionable Roadmap)

### Bước 1: Trích xuất Macro Actions ra khỏi `runner` (Giảm ~80 dòng)
- Tạo module `tools/hauntedroom/actions/macros.py` (hoặc đặt trong `hauntedroom.actions` / `hauntedroom.flows`):
  - Chuyển `ROOMS_DIR`, `BLOCKER_PRIORITY`, `build_blocker_paths()`.
  - Chuyển `build_start_battle_actions()`, `build_spawn_exit_lvup_actions()`, `build_newbie_block_actions()`.
- Export các hàm này để `commands.py` hoặc các flow khác import khi cần.
- **Lợi ích**: Tách rời hoàn toàn template path OpenCV và tọa độ click ra khỏi tầng command runner.

### Bước 2: Tách Data Models & Type Aliases (Giảm ~25 dòng)
- Đưa `ResolvedFlow`, `FlowCommand`, `FlowStarter`, `FlowResolver`, `ControlFactory` sang `tools/hauntedroom/runner/models.py` (hoặc giữ gọn gàng ở đầu `commands.py` nếu file đã đủ ngắn).

### Bước 3: Tạo Generic Flow Resolver Helpers (Giảm ~120 dòng)
Tạo `tools/hauntedroom/runner/resolvers.py` chứa các higher-order functions tái sử dụng:

```python
# Ví dụ các resolver helper tinh gọn:

def resolve_simple_flow(flow_getter):
    """Dùng chung cho research, artifact, diamond_collection, exp_available, hero_up_available."""
    def resolver(actions: list[Action], dev_reload: bool, _path: Optional[Path]) -> ResolvedFlow:
        flow = flow_getter(dev_reload)
        async def run(page, stop_event, _debug: bool):
            return await flow(page, stop_event)
        return ResolvedFlow(actions, run)
    return resolver

def resolve_map_state_flow(flow_getter, automap_runtime_getter):
    """Dùng chung cho automap, train, new_account."""
    def resolver(actions: list[Action], dev_reload: bool, _path: Optional[Path]) -> ResolvedFlow:
        runtime = automap_runtime_getter(dev_reload)
        flow = flow_getter(dev_reload)
        async def run(page, stop_event, debug: bool):
            run_state = MapRunState()
            return await flow(page, runtime.automap_flow, stop_event, debug, run_state=run_state)
        return ResolvedFlow(actions, run)
    return resolver

def resolve_action_loop_flow(actions_builder, loop_count: Optional[int], loop_label: str, runner_getter):
    """Dùng chung cho newbie_block, spawn_exit_lvup."""
    def resolver(_actions: list[Action], dev_reload: bool, _path: Optional[Path]) -> ResolvedFlow:
        runner = runner_getter(dev_reload)
        built_actions = actions_builder()
        async def run(page, stop_event, _debug: bool):
            return await runner(page, built_actions, loop_count=loop_count, stop_event=stop_event, loop_label=loop_label)
        return ResolvedFlow(built_actions, run)
    return resolver
```

### Bước 4: Tái cấu trúc `build_flow_commands` trong `commands.py` thành Declarative Table
Sau khi có các helper trên, `commands.py` trở nên cực kỳ súc tích, chỉ khai báo mapping khai báo (declarative):

```python
def build_flow_commands(reload_policy, start_auto) -> dict[str, FlowCommand]:
    get_runner = reload_policy.get_action_runner
    get_map_rt = reload_policy.get_automap_runtime

    return {
        "newbie_block": FlowCommand(
            "newbie_block", "dismiss newbie blocker", "Dismiss newbie blocker",
            resolve_action_loop_flow(build_newbie_block_actions, loop_count=1, loop_label="Newbie blocker", runner_getter=get_runner),
        ),
        "spawn_exit_lvup": FlowCommand(
            "spawn_exit_lvup", "spawn_exit_lvup loop", "Spawn / exit / level-up loop",
            resolve_action_loop_flow(build_spawn_exit_lvup_actions, loop_count=None, loop_label="spawn_exit_lvup loop", runner_getter=get_runner),
        ),
        "research": FlowCommand(
            "research", "research", "Research",
            resolve_simple_flow(reload_policy.get_research_flow),
            stops_on_repeat_screen_hotkey=True,
        ),
        "artifact": FlowCommand(
            "artifact", "artifact", "Artifact",
            resolve_simple_flow(reload_policy.get_artifact_flow),
            stops_on_repeat_screen_hotkey=True,
        ),
        "diamond_collection": FlowCommand(
            "diamond_collection", "diamond collection", "Diamond collection",
            resolve_simple_flow(reload_policy.get_diamond_collection_flow),
            stops_on_repeat_screen_hotkey=True,
        ),
        "exp_available": FlowCommand(
            "exp_available", "EXP available", "EXP available",
            resolve_simple_flow(reload_policy.get_exp_available_flow),
            stops_on_repeat_screen_hotkey=True,
        ),
        "hero_up_available": FlowCommand(
            "hero_up_available", "hero breakthrough available", "Hero breakthrough available",
            resolve_simple_flow(reload_policy.get_hero_up_available_flow),
            stops_on_repeat_screen_hotkey=True,
        ),
        # ... các command còn lại
    }
```

---

## 5. Kết quả mong đợi sau Refactoring

| Metric / Khía cạnh | Trước Refactor (`commands.py`) | Sau Refactor |
| :--- | :--- | :--- |
| **Tổng số dòng `commands.py`** | 406 dòng | ~60 - 80 dòng |
| **Trách nhiệm (SRP)** | Ôm cả macro UI, models, resolvers, registry | Chỉ giữ command registry & table builder |
| **Asset & Template coupling** | Phụ thuộc trực tiếp vào `rooms/*.png` | Tách sang `actions/macros.py` |
| **Boilerplate lặp lại** | 12 closures riêng biệt (~200 dòng) | ~3 generic resolver functions dùng chung |
| **Khả năng Unit Test** | Test gián tiếp qua dictionary lớn | Test độc lập từng generic resolver |
| **Tính nhất quán kiến trúc** | Vi phạm boundary tầng runner | Tuân thủ tuyệt đối `docs/ARCHITECTURE.md` |

---

## 6. Kế hoạch kiểm thử & Đảm bảo không Regression

1. **Khóa contract bằng test hiện tại**:
   Chạy toàn bộ test suite để đảm bảo baseline xanh:
   ```shell
   uv run --with pytest pytest -q
   ```
2. **Bổ sung Unit Test cho các resolver helpers**:
   Viết unit test cho `resolve_simple_flow`, `resolve_action_loop_flow`, `resolve_map_state_flow` trong `tests/runner/test_commands.py` để verify việc truyền tham số `stop_event`, `page`, `debug`, và `run_state`.
3. **Kiểm tra tương thích ngược**:
   Đảm bảo `FLOW_COMMANDS` và `SCREEN_FLOW_COMMANDS` trong `tools/hauntedroom/runner/default_commands.py` không thay đổi signature hay behavior.
