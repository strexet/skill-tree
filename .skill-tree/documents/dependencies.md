# Dependencies

The source installer and composer require Node.js 18 or later and use Node built-in modules. Python helpers require Python 3.9 or later and use the Python standard library. `package.json` declares no runtime or development package dependencies.

Git is required for registered controller worktrees, repository identity, refs and local recovery fixtures. The optional GitHub CLI adapter uses `gh` for explicitly authorized provider operations; metadata-only review commands require no live provider request. Shell wrappers require the corresponding shell and Node runtime.

Installed target capabilities follow project-owned manifests, supported lockfiles and explicit validation recipes. Installation does not install dependencies or upgrade packages. Unity, browser and hosted tooling belong to the selected target and require matching qualification.

The [provider registry](../config/providers.json) owns discovery destinations and official references. The [capability registry](../config/capabilities.json) owns supported static formats. Provider entries remain configuration claims with separate runtime-qualification limits.
