# `actions/runner.py` audit

File được audit: `tools/hauntedroom/actions/runner.py`

Tài liệu này chỉ ghi nhận các issue còn tồn tại trong code hiện tại.

## Current responsibility

`runner.py` hiện vừa điều phối action loop, vừa chuẩn bị template resources, vừa thực thi action và áp dụng timeout policy.

Luồng chính:

```text
actions
→ collect và preload templates
→ chạy action loop
→ dispatch từng action
→ thực thi browser side effects
→ xử lý stop, timeout và retry
```

## 1. `collect_template_paths()` — resource preparation nằm trong runner

### Nó đang làm gì?

Duyệt toàn bộ actions để tìm các template cần preload:

- `ClickTemplateAction`: lấy `template_path` và `skip_if_template_path`.
- `ClearBlockersAction`: lấy `blocker_paths` và `until_template_path`.
- Dùng `set[Path]` để tránh load trùng template.

`run_actions()` sau đó trực tiếp load các path này thành `dict[Path, np.ndarray]`.

### Issue còn tồn tại

Runner phải biết:

- Action type nào sử dụng template.
- Template nằm ở field nào của từng action.
- Template được load bằng cách nào.
- Template cache sử dụng `Path` và NumPy array.

Đây là resource preparation, không phải loop orchestration. Khi thêm action type mới có template, cả resource collector và action dispatcher đều phải được cập nhật.

### Breakdown đề xuất

Chuyển sang `actions/resources.py`:

```python
def collect_template_paths(actions: list[Action]) -> set[Path]: ...

def load_action_templates(
    actions: list[Action],
) -> dict[Path, np.ndarray]: ...
```

Runner khi đó chỉ cần:

```python
templates = load_action_templates(actions)
```

## 2. `execute_clear_blockers_action()` — action adapter nằm trong runner

### Nó đang làm gì?

Nhận `ClearBlockersAction`, unpack toàn bộ configuration rồi delegate sang `clear_blockers()`:

- Blocker paths.
- Until-template path.
- Threshold.
- Timeout và polling interval.
- Click delay và click positions.
- Stop event và template scales.

Business behavior chính nằm trong `control_events/blockers.py`; function này là adapter từ action model sang API đó.

### Issue còn tồn tại

Đây là action execution concern. Nó không tham gia điều khiển loop, retry hay sequence nhưng vẫn nằm trong runner.

### Breakdown đề xuất

Chuyển function sang `actions/executor.py`. Giữ adapter này giúp `control_events/blockers.py` không cần phụ thuộc trực tiếp vào `ClearBlockersAction`.

## 3. `execute_click_template_action()` — execution behavior lớn nhất vẫn nằm trong runner

### Nó đang làm gì?

Function này chịu trách nhiệm toàn bộ lifecycle của `ClickTemplateAction`:

1. Chuẩn bị template chính, skip-template và repeat delay.
2. Gọi `wait_for_template()`.
3. Xử lý `MATCHED`, `ALTERNATIVE_MATCHED` và `STOPPED`.
4. Delay trước click.
5. Click một hoặc nhiều lần.
6. Tùy chọn capture và recheck template trước repeat click.
7. Cập nhật tọa độ click nếu template dịch chuyển.
8. Dừng repeat clicks nếu template biến mất.

Return contract:

- `True`: action hoàn thành hoặc được skip hợp lệ.
- `False`: flow bị stop.
- `TimeoutError`: không tìm thấy template trong timeout.

### Issue còn tồn tại

Đây là browser execution behavior, không phải runner orchestration. Function cũng là phần lớn nhất trong file và kéo các dependency sau vào runner:

- Mouse control.
- Screenshot capture.
- Template matching và detection.
- NumPy template cache.
- Repeat-click policy.

### Breakdown đề xuất

Chuyển sang `actions/executor.py`.

Nếu cần giảm độ dài bên trong executor, có thể extract helper cho repeat click:

```python
async def click_template_repeatedly(...): ...
```

Không cần tạo thêm file riêng cho helper này.

## 4. `execute_action()` — dispatcher và side effects nằm trong runner

### Nó đang làm gì?

Tạo action label rồi dispatch theo runtime type:

```text
ClickAction          → log và click trực tiếp
ClearBlockersAction  → execute_clear_blockers_action()
ClickTemplateAction  → execute_click_template_action()
WaitAction           → wait_with_countdown() trực tiếp
```

Nếu gặp action type không được hỗ trợ, function raise `TypeError`.

### Issue còn tồn tại

Runner đang biết chi tiết thực thi của mọi action type. Thêm action mới yêu cầu sửa dispatcher trong runner, đồng thời có thể phải thêm dependency browser/vision mới vào cùng file.

`ClickAction` và `WaitAction` đủ nhỏ để xử lý inline trong dispatcher; không cần tạo wrapper function riêng. Issue nằm ở vị trí của dispatcher, không phải số lượng handler.

### Breakdown đề xuất

Chuyển dispatcher cùng các action handlers sang `actions/executor.py`:

```python
async def execute_action(
    page,
    action,
    templates,
    loop_index,
    action_index,
    stop_event,
) -> bool: ...
```

Chưa cần handler registry hoặc visitor. Với bốn action types, `isinstance` explicit vẫn dễ đọc và debug.

## 5. `log_action_timeout()` — tên và return contract chưa phản ánh behavior

### Nó đang làm gì?

Function này:

- Log timeout count.
- Raise lại `TimeoutError` khi timeout count đạt 2.
- Log finite loop đã hết retry hay loop tiếp theo sẽ retry.
- Luôn trả `True` nếu không raise.

Giá trị `True` được gán vào `loop_timed_out`.

### Issue còn tồn tại

Tên `log_action_timeout()` cho thấy đây là logging helper, nhưng function còn áp dụng retry policy và có thể raise exception.

Return value cũng không mang thông tin quyết định vì mọi non-error path đều trả `True`.

### Breakdown đề xuất

Giữ timeout policy trong `runner.py`, nhưng đổi tên thành `handle_action_timeout()`.

Có thể bỏ return value:

```python
handle_action_timeout(...)
loop_timed_out = True
```

Nếu policy phát triển thêm nhiều outcome, dùng enum như `RetryDecision` thay vì boolean.

Chưa cần tách `actions/retry.py` với policy hiện tại.

## 6. `run_actions()` — orchestration đúng role nhưng đang làm thêm resource setup

### Nó đang làm gì?

`run_actions()` hiện chịu trách nhiệm:

1. Collect và preload templates.
2. Quản lý số loop.
3. Kiểm tra cooperative stop/pause.
4. Chạy tuần tự từng action.
5. Bỏ phần còn lại của loop khi action timeout.
6. Retry từ action đầu ở loop kế tiếp.
7. Raise ở timeout lần hai.
8. Reset timeout count sau một loop thành công.
9. Dừng sau lần thành công đầu nếu `stop_after_success=True`.

### Issue còn tồn tại

Phần loop, stop và retry đúng là trách nhiệm của runner. Phần collect/load template nên được chuyển sang resource layer.

Sau khi tách resource preparation và action execution, `run_actions()` chỉ nên phối hợp hai dependency đó và giữ nguyên behavior hiện tại.

## Target breakdown

```text
actions/resources.py
    collect_template_paths()
    load_action_templates()

actions/executor.py
    execute_action()
    execute_clear_blockers_action()
    execute_click_template_action()

actions/runner.py
    action_label()
    handle_action_timeout()
    run_actions()
```

Dependency direction:

```text
runner
├── resources
└── executor
    ├── core.template_detection
    ├── core.template_matching
    ├── core.mouse
    ├── core.runtime
    └── control_events.blockers
```

Sau breakdown, `runner.py` chỉ còn sequence, loop, stop và retry policy.
