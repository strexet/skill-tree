"""Exercise ArtWorkshop scheduling and known negative review controls."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from shutil import which
import subprocess
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "common/scripts/3d-stages.py"
SPEC = importlib.util.spec_from_file_location("test_stage_workflow", SCRIPT)
stages = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stages)


class ArtStages(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.sequence = 0

    def artifact(self, data, extension="bin"):
        self.sequence += 1
        name = f"evidence-{self.sequence}." + ("json" if isinstance(data, dict) else extension)
        content = json.dumps({"schema": 1, **data}).encode() if isinstance(data, dict) else data
        (self.root / name).write_bytes(content)
        return {"path": name, "sha256": sha256(content).hexdigest()}

    def call(self, action, **values):
        return stages.execute(self.root, "test-workflow", action, values)

    def init(self, goal="export", motion=False, fixture=True, diagnostic=False, mirrored=False, temporal=False,
             unity_motion=False):
        selected = list(stages.DEPENDENCIES)
        if goal != "motion" and not motion:
            selected.remove("motion")
        if goal == "motion":
            selected.remove("texture")
        selected = selected[:selected.index(goal) + 1]
        self.plan = {name: {"inputs": {}, "allowed": ["asset"], "protected": ["width"] if name == "detail" else [],
                            "shots": ["front", "side", "top"] if name in stages.VISUAL else []}
                     for name in selected}
        self.plan["references"]["requirements"] = {"shot-states": dict.fromkeys(self.plan["references"]["shots"], "neutral")}
        if "detail" in self.plan:
            self.plan["detail"]["requirements"] = {"protected-values": {"width": {"value": 84.251}}}
        if "motion" in self.plan:
            self.plan["motion"]["requirements"] = {"clips": {"walk": {"minimum-samples": 16, "max-slip-m": 0.002}}}
        if "unity" in self.plan:
            self.plan["unity"]["requirements"] = {"controls": ["Walk"] if motion else []}
        if unity_motion:
            self.plan["unity"]["shots"] += ["other-side", "under", "three-quarter"]
            self.plan["unity"]["requirements"]["unity-motion-review"] = {
                "views": {"left": "side", "right": "other-side", "underside": "under", "oblique": "three-quarter"},
                "ranges": {"walk": {"start": 0, "end": 2, "fps": 30, "loop": True}},
                "cases": {"walk": {"kind": "clip", "sequence": ["walk"],
                                   "contact": {"max-slip-m": .002, "max-penetration-m": .002}}},
                "regions": ["front paw", "tail", "abdomen"],
            }
        if diagnostic:
            for stage in stages.SURFACE_REVIEW.intersection(self.plan):
                shots = ["reverse-axilla", "grazing-underbody"]
                self.plan[stage]["shots"].extend(shots)
                self.plan[stage].setdefault("requirements", {})["diagnostic-shots"] = shots
        if temporal:
            self.plan["motion"]["shots"].append("opposing-profile")
            self.plan["motion"]["requirements"]["temporal-review"] = {
                "views": {"left": "side", "right": "opposing-profile",
                          "underside": "grazing-underbody", "oblique": "reverse-axilla"},
                "ranges": {"walk": {"start": 1, "end": 5, "fps": 30, "loop": True}},
            }
        options = {"neutral-symmetry": self.mirrored_scope()} if mirrored else {}
        self.call("init", asset="asset.test", target="target.test", goal=goal, motion=motion,
                  orthographic=True, fixture=fixture, stages=self.plan, **options)

    def mirrored_scope(self):
        return {"kind": "mirrored", "basis": self.artifact(b"Brief requires a mirror-symmetric animal."),
                "scene": "Scene", "symmetry_frame": "world", "axes": ["Y"], "subjects": ["body"],
                "closed_subjects": ["body"], "pose": "quadruped-square", "state": "neutral"}

    def mirrored_reference(self, attempt, observations, *, wrong=None, revision="r1"):
        stage = attempt["packet"]["stage"]
        primary = stages.ARTIFACTS[stage]
        shots = self.plan[stage]["shots"]
        artifacts = {key: self.artifact(f"{stage} {key} {revision}".encode())
                     for key in (primary, *shots, "reflection-overlay")}
        receipt = {"kind": "neutral-reference-symmetry", "symmetry_frame": "world", "axes": ["Y"],
                   "state": "neutral", "primary": artifacts[primary],
                   "shots": {key: artifacts[key] for key in shots},
                   "checks": {"Y": {"views": ["front", "top"], "comparison": artifacts["reflection-overlay"],
                                    "unmatched_landmarks": [], "unmatched_outline_regions": []}}}
        if wrong == "overlay":
            receipt["checks"]["Y"]["comparison"] = artifacts["front"]
        if wrong == "shape":
            receipt["checks"]["Y"]["unmatched_outline_regions"] = ["ear"]
        if wrong == "primary":
            receipt["primary"] = self.artifact(b"a different sheet")
        proof = self.artifact(receipt)
        return self.submit(attempt, {**observations, "neutral-reference-symmetry": proof}, revision, artifacts)

    def mirrored_mesh(self, attempt, *, wrong=None, revision="r1"):
        stage = attempt["packet"]["stage"]
        artifacts = {key: self.artifact(f"{stage} {key} {revision}".encode())
                     for key in ("blend", *self.plan[stage]["shots"])}

        def phase():
            return {"passed": True, "vertices": 8, "faces": 6, "invalid_vertices": 0,
                    "axes": {"Y": {"passed": True, "unmatched_vertices": 0, "unmatched_faces": 0,
                                    "unmatched_edges": 0}},
                    "integrity": {"body": {"boundary_edges": 0, "nonmanifold_edges": 0, "degenerate_faces": 0,
                                           "duplicate_center_vertices": 0, "passed": True}}}

        receipt = {"kind": "neutral-geometry-symmetry", "asset_sha256": artifacts["blend"]["sha256"],
                   "scene": "Scene", "symmetry_frame": "world", "axes": ["Y"],
                   "subjects": ["body"], "closed_subjects": ["body"],
                   "checks": {"bind": phase(), "evaluated-neutral": phase()}, "passed": True}
        if wrong == "source":
            receipt["asset_sha256"] = "1" * 64
        if wrong == "faces":
            receipt["checks"]["evaluated-neutral"]["axes"]["Y"]["unmatched_faces"] = 1
        if wrong == "seam":
            receipt["checks"]["bind"]["integrity"]["body"]["duplicate_center_vertices"] = 1
        rows = {"width": {"baseline": 84.251, "candidate": 84.251}} if stage == "detail" else {}
        return self.submit(attempt, {"protected": rows, "neutral-geometry-symmetry": self.artifact(receipt)},
                           revision, artifacts)

    def begin(self, stage, actor="author"):
        return self.call("begin", stage=stage, actor=actor)["attempt"]

    def submit(self, attempt, observations, revision="r1", artifacts=None):
        stage = attempt["packet"]["stage"]
        if artifacts is None:
            artifacts = {key: self.artifact(f"fixture artifact {key}".encode())
                         for key in (stages.ARTIFACTS[stage], *self.plan[stage]["shots"])}
        report = self.artifact({"attempt": attempt["id"], "stage": stage, "artifacts": stages.digest(artifacts),
                                "checks": dict.fromkeys(stages.CHECKS[stage], True), "observations": observations})
        return self.call("submit", stage=stage, attempt=attempt["id"], actor="author",
                         candidate={"revision": revision, "artifacts": artifacts, "technical": report})["attempt"]

    def approve(self, attempt):
        return self.call("approve", stage=attempt["packet"]["stage"], attempt=attempt["id"],
                         decision={"origin": "fixture", "answer": "accept",
                                   "candidate": attempt["candidate_digest"]})

    def review(self, attempt, reviewer="critic", failing=None, incomplete=False):
        stage = attempt["packet"]["stage"]
        shots = self.plan[stage]["shots"]
        rows = {shot: {"result": "pass", "observation": "Compared with fixture reference.",
                       "artifact": attempt["candidate"]["artifacts"][shot]}
                for shot in (shots[:-1] if incomplete else shots)}
        if failing:
            rows[shots[0]].update(result="fail", finding=failing, region="inner cheek",
                                  expected="Smooth round contour", observation="Visible ridge in grazing light")
        receipt = self.artifact({"attempt": attempt["id"], "reviewer": reviewer,
                                 "candidate": attempt["candidate_digest"], "shots": rows})
        return self.call("review", stage=stage, attempt=attempt["id"], review=receipt)

    def references(self, swapped=False):
        return {"views": {shot: {"state": "neutral", "expression": "calm",
                                "anchors": {"paw": {"side": "right" if swapped and shot == "top" else "left",
                                                    "contact": True, "anchor": "front-paw"}}}
                          for shot in self.plan["references"]["shots"]}}

    def clay(self, attempt, mark=False):
        return {"pairs": {shot: {"registered": True, "color": attempt["packet"]["supplied"]["references"][shot],
                                 "texture-like": ["iris"] if mark and shot == "front" else []}
                          for shot in self.plan["clay"]["shots"]}}

    def through_detail(self):
        approved = self.submit(self.begin("references"), self.references())
        self.review(approved)
        self.approve(approved)
        clay = self.begin("clay")
        approved = self.submit(clay, self.clay(clay))
        self.review(approved)
        self.approve(approved)
        geom = self.begin("blockout")
        self.assertNotIn("color", geom["packet"]["supplied"]["clay"])
        self.assertNotIn("review-input", geom["packet"]["supplied"]["clay"])
        approved = self.submit(geom, {"protected": {}})
        self.review(approved)
        self.approve(approved)
        geom = self.begin("detail")
        approved = self.submit(geom, {"protected": {"width": {"baseline": 84.251, "candidate": 84.251}}})
        self.review(approved)
        return approved

    def repair(self, attempt, method="reshape", evidence=None):
        resolution = {"method": method, "reason": "Repair scoped fixture issue"}
        if evidence is not None:
            resolution["evidence"] = evidence
        return self.call("repair", stage=attempt["packet"]["stage"], attempt=attempt["id"],
                         resolution=resolution)

    def test_resume_gate_detects_swapped_limb_and_requires_fresh_artifacts(self):
        self.init("references")
        a = self.begin("references")
        self.assertEqual(self.begin("references")["id"], a["id"])
        with self.assertRaisesRegex(ValueError, "Original producer"):
            self.begin("references", "replacement")
        bad = self.submit(a, self.references(swapped=True))
        self.assertEqual(bad["failures"], ["technical-consistent-views"])
        with self.assertRaisesRegex(ValueError, "reviewed candidate"):
            self.approve(bad)
        self.repair(bad)
        a = self.begin("references")
        self.assertNotEqual(a["id"], bad["id"])
        good = self.submit(a, self.references(), "r2")
        with self.assertRaisesRegex(ValueError, "Independent reviewer"):
            self.review(good, reviewer="author")
        with self.assertRaisesRegex(ValueError, "every planned shot"):
            self.review(good, incomplete=True)
        self.review(good)
        self.approve(good)
        self.assertEqual(self.call("next")["status"], "complete")
        (self.root / good["candidate"]["artifacts"]["top"]["path"]).write_bytes(b"drift")
        self.assertEqual(self.call("next")["steps"], [{"stage": "references", "status": "stale"}])

    def test_predecessors_and_clay_surface_gate(self):
        self.init("blockout")
        with self.assertRaisesRegex(ValueError, "predecessor"):
            self.begin("clay")
        refs = self.submit(self.begin("references"), self.references())
        self.review(refs)
        with self.assertRaisesRegex(ValueError, "predecessor"):
            self.begin("clay")
        self.approve(refs)
        a = self.begin("clay")
        rejected = self.submit(a, self.clay(a, mark=True))
        self.assertEqual(rejected["failures"], ["technical-clay-only"])
        self.repair(rejected)
        a = self.begin("clay")
        replacement = self.submit(a, self.clay(a), "r2")
        self.review(replacement)
        self.approve(replacement)
        self.assertEqual(self.call("next")["steps"], [{"stage": "blockout", "status": "pending"}])
        # A visually approved predecessor cannot mask a changed source image.
        (self.root / refs["candidate"]["artifacts"]["top"]["path"]).write_bytes(b"changed")
        self.assertEqual(self.call("inspect")["stages"]["clay"], "stale")

    def test_repeat_visual_failure_blocks_redundant_repair(self):
        self.init("references")
        for rev in ("r1", "r2"):
            a = self.submit(self.begin("references"), self.references(), rev)
            self.review(a, failing="cheek-ridge")
            if rev == "r1":
                self.repair(a)
        with self.assertRaisesRegex(ValueError, "distinct repair method"):
            self.repair(a)
        self.repair(a, method="replace-local-surface")
        self.assertEqual(self.call("next")["steps"], [{"stage": "references", "status": "pending"}])

    def test_texture_drift_motion_intersection_and_targeted_review(self):
        self.init("export", motion=True)
        base = self.through_detail()
        expected = dict.fromkeys(("geometry", "uv", "weights", "rig", "pose", "animation", "material_assignments"), "0" * 64)
        baseline = self.artifact({"source": base["candidate"]["artifacts"]["blend"], "status": "passed",
                                  "blender_build": "fixture", "fingerprints": expected})
        texture = self.begin("texture")
        arts = {name: self.artifact(b"candidate texture") for name in ("blend", *self.plan["texture"]["shots"])}
        candidate_lock = self.artifact({"source": arts["blend"], "status": "passed", "blender_build": "fixture",
                                        "fingerprints": {**expected, "geometry": "1" * 64}})
        tex = self.submit(texture, {"baseline-lock": baseline, "candidate-lock": candidate_lock}, artifacts=arts)
        self.assertEqual(tex["failures"], ["technical-surface-only"])
        self.repair(tex, "restore-approved-mesh")
        tex = self.begin("texture")
        approved_lock = self.artifact({"source": arts["blend"], "status": "passed", "blender_build": "fixture",
                                       "fingerprints": expected})
        tex = self.submit(tex, {"baseline-lock": baseline, "candidate-lock": approved_lock}, "r2", arts)
        self.review(tex)
        self.approve(tex)
        motion = self.begin("motion")
        samples = {"sample_count": 100, "between_keys": True, "loop_ok": True, "intersections": 5,
                   "penetrations": 0, "max_slip_m": 0.001, "allowed_slip_m": 0.002}
        motion = self.submit(motion, {"clips": {"walk": samples}})
        self.assertEqual(motion["failures"], ["technical-continuous-motion"])
        self.repair(motion, "adjust-stride")
        motion = self.submit(self.begin("motion"), {"clips": {"walk": {**samples, "intersections": 0}}}, "r2")
        self.review(motion)
        export = self.begin("export")
        self.assertEqual(set(export["packet"]["supplied"]), {"texture", "motion"})
        parity = dict.fromkeys(("scale", "axes", "pivot", "skin", "animation", "dependencies"), True)
        invalid = self.submit(export, {"round-trip": {**parity, "pivot": False}})
        self.assertEqual(invalid["failures"], ["technical-round-trip"])
        self.repair(invalid, "preserve-body-pivot")
        good = self.submit(self.begin("export"), {"round-trip": parity}, "r2")
        self.assertEqual(good["status"], "accepted")
        self.call("revise", stage="motion", attempt=motion["id"],
                  resolution={"method": "update-stride", "reason": "Approved movement change"})
        status = self.call("inspect")["stages"]
        self.assertEqual((status["texture"], status["motion"], status["export"]), ("accepted", "pending", "stale"))

    def test_frozen_shot_identity_and_unrelated_files(self):
        self.init("references")
        a = self.begin("references")
        inputs = self.references(swapped=True)
        inputs["views"]["top"]["state"] = "invented-neutral"
        result = self.submit(a, inputs)
        self.assertEqual(result["failures"], ["technical-consistent-views"])
        self.repair(result)
        good = self.submit(self.begin("references"), self.references(), "r2")
        self.review(good)
        self.approve(good)
        for name in ("README.md", ".DS_Store"):
            (self.root / name).write_text("unrelated input")
        self.assertEqual(self.call("next")["status"], "complete")

    def test_new_live_surface_plan_requires_additional_diagnostic_angles(self):
        self.init("blockout")
        request = {"asset": "asset.test", "target": {"id": "target.test", "revision": "r1", "checkout_id": "checkout.test"},
                   "goal": "blockout", "stages": self.plan}
        with self.assertRaisesRegex(ValueError, "diagnostic shots"):
            stages.execute(self.root, "live-surface", "init", request)
        self.assertIn("blockout", stages.plan_for(self.root, request, new_run=False))
        blockout = self.plan["blockout"]
        blockout["requirements"] = {"diagnostic-shots": ["reverse", "grazing"]}
        with self.assertRaisesRegex(ValueError, "additional diagnostic shots"):
            stages.execute(self.root, "live-surface", "init", request)
        blockout["shots"].extend(["reverse", "grazing"])
        with self.assertRaisesRegex(ValueError, "resolved neutral symmetry intent"):
            stages.execute(self.root, "live-surface", "init", request)
        request["neutral-symmetry"] = self.mirrored_scope()
        self.assertEqual(stages.execute(self.root, "live-surface", "init", request)["status"], "created")

    def test_mirrored_plan_rejects_expressive_modeling_and_requires_owner_for_asymmetry(self):
        self.init("clay")
        request = {"asset": "asset.test", "target": "target.test", "goal": "clay", "fixture": True,
                   "stages": self.plan, "neutral-symmetry": self.mirrored_scope()}
        states = self.plan["references"]["requirements"]["shot-states"]
        states["front"] = "gesturing"
        with self.assertRaisesRegex(ValueError, "same neutral state"):
            stages.execute(self.root, "expressive-colors", "init", request)
        states["front"] = "neutral"
        self.plan["clay"]["shots"].remove("top")
        with self.assertRaisesRegex(ValueError, "same neutral modeling shots"):
            stages.execute(self.root, "partial-clay", "init", request)
        asymmetric = {"kind": "asymmetric", "scope": "left shoulder armor",
                      "basis": self.artifact({"origin": "agent", "choice": "asymmetric",
                                              "scope": "left shoulder armor", "observation": "A creative choice."})}
        request["neutral-symmetry"] = asymmetric
        with self.assertRaisesRegex(ValueError, "observed owner instruction"):
            stages.execute(self.root, "agent-asymmetry", "init", request)
        asymmetric["basis"] = self.artifact({"origin": "owner", "choice": "asymmetric",
                                            "scope": "left shoulder armor", "observation": "Keep the large left pauldron."})
        self.assertEqual(stages.execute(self.root, "owner-asymmetry", "init", request)["status"], "created")

    def test_neutral_reference_proof_holds_clay_and_binds_the_current_color_and_clay(self):
        self.init("blockout", mirrored=True)
        for index, failure in enumerate(("overlay", "shape", "primary"), 1):
            attempt = self.mirrored_reference(self.begin("references"), self.references(),
                                              wrong=failure, revision=f"r{index}")
            self.assertEqual(attempt["failures"], ["technical-neutral-reference-symmetry"])
            self.repair(attempt, f"correct-{failure}", attempt["candidate"]["technical"])
        color = self.mirrored_reference(self.begin("references"), self.references(), revision="r4")
        self.review(color)
        self.approve(color)
        attempt = self.begin("clay")
        invalid = self.submit(attempt, self.clay(attempt))
        self.assertEqual(invalid["failures"], ["technical-neutral-reference-symmetry"])
        self.repair(invalid, "compare-neutral-clay")
        attempt = self.begin("clay")
        corrected = self.mirrored_reference(attempt, self.clay(attempt), revision="r2")
        self.review(corrected)
        self.approve(corrected)
        self.assertEqual(self.call("next")["steps"], [{"stage": "blockout", "status": "pending"}])
        record = corrected["observation_pins"]["neutral-reference-symmetry"]
        (self.root / record["path"]).write_bytes(b"stale")
        self.assertEqual(self.call("inspect")["stages"]["clay"], "stale")
        with self.assertRaisesRegex(ValueError, "missing or stale"):
            self.begin("blockout")

    def test_exact_mesh_gate_rejects_unmatched_evaluated_faces_and_unwelded_center(self):
        self.init("detail", mirrored=True)
        valid = self.mirrored_reference(self.begin("references"), self.references())
        self.review(valid)
        self.approve(valid)
        attempt = self.begin("clay")
        valid = self.mirrored_reference(attempt, self.clay(attempt))
        self.review(valid)
        self.approve(valid)
        for index, failure in enumerate(("source", "faces", "seam"), 1):
            invalid = self.mirrored_mesh(self.begin("blockout"), wrong=failure, revision=f"r{index}")
            self.assertEqual(invalid["failures"], ["technical-neutral-geometry-symmetry"])
            self.repair(invalid, f"check-{failure}", invalid["candidate"]["technical"])
        valid = self.mirrored_mesh(self.begin("blockout"), revision="r4")
        self.review(valid)
        self.approve(valid)
        self.assertEqual(self.mirrored_mesh(self.begin("detail"))["status"], "review")

    def test_motion_diagnostics_reject_reused_images_and_hold_visible_folds(self):
        self.init("export", motion=True, diagnostic=True)
        self.through_detail()
        started = self.begin("motion")
        clips = {"walk": {"sample_count": 32, "between_keys": True, "loop_ok": True,
                          "intersections": 0, "penetrations": 0, "max_slip_m": 0.001}}
        artifacts = {name: self.artifact(name.encode()) for name in ("clip", *self.plan["motion"]["shots"])}
        repeated = {**artifacts, "reverse-axilla": self.artifact(b"side")}
        with self.assertRaisesRegex(ValueError, "distinct captured evidence"):
            self.submit(started, {"clips": clips}, artifacts=repeated)
        candidate = self.submit(started, {"clips": clips}, artifacts=artifacts)
        with self.assertRaisesRegex(ValueError, "every planned shot"):
            self.review(candidate, incomplete=True)
        rows = {name: {"artifact": artifacts[name], "result": "pass", "observation": "Surface continuous."}
                for name in self.plan["motion"]["shots"]}
        rows["grazing-underbody"].update(result="fail", observation="Sharp pinch at toe-off.",
                                         region="left axilla", expected="Smooth transition", finding="axilla-pinch")
        receipt = self.artifact({"attempt": started["id"], "candidate": candidate["candidate_digest"],
                                 "reviewer": "critic", "shots": rows})
        held = self.call("review", stage="motion", attempt=started["id"], review=receipt)["attempt"]
        self.assertEqual(held["status"], "repair")
        self.assertEqual(held["failures"], ["axilla-pinch"])

    def test_live_motion_requires_distinct_playback_views_and_full_ranges(self):
        self.init("motion", motion=True, diagnostic=True, mirrored=True, temporal=True)
        request = {"asset": "asset.test", "target": {"id": "target.test", "revision": "r1", "checkout_id": "checkout.test"},
                   "goal": "motion", "stages": self.plan, "neutral-symmetry": self.mirrored_scope()}
        requirements = self.plan["motion"]["requirements"]
        temporal = requirements.pop("temporal-review")
        with self.assertRaisesRegex(ValueError, "frozen full clip range"):
            stages.plan_for(self.root, request)
        requirements["temporal-review"] = temporal
        temporal["views"]["right"] = "side"
        with self.assertRaisesRegex(ValueError, "left, right, underside"):
            stages.plan_for(self.root, request)
        temporal["views"]["right"] = "opposing-profile"
        self.assertIn("motion", stages.plan_for(self.root, request))

    def test_legacy_motion_approval_remains_readable_and_cannot_start_new_live_export(self):
        self.init("export", motion=True)
        state = {"fixture": False, "plan": self.plan,
                 "stages": {"motion": {"current": {"status": "accepted"}}}}
        with self.assertRaisesRegex(ValueError, "Requalify legacy live motion"):
            stages.patch(self.root, self.root / "state.json", state, "begin", {"stage": "export", "actor": "author"})
        self.assertEqual(state["stages"]["motion"]["current"]["status"], "accepted")

    @unittest.skipUnless(which("ffmpeg") and which("ffprobe"), "Local media tools are unavailable")
    def test_decoded_video_count_and_cadence_disagree_with_claimed_grid(self):
        good = self.root / "good.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=32x32:rate=30",
                        "-frames:v", "5", "-c:v", "mpeg4", str(good)], check=True, timeout=10)
        self.assertTrue(stages.stage_checks.video_timing(good, 5, 30))
        self.assertFalse(stages.stage_checks.video_timing(good, 17, 30))
        self.assertFalse(stages.stage_checks.video_timing(good, 5, 24))
        text = self.root / "fake.mp4"
        text.write_bytes(b"not a video")
        self.assertFalse(stages.stage_checks.video_timing(text, 5, 30))

    def test_temporal_capture_rejects_reordered_samples_and_review_blocks_flashing_surface(self):
        self.init("motion", motion=True, diagnostic=True, temporal=True)
        self.through_detail()
        plan = self.plan["motion"]
        clips = {"walk": {"sample_count": 17, "between_keys": True, "loop_ok": True,
                          "intersections": 0, "penetrations": 0, "max_slip_m": 0.001}}
        artifacts = {shot: self.artifact(shot.encode()) for shot in ("clip", *plan["shots"])}
        artifacts["blend"] = self.artifact(b"exact animated source", "blend")
        views, playback = {}, {}
        directions = {"left": [0, -1, 0], "right": [0, 1, 0], "underside": [0, 0, 1], "oblique": [0.6, 0.8, 0]}
        for role, shot in plan["requirements"]["temporal-review"]["views"].items():
            views[role] = {"shot": shot, "camera": {"name": shot, "forward": directions[role]}}
            playback[role] = {}
            for speed, step in stages.stage_checks.MOTION_SAMPLE_STEP.items():
                key = f"{role}-{speed}"
                artifacts[key] = self.artifact(key.encode(), "mp4")
                views[role][speed] = {"video": artifacts[key], "ticks": list(range(4, 21, step))}
                playback[role][speed] = {"video": artifacts[key], "full_playback": True,
                                         "loop_boundary_reviewed": True, "result": "pass",
                                         "observation": "Compared all consecutive samples on the fixed view."}
        capture = {"kind": "temporal-motion-capture", "scene": "Test Scene",
                   "blend": artifacts["blend"], "clip": artifacts["clip"],
                   "clips": {"walk": {"action": "Walk", "fps": 30, "views": views}}}
        bad = self.submit(self.begin("motion"), {"clips": clips}, artifacts=artifacts)
        self.assertEqual(bad["failures"], ["technical-temporal-motion-capture"])
        self.repair(bad, "add-playback-captures")
        ticks = views["underside"]["slow"]["ticks"]
        ticks[8], ticks[9] = ticks[9], ticks[8]
        bad = self.submit(self.begin("motion"), {"clips": clips, "temporal-motion-capture": self.artifact(capture)},
                          "r2", artifacts)
        self.assertEqual(bad["failures"], ["technical-temporal-motion-capture"])
        self.repair(bad, "restore-native-frame-order")
        ticks[8], ticks[9] = ticks[9], ticks[8]
        candidate = self.submit(self.begin("motion"), {"clips": clips, "temporal-motion-capture": self.artifact(capture)},
                                "r3", artifacts)
        with self.assertRaisesRegex(ValueError, "every required clip"):
            self.review(candidate)
        shot_results = {shot: {"artifact": artifacts[shot], "result": "pass", "observation": "Still looks smooth."}
                        for shot in plan["shots"]}
        report = {"attempt": candidate["id"], "reviewer": "critic", "candidate": candidate["candidate_digest"],
                  "shots": shot_results, "playback": {"walk": playback}}
        underside = playback["underside"]["slow"]
        underside["loop_boundary_reviewed"] = False
        with self.assertRaisesRegex(ValueError, "complete observation"):
            self.call("review", stage="motion", attempt=candidate["id"], review=self.artifact(report))
        underside.update(loop_boundary_reviewed=True, result="fail", finding="axilla-flash", tick=13,
                         region="front axilla", observation="A flap protrudes briefly at frame 3.25.")
        held = self.call("review", stage="motion", attempt=candidate["id"], review=self.artifact(report))["attempt"]
        self.assertEqual(held["failures"], ["axilla-flash"])
        self.repair(held, "remove-transient-fold")
        with self.assertRaisesRegex(ValueError, "must be recaptured"):
            self.submit(self.begin("motion"), {"clips": clips, "temporal-motion-capture": self.artifact(capture)},
                        "r4", artifacts)
        artifacts["underside-slow"] = self.artifact(b"new underside sequence after repair", "mp4")
        views["underside"]["slow"]["video"] = artifacts["underside-slow"]
        underside["video"] = artifacts["underside-slow"]
        fixed = self.submit(self.begin("motion"), {"clips": clips, "temporal-motion-capture": self.artifact(capture)},
                            "r4", artifacts)
        underside.update(result="pass", observation="Axilla transition stays smooth in the slow sequence.")
        report.update(attempt=fixed["id"], candidate=fixed["candidate_digest"])
        self.assertEqual(self.call("review", stage="motion", attempt=fixed["id"],
                                   review=self.artifact(report))["status"], "accepted")

    def test_scene_requires_the_admitted_export_and_required_controls(self):
        self.init("delivery", motion=True)
        base = self.through_detail()
        sections = dict.fromkeys(("geometry", "uv", "weights", "rig", "pose", "animation", "material_assignments"), "0" * 64)
        def lock(source):
            return self.artifact({"source": source, "status": "passed", "blender_build": "fixture",
                                  "fingerprints": sections})
        texture = self.begin("texture")
        textured = {name: self.artifact(b"texture fixture") for name in ("blend", *self.plan["texture"]["shots"])}
        texture = self.submit(texture, {"baseline-lock": lock(base["candidate"]["artifacts"]["blend"]),
                                        "candidate-lock": lock(textured["blend"])}, artifacts=textured)
        self.review(texture)
        self.approve(texture)
        samples = {"sample_count": 2, "between_keys": True, "loop_ok": True, "intersections": 0,
                   "penetrations": 0, "max_slip_m": 100, "allowed_slip_m": 101}
        motion = self.submit(self.begin("motion"), {"clips": {"walk": samples}})
        self.assertEqual(motion["failures"], ["technical-continuous-motion"])
        self.repair(motion)
        motion = self.submit(self.begin("motion"), {"clips": {"walk": {
            **samples, "sample_count": 80, "max_slip_m": 0.001}}}, "r2")
        self.review(motion)
        parity = dict.fromkeys(("scale", "axes", "pivot", "skin", "animation", "dependencies"), True)
        exported = self.submit(self.begin("export"), {"round-trip": parity})
        scene_content = b"Unity fixture scene"
        scene_path = self.root / "review.unity"
        scene_path.write_bytes(scene_content)
        scene = {"path": scene_path.name, "sha256": sha256(scene_content).hexdigest()}
        artifacts = {name: self.artifact(b"game view") for name in self.plan["unity"]["shots"]}
        artifacts["scene"] = scene
        receipt = {"scene": scene, "export": exported["candidate"]["artifacts"]["export"],
                   "target": "target.test", "opened": True, "preview": artifacts["front"],
                   "open_instructions": "Open review scene", "unresolved": [], "controls": []}
        rejected = self.submit(self.begin("unity"), {"scene-receipt": self.artifact(receipt)}, artifacts=artifacts)
        self.assertIn("technical-playable-scene", rejected["failures"])
        self.repair(rejected)
        wrong = self.submit(self.begin("unity"), {"scene-receipt": self.artifact({
            **receipt, "export": scene, "controls": [{"name": "Walk", "verified": True}],
        })}, "r2", artifacts)
        self.assertIn("technical-playable-scene", wrong["failures"])
        self.repair(wrong, method="reopen-accepted-export")
        ready = self.submit(self.begin("unity"), {"scene-receipt": self.artifact({
            **receipt, "controls": [{"name": "Walk", "verified": True}],
        })}, "r3", artifacts)
        self.review(ready)
        self.approve(ready)
        delivery = self.submit(self.begin("delivery"), {"rollback": True, "repeat_import": True,
                              "conflict_detected": True, "local_edits_preserved": False})
        self.assertIn("technical-preserved-overrides", delivery["failures"])

    def unity_motion_fixture(self):
        self.init("unity", unity_motion=True)
        detail = self.through_detail()
        fingerprint = dict.fromkeys(stages.stage_checks.LOCK_SECTIONS, "0" * 64)
        texture = self.begin("texture")
        textured = {name: self.artifact(name.encode()) for name in ("blend", *self.plan["texture"]["shots"])}

        def lock(source):
            return self.artifact({"source": source, "status": "passed", "blender_build": "fixture",
                                  "fingerprints": fingerprint})

        texture = self.submit(texture, {"baseline-lock": lock(detail["candidate"]["artifacts"]["blend"]),
                                        "candidate-lock": lock(textured["blend"])}, artifacts=textured)
        self.review(texture)
        self.approve(texture)
        return self.submit(self.begin("export"), {"round-trip": dict.fromkeys(stages.stage_checks.ROUND_TRIP, True)})

    def submit_unity_motion(self, exported, revision, *, slide=0.0, missing=False):
        scope = self.plan["unity"]["requirements"]["unity-motion-review"]
        artifacts = {shot: self.artifact((shot + revision).encode()) for shot in self.plan["unity"]["shots"]}
        artifacts["scene"] = scene = self.artifact(("native scene " + revision).encode(), "unity")
        export = exported["candidate"]["artifacts"]["export"]
        receipt = self.artifact({"scene": scene, "export": export, "target": "target.test", "opened": True,
                                 "preview": artifacts["front"], "open_instructions": "Open and play",
                                 "unresolved": [], "controls": [], "animated": True})
        videos = {}
        directions = {"left": [1, 0, 0], "right": [-1, 0, 0], "underside": [0, 1, 0], "oblique": [0, 0, 1]}
        for role, shot in scope["views"].items():
            row = {"shot": shot, "camera": {"name": role, "forward": directions[role]}}
            for speed, stride in stages.stage_checks.MOTION_SAMPLE_STEP.items():
                key = f"{role}-{speed}"
                artifacts[key] = self.artifact((key + revision).encode(), "mp4")
                row[speed] = {"video": artifacts[key], "ticks": list(range(0, 9, stride))}
            videos[role] = row
        frames = [{"tick": tick, "support": {"left": [slide * tick, 0]}, "floor-clearance-m": 0}
                  for tick in range(9)]
        artifacts["trace"] = trace = self.artifact({"kind": "unity-motion-trace", "scene": scene, "case": "walk",
                                                    "frames": frames[:-1] if missing else frames})
        capture = self.artifact({"kind": "unity-motion-capture", "scene": scene, "export": export,
                                 "target": "target.test", "play-mode": True,
                                 "checks": {"walk": {"trace": trace, "regions": dict.fromkeys(scope["regions"], "Observed")}},
                                 "clips": {"walk": {"action": "Walk on the floor", "fps": 30, "views": videos}}})
        return self.submit(self.begin("unity"), {"scene-receipt": receipt, "unity-motion-capture": capture},
                           revision, artifacts), videos

    def test_unity_motion_requires_actual_ordered_contact_and_temporal_review(self):
        exported = self.unity_motion_fixture()
        missing, _ = self.submit_unity_motion(exported, "r1", missing=True)
        self.assertIn("technical-unity-motion-capture", missing["failures"])
        self.repair(missing, method="capture-source-samples")
        sliding, _ = self.submit_unity_motion(exported, "r2", slide=.001)
        self.assertEqual(sliding["motion_findings"], ["technical-unity-contact-walk"])
        self.assert_unity_motion_routes(sliding)
        ready, videos = self.submit_unity_motion(exported, "r3")
        with self.assertRaisesRegex(ValueError, "Playback review must cover"):
            self.review(ready)
        shots = {shot: {"result": "pass", "observation": "Observed live shape",
                        "artifact": ready["candidate"]["artifacts"][shot]} for shot in self.plan["unity"]["shots"]}
        playback = {"walk": {role: {speed: {"video": row[speed]["video"], "result": "pass", "full_playback": True,
                                             "loop_boundary_reviewed": True, "observation": "Reviewed consecutive movement",
                                             "aspects": dict.fromkeys(("surface", "trajectory", "contact"), "Observed")}
                                    for speed in stages.stage_checks.MOTION_SAMPLE_STEP} for role, row in videos.items()}}
        playback["walk"]["underside"]["slow"].update(result="fail", finding="tail-flick", region="tail", tick=5)
        report = self.artifact({"attempt": ready["id"], "candidate": ready["candidate_digest"], "reviewer": "critic",
                                "shots": shots, "playback": playback})
        held = self.call("review", stage="unity", attempt=ready["id"], review=report)["attempt"]
        self.assertEqual(held["motion_findings"], ["tail-flick"])
        with self.assertRaisesRegex(ValueError, "reviewed candidate"):
            self.approve(held)

    def assert_unity_motion_routes(self, attempt):
        initial = self.call("inspect")["state"]
        source = initial["stages"]
        selected = source["unity"]["current"]["candidate"]["artifacts"]["scene"]
        snapshots = {"unity": selected,
                     "blender": source["detail"]["current"]["candidate"]["artifacts"]["blend"],
                     "references": source["references"]["current"]["candidate"]["artifacts"]["color"]}
        path = self.root / stages.workshop.LOCAL / "stages/test-workflow.json"
        for expected, failed in (("detail", {"unity", "blender"}), ("references", {"unity", "references"}),
                                 ("unity", {"unity"})):
            diagnosis = {"kind": "unity-motion-diagnosis", "attempt": attempt["id"],
                         "candidate": attempt["candidate_digest"], "findings": attempt["motion_findings"],
                         "blender-stage": "detail"}
            for key, pin in snapshots.items():
                diagnosis[key] = {"artifact": pin, "result": "fail" if key in failed else "pass",
                                  "observation": "Compared at the same phase", "comparison": self.artifact(key.encode())}
            stages.workshop.atomic_record(path, initial)
            returned = self.repair(attempt, method="repair-floor-contact", evidence=self.artifact(diagnosis))
            self.assertEqual(returned["return-to"], expected)
            self.assertEqual(returned["steps"], [{"stage": expected, "status": "pending"}])

    def test_continuous_intervals_require_an_independent_midpoint(self):
        self.init("unity", unity_motion=True)
        plan = self.plan["unity"]
        scope = plan["requirements"]["unity-motion-review"]
        cases, ranges = scope["cases"], scope["ranges"]
        cases["trot"] = {**cases["walk"], "sequence": ["trot"]}
        cases["half"] = {**cases["walk"], "kind": "hold", "sequence": ["walk", "trot"]}
        ranges.update(trot=ranges["walk"], half=ranges["walk"])
        interval = {"basis": "weight", "from": "walk", "to": "trot", "samples": {"0.25": "half"}}
        scope["blend-holds"] = {"walk-trot": interval}
        check = stages.stage_checks.unity_motion_scope
        self.assertFalse(check(scope, {}, plan["shots"]))
        interval["samples"] = {"0.5": "half"}
        self.assertTrue(check(scope, {"trot"}, plan["shots"]))
        ranges["half"] = {**ranges["walk"], "end": 1, "loop": False}
        self.assertFalse(check(scope, {"trot"}, plan["shots"]))
        ranges["half"] = ranges["walk"]
        interval["samples"]["0.75"] = "half"
        self.assertFalse(check(scope, {}, plan["shots"]))

    def test_held_blend_rejects_a_sweep_short_playback_and_phase_drift(self):
        span = {"start": 0, "end": 2, "fps": 30, "loop": True}
        rows = [{"tick": i, "value": .5, "phases": [i / 4, .2 + i / 4]} for i in range(9)]
        check = stages.stage_checks.settled_blend
        self.assertTrue(check({"basis": "weight", "samples": rows}, span, .5, "weight"))
        self.assertFalse(check({"basis": "control", "samples": rows}, span, .5, "weight"))
        for modified in (
            [{**row, "value": row["tick"] / 8} for row in rows],
            [{**row, "phases": [p / 2 for p in row["phases"]]} for row in rows],
            rows[:-1] + [{**rows[-1], "phases": [2.01, 2.25]}],
            [{**row, "phases": [0, .2]} for row in rows[:-1]] + rows[-1:],
            rows[1:],
        ):
            self.assertFalse(check({"basis": "weight", "samples": modified}, span, .5, "weight"))

    def test_held_blend_requires_contact_free_and_finite_evidence_to_match(self):
        checks = stages.stage_checks
        span = {"start": 0, "end": 2, "fps": 30, "loop": True}
        frames = [{"tick": tick, "floor-clearance-m": 0, "support": {}} for tick in range(9)]
        contact = {"no-plant-reason": "Airborne movement"}
        self.assertTrue(checks.contact_passes(checks.unity_contact_metrics(frames, span), contact))
        frames[4]["support"] = {"left": [0, 0]}
        self.assertFalse(checks.contact_passes(checks.unity_contact_metrics(frames, span), contact))
        frames[4].update({"support": {}, "floor-clearance-m": -.001})
        stats = checks.unity_contact_metrics(frames, span)
        self.assertFalse(checks.contact_passes(stats, contact))
        self.assertTrue(checks.contact_passes(stats, {**contact, "max-penetration-m": .001}))

        rows = [{"tick": i, "value": .5, "phases": [i / 4, None]} for i in range(9)]
        record = {"basis": "weight", "samples": rows}
        self.assertTrue(checks.settled_blend(record, span, .5, "weight", (True, False)))
        self.assertIsNone(checks.settled_blend(record, span, .5, "weight"))
        finite = {**span, "loop": False}
        self.assertIsNone(checks.settled_blend(record, finite, .5, "weight"))
        record["samples"] = [{**row, "phases": None} for row in rows]
        self.assertTrue(checks.settled_blend(record, finite, .5, "weight"))
        self.assertIsNone(checks.settled_blend(None, span, .5, "weight"))

    def test_scene_blend_inventory_must_match_all_planned_intervals(self):
        check = stages.stage_checks.matching_blend_scope
        walk_trot = {"basis": "weight", "from": "walk", "to": "trot"}
        trot_run = {"basis": "control", "from": "trot", "to": "run"}
        scope = {"blend-holds": {"walk-trot": {**walk_trot, "samples": {"0.5": "half"}}}}
        receipt = {"continuous-blends": {"walk-trot": walk_trot}}
        self.assertTrue(check(receipt, scope))
        self.assertTrue(check({"continuous-blends": {}}, {}))
        self.assertFalse(check({}, {}))
        self.assertFalse(check({"continuous-blends": True}, scope))
        receipt["continuous-blends"]["trot-run"] = trot_run
        self.assertFalse(check(receipt, scope))
        scope["blend-holds"]["trot-run"] = {**trot_run, "samples": {"0.5": "run-half"}}
        self.assertTrue(check(receipt, scope))
        receipt["continuous-blends"]["trot-run"] = {**trot_run, "basis": "weight"}
        self.assertFalse(check(receipt, scope))

    def test_reconcile_interrupted_producer_requires_matching_pin(self):
        self.init("references")
        attempt = self.begin("references")
        proof = self.artifact({"observation": "Original tool exited and scratch output was removed"})
        with self.assertRaisesRegex(ValueError, "Original producer"):
            self.call("reconcile", stage="references", attempt=attempt["id"], actor="other",
                      resolution={"method": "cleanup", "reason": "Tool exited", "evidence": proof})
        self.call("reconcile", stage="references", attempt=attempt["id"], actor="author",
                  resolution={"method": "cleanup", "reason": "Tool exited", "evidence": proof})
        self.assertNotEqual(self.begin("references")["id"], attempt["id"])


if __name__ == "__main__":
    unittest.main()
