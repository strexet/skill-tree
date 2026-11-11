# Narrative record inventory

Use the `inventory` command to list exact identities in working records or one accepted snapshot. Select `--drafts` for the working tree or `--snapshot <digest>` for a known work pin. The helper returns a derived JSON projection in stable ID order.

- A working item includes the ID, kind, content revision, current Markdown and sidecar paths, and working status. The sidecar supplies the stable ID. Duplicate IDs and incomplete pairs stop the view.
- An accepted item includes the ID, kind, revision and archive path. The selected pin and recorded decision locator identify the accepted scope. A retired item has an ID and retirement status, while an earlier accepted snapshot can still show the prior revision.
- An absent or invalid pin produces an error. A work with an unresolved pin requires an explicit author decision before accepted inventory selection.

Regenerate the projection from the desired inputs. Keep author decisions, source prose and accepted snapshots in the owning files. No editable mirror or automatic promotion is required.
