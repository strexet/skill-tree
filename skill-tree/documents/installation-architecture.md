# Installation Architecture

Canonical packages reside in skill-tree/skills/. Shared standalone resources are generated from skill-tree/common/ according to config/resource-map.json. Local installer code resides in skill-tree/bin/install.js; root shell launchers invoke the current installer. Source selection accepts the repository root or skill-tree directory. Installed packages require no sibling/source access.

The provider matrix owns detection, profiles, destination paths, tiers and bridges. Soft providers require explicit selection. Copy/symlink preserves unrelated skills unless an explicit force operation permits replacement of the selected package. Optional bridges replace only the marked block, with backup. Uninstall removes only selected packages and owned bridge blocks. Installation never executes bundled helpers. Remote/upstream operations require an explicitly configured source. Tests use temporary destinations; no live provider changes occur during source verification.
