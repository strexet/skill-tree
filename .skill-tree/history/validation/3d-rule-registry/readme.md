# Validation evidence for configurable 3D rules

The implementation run passed 759 Python tests and all 381 Node tests. Three optional Director checks lacked machine-local Unity evidence. The Python runner used six isolated module groups and matched the executed identities against all 762 discovered test identities. Standalone package checks verified installation in the general, director, web and Unity flavors.

Blender 5.3.0 measured four anatomical segments across 17 quarter-frame samples. The maximum length error was 0.045 micrometres against a one-micrometre tolerance. The one-millimetre negative control failed the protected length check. The independent visual review covers five whole frames of the same rigid fixture from one camera. Frame 3 partially occludes the teal lower segment.

The [measurement receipt](measurement-result.json), [bind receipt](bind-lengths.json) and [visual review](independent-visual-review.json) retain exact evidence hashes. Original Blender, FBX and render binaries remain machine-local. The [motion generator](measure-fixture.py) and [rest measurement](measure-rest.py) reproduce the measurement procedure. The [adoption comparison](adoption-comparison.md) covers two existing validation workflows.

The publication review reproduced an impossible required geometry minimum and an inconsistent legacy export handoff. The corrective revision passed all 30 focused stage tests and the standalone installation test. The required geometry minimum is checked before attempt creation. The legacy export frontier reports the requalification requirement and retains the historical motion acceptance.
