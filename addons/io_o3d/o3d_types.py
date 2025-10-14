import bpy
from bpy.types import Object
from mathutils import Vector, Quaternion, Matrix

class Skeleton:
    def __init__(self):
        self.oid = 0
        self.bone_count = 0
        self.bones : list[Bone] = []
        self.send_VS = False
        self.local_RH = []
        self.local_LH = []
        self.local_shield = []
        self.local_knuckle = []
        self.events = []
        self.event_parent_ids = []
        self.blender_armature = None


class TMAnimation:
    def __init__(self):
        self.rot = (0, 0, 0, 0) # its a quaternion
        self.pos = (0, 0, 0)


class Bone:
    def __init__(self):
        self.parent_id = 0
        self.name = ""
        self.local_transform = []
        self.transform = []
        self.inverse_transform = []

        self.blender_bone : bpy.types.EditBone = None
        self.children : list[Bone] = []
        self.children_gmos : list[GMObject] = []
        self.base_trs = (
            Vector((0, 0, 0)),
            Quaternion((1, 0, 0, 0)),
            Vector((1, 1, 1)),
        )
        self.editbone_arma_mat = Matrix.Identity(4)
        self.rotation_before = Quaternion((1, 0, 0, 0))
        self.rotation_after = Quaternion((1, 0, 0, 0))
        self.editbone_trans = Vector((0, 0, 0))
        self.editbone_rot = Quaternion((1, 0, 0, 0))


class BoneFrame:
    def __init__(self):
        self.frames : list[TMAnimation] = []
        self.transform = []


class MotionAttribute:
    def __init__(self):
        self.type = 0
        self.sound_id = 0
        self.frame = 0


class Motion:
    def __init__(self):
        self.name = ""
        self.oid = 0
        self.perslerp = 0.5
        self.bone_count = 0
        self.frame_count = 0
        self.event_count = 0
        self.paths = []
        self.events = []
        self.attributes : list[MotionAttribute] = []
        self.bones : list[Bone] = []
        self.animations : list[TMAnimation] = []
        self.frames : list[BoneFrame] = []


class Material:
    def __init__(self):
        self.texture_name = ""
        self.diffuse = (1, 1, 1, 1)
        self.ambient = (1, 1, 1, 1)
        self.specular = (1, 1, 1, 1)
        self.emissive = (1, 1, 1, 1)
        self.power = 0


class MaterialBlock:
    def __init__(self):
        self.start_vertex = 0
        self.primitive_count = 0
        self.material_id = 0
        self.amount = 0
        self.used_bone_count = 0
        self.effect = 0
        self.used_bones = []


class Object3D:
    def __init__(self):
        self.path = ""
        self.oid = 0
        self.motion : Motion = None
        self.attributes : list[MotionAttribute] = []
        self.forces = []
        self.bbmin = (0, 0, 0)
        self.bbmax = (0, 0, 0)
        self.scrl_u = 0
        self.scrl_v = 0
        self.perslerp = 0
        self.frame_count = 0
        self.event_count = 0
        self.bone_count = 0
        self.events = []
        self.lod = False
        self.send_VS = False
        self.coll_obj = None
        self.base_bones = []
        self.base_inv_bones = []
        self.groups = []
        self.has_skin = False


class GMObject:
    def __init__(self):
        self.name = ""
        self.lod_index = 0
        self.oid = 0
        self.parent_id = 0
        self.gm_type = 0
        self.parent_gm_type = 0
        self.used_bone_count = 0
        self.bbmin = (0, 0, 0)
        self.bbmax = (0, 0, 0)
        self.vertex_list_count = 0
        self.vertex_count = 0
        self.face_list_count = 0
        self.index_count = 0
        self.material_count = 0
        self.material_block_count = 0
        self.vertex_list = []
        self.vertices = []
        self.normals = []
        self.uvs = []
        self.weights = []
        self.bone_ids = []
        self.indices = []
        self.IIB = []
        self.used_bones = []
        self.physique_vertices = []
        self.materials : list[Material] = []
        self.material_blocks : list[MaterialBlock] = []
        self.transform = []
        self.frames : list[TMAnimation] = []
        self.material = False
        self.opacity = False
        self.bump = False
        self.rigid = False
        self.is_collision = False
        self.blender_obj : Object = None
        self.rotation_before = Quaternion((1, 0, 0, 0))
        self.rotation_after = Quaternion((1, 0, 0, 0))