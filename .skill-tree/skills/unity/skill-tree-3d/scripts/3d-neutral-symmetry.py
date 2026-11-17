"""Verify exact mirrored Blender mesh geometry in the declared neutral pose."""
from argparse import ArgumentParser
from collections import Counter
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import sys


AXES = "XYZ"


def canonical_ring(vertices):
    """Identify a geometric face regardless of cyclic starting point or winding."""
    start = vertices.index(min(vertices))
    ring = vertices[start:] + vertices[:start]
    return min(ring, ring[:1] + ring[:0:-1])


def reflect(vertex, axis):
    return vertex[:axis] + (-vertex[axis],) + vertex[axis + 1:]


def shell_integrity(points, faces, edges, axes):
    incidence = Counter()
    degenerate_faces = 0
    for face in faces:
        degenerate_faces += len(face) < 3 or len({points[i] for i in face}) != len(face)
        incidence.update(tuple(sorted((a, b))) for a, b in zip(face, face[1:] + face[:1]))
    tested_edges = set(incidence) | {tuple(sorted(edge)) for edge in edges}
    center = Counter(p for p in points if any(p[AXES.index(axis)] == 0.0 for axis in axes))
    result = {
        "boundary_edges": sum(incidence[e] == 1 for e in tested_edges),
        "nonmanifold_edges": sum(incidence[e] not in (1, 2) for e in tested_edges),
        "duplicate_center_vertices": sum(n - 1 for n in center.values()),
        "degenerate_faces": degenerate_faces,
    }
    result["passed"] = bool(faces) and not any(result.values())
    return result


def audit(subjects, axes, closed_subjects):
    """Compare complete geometry and ordered polygon connectivity in one frame."""
    vertices = Counter()
    faces = Counter()
    edges = Counter()
    coordinate_ids = {}
    integrity = {}
    invalid_vertices = 0
    for name, (points, polygons, links) in subjects.items():
        invalid_vertices += sum(any(not isfinite(value) for value in p) for p in points)
        points_ids = tuple(coordinate_ids.setdefault(p, len(coordinate_ids)) for p in points)
        vertices.update(points_ids)
        faces.update(canonical_ring(tuple(points_ids[i] for i in face)) for face in polygons)
        edges.update(tuple(sorted((points_ids[a], points_ids[b]))) for a, b in links)
        if name in closed_subjects:
            integrity[name] = shell_integrity(points, polygons, links, axes)
    reflection = {}
    for axis in axes:
        lookup = [coordinate_ids.get(reflect(p, AXES.index(axis)), -1) for p in coordinate_ids]
        opposite_vertices = Counter({reflected: vertices[i] for i, reflected in enumerate(lookup) if reflected >= 0})
        opposite_faces = Counter()
        opposite_edges = Counter()
        for face, count in faces.items():
            opposite = tuple(lookup[i] for i in face)
            if min(opposite) >= 0:
                opposite_faces[canonical_ring(opposite)] += count
        for (a, b), count in edges.items():
            if min(lookup[a], lookup[b]) >= 0:
                opposite_edges[tuple(sorted((lookup[a], lookup[b])))] += count
        result = {
            "unmatched_vertices": sum((vertices - opposite_vertices).values()),
            "unmatched_faces": sum((faces - opposite_faces).values()),
            "unmatched_edges": sum((edges - opposite_edges).values()),
        }
        result["passed"] = bool(vertices) and not invalid_vertices and not any(result.values())
        reflection[axis] = result
    return {"axes": reflection, "integrity": integrity, "vertices": vertices.total(),
            "faces": faces.total(), "invalid_vertices": invalid_vertices,
            "passed": all(check["passed"] for check in (*reflection.values(), *integrity.values()))}


def matrix_to_frame(obj, origin):
    from mathutils import Matrix

    if origin is None:
        return obj.matrix_world
    if obj == origin:
        return Matrix.Identity(4)
    return origin.matrix_world.inverted() @ obj.matrix_world


def mesh_records(subjects, frame, bpy, evaluated):
    dependency = bpy.context.evaluated_depsgraph_get() if evaluated else None
    records = {}
    for obj in subjects:
        current = obj.evaluated_get(dependency) if evaluated else obj
        coordinates = matrix_to_frame(current, frame)
        mesh = current.data
        records[obj.name] = (
            [tuple(coordinates @ vertex.co) for vertex in mesh.vertices],
            [tuple(face.vertices) for face in mesh.polygons],
            [tuple(edge.vertices) for edge in mesh.edges],
        )
    return records


def main(argv):
    import bpy

    cli = ArgumentParser(description=__doc__)
    cli.add_argument("--axes", nargs="+", choices=tuple(AXES), required=True)
    cli.add_argument("--subjects", nargs="+", required=True)
    cli.add_argument("--closed-subjects", nargs="+", default=[])
    cli.add_argument("--symmetry-frame", default="world", help="World origin or an exact Blender object name.")
    cli.add_argument("--scene", help="Exact scene containing the neutral authoring objects.")
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args(argv)
    if len(set(args.axes)) != len(args.axes) or len(set(args.subjects)) != len(args.subjects):
        cli.error("Declare each symmetry plane and mesh exactly once.")
    if not set(args.closed_subjects) <= set(args.subjects):
        cli.error("Continuous shells must belong to the declared scope.")
    if args.scene:
        bpy.context.window.scene = bpy.data.scenes[args.scene]
    scene = bpy.context.scene
    subjects = [scene.objects[name] for name in args.subjects]
    if any(obj.type != "MESH" for obj in subjects):
        cli.error("Every subject must be a mesh.")
    frame = None if args.symmetry_frame == "world" else scene.objects[args.symmetry_frame]
    selected = set(args.closed_subjects)
    asset = Path(bpy.data.filepath)
    bind = audit(mesh_records(subjects, frame, bpy, False), args.axes, selected)
    saved = [(obj.data, obj.data.pose_position) for obj in scene.objects if obj.type == "ARMATURE"]
    try:
        for armature, _ in saved:
            armature.pose_position = "REST"
        bpy.context.view_layer.update()
        evaluated = audit(mesh_records(subjects, frame, bpy, True), args.axes, selected)
    finally:
        for armature, state in saved:
            armature.pose_position = state
    report = {"schema": 1, "kind": "neutral-geometry-symmetry",
              "asset_sha256": sha256(asset.read_bytes()).hexdigest(),
              "scene": scene.name, "symmetry_frame": args.symmetry_frame, "axes": args.axes,
              "subjects": args.subjects, "closed_subjects": args.closed_subjects,
              "checks": {"bind": bind, "evaluated-neutral": evaluated},
              "passed": bind["passed"] and evaluated["passed"]}
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[sys.argv.index("--") + 1:]))
