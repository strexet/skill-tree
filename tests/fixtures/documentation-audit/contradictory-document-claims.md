# Contradictory Document Claims Fixture

Purpose: contradictory document claims case.

Repository state:

- `TECHNICAL.md` says networking uses REST polling.
- `FEATURES.md` says networking uses WebSockets.
- Current code contains only `UnityWebRequest` REST calls.

Expected audit action:

- Correct unsupported WebSocket claim or mark it unverified based on evidence.
