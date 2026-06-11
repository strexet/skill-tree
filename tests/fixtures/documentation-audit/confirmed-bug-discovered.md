# Confirmed Bug Discovered Fixture

Purpose: confirmed bug discovered during audit.

Repository state:

- `SaveService.Load()` catches parse errors and returns a default save without logging or backup.
- Existing tests cover valid saves only.
- `FEATURES.md` claims corrupt saves are recoverable with backup.

Expected audit action:

- Correct unsupported documentation claim.
- Add a confirmed bug backlog entry with evidence, affected symbol, impact, acceptance criteria, and focused tests.
