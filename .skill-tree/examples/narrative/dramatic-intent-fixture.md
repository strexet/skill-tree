# Dramatic Intent Fixture

The synthetic harbor example links a warning from an optional relay log to a later pressure-latch scene. A public notice supplies the required action cue even if the log is skipped.

```json
{
  "id": "intent-latch-warning",
  "source": {"scene": "scene-relay-log", "beat": "beat-pressure-note"},
  "target": {"scene": "scene-selector", "beat": "beat-latch-choice"},
  "relation": "prepares",
  "method": "setup-payoff",
  "scope": {
    "work": "work-harbor-evacuation",
    "continuity": "continuity-harbor",
    "period": "evacuation-night",
    "routes": ["route-log"]
  },
  "coverage": "optional-enrichment",
  "function": "The note explains the pressure history behind a public latch warning.",
  "evidence": {
    "presentation": {"status": "specified", "route": "route-log"},
    "interpretation_choice": {"status": "not-observed"},
    "observed_understanding": {"status": "not-observed"}
  }
}
```

The selected route can skip the log. The required warning remains in `scene-public-notice` and no condition requires the log. A missing `beat-latch-choice` target leaves the link unresolved. A recorded presentation alone cannot support a claim of understanding. No method key is a normative dependency or a runtime gate.
