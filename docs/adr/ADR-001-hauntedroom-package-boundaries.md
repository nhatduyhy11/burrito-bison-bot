# ADR-001: Haunted Room package boundaries

## Status

Accepted.

Decision date: 2026-07-27.

Tài liệu này ghi lại quyết định tạo khung package Haunted Room ban đầu. Nó không
phải mô tả sống của source tree. Kiến trúc hiện hành nằm tại
[`ARCHITECTURE.md`](../ARCHITECTURE.md). Nếu framework/game boundary được chấp
nhận trong tương lai, một ADR mới sẽ supersede phần liên quan của quyết định này.

## Context

Các module từng nằm trực tiếp trong `hauntedroom/`, làm khó phân biệt capability
nền tảng, action execution, orchestration và business flow. `common.py` đồng thời
chứa CLI cùng nhiều runtime helper không chung responsibility. Dependency có thể
chưa cycle nhưng boundary và hướng mở rộng không rõ ràng.

## Decision

Tổ chức Haunted Room thành các vùng trách nhiệm:

- `core`: foundational capability không biết action engine hoặc business flow;
- `actions`: load, validate và thực thi action JSON;
- `flows`: Haunted Room business flows và support code theo feature;
- `runner`: nối command/hotkey với flow, navigation và dev reload;
- `control_events`: xử lý control/blocker có thể preempt normal flow;
- entrypoint: composition root cho CLI, browser và các dependency trên.

Dependency đi từ composition/orchestration xuống capability. `core` không import
`actions`, `flows`, `runner` hoặc entrypoint; `actions` không import `flows`; tầng
dưới không import ngược composition root. Composite dependency đặc biệt phải rõ
ràng thay vì biến mọi flow thành một dependency graph tự do.

Trong quyết định này, tên `core` chỉ có nghĩa là foundational module của
Haunted Room codebase. Nó không phải domain layer theo Clean Architecture và
không khẳng định module đó đã đủ generic để trở thành reusable framework.

## Consequences

Tích cực:

- Trách nhiệm và dependency direction dễ nhận biết hơn.
- Business flow mới không buộc action engine hoặc capability nền tảng biết về nó.
- Validation của action không rò vào vision primitive.
- Có boundary đủ rõ để viết architecture tests và làm migration seam sau này.

Trade-off:

- Import path dài hơn.
- Một số application/game coupling vẫn tồn tại trong package có tên `core`,
  `runner`, `actions` và `control_events`.
- Boundary này phục vụ một game nên chưa chứng minh được framework contract.
- Khi package tree và runtime wiring thay đổi, tài liệu kiến trúc hiện hành phải
  cập nhật; ADR này vẫn giữ nguyên như record của quyết định ban đầu.

## Follow-up

Ý tưởng tách reusable automation framework được theo dõi riêng tại
[`FRAMEWORK_EXTRACTION_HANDOVER.md`](../planning/FRAMEWORK_EXTRACTION_HANDOVER.md).
Backlog đó chưa supersede ADR này cho tới khi một framework/game boundary cụ thể
được chấp nhận trong ADR mới.
