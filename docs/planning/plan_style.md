---
name: plan-style-high-level
description: Planning docs stay high-level overview — no execution-level detail embedded; the implementing agent figures that out
metadata:
  type: feedback
---

Planning docs / plan reviews stay at the **high-level overview** level: target
architecture, layer boundaries, commit scope, principles. Do not embed
execution-level detail (explicit consumer/wiring lists, per-caller semantics
tables, edge-case handling, dev-reload mappings, per-file test updates).

**Why:** User (2026-09-29): "t đang muốn cái plan overview high-level chứ ko
đi vào detail chi tiết, các issue nếu là hệ quả khi execute thì bỏ qua, để
agent khi chạy tự figure out". Excessive detail makes the plan hard to read
and duplicates what the agent discovers on its own when the suite runs.

**How to apply:**
- When writing or reviewing a plan, only flag plan-level issues: a commit
  structure that contradicts itself, wrong boundaries, a scope gap covering
  a whole cluster — not execution-level consequences.
- Anything the agent catches itself when the suite runs (import errors,
  wiring, test updates) stays out of the plan.
- Keep behavior-preserving rules as general principles, not per-caller
  detail tables.

Related: [[specs-location]].
