# Stable Ink Handoff

Map work, quest, scene and action IDs to one authoritative source file and knot or stitch. Preserve exact dialogue in Ink. Narrative records describe intent, expected behavior and linked evidence. Mark optional or unmapped beats explicitly.

Use `choice-id: stable-id` in each displayed choice tag. A runtime test selects by the choice tag, validates the active identity set, and checks visible wording separately when a phrase matters. Multiple active choices with one ID or a choice without an ID fail with the exact context. Changing a label may preserve an action identity. A material change to the action can require a new identity and a reviewed mapping.

The standalone fixture checks fresh and same-build restored choices using the pinned official runtime. The runtime's choice clone path, cross-build saves, Unity host integration and human interpretation need separate evidence. [Official story runtime](https://raw.githubusercontent.com/inkle/ink/v1.2.1/ink-engine-runtime/Story.cs) · [Official save serialization](https://raw.githubusercontent.com/inkle/ink/v1.2.1/ink-engine-runtime/JsonSerialisation.cs)
