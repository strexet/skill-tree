using System.Collections;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
#if UNITY_EDITOR
using UnityEditor.SceneManagement;
#endif

namespace SkillTreeSandbox.Director
{
    public sealed class DirectorLanternCarry
    {
        private const string CaveAsset = "Assets/SkillTree3D/LanternPilot/Scenes/PilotInterior.unity";
        private Scene cave;

        [UnityTest]
        public IEnumerator HandPickupAndCarryThroughCave() => ObserveCarry("hand");

        [UnityTest]
        public IEnumerator BeltPickupAndCarryThroughCave() => ObserveCarry("belt");

        [UnityTearDown]
        public IEnumerator UnloadCave()
        {
            if (cave.IsValid() && cave.isLoaded)
                yield return SceneManager.UnloadSceneAsync(cave);
        }

        private IEnumerator ObserveCarry(string attachment)
        {
#if UNITY_EDITOR
            Assert.That(Application.isPlaying, Is.True);
            Assert.That(SceneManager.GetSceneByPath(CaveAsset).isLoaded, Is.False);
            cave = EditorSceneManager.LoadSceneInPlayMode(CaveAsset, new LoadSceneParameters(LoadSceneMode.Additive));
            Assert.That(cave.path, Is.EqualTo(CaveAsset));
            yield return null;

            Transform route = cave.GetRootGameObjects().SelectMany(root => root.GetComponentsInChildren<Transform>(true))
                .Single(node => node.name == "route.main");
            Transform[] stops = { route.Find("entry"), route.Find("threshold"), route.Find("turn"), route.Find("exit") };
            Assert.That(stops.All(stop => stop != null), Is.True, "The cave route needs all four native waypoints.");
            Vector3 pickupPosition = stops[0].position + Vector3.up * 0.5f;

            LanternRevision revision = LanternRevision.Load(attachment);
            var modelAsset = Resources.Load<GameObject>("DirectorLantern");
            Assert.That(modelAsset, Is.Not.Null);
            Transform model = Object.Instantiate(modelAsset).transform;
            SceneManager.MoveGameObjectToScene(model.gameObject, cave);
            model.position = pickupPosition;
            Transform socket = revision.ResolveSocket(model);
            string alternate = attachment == "hand" ? "belt" : "hand";
            Transform alternateSocket = LanternRevision.Load(alternate).ResolveSocket(model);

            var actor = new GameObject("DirectorFixtureCarrier");
            SceneManager.MoveGameObjectToScene(actor, cave);
            Rigidbody movement = actor.AddComponent<Rigidbody>();
            movement.isKinematic = true;
            var collector = actor.AddComponent<SphereCollider>();
            collector.radius = 0.14f;
            Transform hand = AddMount(actor.transform, "HandMount", new Vector3(0.32f, 0.36f, 0.12f));
            Transform belt = AddMount(actor.transform, "BeltMount", new Vector3(-0.25f, 0.13f, 0.0f));
            Transform mount = attachment == "hand" ? hand : belt;
            Transform otherMount = attachment == "hand" ? belt : hand;
            actor.transform.position = pickupPosition - Vector3.forward * 1.2f;

            var stand = new GameObject("DirectorFixturePickup");
            SceneManager.MoveGameObjectToScene(stand, cave);
            stand.transform.position = pickupPosition;
            var trigger = stand.AddComponent<SphereCollider>();
            trigger.radius = 0.25f;
            trigger.isTrigger = true;
            var pickup = stand.AddComponent<DirectorLanternPickup>();
            pickup.Configure(collector, mount, model, revision);

            Physics.SyncTransforms();
            yield return new WaitForFixedUpdate();
            Assert.That(pickup.IsCarried, Is.False, "The pickup must wait for the assigned collector to enter.");
            Assert.That(model.parent, Is.Null);

            actor.transform.position = pickupPosition;
            Physics.SyncTransforms();
            for (int attempt = 0; attempt < 5 && !pickup.IsCarried; attempt++)
                yield return new WaitForFixedUpdate();
            Assert.That(pickup.IsCarried, Is.True, "The Unity trigger must cause the pickup.");
            AssertAttached(model, socket, alternateSocket, mount, otherMount);

            for (int index = 1; index < stops.Length; index++)
            {
                Vector3 prior = actor.transform.position;
                Vector3 destination = stops[index].position + Vector3.up * 0.5f;
                Assert.That(Vector3.Distance(prior, destination), Is.GreaterThan(0.75f));
                actor.transform.rotation = Quaternion.LookRotation(destination - prior);
                for (int step = 1; step <= 4; step++)
                {
                    actor.transform.position = Vector3.Lerp(prior, destination, step / 4.0f);
                    yield return null;
                    AssertAttached(model, socket, alternateSocket, mount, otherMount);
                }
                Assert.That(Vector3.Distance(actor.transform.position, destination), Is.LessThan(0.002f));
            }

            string privateResults = Path.Combine(Application.persistentDataPath, "TestResults.xml");
            Debug.Log($"DirectorLanternCarry observed attachment={attachment} revision={revision.revision} socket={socket.name} route=entry,threshold,turn,exit private_results={privateResults}");
#else
            Assert.Fail("The carried-lantern fixture requires the owned PlayMode Editor recipe.");
            yield break;
#endif
        }

        private static Transform AddMount(Transform actor, string mountName, Vector3 position)
        {
            Transform mount = new GameObject(mountName).transform;
            mount.SetParent(actor, false);
            mount.localPosition = position;
            return mount;
        }

        private static void AssertAttached(Transform model, Transform socket, Transform alternateSocket, Transform mount, Transform otherMount)
        {
            Assert.That(model.parent, Is.SameAs(mount));
            Assert.That(Vector3.Distance(socket.position, mount.position), Is.LessThan(0.002f));
            Assert.That(Quaternion.Angle(socket.rotation, mount.rotation), Is.LessThan(0.1f));
            Assert.That(Vector3.Distance(alternateSocket.position, mount.position), Is.GreaterThan(0.1f));
            Assert.That(Vector3.Distance(socket.position, otherMount.position), Is.GreaterThan(0.2f));
        }
    }
}
