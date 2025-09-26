bl_info = {
    "name": "O3D Format",
    "author": "Frostiae",
    "version": (1, 0),
    "blender": (4, 3, 2),
    "location": "File > Import-Export",
    "description": "Import-Export as O3D",
    "category": "Import-Export",
}

import bpy
import glob
from .o3d_types import *
from .importer import O3DFile
from .blender_control import *
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper, ExportHelper, poll_file_object_drop
from bpy.props import (StringProperty, BoolProperty, EnumProperty)


class ImportO3D(Operator, ImportHelper):
    """Import a Fly For Fun O3D model."""
    bl_idname = "import_scene.o3d"
    bl_label = "Import O3D Model"

    filename_ext = ".o3d"

    filter_glob: StringProperty(
        default="*.o3d",
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


    def execute(self, context):
        o3d_file = O3DFile(self.filepath)
        o3d_file.read_o3d(self.as_keywords())

        filename = self.filepath.split("\\")[-1]
        skel_name : str = ""
        if filename.lower().startswith("mvr"):
            skel_name = self.filepath
            last_index = skel_name.rfind(".")
            skel_name = skel_name[:last_index] + ".chr"
            o3d_file.read_chr(skel_name)
        elif filename.lower().startswith("part"):
            pass

        if len(skel_name) > 0 and o3d_file.import_settings["include_animations"]:
            ani_files = glob.glob(skel_name[:skel_name.rfind(".")] + "_*.ani")
            for ani in ani_files:
                o3d_file.read_ani(ani)
        
        create_scene(o3d_file)
        print("Done.")
        return {'FINISHED'}


class IO_FH_O3D(bpy.types.FileHandler):
    bl_idname = "IO_FH_O3D"
    bl_label = "O3D"
    bl_import_operator = "import_scene.o3d"
    #bl_export_operator = "export_scene.o3d"
    bl_file_extensions = ".o3d"

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
        create_blender_armature("Skeleton", o3d_file.chr, o3d_file.gmobjects)

    if o3d_file.import_settings["include_animations"]:
        for ani in o3d_file.animations:
            create_blender_action(o3d_file.chr, ani)
    

def menu_func_import(self, context):
    self.layout.operator(ImportO3D.bl_idname, text="FlyFF (.o3d)")


def register():
    bpy.utils.register_class(ImportO3D)
    bpy.utils.register_class(IO_FH_O3D)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportO3D)
    bpy.utils.unregister_class(IO_FH_O3D)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
