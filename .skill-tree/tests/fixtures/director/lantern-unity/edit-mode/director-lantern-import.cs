using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;

namespace SkillTreeSandbox.Director
{
    public sealed class DirectorLanternImport
    {
        private const string Candidate = "Assets/DirectorLanternFixture/Resources/DirectorLantern.fbx";
        private const string WallPrefab = "Assets/SkillTree3D/LanternPilot/Lantern.prefab";
        private const string WallModel = "Assets/SkillTree3D/LanternPilot/Imported/prop.pilot-lantern/model.fbx";

        [Test]
        public void RepeatedImportPreservesGuidMeshAndMetricSockets()
        {
            string initialGuid = AssetDatabase.AssetPathToGUID(Candidate);
            Assert.That(initialGuid, Does.Match("^[a-f0-9]{32}$"));
            string initialMeta = File.ReadAllText(Candidate + ".meta");
            long[] first = ReimportCandidate(initialGuid);
            long[] again = ReimportCandidate(initialGuid);
            Assert.That(again, Is.EqualTo(first));
            Assert.That(File.ReadAllText(Candidate + ".meta"), Is.EqualTo(initialMeta));
            string privateResults = Path.Combine(Application.persistentDataPath, "TestResults.xml");
            Debug.Log($"DirectorLanternImport observed guid={initialGuid} stable_meshes={again.Length} private_results={privateResults}");
        }

        [Test]
        public void WrongTargetAndWallMountedControlRejectAttachment()
        {
            var wall = AssetDatabase.LoadAssetAtPath<GameObject>(WallPrefab);
            Assert.That(wall, Is.Not.Null);
            Assert.That(AssetDatabase.AssetPathToGUID(WallPrefab), Is.EqualTo("26676c7dcdcf941d99dda41b1fb88b2e"));
            Assert.That(AssetDatabase.AssetPathToGUID(WallModel), Is.EqualTo("e907cc9d7b853474ea0b4843cef2a681"));
            Assert.That(AssetImporter.GetAtPath(WallModel), Is.TypeOf<ModelImporter>());
            Assert.That(wall.GetComponentsInChildren<Transform>(true).Any(node => node.name == "MountOrigin"), Is.True);

            var hand = LanternRevision.Load("hand");
            var belt = LanternRevision.Load("belt");
            Assert.Throws<InvalidDataException>(() => hand.ResolveSocket(wall.transform));
            Assert.Throws<InvalidDataException>(() => belt.ResolveSocket(wall.transform));

            var carried = AssetDatabase.LoadAssetAtPath<GameObject>(Candidate);
            Assert.That(carried, Is.Not.Null);
            var wrongTarget = new LanternRevision { attachment = "hand", socket = "BeltSocket", revision = hand.revision };
            Assert.Throws<InvalidDataException>(() => wrongTarget.ResolveSocket(carried.transform));
            var grip = hand.ResolveSocket(carried.transform);
            var alternate = belt.ResolveSocket(carried.transform);
            Assert.That(grip.GetInstanceID(), Is.Not.EqualTo(alternate.GetInstanceID()));
            Debug.Log("DirectorLanternImport observed wrong_target=rejected wall_attachment=rejected");
        }

        private static long[] ReimportCandidate(string expectedGuid)
        {
            AssetDatabase.ImportAsset(Candidate, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
            Assert.That(AssetDatabase.AssetPathToGUID(Candidate), Is.EqualTo(expectedGuid));
            Assert.That(AssetImporter.GetAtPath(Candidate), Is.TypeOf<ModelImporter>());
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(Candidate);
            Assert.That(asset, Is.Not.Null);
            var grip = LanternRevision.Load("hand").ResolveSocket(asset.transform);
            var belt = LanternRevision.Load("belt").ResolveSocket(asset.transform);
            Assert.That(Vector3.Distance(asset.transform.position, grip.position), Is.EqualTo(0.28f).Within(0.025f));
            Assert.That(Vector3.Distance(asset.transform.position, belt.position), Is.EqualTo(0.149f).Within(0.025f));
            Assert.That(Vector3.Distance(grip.position, belt.position), Is.GreaterThan(0.1f));
            var meshes = asset.GetComponentsInChildren<MeshFilter>(true).Where(filter => filter.sharedMesh != null).ToArray();
            Assert.That(meshes, Is.Not.Empty);
            return meshes.Select(filter =>
            {
                Assert.That(filter.sharedMesh.vertexCount, Is.GreaterThan(2));
                Assert.That(AssetDatabase.TryGetGUIDAndLocalFileIdentifier(filter.sharedMesh, out string guid, out long id), Is.True);
                Assert.That(guid, Is.EqualTo(expectedGuid));
                return id;
            }).OrderBy(id => id).ToArray();
        }
    }
}
