---
name: specs-location
description: Specs / planning docs đặt ở docs/planning/ — chỉ lưu issue còn tồn động, done thì remove, không dùng làm log/history
metadata:
  type: feedback
---

Spec và planning doc của project burrito-bison-bot đặt trong `docs/planning/`
(tên file giữ prefix ngày, ví dụ `2026-09-04-standby-orchestration-test-split-design.md`).

Nội dung planning doc chỉ ghi lại các **issue / việc còn tồn động (open items)** —
không phải log hay history của những gì đã hoàn thiện.

**Why:** User yêu cầu move specs vào "planning của proj" (2026-09-04); `docs/planning/`
là nơi project giữ handoff, research, TODO — version-controlled và visible cho team.
User xác nhận lại (2026-09-07): doc này để lưu issue còn tồn động, việc done thì
remove, chỉ snapshot issue khi lần đầu init scan / audit.

**How to apply:**
- Ghi spec/plan mới vào `docs/planning/` (prefix ngày).
- Việc nào đã hoàn thiện (done) thì remove khỏi doc — không giữ lại như log,
  không append dòng "đã xong".
- Chỉ liệt kê toàn bộ issue khi lần đầu init scan / audit; các lần cập nhật sau
  chỉ giữ lại phần còn mở.
