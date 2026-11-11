# Capture and resume narrative context

Treat a context record as a derived description of one task. Preserve the work manifest, accepted snapshot, source artifact and decision as separate authorities.

## Establish scope

1. Record `context_id`, work, IP, continuity, period, predecessor or route and the authorized request mode. Copy the selected `canon_pin` state and digest from the work manifest.
2. For an accepted pin, call the helper with `context ROOT --snapshot DIGEST --ids ID ...`. Check the returned work and continuity against the intended scope. A new work may explicitly reuse a predecessor pin with recorded provenance and compatible continuity. Record each selected and required accepted record with stable ID, revision and source role.
3. For an intentional empty first baseline, record `canon_pin.state` as `empty`, keep the digest null and identify every draft explicitly. An unknown, missing or incompatible pin remains unresolved. Ask for the exact work or pin before changing dependent material.
4. For each draft, record repository-relative path, stable source ID, hash of exact bytes and source role. Record alternative groups with separate route or predecessor conditions. Compare alternatives without folding incompatible assumptions into the accepted view.
5. Attach unresolved decisions, findings and planned edits to the exact source IDs that support each item. Record which outputs stay held and which unaffected actions remain within scope.

## Reopen from a record

Load the recorded work, scope and exact snapshot. Resolve selected record revisions and compare each stored draft hash with current source bytes. Missing work, continuity or route remains explicit. A file move with the same stable identity still needs a verified path and matching bytes before source reuse.

Refresh only findings and decisions supported by changed or missing inputs. Preserve independently supported findings and the original accepted pin. Record the replacement source and reason for reopening work. A proposal that contradicts a selected route remains an alternative until the author resolves the conflict.

The Ridge example describes one accepted scope and two alternative draft groups. Create the synthetic baseline in a disposable project by copying the listed record pairs. Propose the three IDs for the listed work and continuity. Write the fixture decision path as UTF-8 JSON with two-space indentation and a final newline. Write keys in the following order. `proposal_digest`, `decision` with value `accepted`, `author`, and `reason`. Use the actual proposal digest and listed author and reason. Resolve the generated pin before comparing draft hashes. The fixture setup is demonstration data and grants no authority for project canon.
