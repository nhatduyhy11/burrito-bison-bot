# Audit `runner/commands.py`

Các file được đối chiếu:

- `tools/hauntedroom/runner/commands.py` (405 dòng - đối tượng audit chính)
- `tools/hauntedroom/runner/default_commands.py` (30 dòng - registration/mapping)
- `tools/hauntedroom/runner/reload.py` (226 dòng - hot-reload provider)
- `tests/runner/test_commands.py` (156 dòng - command policy/behavior tests)
- `tests/runner/test_start_automap_loop.py` (có test trực tiếp các action builder)
- `tests/runner/test_standby_orchestration.py` (consumer của `FlowCommand` và `ResolvedFlow`)
- `docs/ARCHITECTURE.md` (boundary hiện hành)

## Kết luận ngắn

`commands.py` có vấn đề về **cohesion và readability**, nhưng audit cũ đã đánh giá
quá nặng thành vi phạm kiến trúc và đề xuất breakdown quá sớm.

Hướng phù hợp là refactor tăng dần:

1. giảm duplication rõ ràng ngay trong `commands.py`;
2. giữ model/type nhỏ tại chỗ;
3. chỉ tách một khối khi khối đó có trách nhiệm rõ và đủ lớn để đứng thành module;
4. không đặt mục tiêu ép `commands.py` xuống 60-80 dòng.

Target là file dễ đọc và có lý do thay đổi tương đối rõ, không phải số dòng thấp
nhất hay mỗi abstraction một file.

## 1. Vì sao `test_commands.py` ngắn hơn `commands.py`?

So sánh riêng 156 dòng test với 405 dòng production không đủ để kết luận
`commands.py` là "God Factory".

Coverage liên quan đến command đang được phân tán theo consumer:

- `test_commands.py` kiểm tra registry metadata và behavior của một số resolver;
- `test_start_automap_loop.py` kiểm tra `build_start_battle_actions()` và
  `build_spawn_exit_lvup_actions()`;
- `test_standby_orchestration.py` dùng trực tiếp `FlowCommand` và `ResolvedFlow`
  để kiểm tra dispatch/lifecycle.

Tuy vậy, `test_commands.py` hiện mới kiểm tra execution chi tiết cho
`newbie_block`, `json_actions` và `spawn_exit_lvup`. Các resolver leaf và
stateful chủ yếu được bảo vệ gián tiếp, nên có **coverage gap** trước khi refactor.
Đây là vấn đề thiếu characterization test, không phải bằng chứng tự thân rằng
production file vi phạm SRP.

## 2. Đánh giá lại từng issue

| Nhận định cũ | Verdict | Đánh giá sau khi đối chiếu code |
| :--- | :--- | :--- |
| `commands.py` vi phạm boundary của `runner` | **Không đúng** | `ARCHITECTURE.md` mô tả `runner/commands.py` là command spec/factory và cho phép `runner -> actions / flows / screen_detect / control_events / core`. Registration và reload policy hiện còn game-specific cũng được ghi nhận là kiến trúc hiện hành. |
| File có cohesion thấp vì trộn action builder, command model, resolver và registry | **Đúng một phần** | Có nhiều nhóm code trong một file và action builder làm registry khó scan. Đây là lý do hợp lệ để refactor dần, nhưng chưa đủ để gọi là "God Factory" hay boundary violation. |
| 5 simple leaf resolver lặp cùng một shape | **Đúng** | `research`, `artifact`, `diamond_collection`, `exp_available`, `hero_up_available` chỉ khác flow getter. Đây là duplication rõ nhất và là nơi nên xử lý đầu tiên. |
| 4 stateful resolver lặp cùng một implementation | **Phóng đại** | Cả 4 đều tạo `MapRunState`, nhưng `automap`, `start_auto`, `train` và `new_account` có dependency và call signature khác nhau. Chỉ `train` và `new_account` gần như cùng shape; `start_auto` là composite flow riêng. |
| 3 action-runner resolver lặp cùng một implementation | **Đúng một phần** | `newbie_block` và `spawn_exit_lvup` có thể chia sẻ một helper nhỏ. `json_actions` còn validate path, lazy-load JSON và không có `loop_label`, nên không nên ép chung nếu helper trở nên nhiều option. |
| Closure lồng nhau khiến không thể unit test resolver riêng | **Không đúng** | Resolver vẫn test trực tiếp được qua `FLOW_DEFINITIONS[key].resolve(...)` hoặc qua command table, như test hiện tại đang làm. Điểm bất tiện thật là phải lấy command từ factory/table và inject một provider đủ API. |
| Cần tách ngay `models.py`, `resolvers.py`, `actions/macros.py` | **Không nên làm ngay** | `models.py` chỉ khoảng 16-20 dòng và sẽ thành file quá nhỏ; generic `resolvers.py` dễ biến behavior cụ thể thành higher-order abstraction khó đọc; đặt macro game-specific trong `actions` làm mờ vai trò generic action engine. |
| `commands.py` phải còn khoảng 60-80 dòng | **Không có cơ sở** | Line count không phải architecture target. Registry 12 command tự nó đã cần nhiều dòng nếu ưu tiên explicitness. Khoảng 200-300 dòng nhưng cohesive/readable vẫn tốt hơn 60 dòng phụ thuộc nhiều abstraction nhỏ. |

## 3. Vấn đề thực sự nên giữ lại

### 3.1. Registry khó scan

Muốn hiểu một command, người đọc phải đi qua resolver closure ở nửa trên rồi tìm
metadata tương ứng ở dictionary cuối file. Action builder ở đầu file làm khoảng
cách này dài hơn.

Đây là vấn đề readability chính. Có thể cải thiện mà chưa cần chia thành nhiều
module.

### 3.2. Duplication ở leaf resolver

Năm leaf resolver có cùng contract:

```python
flow = flow_getter(dev_reload)

async def run(page, stop_event, _debug):
    return await flow(page, stop_event)

return ResolvedFlow(actions, run)
```

Một helper private ngay trong `commands.py` là đủ. Chưa cần tạo
`runner/resolvers.py` chỉ để chứa helper này.

### 3.3. Coverage chưa cân đối với rủi ro refactor

Hot reload được resolve tại thời điểm gọi `command.resolve(...)`, không phải lúc
build registry. Refactor helper phải giữ nguyên property này. Trước khi gom code,
nên khóa behavior cho:

- một leaf flow với `dev_reload=True/False`;
- `automap`, `train`, `new_account` tạo `MapRunState` mới cho mỗi lần `run`;
- `start_auto` truyền đúng `start_actions`, automap flow và action runner;
- `json_actions` vẫn lazy-load theo path mỗi lần resolve.

### 3.4. Action builder là candidate tách hợp lý, nhưng chưa bắt buộc ở phase đầu

Ba builder và asset constants chiếm khoảng 80 dòng, có test/consumer riêng và
không phải metadata registry. Nếu sau cleanup `commands.py` vẫn khó đọc, đây là
khối đầu tiên đủ lớn để tách.

Không nên đặt trong `hauntedroom.actions` vì package đó đang sở hữu model,
loader và executor generic; các sequence này mang policy Haunted Room. Vị trí ít
xáo trộn boundary hiện tại nhất là một module game-specific trong `runner`, ví dụ
`runner/command_actions.py`. Tên/vị trí cuối cùng nên được quyết định khi thực sự
tách, dựa trên hướng framework extraction lúc đó.

## 4. Roadmap breakdown tăng dần

### Phase 0 - Characterization tests, không đổi structure

Bổ sung test cho các contract có nguy cơ bị thay đổi khi gom resolver:

1. leaf flow resolve đúng getter và forward `(page, stop_event)`;
2. stateful flow không reuse `MapRunState` giữa hai lần chạy;
3. `start_auto` giữ đúng dependency wiring;
4. hot reload getter chỉ được gọi khi resolve command.

Không cần tạo file test mới nếu các test vẫn vừa với `test_commands.py`.

### Phase 1 - Giảm duplication ngay trong `commands.py`

Thêm một helper private cho 5 leaf flow và thay 5 resolver giống nhau bằng helper
đó. Có thể cân nhắc helper thứ hai chỉ cho `train`/`new_account` nếu signature thực
sự giữ ổn định sau test.

Không tạo generic helper cho mọi stateful/action flow. Nếu helper cần nhiều flag
như `uses_runtime`, `loop_label`, `load_path`, `start_actions`, đó là dấu hiệu các
flow không cùng abstraction.

Kết quả kỳ vọng của phase này:

- giảm khoảng 40-60 dòng duplication;
- behavior và import path không đổi;
- chưa có module mới;
- registry vẫn explicit.

### Phase 2 - Tách action builders nếu file vẫn khó đọc

Chỉ tách nguyên khối sau vào **một** module:

- `ROOMS_DIR`, `BLOCKER_PRIORITY`, `build_blocker_paths()`;
- `build_start_battle_actions()`;
- `build_spawn_exit_lvup_actions()`;
- `build_newbie_block_actions()`.

Khối này khoảng 80 dòng, có cohesion và test riêng nên không tạo file vụn. Cập
nhật import trong `test_start_automap_loop.py` và giữ test behavior hiện tại.

Sau phase này, đánh giá lại trước khi tách tiếp. Không mặc định phải có phase 3.

### Phase 3 - Chỉ split resolver/registry khi có thêm evidence

Chỉ cân nhắc tách khi một trong các điều kiện sau xuất hiện:

- số command/resolver tiếp tục tăng đáng kể;
- resolver logic thay đổi độc lập thường xuyên với registry metadata;
- nhiều consumer cần import model mà không nên kéo theo command construction;
- file vẫn khó navigate sau phase 1 và 2.

Nếu cần split, ưu tiên hai module có kích thước/cohesion đủ rõ, ví dụ:

```text
runner/
├── command_actions.py   # action sequences game-specific (~80 dòng)
├── commands.py          # model + resolver wiring
└── default_commands.py  # concrete registration/screen mapping
```

Chưa nên tạo riêng `models.py` cho hai dataclass nhỏ. Cũng chưa nên tạo
`resolvers.py` chỉ để đạt mục tiêu line count.

## 5. Target sau mỗi phase

| Khía cạnh | Hiện tại | Sau phase 1 | Sau phase 2 (nếu cần) |
| :--- | :--- | :--- | :--- |
| Module mới | 0 | 0 | 1 module đủ lớn |
| Duplication leaf resolver | 5 implementation gần giống | 1 helper private | Giữ như phase 1 |
| Action builder trong registry file | Có | Có | Không |
| Model/type file riêng | Không | Không | Không |
| Mục tiêu line count | 405 | Không ép cứng | Không ép cứng |
| Tiêu chí dừng | - | File đã dễ scan hơn | Dừng nếu mỗi file đã cohesive |

## 6. Kiểm thử và chống regression

Chạy baseline trước và sau mỗi phase:

```shell
uv run --with pytest pytest -q
```

Ít nhất cần chạy nhóm liên quan trong vòng lặp ngắn:

```shell
uv run --with pytest pytest -q tests/runner/test_commands.py tests/runner/test_start_automap_loop.py tests/runner/test_standby_orchestration.py tests/test_hauntedroom_architecture.py
```

Các invariant cần giữ:

- `FLOW_COMMANDS` và `SCREEN_FLOW_COMMANDS` không đổi key/metadata/behavior;
- getter reload vẫn được resolve theo `dev_reload` tại thời điểm bắt đầu flow;
- mỗi run stateful có `MapRunState` riêng;
- action order, loop count và stop event không đổi;
- không đưa policy Haunted Room vào generic action engine chỉ để giảm line count.
