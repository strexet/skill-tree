# Ridge Pack verification

Executed on 10 November 2026 on macOS arm64 with .NET SDK 8.0.125. The downloaded official macOS release archive matched SHA-256 `200aae0b4471b38142465559a0640baf143e87fc9a236c68d08e1adde48053cf`. The test used the archive's compiler and bundled `ink-engine-runtime.dll`. [Inkle release v1.2.1](https://github.com/inkle/ink/releases/tag/v1.2.1)

Tested source `quest.ink` SHA-256 `9a5a0c91945f138ba56faf4adfd04d02cdd60d96f4167ccd0c09c84c0daf7213`.

```text
PASS official Ink compilation without diagnostics
Build succeeded.
    0 Warning(s)
    0 Error(s)
PASS discovery and lift rescue
PASS optional discovery skipped and clinic supply preserved
PASS failed heater and pack isolation
PASS same-build save, restore and repeated ledger visit
```

The automated check asserts the exact available choices, the payoff text on discovery, distinct outcome text, the relevant flags after each outcome, and a ledger count of one after two visits following restoration. The first exploratory run exposed the once-only marker on the revisit choice. The repeatable marker now matches the narrative contract.

A separate smoke run piped choices 1, 1 and 2 through official `inklecate -p quest.ink`. The relay log appeared, the rescue played, and the story ended after the logbook closed.

The results cover one compiled build and an external standalone story runtime. Human playtesting, Unity integration and cross-build save compatibility have separate qualification requirements.
