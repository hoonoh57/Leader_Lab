# Todo Update Rule v1

Date: 2026-05-13

`todo_list.md` is the operational source of truth.

## Rule

After successful local verification, update `todo_list.md` from the server side.

Local side should only run:

```text
git pull origin main
run script
git status
```

## Completed item format

```text
- [x] task name
  - files
  - verification script
  - observed result
  - next step
```

No completed work should remain only in chat.
