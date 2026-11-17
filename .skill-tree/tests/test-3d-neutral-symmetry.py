"""Regression checks for exact vertex and face reflection and welded shells."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1]/"common/scripts/3d-neutral-symmetry.py"
spec = spec_from_file_location("neutral_symmetry",SOURCE)
symmetry = module_from_spec(spec)
spec.loader.exec_module(symmetry)


def tetrahedron():
    points = [(-1.,0.,0.),(1.,0.,0.),(0.,1.,0.),(0.,0.,1.)]
    faces = [(0,1,2),(0,3,1),(0,2,3),(1,3,2)]
    edges = [(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)]
    return points,faces,edges


class NeutralGeometryTests(unittest.TestCase):
    def test_closed_reflection_with_faces_that_cross_the_plane(self):
        report = symmetry.audit({"Subject": tetrahedron()}, ["X"], {"Subject"})
        self.assertTrue(report["passed"])
        self.assertFalse(report["integrity"]["Subject"]["boundary_edges"])

    def test_rounding_does_not_hide_a_small_asymmetry(self):
        points,faces,edges = tetrahedron()
        points[0] = (-1.00000001,0.,0.)
        report = symmetry.audit({"Subject":(points,faces,edges)}, ["X"], {"Subject"})
        self.assertFalse(report["passed"])
        self.assertEqual(report["axes"]["X"]["unmatched_vertices"],2)

    def test_different_topology_fails_even_when_every_vertex_matches(self):
        points = [(-1.,0.,0.),(-1.,1.,0.),(-1.,1.,1.),(-1.,0.,1.),
                  (1.,0.,0.),(1.,1.,0.),(1.,1.,1.),(1.,0.,1.)]
        faces = [(0,1,2),(0,2,3),(4,5,7),(5,6,7)]
        assert symmetry.audit({"Subject":(points,faces,[])},["X"],set())["axes"]["X"]["unmatched_vertices"] == 0
        result = symmetry.audit({"Subject": (points,faces,[])},["X"],set())
        self.assertEqual(result["axes"]["X"]["unmatched_faces"],4)
        self.assertFalse(result["passed"])

    def test_joined_halves_cannot_have_duplicate_center_verts(self):
        geometry = [(0.,0.,0.),(0.,1.,0.),(-1.,0.,0.),
                    (0.,0.,0.),(0.,1.,0.),(1.,0.,0.)]
        pairs=[(0,1,2),(3,4,5)]
        result = symmetry.audit({"Subject":(geometry,pairs,[])},["X"],{"Subject"})
        self.assertTrue(result["axes"]["X"]["passed"])
        self.assertEqual(result["integrity"]["Subject"]["duplicate_center_vertices"],2)
        self.assertFalse(result["passed"])

    def test_empty_scope_fails(self):
        self.assertFalse(symmetry.audit({},["X"],set())["passed"])


if __name__ == "__main__":
    unittest.main()
