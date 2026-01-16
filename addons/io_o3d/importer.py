import struct
from .o3d_types import *
from .blender_control import *
from mathutils import Vector, Quaternion, Matrix


class BinaryReader:
    def __init__(self, file):
        self.file = file
        
    def read_char(self):
        return struct.unpack("B", self.file.read(1))[0]
        
    def read_int32(self):
        return struct.unpack("<i", self.file.read(4))[0]

    def read_uint32(self):
        return struct.unpack("<I", self.file.read(4))[0]
    
    def read_uint16(self):
        return struct.unpack("<H", self.file.read(2))[0]

    def read_float(self):
        return struct.unpack("<f", self.file.read(4))[0]
    
    def read_vec2(self):
        return struct.unpack("<ff", self.file.read(8))

    def read_vec3(self):
        x, y, z = struct.unpack("<fff", self.file.read(12))
        return (x, y, z)
    
    def read_vec4(self):
        x, y, z, w = struct.unpack("<ffff", self.file.read(16))
        return (x, y, z, w)
    
    def read_quat(self):
        return struct.unpack("<ffff", self.file.read(16))
    
    def read_transform(self):
        return struct.unpack("<ffffffffffffffff", self.file.read(16 * 4))
    
    def read_bytes(self, length):
        return struct.unpack("B" * length, self.file.read(length))
    
    def read_string(self, length):
        raw = self.file.read(length)
        return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")


class BinaryWriter:
    def __init__(self, file):
        self.file = file

    def write_char(self, v):
        self.file.write(struct.pack("B", v & 0xFF))

    def write_int32(self, v):
        self.file.write(struct.pack("<i", int(v)))

    def write_uint32(self, v):
        self.file.write(struct.pack("<I", int(v) & 0xFFFFFFFF))

    def write_uint16(self, v):
        self.file.write(struct.pack("<H", int(v) & 0xFFFF))

    def write_float(self, v):
        self.file.write(struct.pack("<f", float(v)))

    def write_vec2(self, v):
        self.file.write(struct.pack("<ff", float(v[0]), float(v[1])))

    def write_vec3(self, v):
        self.file.write(struct.pack("<fff", float(v[0]), float(v[1]), float(v[2])))

    def write_vec4(self, v):
        self.file.write(struct.pack("<ffff", float(v[0]), float(v[1]), float(v[2]), float(v[3])))

    def write_quat(self, q):
        self.file.write(struct.pack("<ffff", float(q[0]), float(q[1]), float(q[2]), float(q[3])))

    def write_transform(self, t):
        if hasattr(t, "row"):  # mathutils.Matrix
            flat = [v for row in t for v in row]
        else:
            flat = list(t)
        self.file.write(struct.pack("<ffffffffffffffff", *[float(x) for x in flat]))

    def write_bytes(self, b):
        self.file.write(b)

    def write_string_fixed(self, s, length):
        bs = s.encode("utf-8", errors="ignore")
        if len(bs) >= length:
            self.file.write(bs[:length])
        else:
            self.file.write(bs + b"\x00" * (length - len(bs)))


class O3DFile:
    """o3d file description."""
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.o3d : Object3D = None
        self.gmobjects : list[GMObject] = []
        self.animations : list[Motion] = []
        self.chr : Skeleton = None
        self.import_settings = {}


    def read_o3d(self, import_settings) -> Object3D:
        print(f"Reading {self.filepath}...")
        self.import_settings = import_settings
        f = open(self.filepath, "rb")
        reader = BinaryReader(f)
        self.o3d = Object3D()
        self.o3d.path = self.filepath
        
        name_len = reader.read_char()
        name = bytearray(f.read(name_len))
        for i in range(name_len):
            name[i] ^= 0xcd
            
        name = name.decode("utf-8", errors="ignore")
        
        version = reader.read_int32()
        self.o3d.oid = reader.read_int32() # ID
        self.o3d.forces.append(reader.read_vec3())
        self.o3d.forces.append(reader.read_vec3())
        
        if version >= 22:
            self.o3d.forces.append(reader.read_vec3())
            self.o3d.forces.append(reader.read_vec3())
            
        self.o3d.scrl_u = reader.read_float()
        self.o3d.scrl_v = reader.read_float()
        
        f.read(16) # skip 16
        
        self.o3d.bbmin = reader.read_vec3()
        self.o3d.bbmax = reader.read_vec3()
        
        self.o3d.perslerp = reader.read_float() 
        self.o3d.frame_count = reader.read_int32()
        
        self.o3d.event_count = reader.read_int32()
        for i in range(self.o3d.event_count):
            self.o3d.events.append(reader.read_vec3())
            
        if reader.read_int32() > 0:
            coll_obj = GMObject()
            coll_obj.gm_type = 0
            coll_obj.is_collision = True
            self.read_geometry(f, reader, coll_obj)
            self.gmobjects.append(coll_obj)

        self.o3d.lod = reader.read_int32() != 0
        
        self.o3d.bone_count = reader.read_int32()
        if self.o3d.bone_count > 0:
            for _ in range(self.o3d.bone_count):
                self.o3d.base_bones.append(reader.read_transform())

            for _ in range(self.o3d.bone_count):
                self.o3d.base_inv_bones.append(reader.read_transform())

            # TODO: These bone animations need to be handled
            if self.o3d.frame_count > 0:
                self.o3d.motion = Motion()
                self.read_TMAnimation(reader, self.o3d.motion, self.o3d.bone_count, self.o3d.frame_count)
                
            self.o3d.send_VS = reader.read_int32() != 0
        
        reader.read_int32() # Pool size
        for i in range(3 if self.o3d.lod else 1):
            object_count = reader.read_int32()

            for j in range(object_count):
                gmo = GMObject()
                gmo.name = f"GMObject{j + 1}"
                gmo.lod_index = i
                if self.o3d.lod:
                    gmo.name += f"-lod{i + 1}"

                gmo.gm_type = reader.read_int32()
                gmo.gm_type = gmo.gm_type & 0xffff

                gmo.used_bone_count = reader.read_int32()
                for _ in range(gmo.used_bone_count):
                    gmo.used_bones.append(reader.read_int32())
                
                gmo.oid = reader.read_int32() # ID
                gmo.parent_id = reader.read_int32()
                if gmo.parent_id != -1:
                    gmo.parent_gm_type = reader.read_int32()
                
                # Transform
                gmo.transform = reader.read_transform()
                
                self.read_geometry(f, reader, gmo)

                if gmo.gm_type == 0 and self.o3d.frame_count > 0:
                    if reader.read_int32():
                        for _ in range(self.o3d.frame_count):
                            anim = TMAnimation()
                            anim.rot = reader.read_quat()
                            anim.pos = reader.read_vec3()
                            gmo.frames.append(anim)

                self.gmobjects.append(gmo)

        # TODO: Somehow crashes some files like mvr_vempain.o3d
        """
        if version >= 21:
            if reader.read_int32() == self.o3d.frame_count:
                for _ in range(self.o3d.frame_count):
                    ma = MotionAttribute()
                    ma.type = reader.read_uint16()
                    ma.sound_id = reader.read_int32()
                    ma.frame = reader.read_float()
                    self.o3d.attributes.append(ma)
        """

        f.close()
        return self.o3d
    

    def read_geometry(self, f, reader: BinaryReader, gmo : GMObject):
        gmo.bbmin = reader.read_vec3()
        gmo.bbmax = reader.read_vec3()
        
        gmo.opacity = reader.read_int32() != 0
        gmo.bump = reader.read_int32() != 0
        gmo.rigid = reader.read_int32() != 0
        
        f.read(28) # skip
        
        gmo.vertex_list_count = reader.read_int32()
        gmo.vertex_count = reader.read_int32()
        gmo.face_list_count = reader.read_int32()
        gmo.index_count = reader.read_int32()
        
        for _ in range(gmo.vertex_list_count):
            gmo.vertex_list.append(reader.read_vec3())
            
        self.o3d.has_skin = gmo.gm_type == 1

        for _ in range(gmo.vertex_count):
            pos = reader.read_vec3()
            if self.o3d.has_skin:
                w1 = reader.read_float()
                w2 = reader.read_float()
                id1 = reader.read_uint16()
                id2 = reader.read_uint16()
                
                gmo.weights.append((w1, w2))
                gmo.bone_ids.append((id1, id2))

            normal = reader.read_vec3()
            uv = reader.read_vec2()

            uvl = list(uv)
            uvl[1] = -uvl[1] + 1.0
            uv = tuple(uvl)

            gmo.vertices.append(pos)
            gmo.normals.append(normal)
            gmo.uvs.append(uv)
            
        for _ in range(0, gmo.index_count, 3):
            face = (reader.read_uint16(), reader.read_uint16(), reader.read_uint16())
            gmo.indices.append(face)
        
        for _ in range(gmo.vertex_count):
            gmo.IIB.append(reader.read_uint16())
            
        if reader.read_int32() > 0:
            for _ in range(gmo.vertex_list_count):
                gmo.physique_vertices.append(reader.read_int32())

        ## Material

        gmo.material = reader.read_int32() != 0
        if gmo.material:
            gmo.material_count = reader.read_int32()
            if gmo.material_count == 0:
                gmo.material_count = 1

            texture_name_length = 0
            for _ in range(gmo.material_count):
                mat = Material()
                mat.diffuse = reader.read_vec4()
                mat.ambient = reader.read_vec4()
                mat.specular = reader.read_vec4()
                mat.emissive = reader.read_vec4()
                mat.power = reader.read_float()
                texture_name_length = reader.read_int32()
                mat.texture_name = reader.read_string(texture_name_length)
                gmo.materials.append(mat)

        gmo.material_block_count = reader.read_int32()
        for _ in range(gmo.material_block_count):
            block = MaterialBlock()
            block.start_vertex = reader.read_int32()
            block.primitive_count = reader.read_int32()
            block.material_id = reader.read_int32()
            block.effect = reader.read_uint32()
            block.amount = reader.read_int32()
            block.used_bone_count = reader.read_int32()
            for _ in range(28):
                block.used_bones.append(reader.read_int32())

            gmo.material_blocks.append(block)


    def read_chr(self, chr_filepath : str):
        f = open(chr_filepath, "rb")
        reader = BinaryReader(f)
        self.chr = Skeleton()

        version = reader.read_int32()
        if version < 4:
            print("Skeleton version is no longer supported")
            return
        
        self.chr.oid = reader.read_int32()
        self.chr.bone_count = reader.read_int32()

        for _ in range(self.chr.bone_count):
            bone = Bone()
            name_len = reader.read_int32()
            bone.name = reader.read_string(name_len)
            bone.transform = reader.read_transform()
            bone.inverse_transform = reader.read_transform()
            bone.local_transform = reader.read_transform()
            bone.parent_id = reader.read_int32()
            self.chr.bones.append(bone)

        for bone in self.chr.bones:
            if bone.parent_id != -1:
                self.chr.bones[bone.parent_id].children.append(bone)

        for gmo in self.gmobjects:
            if gmo.parent_id != -1 and gmo.parent_gm_type == 2:
                self.chr.bones[gmo.parent_id].children_gmos.append(gmo)

        ### Coordinate space stuff
        for bone in self.chr.bones:
            bone.base_trs = convert_matrix(bone.local_transform).decompose()
        
        self.chr.send_VS = reader.read_int32() != 0
        self.chr.local_RH = reader.read_transform()
        self.chr.local_shield = reader.read_transform()
        self.chr.local_knuckle = reader.read_transform()

        if version == 5:
            for _ in range(4):
                self.chr.events.append(reader.read_vec3())
                self.chr.event_parent_ids.append(reader.read_int32())
        elif version >= 6:
            for _ in range(8):
                self.chr.events.append(reader.read_vec3())
                self.chr.event_parent_ids.append(reader.read_int32())

        if version == 7:
            self.chr.local_LH = reader.read_transform()

        f.close()
        self.setup_chr_space()


    def setup_chr_space(self):
        for bone in self.chr.bones:
            bone.editbone_trans = Vector(bone.base_trs[0])
            bone.editbone_rot = Quaternion(bone.base_trs[1])

        # Prettify
        def rotate_bone(bone: Bone):
            rot = Quaternion((2**0.5 / 2, 2**0.5 / 2, 0, 0))
            # rotate_edit_bone
            bone.editbone_rot @= rot
            rot_inv = rot.conjugated()
            for child in bone.children:
                child.editbone_trans = rot_inv @ child.editbone_trans
                child.editbone_rot = rot_inv @ child.editbone_rot

            # local_rotation
            bone.rotation_before @= rot
            for child in bone.children:
                child.rotation_after = rot_inv @ child.rotation_after

            for child_gmo in bone.children_gmos:
                child_gmo.rotation_after = rot_inv @ child_gmo.rotation_after

            for child in bone.children:
                rotate_bone(child)

        rotate_bone(self.chr.bones[0])

        # Calc matrices
        def calc_matrices(bone: Bone):
            if bone.parent_id != -1:
                parent_editbone_mat = self.chr.bones[bone.parent_id].editbone_arma_mat
            else:
                parent_editbone_mat = Matrix.Identity(4)

            t, r = bone.editbone_trans, bone.editbone_rot
            local_to_parent = Matrix.Translation(t) @ Quaternion(r).to_matrix().to_4x4()
            bone.editbone_arma_mat = parent_editbone_mat @ local_to_parent

            for child in bone.children:
                calc_matrices(child)

        calc_matrices(self.chr.bones[0])


    def read_ani(self, ani_filepath : str) -> Motion:
        f = open(ani_filepath, "rb")
        reader = BinaryReader(f)
        ani = Motion()

        version = reader.read_int32()
        if version < 10:
            print("Animation is not supported on this version")
            f.close()
            return
        
        ani.oid = reader.read_int32()
        ani.perslerp = reader.read_float()

        f.read(32) # Skip 32

        ani.bone_count = reader.read_int32()
        ani.frame_count = reader.read_int32()

        if reader.read_int32() > 0:
            for _ in range(ani.frame_count):
                ani.paths.append(reader.read_vec3())

        self.read_TMAnimation(reader, ani, ani.bone_count, ani.frame_count)

        for _ in range(ani.frame_count):
            ma = MotionAttribute()
            ma.type = reader.read_uint16()
            ma.sound_id = reader.read_int32()
            ma.frame = reader.read_float()
            ani.attributes.append(ma)

        ani.event_count = reader.read_int32()
        for _ in range(ani.event_count):
            ani.events.append(reader.read_vec3())

        ani.name = ani_filepath[ani_filepath.rfind("_")+1:-4]
        self.animations.append(ani)

        f.close()
        return ani
    

    def read_TMAnimation(self, reader : BinaryReader, ani: Motion, bone_count : int, frame_count : int) -> TMAnimation:
        ani.bone_count = bone_count
        ani.frame_count = frame_count
        
        for _ in range(bone_count):
            bone = Bone()
            name_len = reader.read_int32()
            bone.name = reader.read_string(name_len)
            bone.inverse_transform = reader.read_transform()
            bone.local_transform = reader.read_transform()
            bone.parent_id = reader.read_int32()
            ani.bones.append(bone)

        ani_count = reader.read_int32()

        #ani.animations.extend([TMAnimation()] * (ani_count - len(ani.animations)))
        #ani.attributes.extend([MotionAttribute()] * (ani.frame_count - len(ani.attributes)))
        #ani.frames.extend([BoneFrame()] * (ani.bone_count - len(ani.frames)))

        for i in range(bone_count):
            bone_frame = BoneFrame()

            if reader.read_int32() != 0:
                for _ in range(ani.frame_count):
                    anim = TMAnimation()
                    anim.rot = reader.read_quat()
                    anim.pos = reader.read_vec3()
                    bone_frame.frames.append(anim)
            else:
                bone_frame.transform = reader.read_transform()
            
            ani.frames.append(bone_frame)

    def write_ani(self, motion, filepath):
        with open(filepath, 'wb') as f:
            writer = BinaryWriter(f)

            writer.write_int32(10)
            writer.write_int32(motion.oid)
            writer.write_float(motion.perslerp)

            writer.write_bytes(b'\x00' * 32)

            writer.write_int32(motion.bone_count)
            writer.write_int32(motion.frame_count)

            has_paths = 1 if motion.paths else 0
            writer.write_int32(has_paths)
            if has_paths:
                for path in motion.paths:
                    writer.write_transform(path)

            self.write_TMAnimation(writer, motion)

            for attr in motion.attributes:
                writer.write_uint16(attr.type)
                writer.write_int32(attr.sound_id)
                writer.write_float(attr.frame)

            writer.write_int32(motion.event_count)
            if motion.event_count > 0:
                for event in motion.events:
                    writer.write_bytes(event) 


    def write_TMAnimation(self, writer, motion):
        for bone in motion.bones:
            name_bytes = bone.name.encode('utf-8')
            writer.write_int32(len(name_bytes) + 1)
            writer.write_bytes(name_bytes)
            writer.write_char(0)
            writer.write_transform(bone.inverse_transform)
            writer.write_transform(bone.local_transform)
            writer.write_int32(bone.parent_id)

        ani_count = 0
        for bone_frame in motion.frames:
            if bone_frame.frames is not None:
                ani_count += motion.frame_count
        
        writer.write_int32(ani_count)

        for i in range(motion.bone_count):
            bone_frame = motion.frames[i]
            has_frames = 1 if bone_frame.frames else 0
            writer.write_int32(has_frames)

            if has_frames == 1:
                for j in range(motion.frame_count):
                    writer.write_quat(bone_frame.frames[j].rot)
                    writer.write_vec3(bone_frame.frames[j].pos)
            else:
                writer.write_transform(bone_frame.transform)
