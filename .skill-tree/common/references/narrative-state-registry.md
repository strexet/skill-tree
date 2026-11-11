# Narrative State Registry

Register each state key before adding a trace. Use one owner per value. Define allowed writers and readers, scope, initialization, persistence, missing-value policy and save version.

| Field | Contract |
| --- | --- |
| Stable key and type | Boolean, enumerated string or bounded integer with explicit allowed values. |
| Owner | The only component that can commit a value. Other components request writes and observe acknowledgements. |
| Scope | Session, playthrough or persistent save. Record the earliest valid read. |
| Default and missing value | State a fresh initial value separately from an absent saved value. The model does not infer false. |
| Read and write points | List events and consumers with stable references. A unique effect may grant at most once per allowed scope. |
| Save policy | Specify compatible schema and build or a named migration. Preserve explicit failure for unsupported versions. |

The worked JSON keeps the pilot's five Ink variables under Ink ownership. The separate synthetic host example distinguishes scene exposure, player interpretation, protagonist knowledge and Ilya's belief. Displaying a clue can change exposure while interpretation remains unexpressed. The listed fields do not establish human understanding.

## Save and conflict review

For a fresh route initialize from the declared fresh values. For a legacy save, determine the schema first. Supply a missing value only through an explicit migration approved for the specific old and target versions. When migration is absent, preserve the missing value and report a prerequisite. An unknown version can offer restart with informed player choice or preserve the existing save for a supported host.

A duplicate writer is an ownership fault. For example, Ink and a host event both writing crew safety can race even with a valid save. A missing legacy key is a migration prerequisite even with a single owner. Compare both before changing the registry.
