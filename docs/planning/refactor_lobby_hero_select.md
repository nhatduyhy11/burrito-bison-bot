# Refactor lobby và hero-select — phần còn lại

## Bối cảnh

Refactor chính đã nằm trong code: `flows/hero_select/` là implementation
chung duy nhất (constants + `find_battle_button`); wrapper
`actions/hero_select_battle.py` (lobby_map, giữ recovery) và
`train_support/entry.py::wait_and_click_hero_select_battle` (lobby_train)
cùng delegate vào đó. Action type `click_hero_select_battle` giữ nguyên,
wiring ba consumer không đổi.

```text
lobby_map   ──┐
              ├──> flows/hero_select (chung) ──> battle/auto (map)
              │         │
              │         └─(chỉ train)──> train_select ──> auto_train
lobby_train ──┘
```

## Issue còn tồn

### 1. Đổi tên `tests/hero_select/` -> `tests/hero_levelup/`

Thư mục test này (8 file: hero vision, action, flow adapter, integration,
choice policy, train_select) thực chất test level-up picker giữa trận —
tên đang trùng với phase hero-select screen, gây nhầm với
`tests/flows/test_hero_select.py`.

### 2. (Tùy chọn) Đổi tên `train_support/hero_selection.py` ->
`train_support/card_selection.py`

Cùng lý do: đây là chọn 2/4 card × 5 round của train_select, không phải
chọn hero trên màn hero-select.

## Nguyên tắc

- Chỉ thêm/đổi tên test và module; không đổi behavior runtime.
- Mỗi commit chạy được độc lập và giữ test suite xanh.

## Điều kiện hoàn thành

- Không còn thư mục/file tên trùng với phase hero-select screen.
