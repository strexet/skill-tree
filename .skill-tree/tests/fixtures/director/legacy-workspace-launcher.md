---
name: skill-tree-director
description: Open Director Setup to connect an existing project, create a new project, or inspect the coordinator.
---

# Skill Tree Director

Run commands from this workspace. Ask whether to connect an existing project, create a new one or continue later.
For an existing project, ask for its folder. For a new project, ask for a name and offer the named folder in the workspace, or a custom location.
Use a portable lowercase project name. Pass a JSON request containing kind (existing or new), name, optional path and optional flavor.
Run the following read-only command with the request. Show the proposed path, profile and hosts. Once the user chooses the project, run project-setup with the same input.

```sh
python3 ".skill-tree-director/.agents/skills/skill-tree-director-setup/scripts/director-entry.py" project-preview .skill-tree-director --input <request.json>
```

To check the available actions, run project-menu in place of project-preview and omit --input.
