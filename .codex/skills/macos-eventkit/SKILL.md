---
name: macos-eventkit
description: Safe, performant EventKit/PyObjC patterns for Apple Reminders sync.
---

# macOS EventKit Integration

Use this skill when editing `flow/sync/` or any EventKit/PyObjC interaction.

## Safety Rules

- Check authorization before reading/writing reminders.
- Wrap PyObjC calls in `try/except Exception` with graceful fallback.
- Never allow crashes to propagate to the TUI.

## Data Mapping

- `EKReminder.title` -> `Item.title`
- `EKReminder.notes` -> `Item.description`
- `EKReminder.dueDate` -> `Item.due_date` (convert `NSDate` early)

## Concurrency

- EventKit fetch/write can be slow; run blocking calls off the main async loop:
  - `await asyncio.to_thread(...)` or worker thread APIs.

## Privacy and Integrity

- Avoid logging sensitive reminder content.
- Ensure sync flows are idempotent and avoid destructive operations on user data.
