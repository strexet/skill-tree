# Build and Release

The source package is private and declares version 0.3.0. `package.json` and `.skill-tree/config/flavors.json` carry matching release versions. The composer records the source release in installed profiles.

`python3 .skill-tree/scripts/sync-skill-references.py` regenerates representative packages from canonical inputs. The [testing policy](testing.md) owns local qualification boundaries. [Installation](install.md) owns project-scoped installation and local-manager commands.

There is no application bundle or hosted service in the source package. Shell wrappers dispatch to the Node installer. Source qualification uses static checks and temporary Git/project fixtures.

Version changes, commits, publication, push, tags and external PR operations require applicable explicit developer scope. Local checks supply no publication authorization. [PR review cycle](../common/references/pr-review-cycle.md) owns provider-confirmed readiness and merge evidence.
