# Exact Narrative Review Packets

A review packet freezes the candidate and scope inspected by a reviewer. Author approval is a separate decision with a separate receipt. A source inspection does not qualify runtime behavior or an audience effect.

## Bind the review

Use `propose --review-source RELATIVE_PATH` for each explicit source outside the candidate record set, such as an authoritative work definition or an Ink scene. A bound proposal uses schema 2 and includes ordered `review_sources` entries with the path and lowercase SHA-256 of exact file bytes. Use repository-relative regular files inside the project. Reject duplicate, ambiguous, missing, absolute, escaping or symlinked paths. Keep source hashes separate from canon record dependency edges.

The schema 1 review packet carries the fields below. A packet uses the exact proposal digest and copies work, continuity and accepted base from the proposal. Sort bound source entries by repository-relative path and preserve exact source equality with the proposal.

| Field | Meaning |
| --- | --- |
| `schema` | Review packet version 1. |
| `proposal_digest` | Canonical digest of the bound candidate. |
| `work`, `continuity`, `base` | Exact proposal scope and base snapshot or null. |
| `record_scope` | `selected`, `retired` and `unchanged_dependents` match proposal `ids`, `retire` and `affected` respectively. |
| `review_sources` | Exact ordered `path` and `sha256` pairs. |
| `reviewer` | Nonempty strings for `id`, `role` and `evidence` identify the actual review. Use an independent reviewer for consequential changes. |
| `coverage` | Nonempty list of reviewed cases. Each case has nonempty `kind` and `scope` strings and a nonempty `evidence` list of nonempty strings. |
| `findings` | List of `id`, `scope`, `severity`, `status` and `evidence`. Each `evidence` list contains at least one nonempty string. Include a nonempty `resolution` string for a resolved or dismissed blocker. |
| `packet_digest` | Lowercase SHA-256 hex digest of the canonical UTF-8 packet body. |

Compute the digest from the packet object without the `packet_digest` field. Parse source JSON with duplicate-key rejection before encoding.

```python
import hashlib
import json

body = {key: value for key, value in packet.items() if key != "packet_digest"}
encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))
packet["packet_digest"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
```

A finding scope is `in-scope` or `out-of-scope`. Severity is `blocker` or `note`. Status is `open`, `resolved` or `dismissed`. Open in-scope blockers hold approval. Record concrete resolution evidence for resolved blockers or a source-backed reason for dismissal. Unrelated unresolved work can remain visible outside the selected scope. Confirm current coverage after a repair.

## Recheck and hand off

Verify the current proposal digest and scope, the packet digest, the bound source bytes and the cleared in-scope findings before presenting the package for acceptance. A changed work setting or Ink source invalidates the affected review. Refresh the exact proposal and affected review before requesting the author's choice. For a bound candidate, the author receipt must explicitly accept the current `proposal_digest` and `review_packet_digest`. The `accept --review-packet RELATIVE_PATH` path verifies the exact packet again before publishing.

A legacy record-only proposal uses schema 1 and the existing author receipt without review packet identity. Existing snapshots and exact historical retries retain the original verification scope. A bound proposal requires the packet and cannot use a legacy call to omit the bound inputs. The helper validates evidence identity and packet state. The agent still obtains the actual author decision and genuine review evidence.

## Synthetic example

The example review packet uses a scratch proposal changing `event-trip` with `scene-relay` as an unchanged normative dependent. The original event says the short preceded the storm. The new event names 06:12 and the first lightning at 06:40. The bound files are a work scope and an Ink excerpt, each with a byte hash. The source inspection observes a matching displayed trip time and clears the in-scope discrepancy. The open playtest note remains outside the reviewed scope. Synthetic packet metadata is an example of shape and integrity, never evidence of an actual reviewer or owner action.
