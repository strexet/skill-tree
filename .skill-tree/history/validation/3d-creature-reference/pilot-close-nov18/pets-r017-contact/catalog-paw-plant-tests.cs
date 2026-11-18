using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using Object = UnityEngine.Object;

public sealed class CatalogPawPlantTests
{
    [Serializable] sealed class Request { public Species[] species; }
    [Serializable] sealed class Species { public string id; public Pad[] pads; public Gait[] gaits; }
    [Serializable] sealed class Pad { public int[] points; }
    [Serializable] sealed class Gait { public string name; public int count; public float distance; public float[] contacts; }

    [UnityTest]
    public IEnumerator SampleCatalogPlants()
    {
        var request = JsonUtility.FromJson<Request>(File.ReadAllText(Environment.GetEnvironmentVariable("CATALOG_PAW_INPUT")));
        Assert.That(Application.unityVersion, Is.EqualTo("6000.3.27f2"));
        Assert.That(SystemInfo.graphicsDeviceType, Is.EqualTo(UnityEngine.Rendering.GraphicsDeviceType.Metal));
        Assert.That(QualitySettings.names[QualitySettings.GetQualityLevel()], Is.EqualTo("PC"));
        Assert.That(UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline?.GetType().Name,
            Is.EqualTo("UniversalRenderPipelineAsset"));
        File.WriteAllText(Environment.GetEnvironmentVariable("CATALOG_PAW_CONTEXT"),
            Application.unityVersion + "\n" + Application.persistentDataPath + "\n" + SystemInfo.graphicsDeviceType + "\nPC URP\n");
        using var output = new StreamWriter(Environment.GetEnvironmentVariable("CATALOG_PAW_OUTPUT"));
        output.WriteLine("species,gait,lod,frame,paw,points,x_m,z_m,sole_m");
        var baker = new Mesh();
        var vertices = new List<Vector3>();
        Assert.That(request.species.Length, Is.EqualTo(2));
        try
        {
            foreach (var specimen in request.species)
            {
                var prefab = Resources.Load<GameObject>("Pets/" + specimen.id);
                Assert.That(prefab, Is.Not.Null);
                var actor = Object.Instantiate(prefab);
                try
                {
                    var animator = actor.GetComponentInChildren<Animator>();
                    Assert.That(animator.avatar.isValid && !animator.avatar.isHuman && !animator.applyRootMotion);
                    animator.speed = 0;
                    animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
                    var correction = actor.GetComponents<MonoBehaviour>().Single(x => x.GetType().Name == "CatalogSurfaceCorrection");
                    var apply = correction.GetType().GetMethod("ApplyCurrentPose");
                    var group = actor.GetComponent<LODGroup>();
                    var levels = group.GetLODs();
                    Assert.That(levels.Length, Is.EqualTo(2));
                    var positions = actor.transform.position;
                    var travel = animator.transform.TransformDirection(Vector3.right);
                    Assert.That(Math.Abs(travel.y), Is.LessThan(.00001f));
                    Assert.That(travel.magnitude, Is.EqualTo(1f).Within(.00001f));
                    yield return null;
                    foreach (int lod in new[] {0, 1})
                    {
                        group.ForceLOD(lod);
                        var skin = levels[lod].renderers.Cast<SkinnedMeshRenderer>().OrderByDescending(x => x.sharedMesh.vertexCount).First();
                        int[][] points = MapPads(specimen, skin, lod);
                        foreach (var gait in specimen.gaits)
                        {
                            Assert.That(gait.count, Is.GreaterThan(10));
                            Assert.That(gait.contacts.Length, Is.EqualTo(gait.count * 20));
                            Assert.That(gait.distance, Is.GreaterThan(0));
                            for (int frame = 0; frame < gait.count - 1; frame++)
                            {
                                float phase = frame / (float)(gait.count - 1);
                                actor.transform.position = positions + travel * (gait.distance * phase);
                                animator.Play(gait.name, 0, phase);
                                animator.Update(0f);
                                var state = animator.GetCurrentAnimatorStateInfo(0);
                                Assert.That(state.shortNameHash, Is.EqualTo(Animator.StringToHash(gait.name)));
                                Assert.That(state.normalizedTime, Is.EqualTo(phase).Within(.0001f));
                                apply.Invoke(correction, null);
                                skin.BakeMesh(baker);
                                baker.GetVertices(vertices);
                                Assert.That(vertices.Count, Is.EqualTo(skin.sharedMesh.vertexCount));
                                for (int paw = 0; paw < 4; paw++)
                                {
                                    float sole = float.PositiveInfinity;
                                    Vector3 sum = Vector3.zero;
                                    foreach (int index in points[paw])
                                    {
                                        var observed = skin.transform.position + skin.transform.rotation * vertices[index];
                                        sum += observed;
                                        sole = Math.Min(sole, observed.y);
                                    }
                                    var center = sum / points[paw].Length;
                                    output.WriteLine(FormattableString.Invariant($"{specimen.id},{gait.name},{lod},{frame},{paw},{points[paw].Length},{center.x:R},{center.z:R},{sole:R}"));
                                }
                                if ((frame & 15) == 15) yield return null;
                            }
                            Console.WriteLine(FormattableString.Invariant($"Catalog paw samples {specimen.id}/{gait.name}/LOD{lod} travel {travel.x:R} {travel.z:R}"));
                            output.Flush();
                        }
                    }
                }
                finally { Object.Destroy(actor); }
                yield return null;
            }
        }
        finally { Object.Destroy(baker); }
    }

    static int[][] MapPads(Species specimen, SkinnedMeshRenderer skin, int lod)
    {
        var uv = new List<Vector2>();
        skin.sharedMesh.GetUVs(specimen.id == "cat" ? 0 : 1, uv);
        Assert.That(uv.Count, Is.EqualTo(skin.sharedMesh.vertexCount));
        var byPoint = new Dictionary<int, int>();
        for (int index = 0; index < uv.Count; index++)
        {
            int id = Mathf.RoundToInt(uv[index].x * 1024) + 1024 * Mathf.RoundToInt(uv[index].y * 1024);
            byPoint.TryAdd(id, index);
        }
        var result = specimen.pads.Select(pad => pad.points.Where(byPoint.ContainsKey).Select(x => byPoint[x]).ToArray()).ToArray();
        Assert.That(result.Length, Is.EqualTo(4));
        foreach (var pad in result)
        {
            if (lod == 0) Assert.That(pad.Length, Is.EqualTo(65));
            else Assert.That(pad.Length, Is.GreaterThanOrEqualTo(8));
        }
        return result;
    }
}
