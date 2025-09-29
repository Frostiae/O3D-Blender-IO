from .o3d_types import *
from bpy.types import Object


# Y-Up space --> Blender Z-up space
# X,Y,Z --> X,-Z,Y

def convert_pos(x): return Vector([x[0], x[2], x[1]])
def convert_quat(q): return Quaternion([q[3], q[0], -q[2], q[1]])
def convert_scale(s): return Vector([s[0], s[2], s[1]])
def convert_matrix(m):
    return Matrix([
        [m[0], m[8], m[4], m[12]],
        [m[2], m[10], m[6], m[14]],
        [m[1], m[9], m[5], m[13]],
        [m[3], m[11], m[7], m[15]],
    ])


def create_blender_mesh(name: str, gmo: GMObject, o3d: Object3D) -> Object:
    """
    Create a blender mesh from the given GMObject.
    """
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(mesh.name, mesh)
    col = bpy.data.collections["Collection"]
    col.objects.link(obj)
    
    bpy.context.view_layer.objects.active = obj
    
    vertices = [convert_pos(v) for v in gmo.vertices]
    mesh.from_pydata(vertices, [], gmo.indices)
    # TODO: Set normals from gmo.normals
    mesh.validate()
    mesh.update()

    if gmo.gm_type != 1 and len(gmo.transform) > 0:
        obj.matrix_local = convert_matrix(gmo.transform)

    # Non-bone animation
    if len(gmo.frames) > 0:
        obj.rotation_mode = 'QUATERNION'
        for i, frame in enumerate(gmo.frames):
            obj.location = convert_pos(frame.pos)
            obj.rotation_quaternion = convert_quat(frame.rot)

            obj.keyframe_insert(data_path="location", frame=i)
            obj.keyframe_insert(data_path="rotation_quaternion", frame=i)

    if o3d.frame_count > 0:
        bpy.context.scene.frame_start = 0
        bpy.context.scene.frame_end = o3d.frame_count

    uv_layer = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            vert_index = mesh.loops[loop_index].vertex_index
            uv_layer.data[loop_index].uv = gmo.uvs[vert_index]

    # Make new materials
    for mat in gmo.materials:
        new_mat = bpy.data.materials.get(mat.texture_name)
        if new_mat is None:
            new_mat = bpy.data.materials.new(mat.texture_name)
            new_mat.use_nodes = True

            # Load texture from model path ./Texture
            bsdf_node = new_mat.node_tree.nodes[0]
            bsdf_node.inputs["Roughness"].default_value = 1.0
            bsdf_node.inputs["IOR"].default_value = 1.0
            texture_path = o3d.path[:o3d.path.rfind("\\")] + "\\Texture\\" + mat.texture_name

            try:
                image = bpy.data.images.load(texture_path)
                texture_node = new_mat.node_tree.nodes.new("ShaderNodeTexImage")
                texture_node.image = image
                new_mat.node_tree.links.new(texture_node.outputs["Color"], bsdf_node.inputs["Base Color"])

                if gmo.opacity:
                    new_mat.node_tree.links.new(texture_node.outputs["Alpha"], bsdf_node.inputs["Alpha"])
            except RuntimeError:
                print("Texture not found:", texture_path)

        mesh.materials.append(new_mat)

    # Set material indices for each face
    start = 0
    for mat_block in gmo.material_blocks:
        for i in range(start, start + mat_block.primitive_count):
            mesh.polygons[min(i, len(mesh.polygons) - 1)].material_index = mat_block.material_id
        start += mat_block.primitive_count

    mesh.validate()
    mesh.update()

    gmo.blender_obj = obj
    return obj


def create_blender_armature(name : str, chr : Skeleton, gmobjects : list[GMObject]):
        arm_data = bpy.data.armatures.new(name)
        arm_obj = bpy.data.objects.new(name, arm_data)

        # Bone display
        arm_obj.show_in_front = True
        arm_obj.data.show_names = True
        arm_obj.data.relation_line_position = "HEAD"

        SPECIAL_COLLECTION = "o3d_not_exported"
        if SPECIAL_COLLECTION not in bpy.data.collections:
            bpy.data.collections.new(SPECIAL_COLLECTION)
            bpy.data.scenes[bpy.context.scene.name].collection.children.link(bpy.data.collections[SPECIAL_COLLECTION])
            bpy.data.collections[SPECIAL_COLLECTION].hide_viewport = True
            bpy.data.collections[SPECIAL_COLLECTION].hide_render = True

        # Create an icosphere, and assign it to the collection
        bpy.ops.mesh.primitive_ico_sphere_add(
            radius=1, 
            enter_editmode=False, 
            align='WORLD', 
            location=(0, 0, 0), 
            scale=(1, 1, 1)
        )
        bpy.data.collections[SPECIAL_COLLECTION].objects.link(bpy.context.object)
        bone_shape = bpy.context.object.name
        bpy.context.collection.objects.unlink(bpy.context.object)

        bpy.context.collection.objects.link(arm_obj)

        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode="EDIT")

        for bone in chr.bones:
            eb = arm_data.edit_bones.new(bone.name)
            bone.blender_bone = eb
            eb.use_connect = False

            # Position of the bone in armature space
            mat = bone.editbone_arma_mat
            eb.head = mat @ Vector((0, 0, 0))
            eb.tail = mat @ Vector((0, 0.1, 0))
            eb.align_roll(mat @ Vector((0, 0, 1)) - eb.head)

        # Set all bone parents
        for bone in chr.bones:
            if bone.parent_id != -1:
                bone.blender_bone.parent = chr.bones[bone.parent_id].blender_bone

        # Do pose bones
        bpy.ops.object.mode_set(mode="OBJECT")

        for bone in chr.bones:
            pbone = arm_obj.pose.bones.get(bone.name)

            def trs(b: Bone):
                t, r, s = b.base_trs
                return (
                    b.rotation_after @ t,
                    b.rotation_after @ r @ b.rotation_before,
                    s
                )

            t, r, s = trs(bone)
            et, er = bone.editbone_trans, bone.editbone_rot
            pbone.location = er.conjugated() @ (t - et)
            pbone.rotation_mode = "QUATERNION"
            pbone.rotation_quaternion = er.conjugated() @ r
            
            pbone.custom_shape = bpy.data.objects[bone_shape]
            armature_min_dim = min([arm_obj.dimensions[0] /
                                    arm_obj.scale[0], arm_obj.dimensions[1] /
                                    arm_obj.scale[1], arm_obj.dimensions[2] /
                                    arm_obj.scale[2]])
            pbone.custom_shape_scale_xyz = Vector([armature_min_dim * 0.05] * 3)
            pbone.use_custom_shape_bone_size = False

        # Set any gameobject parents to bones
        for gmo in gmobjects:
            if gmo.parent_id != -1 and gmo.parent_gm_type == 2:
                bone = chr.bones[gmo.parent_id]
                gmo.blender_obj.parent = arm_obj
                gmo.blender_obj.parent_type = "BONE"
                gmo.blender_obj.parent_bone = bone.name

                t, r, s = convert_matrix(gmo.transform).decompose()
                t, r, s = (gmo.rotation_after @ t, gmo.rotation_after @ r @ gmo.rotation_before, s)
                gmo.blender_obj.rotation_mode = "QUATERNION"
                gmo.blender_obj.location = t
                gmo.blender_obj.rotation_quaternion = r
                gmo.blender_obj.scale = s

        # Link the armature to the mesh
        for gmo in gmobjects:
            if gmo.gm_type != 1: continue

            obj = gmo.blender_obj
            mod = obj.modifiers.new(name="ArmatureMod", type="ARMATURE")
            mod.object = arm_obj

            bone_ids = []
            if gmo.used_bone_count > 0:
                bone_ids = gmo.used_bones
            else:
                bone_ids = [i for i in range(28)]

            for block in gmo.material_blocks:
                if block.used_bone_count > 0:
                    bone_ids = block.used_bones                

                for bone_id in bone_ids:
                    if bone_id < len(chr.bones) and chr.bones[bone_id].name not in obj.vertex_groups:
                        obj.vertex_groups.new(name=chr.bones[bone_id].name)

                for i in range(block.primitive_count * 3):
                    v_id = block.start_vertex + i
                    vertex_id = gmo.indices[v_id // 3][v_id % 3]
                    weight1, weight2 = gmo.weights[vertex_id]
                    bone1, bone2 = gmo.bone_ids[vertex_id]

                    if weight1 != 0:
                        obj.vertex_groups[chr.bones[bone_ids[bone1 // 3]].name].add([vertex_id], weight1, "REPLACE")
                    if weight2 != 0:
                        obj.vertex_groups[chr.bones[bone_ids[bone2 // 3]].name].add([vertex_id], weight2, "REPLACE")

        chr.blender_armature = arm_obj


def create_blender_action(chr: Skeleton, ani: Motion):
        action = bpy.data.actions.new(name=ani.name)
        if not chr.blender_armature.animation_data:
            chr.blender_armature.animation_data_create()

        chr.blender_armature.animation_data.action = action

        for i, frame in enumerate(ani.frames):
            bone = chr.bones[i]
            pbone = chr.blender_armature.pose.bones.get(bone.name)
            if not pbone:
                continue

            for j, f in enumerate(frame.frames):
                pos_adj = (f.pos[0], f.pos[1], -f.pos[2])
                pos_val = convert_pos(pos_adj)
                pos_val[1] = -pos_val[1]
                pos_val = bone.rotation_after @ pos_val

                rot_adj = (-f.rot[0], -f.rot[1], f.rot[2], f.rot[3])
                rot_val = convert_quat(rot_adj)
                rot_val = bone.rotation_after @ rot_val @ bone.rotation_before

                edit_trans, edit_rot = bone.editbone_trans, bone.editbone_rot
                edit_rot_inv = edit_rot.conjugated()
                pos = edit_rot_inv @ (pos_val - edit_trans)

                rot = edit_rot_inv @ rot_val

                pbone.location = pos
                pbone.rotation_quaternion = rot

                pbone.keyframe_insert(data_path="location", frame=j)
                pbone.keyframe_insert(data_path="rotation_quaternion", frame=j)

            #bpy.context.scene.frame_start = 0
            #bpy.context.scene.frame_end = len(frame.frames) - 1
