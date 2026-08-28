# `actions/loader.py` audit

Các file được audit:

- `tools/hauntedroom/actions/loader.py`
- `tools/hauntedroom/actions/validation.py`
- `tools/hauntedroom/actions/models.py`
- `tests/actions/test_loader.py`

Tài liệu này chỉ ghi nhận các issue còn tồn tại trong code hiện tại.

## Current responsibility

Loader biến một JSON action document thành `list[Action]` đã được normalize:

```text
JSON file
→ kiểm tra root array và từng item object
→ dispatch theo `type`
→ parse và validate field
→ resolve asset path và rule liên-field
→ tạo typed Action model
```

`actions/validation.py` chứa các parser và field adapter dùng chung. Loader giữ
schema của từng action type, path resolution, blocker priority và public entry point
`load_actions(path)`.

## 1. Numeric coercion policy chưa rõ

### Hiện trạng

`parse_int()` chấp nhận `"10"` và `10.0`, nhưng từ chối `10.5` và boolean.
`parse_float()` cũng chấp nhận numeric string. DSL vì vậy đang dùng permissive
config parsing thay vì strict JSON typing.

Policy này chưa được mô tả thành contract rõ ràng và có thể khiến các field mới vô
tình nhận kiểu dữ liệu không mong muốn.

### Breakdown đề xuất

Chọn một policy thống nhất:

- Cho mọi numeric field nhận JSON number và numeric string; hoặc
- Chỉ nhận JSON number, kèm migration riêng nếu file cũ có numeric string.

Khóa quyết định bằng test cho integer, float, numeric string, fractional value và
boolean.

## 2. Non-finite float có thể lọt qua scales

### Hiện trạng

Python `json.load()` mặc định nhận `NaN` và `Infinity`; `parse_float()` không kiểm
tra `math.isfinite()`.

Threshold thường bị range check loại, nhưng scale `NaN` lọt qua vì
`NaN <= 0` là false; positive infinity cũng được xem là scale dương.

### Breakdown đề xuất

- Reject non-finite value trong numeric validation dùng cho config.
- Thêm test `NaN`, `Infinity` và `-Infinity` cho threshold và scales.
- Nếu giữ `parse_float()` generic, thể hiện finite policy bằng parameter hoặc một
  wrapper có tên rõ ràng.

## 3. `wait.ms` cho phép số âm

### Hiện trạng

`load_wait_action()` gọi `parse_int()` thay vì `load_non_negative_int()`. Test
`test_load_wait_preserves_negative_duration_behavior` đang khóa behavior nhận
negative wait.

Các timing field khác như `timeout_ms`, `poll_ms` và `delay_ms` đều không cho phép
số âm, nên contract của `wait.ms` đang không nhất quán.

### Breakdown đề xuất

- Xác nhận negative wait không có semantics chủ đích.
- Dùng non-negative validation cho `wait.ms`.
- Đổi test hiện tại thành assertion reject negative duration.

## 4. `note` chưa được validate

### Hiện trạng

Models khai báo `Optional[str]`, nhưng loader truyền thẳng `action.get("note")`.
Array, object hoặc number vẫn vào model và chỉ bị stringify khi runner tạo label.

Typed model vì vậy không phản ánh chắc chắn dữ liệu runtime thực tế.

### Breakdown đề xuất

Thêm một field adapter chỉ nhận:

- `str`;
- `null` hoặc field không tồn tại.

Các kiểu còn lại phải raise `ValueError` kèm action index và field name.

## 5. Unknown field bị bỏ qua

### Hiện trạng

Typo như `timeot_ms` không báo lỗi; loader âm thầm dùng `timeout_ms` mặc định. Với
DSL điều khiển automation, lỗi chỉ xuất hiện gián tiếp dưới dạng behavior runtime
khác mong đợi.

### Breakdown đề xuất

- Định nghĩa allowlist field theo từng action type.
- Reject key không thuộc allowlist với error chứa action index, action type và tên
  field.
- Thêm test typo cho mỗi schema có nhiều optional field, đặc biệt
  `click_template` và `clear_blockers`.

## 6. `clear_blockers.click_positions` mutate raw input

### Hiện trạng

Loader normalize từng click position rồi gán ngược vào dictionary lấy trực tiếp từ
JSON:

```python
click_positions[template_name] = load_click_position(click_position, index)
```

Flow hiện tại không reuse raw document nên chưa gây lỗi quan sát được, nhưng handler
không còn là pure transformation và khó tái sử dụng độc lập.

### Breakdown đề xuất

Build dictionary mới trong quá trình validation:

```python
normalized_click_positions = {
    name: load_click_position(value, index)
    for name, value in click_positions.items()
}
```

Model nhận dictionary mới; raw input không bị sửa.

## 7. Error model chưa thống nhất

### Hiện trạng

Validation chủ động dùng `ValueError`, còn file không tồn tại, permission error và
JSON syntax error giữ exception gốc. Error validation thường có action index nhưng
không có source file path.

Caller vì vậy khó hiển thị lỗi load theo một format thống nhất, nhất là khi có nhiều
action file.

### Breakdown đề xuất

Nếu action engine cần error boundary ổn định, thêm một error type nhỏ:

```python
class ActionLoadError(ValueError):
    ...
```

Error nên mang source path và location như action index/field. Giữ exception gốc
bằng `raise ... from error`; không cần custom exception hierarchy lớn.

## 8. `resolve_template_file` eager I/O check và coupling với filesystem

### Hiện trạng

`resolve_template_file()` thực hiện `(path.parent / raw_template).resolve()` và
ngay lập tức kiểm tra `template_path.is_file()`, tương tự `load_clear_blockers_action()`
kiểm tra `templates_dir_path.is_dir()`.

Việc eager check disk existence ngay trong bước parse JSON khiến parser phụ thuộc
chặt vào filesystem:
- Mọi unit test kiểm tra schema/numeric/bounds của loader đều bị buộc phải tạo dummy
  image files trên disk (`target.png.write_bytes(b"fixture")`), làm test cồng kềnh.
- Ở runtime, `actions/runner.py` và `template_matching.load_template()` đằng nào cũng
  đã kiểm tra và raise exception khi không đọc được file qua OpenCV (`OpenCV could not read template`).
- Logic ghép path lặp lại giữa `raw_template`, `skip_if_template`, `until_template`
  và `templates_dir_path`, đồng thời chưa xử lý tường minh trường hợp `raw_template`
  là absolute path.

### Breakdown đề xuất

- Tách path normalization thành helper thuần túy (chuẩn hóa relative/absolute path
  thành `Path` mà không assert `.is_file()`).
- Nếu cần xác thực sự tồn tại của asset trước khi chạy, thực hiện ở phase validation/preparation
  riêng biệt trước execution, hoặc để runtime loading handle tự nhiên.
- Dọn dẹp unit test của loader để test schema độc lập mà không cần tạo dummy file fixture.

## Thứ tự xử lý đề xuất

1. Reject non-finite number.
2. Reject negative `wait.ms`.
3. Validate `note`.
4. Không mutate `click_positions`.
5. Quyết định numeric coercion policy.
6. Tách path normalization khỏi eager filesystem check (`resolve_template_file`).
7. Reject unknown field.
8. Chuẩn hóa error boundary nếu caller cần error UX thống nhất.

Mỗi thay đổi strictness nên có test riêng vì có thể làm action file hiện tại không
còn hợp lệ.
