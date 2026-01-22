bl_info = {
    "name": "O3D Format",
    "author": "Frostiae",
    "version": (1, 0),
    "blender": (4, 3, 2),
    "location": "File > Import-Export",
    "description": "Import-Export as O3D",
    "category": "Import-Export",
}

import os
import bpy
import glob
from .o3d_types import *
from .importer import O3DFile
from .blender_control import *
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper, ExportHelper, poll_file_object_drop
from bpy.props import (StringProperty, BoolProperty, EnumProperty)


class ImportO3D(Operator, ImportHelper):
    """Import a Fly For Fun O3D model/ani."""
    bl_idname = "import_scene.o3d"
    bl_label = "Import O3D/ANI"

    filename_ext = ".o3d"

    filter_glob: StringProperty(
        default="*.o3d;*.ani",
        options={'HIDDEN'},
        maxlen=255  # Max internal buffer length, longer would be clamped.
    )

    hide_lod: BoolProperty(
        name="Hide LODs",
        description=(
            "Hide level of detail meshes on import if they exist, except for the base one"
        ),
        default=True
    )

    hide_coll: BoolProperty(
        name="Hide Collision Mesh",
        description=(
            "Hide collision meshes on import if they exist"
        ),
        default=True
    )

    include_animations: BoolProperty(
        name="Import Animations",
        description=(
            "Import all associated .ani file animations"
        ),
        default=True
    )
    
    def import_model(self, context, filepath=None, include_animations=None):
        filepath = filepath or self.filepath
        
        o3d_file = O3DFile(filepath)
        o3d_file.read_o3d(self.as_keywords())
        
        if include_animations is None:
            include_animations = o3d_file.import_settings.get("include_animations", True)

        filename = os.path.basename(filepath)
        skel_name: str = ""

        if filename.lower().startswith("mvr"):
            skel_name = filepath
            last_index = skel_name.rfind(".")
            skel_name = skel_name[:last_index] + ".chr"
            o3d_file.read_chr(skel_name)
        elif filename.lower().startswith("part_m"):
            skel_name = os.path.join(os.path.dirname(filepath), "mvr_male.chr")
            o3d_file.read_chr(skel_name)
        elif filename.lower().startswith("part_f"):
            skel_name = os.path.join(os.path.dirname(filepath), "mvr_female.chr")
            o3d_file.read_chr(skel_name)

        if skel_name and include_animations:
            # TODO: Case insensitive glob
            ani_files = glob.glob(skel_name[:skel_name.rfind(".")] + "_*.ani")
            for ani in ani_files:
                o3d_file.read_ani(ani)

        print("Model import complete.")
        
        return o3d_file


    def import_animation(self, context):
        ani_file = self.filepath
        ani_filename = os.path.basename(ani_file)

        parts = ani_filename.split("_")
        if len(parts) < 3:
            self.report({'ERROR'}, f"Invalid animation filename: {ani_filename}")
            return {'CANCELLED'}

        base_name = f"{parts[0]}_{parts[1]}"
        chr_file = os.path.join(os.path.dirname(ani_file), f"{base_name}.chr")
        if not os.path.exists(chr_file):
            self.report({'ERROR'}, f"Skeleton file not found: {chr_file}")
            return {'CANCELLED'}

        lower_base = base_name.lower()

        o3d_path = os.path.join(os.path.dirname(chr_file), f"{base_name}.o3d")
        if lower_base == "mvr_male":
            o3d_path = os.path.join(os.path.dirname(chr_file), f"Part_mAcr01Upper.o3d")
        elif lower_base == "mvr_female":
            o3d_path = os.path.join(os.path.dirname(chr_file), f"Part_fAcr01Upper.o3d")
        
        if os.path.exists(o3d_path):
            o3d_file = self.import_model(context, filepath=o3d_path, include_animations=False)

        o3d_file.read_ani(ani_file)

        bpy.context.scene.frame_end = o3d_file.animations[0].frame_count
        print(f"Loaded skeleton {chr_file} and applied animation {ani_filename}")
        
        return o3d_file


    def execute(self, context):
        if self.filepath.lower().endswith(".ani"):
            o3d_file = self.import_animation(context)
        else:
            o3d_file = self.import_model(context)
        
        create_scene(o3d_file)
        
        return {'FINISHED'}
        
class ExportO3D(Operator, ExportHelper):
    """Export a Fly For Fun O3D."""
    bl_idname = "export_scene.o3d"
    bl_label = "Export O3D"

    filename_ext = ".o3d"
    
    action_name: EnumProperty(
        name="Action",
        description="Select which animation to export",
        items=lambda self, context: [(a.name, a.name, "") for a in bpy.data.actions]
    )
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    def execute(self, context):
        o3d_file = create_o3dfile_from_blender_scene(self.filepath)
        o3d_file.write_o3d()
        return {'FINISHED'}

        """
        obj = context.active_object
        if obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object is not an armature")
            return {'CANCELLED'}

        action = bpy.data.actions.get(self.action_name)
        if not action:
            self.report({'ERROR'}, f"Action {self.action_name} not found")
            return {'CANCELLED'}

        skeleton = create_skeleton_from_blender_armature(obj)
        motion = create_motion_from_blender_action(skeleton, action)
        ani_file = O3DFile(self.filepath)
        ani_file.write_ani(motion, self.filepath)

        self.report({'INFO'}, f"Exported animation {self.action_name} to {self.filepath}")
        return {'FINISHED'}
        """


class IO_FH_O3D(bpy.types.FileHandler):
    bl_idname = "IO_FH_O3D"
    bl_label = "O3D"
    bl_import_operator = "import_scene.o3d"
    bl_export_operator = "export_scene.o3d"
    bl_file_extensions = ".o3d;.ani"

    @classmethod
    def poll_drop(cls, context):
        return poll_file_object_drop(context)


def create_scene(o3d_file : O3DFile):
    for gmo in o3d_file.gmobjects:
        name = gmo.name
        if gmo.is_collision:
            name = "#coll"

        blender_obj = create_blender_mesh(name, gmo, o3d_file.o3d)
        if o3d_file.import_settings["hide_lod"] and gmo.lod_index > 0:
            blender_obj.hide_set(True)

        if o3d_file.import_settings["hide_coll"] and gmo.is_collision:
            blender_obj.hide_set(True)

    if o3d_file.chr is not None:
        create_blender_armature("Armature", o3d_file.chr, o3d_file.gmobjects)

    if o3d_file.import_settings["include_animations"]:
        for ani in o3d_file.animations:
            create_blender_action(o3d_file.chr, ani)


def create_o3dfile_from_blender_scene(filepath : str) -> O3DFile:
    o3d_file = O3DFile(filepath)

    # Prep
    if bpy.context.active_object is not None:
        if bpy.context.active_object.mode != "OBJECT": # For linked object, you can't force OBJECT mode
            bpy.ops.object.mode_set(mode='OBJECT')

    bpy.context.scene.frame_set(0)

    o3d_file.o3d = Object3D() # Default for now, TODO: proper conversion with element meshes and what-not

    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue

        gmobject = create_gmobject_from_blender_obj(obj)
        o3d_file.gmobjects.append(gmobject)

    return o3d_file
    

def menu_func_import(self, context):
    self.layout.operator(ImportO3D.bl_idname, text="FlyFF (.o3d/.ani)")

def menu_func_export(self, context):
    self.layout.operator(ExportO3D.bl_idname, text="FlyFF (.o3d/.ani)")

def register():
    bpy.utils.register_class(ImportO3D)
    bpy.utils.register_class(ExportO3D)
    bpy.utils.register_class(IO_FH_O3D)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ImportO3D)
    bpy.utils.unregister_class(ExportO3D)
    bpy.utils.unregister_class(IO_FH_O3D)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
