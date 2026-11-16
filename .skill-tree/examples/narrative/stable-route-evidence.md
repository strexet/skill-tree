# Stable Ink Route Evidence

The owned standalone recipe used the pinned Ink compiler and runtime with a temporary local .NET build. The compiler and runtime checksums matched the documented release. The duplicate-choice control failed with the selected trace, beat and action in the diagnostic.

```text
PASS ridge-discover-lift
PASS ridge-discover-cooler
PASS ridge-discover-heater
PASS ridge-skip-lift
PASS ridge-skip-cooler
PASS ridge-skip-heater
PASS ridge-restore-repeat
PASS renamed label preserves identity
PASS duplicate active identity is diagnosed
```

The current evidence covers the standalone fixture and same-build save restore. Unity behavior and human interpretation require separate observations.
