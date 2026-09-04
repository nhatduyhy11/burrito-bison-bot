# Audit & Kế hoạch Chuẩn hóa Mouse Click

Audit date: 2026-09-03
Trạng thái: **Draft đã review — chưa phải kế hoạch migration hàng loạt**

---

## 1. Kết luận

Code click hiện tại phần lớn đang hoạt động tốt và mỗi custom loop có thể mang semantics khác nhau. Việc gom toàn bộ về một helper chung sẽ tạo phạm vi regression lớn, buộc phải test lại nhiều flow vốn không có nhu cầu thay đổi.

Quyết định hiện tại:

- **Giữ nguyên các custom loop cũ đang hoạt động ổn.**
- Có thể xây utility retry mới để dùng cho **code mới**.
- Chỉ refactor code cũ khi đang sửa bug, thay đổi tính năng hoặc đã có characterization test đủ mạnh.
- Không đặt mục tiêu xóa toàn bộ custom loop hoặc bắt mọi click phải dùng chung một helper.

> [!WARNING]
> Migration phải được thực hiện theo hướng **opportunistic refactoring**: chỉ migrate một flow cũ khi flow đó đang được sửa vì một lý do thực tế và utility mới phù hợp tự nhiên. Không mở chiến dịch refactor hàng loạt chỉ để đồng nhất hình thức code.

---

## 2. Finding sau review

### 2.1. Post-check không phải tiêu chí phân loại duy nhất

Câu hỏi "sau click có post-check hay không" vẫn hữu ích, nhưng không đủ để quyết định một loop có thể dùng helper chung hay không. Trước khi migrate cần xét thêm:

1. Target cố định hay phải detect lại trên mỗi frame.
2. Action có idempotent hay là toggle/có side effect nguy hiểm.
3. Flow chỉ có một transition hay có nhiều intermediate state/action.
4. Retry được giới hạn bằng timeout, số attempt hay cố ý chờ vô hạn.
5. Thứ tự hiện tại là check-first hay click-first.
6. Failure phải trả `False`, `None`, raise exception hay chạy soft recovery.
7. Capture dùng BGR, grayscale hay detector/screen classifier riêng.
8. Timing giữa các action có phải business behavior cần giữ nguyên hay không.

False predicate không đồng nghĩa với click bị drop. Nó cũng có thể do animation, detector false-negative, target đã di chuyển hoặc flow đang ở một màn hình khác. Vì vậy không được mặc định rằng `predicate(frame) == False` thì luôn an toàn để click lại.

### 2.2. Abstraction `click_until` cũ quá hẹp

Mẫu cũ hard-code `click_pos` và `capture_page_bgr`, nên không hỗ trợ tự nhiên:

- target động phải detect lại;
- grayscale capture;
- chuỗi nhiều action;
- max attempts;
- soft recovery;
- trạng thái success/stopped/timeout riêng biệt.

Ngoài ra mẫu cũ còn có các vấn đề cần tránh:

- `label` được khai báo nhưng không dùng;
- `bool | Any` không tạo type contract hữu ích;
- `None` nhập nhằng giữa timeout, stopped và failure;
- luôn wait cả `settle_ms + poll_ms` dù không observe ở giữa;
- không quy định check-first hay click-first;
- không có exception policy hoặc timeout diagnostics;
- không bảo toàn compatibility Python 3.9 nếu dùng cú pháp union mới trong module không có postponed annotations.

### 2.3. Không đặt helper side-effect vào `template_matching.py`

`core/template_matching.py` nên tiếp tục là tầng matching thuần, không chứa mouse click hoặc flow orchestration. Nếu tạo utility mới, ưu tiên module riêng như `core/interaction.py` và cập nhật architecture test một cách có chủ đích.

---

## 3. Đánh giá lại các candidate cũ

| # | Flow | Kết luận sau review | Lý do |
|---|---|---|---|
| 1 | `train_support/exit_flow.py::wait_for_train_screen` | **Có thể cân nhắc sau** | Target cố định và condition đơn giản, nhưng loop hiện chờ vô hạn. Áp timeout mặc định sẽ đổi behavior. |
| 2 | `pet_and_ad.py::activate_middle_pet_and_summon` — mở pet menu | **Giữ custom loop** | Mở/đóng menu có tính toggle. Detector false-negative rồi click lại có thể đóng menu vừa mở. |
| 3 | `pet_and_ad.py::activate_middle_pet_and_summon` — summon/đóng menu | **Candidate phù hợp tương đối** | Fixed target và post-check rõ, nhưng phải giữ click-first và khoảng chờ 1000ms hiện tại. Không cần migrate khi flow chưa phải sửa. |
| 4 | `pet_and_ad.py::wait_and_dismiss_level_spin` | **Giữ custom loop** | Click position được detect lại trên từng frame, không phải fixed target. |
| 5 | `artifact.py::_open_artifact_popup` | **Candidate tốt nhất** | Transition đơn giản, nhưng phải giữ grayscale, click-first, delay và đúng giới hạn 4 attempts. |
| 6 | `diamond_collection.py::_collect_detail_popup` | **Giữ custom flow** | Phân loại cũ không chính xác: card được click ở caller; helper này xử lý reward, reserve clicks và close popup qua nhiều state/action. |
| 7 | `boss_action.py::deploy_boss_pet` | **Giữ custom flow** | Sau khi mở menu còn phải detect và click summon target động; không phải một transition đơn giản. |
| 8 | `gear_action.py::_soft_fail_initial_gear` | **Giữ custom recovery** | Có exception policy và cố ý tránh click lại khi không xác minh được trạng thái menu. |
| 9 | `map/first_win.py::handle_daily_first_win` | **Giữ custom state machine** | Detect label, checkbox unchecked/checked, toggle rồi confirm; target và action thay đổi theo state. |
| 10 | `new_account.py::run_new_account_flow` | **Giữ custom state machine** | Chỉ được click khi screen là `NEW_ACCOUNT`; screen lạ phải poll, không được click mù cho tới `AUTOMAP`. |

Trong danh sách trên, chỉ #3 và #5 gần với helper fixed-target. #1 có thể tham gia nếu xác định rõ timeout policy. Điều này **không tạo yêu cầu phải migrate chúng ngay**.

---

## 4. Định hướng utility cho code mới

Utility chung nên quản lý retry lifecycle, thay vì tự giả định mọi action là một click cố định:

```python
class RetryStatus(Enum):
    SUCCEEDED = auto()
    STOPPED = auto()
    EXHAUSTED = auto()


@dataclass(frozen=True)
class RetryPolicy:
    interval_ms: int
    timeout_ms: Optional[int] = None
    max_attempts: Optional[int] = None


async def retry_transition(
    page,
    *,
    observe,
    act,
    policy: RetryPolicy,
    stop_event=None,
):
    """Run an explicitly configured observe/action retry lifecycle."""
    ...
```

Utility chỉ nên chịu trách nhiệm cho:

- stop/pause checkpoint;
- timeout và/hoặc max attempts;
- thứ tự observe/action đã được contract quy định;
- cooperative wait;
- kết quả phân biệt success, stopped và exhausted.

Từng flow tiếp tục chịu trách nhiệm cho:

- capture BGR/grayscale;
- detector và target resolution;
- click, drag hoặc chuỗi nhiều action;
- business logging;
- recovery policy;
- quyết định action có an toàn để retry hay không.

Có thể cung cấp wrapper `click_until` nhỏ trên `retry_transition` cho code mới thật sự có fixed target và action idempotent. Wrapper này là opt-in, không phải architectural mandate.

---

## 5. Kế hoạch triển khai an toàn

### Phase 1 — Xây utility độc lập

- Tạo `core/interaction.py` hoặc vị trí tương đương sau khi xác nhận dependency boundary.
- Chốt contract về action-first/check-first, timeout, attempts, exception và result status.
- Viết unit test cho utility mà chưa migrate flow cũ.
- Dùng utility cho code mới có retry semantics phù hợp.

### Phase 2 — Refactor opportunistically

Chỉ xem xét migrate một flow cũ khi đồng thời thỏa mãn:

1. Flow đang cần sửa bug hoặc thay đổi tính năng.
2. Behavior hiện tại đã được ghi nhận bằng characterization test.
3. Utility mô tả flow tự nhiên, không cần nhiều flag/special case.
4. Có thể giữ nguyên timing, click count, retry limit và failure semantics.
5. Test liên quan chạy pass trước và sau migration.

Nếu phải làm utility phức tạp hơn custom loop hoặc phải thêm callback/flag chỉ để mô phỏng một flow duy nhất, giữ custom loop.

### Phase 3 — Đánh giá lại sau sử dụng thực tế

Sau khi utility đã được dùng trong một số code mới:

- kiểm tra API nào thực sự ổn định;
- tìm duplication thực tế thay vì duplication dự đoán;
- chỉ mở rộng helper khi có ít nhất vài use case cùng semantics;
- không đặt deadline xóa custom loops.

---

## 6. Test gate cho mọi migration sau này

Một migration chỉ được merge khi có test bao phủ tối thiểu:

- success trước action nếu contract cho phép check-first;
- success sau một hoặc nhiều retry;
- đúng max attempts hoặc timeout;
- stop và pause/resume;
- không click thêm sau success;
- bảo toàn exact delay/click count cần thiết;
- false-negative không gây toggle hoặc action nguy hiểm;
- exception/failure giữ đúng behavior cũ;
- architecture dependency test vẫn pass.

---

## 7. Decision record ngắn

```text
Code cũ đang ổn
    -> Giữ nguyên

Code mới có retry transition đơn giản
    -> Dùng utility mới nếu phù hợp

Flow cũ đang cần sửa
    -> Thêm characterization test
    -> Sửa vấn đề chính
    -> Chỉ migrate nếu helper giữ nguyên behavior một cách tự nhiên
```

Mục tiêu của utility là giảm duplication trong code mới và tạo một lựa chọn an toàn khi refactor có lý do, không phải chuẩn hóa cưỡng ép toàn bộ hệ thống click.
