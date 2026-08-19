# `actions/runner.py` audit

File được audit: `tools/hauntedroom/actions/runner.py`

`runner.py` hiện có 11 function, cộng thêm một sentinel constant. Nội dung dưới đây liệt kê lần lượt từng thành phần, role hiện tại và khả năng tách sang file khác.

## 0. `SKIP_TEMPLATE_MATCHED`

Không phải function. Đây là sentinel để biểu diễn trường hợp template chính chưa xuất hiện, nhưng `skip_if_template` đã xuất hiện nên action được xem là không cần chạy nữa.

`wait_for_template()` có thể trả:

- `(x, y, score)` khi template chính match.
- `SKIP_TEMPLATE_MATCHED` khi skip-template match.
- `None` khi flow bị stop.
- Raise `TimeoutError` khi hết timeout.

Có thể tách cùng `wait_for_template()` sang `template_waiter.py`.

## 1. `wait_for_template()`

### Nó làm gì?

Function này liên tục chụp màn hình và tìm template cho đến khi xảy ra một trong bốn trường hợp:

1. Template chính đạt threshold: trả tọa độ và score.
2. Skip-template đạt threshold: trả `SKIP_TEMPLATE_MATCHED`.
3. Flow bị stop: trả `None`.
4. Hết timeout: lưu screenshot rồi raise `TimeoutError`.

### Luồng chi tiết

```text
flow checkpoint
→ capture screenshot grayscale
→ tìm template chính
→ nếu đủ threshold: return match
→ nếu có skip template: tìm skip template
→ nếu skip đủ threshold: return sentinel
→ nếu hết deadline: save screenshot + raise
→ chờ poll_ms
→ lặp lại
```

Nó còn:

- Tính deadline bằng `flow_time()` để thời gian pause không bị tính vào timeout.
- Theo dõi `best_score` để báo score tốt nhất khi timeout.
- Theo dõi `best_skip_score`.
- Hỗ trợ nhiều scale.
- Hỗ trợ giới hạn search region.
- Hỗ trợ các click position khác nhau.

### Có thể tách không?

Rất nên tách sang:

```text
actions/template_waiter.py
```

Không nên đưa thẳng vào `core/template.py`, vì function này không chỉ làm vision; nó còn biết flow control, polling, timeout screenshot và skip-action semantics.

## 2. `note_suffix()`

### Nó làm gì?

Format note dùng trong log:

```python
note_suffix(None)       # ""
note_suffix("buy gear") # " (buy gear)"
```

### Có thể tách không?

Có thể, nhưng function quá nhỏ nên không đáng tạo file riêng.

Các lựa chọn hợp lý:

- Giữ gần code logging.
- Chuyển logic trực tiếp vào `action_label()`.
- Chuyển sang `actions/logging.py` nếu sau này có nhiều helper format log.

Có thể đơn giản hóa thành:

```python
def action_label(loop_index, action_index, note):
    suffix = f" ({note})" if note else ""
    return f"{loop_index}.{action_index}{suffix}"
```

Sau đó xóa `note_suffix()`.

## 3. `action_label()`

### Nó làm gì?

Tạo label cho một action dựa trên:

- Số thứ tự loop.
- Số thứ tự action.
- Note tùy chọn.

Ví dụ:

```python
action_label(2, 3, None)
# "2.3"

action_label(2, 3, "open shop")
# "2.3 (open shop)"
```

Label này được dùng trong log và timeout screenshot.

### Có thể tách không?

Có thể chuyển cùng executor sang `actions/executor.py`, hoặc để trong runner nếu runner chịu trách nhiệm tạo execution context. Không đáng tạo file riêng chỉ cho function này.

## 4. `collect_template_paths()`

### Nó làm gì?

Duyệt toàn bộ action để thu thập các file template cần preload.

Với `ClickTemplateAction`, nó lấy:

- `template_path`.
- `skip_if_template_path`, nếu có.

Với `ClearBlockersAction`, nó lấy:

- Tất cả `blocker_paths`.
- `until_template_path`.

`ClickAction` và `WaitAction` không cần template nên bị bỏ qua. Function dùng `set[Path]` để tránh load trùng template.

Sau đó `run_actions()` dùng tập path này để load toàn bộ ảnh vào memory:

```python
templates = {path: load_template(path) for path in template_paths}
```

### Có thể tách không?

Nên tách vì đây là resource preparation, không phải loop orchestration:

```text
actions/resources.py
```

Có thể gom cả collect và load:

```python
def load_action_templates(actions: list[Action]) -> dict[Path, np.ndarray]:
    paths = collect_template_paths(actions)
    return {path: load_template(path) for path in paths}
```

Khi đó runner không cần biết `Path`, NumPy hay cách từng loại action tham chiếu template.

## 5. `execute_click_action()`

### Nó làm gì?

Thực thi `ClickAction` đơn giản:

1. Log tọa độ click.
2. Gọi `bot_click()`.
3. Trả `True`.

Nó không delay, recheck, template match hoặc kiểm tra stop event trực tiếp. Checkpoint đã được runner gọi trước khi execute action.

### Có thể tách không?

Có. Chuyển sang `actions/executor.py`. Đây là một action handler.

## 6. `execute_clear_blockers_action()`

### Nó làm gì?

Function này chủ yếu là adapter giữa `ClearBlockersAction` và function `clear_blockers()`.

Nó unpack các field từ action:

- Blocker paths.
- Until-template path.
- Threshold.
- Timeout và polling.
- Click delay.
- Click positions.
- Label.
- Stop event.
- Template scales.

Sau đó truyền toàn bộ vào `clear_blockers()`.

Business behavior thật nằm trong `tools/hauntedroom/control_events/blockers.py`. Function trong runner gần như không có logic riêng, chỉ chuyển object thành một danh sách argument dài.

### Có thể tách không?

Nên chuyển sang `actions/executor.py`.

Có thể giảm argument plumbing bằng cách đổi API thành nhận `ClearBlockersAction`, nhưng như vậy `control_events/blockers.py` sẽ phụ thuộc vào action model. Phương án trung lập là giữ adapter trong `executor.py`.

## 7. `execute_click_template_action()`

Đây là function lớn nhất và chứa phần lớn behavior của một `ClickTemplateAction`.

### Phase 1: Chuẩn bị

Nó lấy từ action:

- Template chính.
- Skip-template.
- Repeat delay.

Sau đó log rằng runner đang đợi template.

### Phase 2: Chờ template

Nó gọi `wait_for_template()` với:

- Template image đã preload.
- Threshold.
- Timeout.
- Poll interval.
- Stop event.
- Skip-template.
- Click position.
- Scale.
- Region.

### Phase 3: Xử lý kết quả

Nếu skip-template match:

- Log rằng step đã sẵn sàng.
- Không click.
- Trả `True`.

Nếu flow bị stop và nhận `None`:

- Trả `False`.

Nếu template chính match:

- Lấy `(x, y, score)`.
- Log vị trí, score và click configuration.

Nếu timeout:

- `wait_for_template()` raise exception.
- Function này không catch.
- Exception đi lên `run_actions()`.

### Phase 4: Click

Nó chạy từ `0` đến `click_count - 1`.

Trước mỗi click:

- Click đầu chờ `delay_ms`.
- Click sau chờ `repeat_delay_ms`.

Nếu flow stop trong lúc delay, function trả `False`.

### Phase 5: Recheck trước repeat click

Nếu đây không phải click đầu và `recheck_before_repeat=True`:

1. Chụp screenshot mới.
2. Tìm lại template.
3. Nếu template biến mất, log và bỏ các repeat click còn lại.
4. Nếu template vẫn còn, cập nhật tọa độ mới và log repeat click.

Cuối cùng gọi `bot_click()`.

### Output

- `True`: action hoàn thành hoặc được skip hợp lệ.
- `False`: flow bị stop.
- `TimeoutError`: không thấy template trong thời gian cho phép.

### Có thể tách không?

Rất nên chuyển sang `actions/executor.py`.

Nếu cần breakdown sâu hơn, có thể tách nội bộ thành:

```python
async def execute_click_template_action(...)
async def click_template_repeatedly(...)
def describe_repeat_policy(...)
```

Chưa cần tạo thêm file ngoài `executor.py`.

## 8. `execute_wait_action()`

### Nó làm gì?

Adapter cho `WaitAction`:

```python
return await wait_with_countdown(
    page,
    action.ms,
    label,
    stop_event,
)
```

`wait_with_countdown()` mới là nơi:

- Chia wait thành các step ngắn.
- In countdown nếu wait dài.
- Kiểm tra pause/stop giữa các step.

### Có thể tách không?

Chuyển sang `actions/executor.py` cùng các handler khác.

## 9. `execute_action()`

### Nó làm gì?

Đây là dispatcher.

Nó:

1. Tạo action label.
2. Kiểm tra runtime type của action.
3. Gọi đúng executor.

Mapping hiện tại:

```text
ClickAction          → execute_click_action
ClearBlockersAction  → execute_clear_blockers_action
ClickTemplateAction  → execute_click_template_action
WaitAction           → execute_wait_action
```

Nếu object không thuộc loại được hỗ trợ, nó raise `TypeError`.

### Role thật

Đây là entry point của action execution layer:

```text
Action model → action handler
```

### Có thể tách không?

Nên chuyển sang `actions/executor.py`.

Không cần đổi thành registry hoặc visitor ngay. Với bốn action types, `isinstance` rõ ràng và dễ debug.

## 10. `log_action_timeout()`

Tên function hơi thiếu vì nó không chỉ log; nó còn áp dụng timeout policy.

### Nó làm gì?

Đầu tiên log timeout count:

```text
timeout count=1/2
```

Nếu `timeout_count >= 2`:

- Log `Second timeout; stopping runner.`
- Raise lại `TimeoutError`.

Nếu đây là loop cuối:

- Log rằng không còn retry.
- Phần còn lại của action loop sẽ bị bỏ qua.

Nếu vẫn còn loop:

- Log rằng bỏ phần còn lại của loop hiện tại.
- Loop sau sẽ retry từ action đầu tiên.

Cuối cùng trả `True`, và giá trị này được gán vào `loop_timed_out`.

### Vấn đề về role

Function mang tên `log_...`, nhưng thực tế nó:

- Log.
- Kiểm tra retry limit.
- Quyết định dừng.
- Raise exception.
- Báo cho runner rằng loop bị timeout.

Đây là retry/error policy, không đơn thuần là logger.

### Có thể tách không?

Có hai lựa chọn:

- Giữ trong `runner.py`, vì retry policy đúng là trách nhiệm của runner.
- Tách thành `actions/retry.py` nếu policy sẽ phức tạp hơn.

Hiện tại nên giữ trong runner nhưng đổi tên, ví dụ `handle_action_timeout()`. Chưa cần một file riêng chỉ cho function này.

## 11. `run_actions()`

Đây là function runner chính.

### Phase 1: Preload resources

Nó:

1. Thu thập template paths từ actions.
2. Load toàn bộ template vào dictionary.

Template chỉ được load một lần trước các loop.

### Phase 2: Khởi tạo state

Nó quản lý:

- `timeout_count`: số timeout liên tiếp qua các loop.
- `loop_index`: loop hiện tại.
- `loop_count`: số loop tối đa, hoặc `None` để chạy vô hạn.

### Phase 3: Bắt đầu loop

Điều kiện:

```python
while loop_count is None or loop_index < loop_count:
```

Mỗi loop:

1. Kiểm tra flow checkpoint.
2. Tăng loop index.
3. Log loop start.
4. Reset `loop_timed_out=False`.

### Phase 4: Chạy từng action

Với mỗi action:

1. Kiểm tra flow checkpoint.
2. Tạo label.
3. Gọi `execute_action()`.

Nếu executor trả `False`:

- Xem như flow đã stop.
- Log idle.
- Return `False`.

Nếu executor raise `TimeoutError`:

- Tăng `timeout_count`.
- Gọi timeout handler.
- Break khỏi action loop.

Điểm quan trọng: timeout ở giữa sequence làm bỏ toàn bộ action còn lại, và lần retry sau bắt đầu lại từ action đầu tiên.

### Phase 5: Xử lý loop timeout

Nếu loop vừa timeout:

- Nếu đó là finite loop cuối: return `False`.
- Nếu còn retry: bắt đầu loop mới.

### Phase 6: Xử lý loop thành công

Nếu trước đó từng timeout nhưng loop hiện tại hoàn thành:

- Reset `timeout_count` về zero.

Sau đó:

- Log loop finish.
- Nếu `stop_after_success=True`: return `True`.
- Nếu không: chạy loop tiếp theo.

Khi đủ số loop, return `True`.

### Có thể tách không?

Function này nên ở lại `runner.py`, nhưng chỉ giữ orchestration.

Sau khi chuyển các phần khác đi, runner chỉ còn:

- Loop control.
- Sequence control.
- Stop handling.
- Timeout/retry policy.
- Success/failure result.

## Breakdown đề xuất

| Thành phần | File đề xuất |
|---|---|
| `wait_for_template`, sentinel/result | `actions/template_waiter.py` |
| `collect_template_paths`, load templates | `actions/resources.py` |
| Bốn action handlers | `actions/executor.py` |
| `execute_action` dispatch | `actions/executor.py` |
| `note_suffix`, `action_label` | Giữ gần executor hoặc execution context |
| `log_action_timeout` | Giữ trong `runner.py` |
| `run_actions` | Giữ trong `runner.py` |

Layout sau khi breakdown:

```text
runner.py
    run_actions()
    handle_action_timeout()
    action loop/retry policy

executor.py
    execute_action()
    execute_click_action()
    execute_click_template_action()
    execute_clear_blockers_action()
    execute_wait_action()

template_waiter.py
    wait_for_template()
    TemplateWaitResult

resources.py
    collect_template_paths()
    load_action_templates()
```

Đây là breakdown theo responsibility. `runner.py` lúc đó đúng nghĩa chỉ điều phối sequence và retry.
