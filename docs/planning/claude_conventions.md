---
name: specs-location
description: Specs / planning docs cho project này nằm ở docs/planning/, không dùng docs/superpowers/specs/
metadata:
  type: feedback
---

Spec và planning doc của project burrito-bison-bot đặt trong `docs/planning/`
(tên file giữ prefix ngày, ví dụ `2026-09-04-standby-orchestration-test-split-design.md`),
không dùng thư mục mặc định `docs/superpowers/specs/` của superpowers skill.

**Why:** User yêu cầu move specs vào "planning của proj" (2026-09-04); `docs/planning/`
là nơi project đã giữ handoff, research, TODO — version-controlled và visible cho team.

**How to apply:** Khi superpowers skill (brainstorming/writing-plans) muốn ghi spec vào
`docs/superpowers/specs/`, ghi vào `docs/planning/` thay thế. User preference overrides
skill default.
