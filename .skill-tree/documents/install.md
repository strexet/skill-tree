# Installation

Local installation requires Node.js 18 or later. Deterministic workflow helpers require Python 3.9 or later and the standard library.

```sh
node .skill-tree/bin/install.js --list
node .skill-tree/bin/install.js --dry-run --all
node .skill-tree/bin/install.js --only codex --project --copy --skills skill-tree-work-through-next
```

The local installer supports provider selection, copy/symlink, project/global destinations, explicit upstream sources, optional bridges, verification and scoped uninstall. Provider paths and support tiers reside in .skill-tree/config/providers.json. Dry-run performs no installation. Reinstallation and target documentation setup are explicit operations. No automatic metadata conversion is supported.
