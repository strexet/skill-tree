using System;
using System.IO;
using System.Linq;
using UnityEngine;

namespace SkillTreeSandbox.Director
{
    [Serializable]
    public sealed class LanternRevision
    {
        public string attachment;
        public string socket;
        public string revision;

        public static LanternRevision Load(string attachment)
        {
            TextAsset wrapper = Resources.Load<TextAsset>("lantern-" + attachment);
            if (wrapper == null)
                throw new InvalidDataException("Missing reviewed lantern wrapper: " + attachment);

            LanternRevision result = JsonUtility.FromJson<LanternRevision>(wrapper.text);
            if (result == null || result.attachment != attachment || string.IsNullOrEmpty(result.revision))
                throw new InvalidDataException("Lantern wrapper does not identify the selected revision.");

            return result;
        }

        public Transform ResolveSocket(Transform model)
        {
            string expected = attachment switch
            {
                "hand" => "GripSocket",
                "belt" => "BeltSocket",
                _ => null,
            };
            if (expected == null || socket != expected)
                throw new InvalidDataException("Lantern attachment targets the wrong socket.");

            Transform[] matches = model.GetComponentsInChildren<Transform>(true)
                .Where(candidate => candidate != model && candidate.name == expected).ToArray();
            if (matches.Length != 1)
                throw new InvalidDataException("Lantern model is missing a unique " + expected + ".");

            return matches[0];
        }
    }

    public sealed class DirectorLanternPickup : MonoBehaviour
    {
        private Collider collector;
        private Transform mount;
        private Transform model;
        private Transform socket;

        public bool IsCarried { get; private set; }

        public void Configure(Collider allowedCollector, Transform carryMount, Transform lantern, LanternRevision revision)
        {
            socket = revision.ResolveSocket(lantern);
            collector = allowedCollector;
            mount = carryMount;
            model = lantern;
        }

        private void OnTriggerEnter(Collider other)
        {
            if (other != collector || IsCarried)
                return;

            model.SetParent(mount, true);
            model.rotation = mount.rotation * Quaternion.Inverse(socket.rotation) * model.rotation;
            model.position += mount.position - socket.position;
            IsCarried = true;
        }
    }
}
