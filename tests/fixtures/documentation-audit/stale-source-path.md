# Stale Source Path Fixture

Purpose: stale path case.

Repository state:

- `FEATURES.md` references `Assets/Scripts/Save/SaveManager.cs`.
- Current code moved save ownership to `Assets/Game/Runtime/Persistence/SaveService.cs`.
- Tests reference the new path.

Expected audit action:

- Update stale path references and record drift corrected.
