"""Run within the pinned Blender binary and export the disposable lantern model."""
from __future__ import annotations

import hashlib
import json
from math import cos, pi, sin
import os
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def empty(root, name, location=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = root
    obj.location = location
    obj.empty_display_type = 'PLAIN_AXES'
    return obj


def cylinder(root, name, radius, depth, z):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius, depth=depth, location=(0, 0, z))
    obj = bpy.context.object
    obj.name = name
    obj.parent = root
    return obj


def grip(root):
    vertices = []
    faces = []
    for index in range(17):
        angle = pi * index / 16
        for radius, y in ((0.077, -0.012), (0.055, -0.012), (0.077, 0.012), (0.055, 0.012)):
            vertices.append((radius * cos(angle), y, 0.245 + radius * sin(angle)))
    for index in range(16):
        first = index * 4
        for a, b in ((0, 1), (1, 3), (3, 2), (2, 0)):
            faces.append((first + a, first + b, first + b + 4, first + a + 4))
    faces.extend(((0, 2, 3, 1), (64, 65, 67, 66)))
    mesh = bpy.data.meshes.new('CarryGrip')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new('CarryGrip', mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = root
    return obj


def round_vector(values):
    return [round(value, 6) for value in values]


def inventory(objects, socket_names):
    bpy.context.view_layer.update()
    meshes = [obj for obj in objects if obj.type == 'MESH']
    vertices = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    require(meshes and vertices, 'The lantern does not contain geometry')
    dimensions = [max(point[index] for point in vertices) - min(point[index] for point in vertices)
                  for index in range(3)]
    sockets = {obj.name: round_vector(obj.matrix_world.translation) for obj in objects if obj.name in socket_names}
    require(set(sockets) == set(socket_names), 'The lantern is missing an exact attachment socket')
    socket_distance = (Vector(sockets['GripSocket']) - Vector(sockets['BeltSocket'])).length
    return {'mesh_names': sorted(obj.name for obj in meshes), 'dimensions': round_vector(dimensions),
            'vertices': sum(len(obj.data.vertices) for obj in meshes), 'sockets': sockets,
            'socket_distance': round(socket_distance, 6)}


def create(model):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1.0
    root = empty(None, 'DirectorLantern')
    cylinder(root, 'LanternFoot', 0.105, 0.04, 0.02)
    cylinder(root, 'LanternBody', 0.095, 0.15, 0.115)
    cylinder(root, 'LanternCap', 0.105, 0.055, 0.2175)
    grip(root)
    for name, location in model['sockets'].items():
        empty(root, name, location)
    return list(bpy.context.scene.objects)


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    require(len(args) == 1, 'Select the immutable fixture manifest')
    manifest = Path(args[0])
    model = json.loads(manifest.read_bytes())['model']
    require(model['asset'] == 'DirectorLantern.fbx' and set(model['sockets']) == {'GripSocket', 'BeltSocket'},
            'Unsupported exact lantern asset')
    output = Path(model['asset'])
    observations = Path('blender-native.json')
    require(not output.exists() and not observations.exists(), 'Fresh Blender observations are required')
    objects = create(model)
    pre_export = inventory(objects, model['sockets'])
    for obj in objects:
        obj.select_set(True)
    result = bpy.ops.export_scene.fbx(
        filepath=str(output.resolve()), check_existing=False, use_selection=True,
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', use_space_transform=True,
        axis_forward='-Z', axis_up='Y', object_types={'EMPTY', 'MESH'}, use_custom_props=False,
        bake_anim=False, add_leaf_bones=False, use_metadata=False,
    )
    require(result == {'FINISHED'} and output.is_file(), 'Blender did not produce the expected FBX')
    exported_sha = digest(output)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imported = bpy.ops.import_scene.fbx(filepath=str(output.resolve()))
    require(imported == {'FINISHED'}, 'Blender could not reimport the exact exported bytes')
    post_import = inventory(list(bpy.context.scene.objects), model['sockets'])
    require(pre_export['mesh_names'] == post_import['mesh_names']
            and pre_export['vertices'] == post_import['vertices'], 'Round trip altered mesh identity')
    require(digest(output) == exported_sha, 'The inspection altered the exported FBX')
    write(observations, {
        'schema': 1, 'kind': 'director-lantern-blender-runtime',
        'pid': os.getpid(), 'version': '.'.join(map(str, bpy.app.version)),
        'build': bpy.app.build_hash.decode(), 'manifest_sha256': digest(manifest),
        'artifact': {'path': model['asset'], 'sha256': exported_sha, 'bytes': output.stat().st_size},
        'pre_export': pre_export, 'native_reimport': post_import,
    })
    print('DIRECTOR_LANTERN_EXPORT_VERIFIED')


if __name__ == '__main__':
    main()
