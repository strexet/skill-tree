# Generic Adapter

- Provider id: `generic`
- Tier: 3
- Install mechanism: explicit destination copy or symlink
- Automatic discovery: not claimed
- Last verified: 2026-06-10

Use for agents without a verified native profile:

```bash
node bin/install.js --only generic --target /path/to/agent/skills --copy
```

Manual install is also valid: copy selected `skills/skill-tree-<skill-name>/` folders into the agent's documented skill location.
