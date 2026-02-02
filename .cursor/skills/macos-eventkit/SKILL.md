---
name: macos-eventkit
description: Guidelines for MacOS EventKit and PyObjC integration for Apple Reminders sync. Use when working with flow/sync/ components, EKEventStore, EKReminder, pyobjc bindings, or Apple Reminders synchronization.
---

# MacOS EventKit Integration

Role: MacOS Integration Engineer

## Safety Rules

1. **Permissions**: Always check `EKEventStore.authorizationStatus` before access.
2. **Crash Prevention**: Wrap all `pyobjc` calls in `try/except Exception`. MacOS APIs are unforgiving.
3. **Data Mapping**:
   - `EKReminder.title` → `Item.title`
   - `EKReminder.notes` → `Item.description`
   - `EKReminder.dueDate` → `Item.due_date` (Convert `NSDate` to Python `datetime` immediately)

## Performance

- EventKit fetching is slow. Always run in a separate thread when called from TUI:

```python
await asyncio.to_thread(fetch_reminders, ...)
```

## Quick Reference

### Authorization Check

```python
from EventKit import EKEventStore, EKEntityTypeReminder, EKAuthorizationStatusAuthorized

store = EKEventStore.alloc().init()
status = EKEventStore.authorizationStatusForEntityType_(EKEntityTypeReminder)

if status != EKAuthorizationStatusAuthorized:
    # Request access or handle unauthorized state
    pass
```

### Safe PyObjC Call Pattern

```python
try:
    result = store.someEventKitMethod_()
except Exception as e:
    # Log and handle gracefully - never crash the app
    logger.error(f"EventKit error: {e}")
    return None
```

### NSDate Conversion

```python
from Foundation import NSDate
from datetime import datetime, timezone

def nsdate_to_datetime(nsdate: NSDate | None) -> datetime | None:
    if nsdate is None:
        return None
    timestamp = nsdate.timeIntervalSince1970()
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
```
