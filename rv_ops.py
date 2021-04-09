import bpy
import bmesh
import numpy as np
import bgl
import blf
import gpu
import random
import mathutils

from bpy.props import StringProperty, FloatVectorProperty, BoolProperty, EnumProperty
from bpy.types import Operator
from mathutils import Color
from gpu_extras.batch import batch_for_shader

from . rv_shaders import vertex_shader, fragment_shader


def set_up_marker_data_layer(self, context):
    obj = context.object

    object_mode = obj.mode
    bpy.ops.object.mode_set(mode='OBJECT')

    mesh = obj.data

    retopoViewGroupLayer = mesh.polygon_layers_int.get("RetopoViewGroupLayer")
    if retopoViewGroupLayer is None:
        retopoViewGroupLayer = mesh.polygon_layers_int.new(name='RetopoViewGroupLayer')

    bpy.ops.object.mode_set(mode=object_mode)


class RETOPOVIEW_OT_add_group(Operator):
    bl_idname = "retopoview.add_group"
    bl_label = "Add New Group"
    bl_description = "Add new group"

    group_name: StringProperty(name="Group Name", default="New Group")
    group_color: FloatVectorProperty(name="Group Color", subtype='COLOR', default=(1, 1, 1), min=0.0, max=1.0)

    def get_random_color(self):
        color = Color()
        # set value and saturation to 1 - provides best overlay visibility
        color.hsv = (random.random(), 1, 1)

        return color

    def execute(self, context):
        obj = context.object

        group = obj.rv_groups.add()

        group.color = self.group_color
        group.group_id = obj.rv_group_idx_counter
        group.name = self.group_name

        obj.rv_group_idx_counter += 1

        obj.rv_index = len(obj.rv_groups) - 1

        if len(obj.rv_groups) == 1:
            obj.rv_enabled = True
            set_up_marker_data_layer(self, context)
            obj.data.update()
            bpy.ops.retopoview.overlay('INVOKE_DEFAULT')

        return {'FINISHED'}

    def invoke(self, context, event):
        self.group_color = self.get_random_color()
        return context.window_manager.invoke_props_dialog(self)


class RETOPOVIEW_OT_handle_face_selection(Operator):
    bl_idname = "retopoview.handle_face_selection"
    bl_label = "Select/Deselect Faces"
    bl_description = "Select/Deselect Faces assigned to a group"

    deselect: BoolProperty()

    def execute(self, context):
        obj = context.object

        if obj.mode != 'EDIT' or len(obj.rv_groups) <= 0:
            return {'FINISHED'}

        group_id = obj.rv_groups[obj.rv_index].group_id

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        retopoViewGroupLayer = bm.faces.layers.int["RetopoViewGroupLayer"]

        for face in bm.faces:
            if face[retopoViewGroupLayer] == group_id:
                face.select = not self.deselect

        bmesh.update_edit_mesh(mesh)
        mesh.update()

        return {'FINISHED'}


class RETOPOVIEW_OT_find_parent_group(Operator):
    bl_idname = "retopoview.find_parent_group"
    bl_label = "Find Parent Group"
    bl_description = "Find parent group of selected faces, returns the first found group"

    def execute(self, context):
        obj = context.object

        if obj.mode != 'EDIT' or len(obj.rv_groups) <= 0:
            return {'FINISHED'}

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        retopoViewGroupLayer = bm.faces.layers.int["RetopoViewGroupLayer"]

        for face in bm.faces:
            if face.select and face[retopoViewGroupLayer] != 0:
                for idx, group in enumerate(obj.rv_groups):
                    if group.group_id == face[retopoViewGroupLayer]:
                        obj.rv_index = idx
                        return {'FINISHED'}

        return {'FINISHED'}


class RETOPOVIEW_OT_move_group(Operator):
    bl_idname = "retopoview.move_group"
    bl_label = "Move Group"
    bl_description = "Change group position in the list"

    direction: EnumProperty(
        items=(
            ('UP', "Up", ""),
            ('DOWN', "Down", "")
        )
    )

    def move_group(self, offset, context, active_index, obj):
        obj.rv_groups.move(active_index, active_index + offset)
        obj.rv_index += offset

    def execute(self, context):
        obj = context.object

        active_index = obj.rv_index
        max_allowed_index = len(obj.rv_groups) - 1

        if max_allowed_index <= 0:
            return {'FINISHED'}

        if self.direction == 'UP' and active_index > 0:
            self.move_group(-1, context, active_index, obj)

        if self.direction == 'DOWN' and active_index < max_allowed_index:
            self.move_group(1, context, active_index, obj)

        return {'FINISHED'}


class RETOPOVIEW_OT_change_selection_group_id(Operator):
    bl_idname = "retopoview.change_selection_group_id"
    bl_label = "Assign Selection to Group"
    bl_description = "Assign selected faces to group"

    remove: BoolProperty()

    def execute(self, context):
        obj = context.object

        if len(obj.rv_groups) <= 0:
            return {'FINISHED'}

        group_id = obj.rv_groups[obj.rv_index].group_id

        if self.remove:
            group_id = 0

        object_mode = obj.mode

        if object_mode != "EDIT":
            bpy.ops.object.mode_set(mode='EDIT')

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        retopoViewGroupLayer = bm.faces.layers.int["RetopoViewGroupLayer"]

        if obj.rv_use_x_mirror:
            current_selection = set()
            for face in bm.faces:
                if face.select:
                    current_selection.add(face)

            bpy.ops.mesh.select_mirror(axis={'X'}, extend=True)

        for face in bm.faces:
            if face.select:
                face[retopoViewGroupLayer] = group_id

                if obj.rv_use_x_mirror and face not in current_selection:
                    face.select = False

        bmesh.update_edit_mesh(mesh)
        mesh.update()

        if object_mode != "EDIT":
            bpy.ops.object.mode_set(mode=object_mode)

        return {'FINISHED'}


class RETOPOVIEW_OT_toggle_mode(Operator):
    bl_idname = "retopoview.toggle_mode"
    bl_label = "Toggle overlay mode"
    bl_description = "Toggle overlay mode"

    def invoke(self, context, event):
        obj = context.object
        obj.rv_enabled = not obj.rv_enabled

        if obj.rv_enabled:
            set_up_marker_data_layer(self, context)
            obj.data.update()
            bpy.ops.retopoview.overlay('INVOKE_DEFAULT')

        return {'FINISHED'}


class RETOPOVIEW_OT_remove_group(Operator):
    bl_idname = "retopoview.remove_group"
    bl_label = "Remove Group"
    bl_description = "Remove group"

    def execute(self, context):
        obj = context.object

        remove_id = obj.rv_index
        group_id = obj.rv_groups[remove_id].group_id

        object_mode = obj.mode
        bpy.ops.object.mode_set(mode='EDIT')

        mesh = obj.data
        bm = bmesh.from_edit_mesh(mesh)
        retopoViewGroupLayer = bm.faces.layers.int["RetopoViewGroupLayer"]

        for face in bm.faces:
            if face[retopoViewGroupLayer] == group_id:
                face[retopoViewGroupLayer] = 0

        bmesh.update_edit_mesh(mesh)
        mesh.update()

        bpy.ops.object.mode_set(mode=object_mode)

        obj.rv_groups.remove(remove_id)
        obj.rv_index = obj.rv_index - 1 if obj.rv_index >= 1 else 0

        if len(obj.rv_groups) == 0:
            obj.rv_enabled = False

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event) if len(context.object.rv_groups) != 0 else {'FINISHED'}


class RETOPOVIEW_OT_overlay(Operator):
    bl_idname = "retopoview.overlay"
    bl_label = "Retopoview face overlay operator"
    bl_description = "Draw RetopoView face overlay"

    def get_smallest_vector_dimension(self, vector):
        smallest_dimension = vector[0]

        for dimension in vector:
            if dimension < smallest_dimension:
                smallest_dimension = dimension

        return smallest_dimension

    def prep_wireframe_batch(self, shader, mesh, obj, vert_idx_cache, edge_indices):
        coords = np.empty((len(mesh.vertices), 3), 'f')
        mesh.vertices.foreach_get("co", np.reshape(coords, len(mesh.vertices) * 3))

        # offset wireframe verts to have slightly different depth - works well only for close view range
        for c_idx, coord in enumerate(coords):
            coords[c_idx] = coord + mesh.vertices[c_idx].normal*0.0035

        wireframe_colors = np.empty((len(mesh.vertices), 4), 'f')
        for v_idx, _ in enumerate(mesh.vertices):
            wireframe_colors[v_idx] = (0, 0, 0, obj.rv_groups_alpha) if v_idx in vert_idx_cache else (0, 0, 0, 0)

        return batch_for_shader(shader, 'LINES', {"position": coords, "color": wireframe_colors}, indices=edge_indices)

    def prep_pole_batch(self, shader, mesh, obj):
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj.data)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj.data)

        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        pole_verts = [vert for vert in bm.verts if len(vert.link_edges) > 4]
        pole_coords = []
        pole_indices = []

        pole_idx = 0
        for vert in pole_verts:
            pole_coords.append(vert.co)

            smallest_dimension = self.get_smallest_vector_dimension(obj.dimensions)
            pole_coords.append(vert.co + vert.normal * smallest_dimension * 0.5 * obj.rv_poles_size)
            pole_indices.append([pole_idx, pole_idx+1])

            pole_idx += 2

        pole_color = (obj.rv_poles_color.r, obj.rv_poles_color.g, obj.rv_poles_color.b, 1)
        pole_colors = [pole_color for _ in pole_coords]

        return batch_for_shader(shader, 'LINES', {"position": pole_coords, "color": pole_colors}, indices=pole_indices)

    def draw_overlay(self, context, depsgraph, obj):
        try:
            if not obj or not obj.rv_enabled or len(obj.rv_groups) <= 0:
                return {'FINISHED'}
        except ReferenceError:
            return {'FINISHED'}

        obj = obj.evaluated_get(depsgraph)
        mesh = obj.to_mesh()

        mesh.calc_loop_triangles()
        shader = gpu.types.GPUShader(vertex_shader, fragment_shader)

        verts = []
        triangle_indices = []
        colors = []
        edge_indices = []
        vert_idx_cache = set()

        retopoViewGroupLayer = mesh.polygon_layers_int.get("RetopoViewGroupLayer")

        idx = 0
        for _, triangle in enumerate(mesh.loop_triangles):
            if mesh.polygons[triangle.polygon_index].hide and obj.mode == 'EDIT':
                continue

            group_color = (1, 1, 1, 0)
            triangle_parent_poly_group_id = retopoViewGroupLayer.data[triangle.polygon_index].value

            for group in obj.rv_groups:
                if group.group_id == triangle_parent_poly_group_id:
                    group_color = (group.color.r, group.color.g, group.color.b, 0.5)

                    if obj.rv_show_wire:
                        parent_poly = mesh.polygons[triangle.polygon_index]
                        for edge_key in parent_poly.edge_keys:
                            edge_indices.append(edge_key)

                        for i in range(3):
                            vert_idx_cache.add(triangle.vertices[i])

            for i in range(3):
                verts.append(mesh.vertices[triangle.vertices[i]].co)
                colors.append(group_color)

            triangle_indices.append([idx, idx+1, idx+2])
            idx = idx + 3

        shader = gpu.types.GPUShader(vertex_shader, fragment_shader)
        batch = batch_for_shader(
            shader, 'TRIS',
            {"position": verts, "color": colors},
            indices=triangle_indices,
        )

        if obj.rv_show_wire:
            wireframe_batch = self.prep_wireframe_batch(shader, mesh, obj, vert_idx_cache, edge_indices)

        if obj.rv_show_poles:
            pole_batch = self.prep_pole_batch(shader, mesh, obj)

        if obj.rv_backface_culling:
            bgl.glEnable(bgl.GL_CULL_FACE)

        bgl.glEnable(bgl.GL_DEPTH_TEST)
        bgl.glEnable(bgl.GL_BLEND)

        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        if space.shading.type == 'WIREFRAME':
                            bgl.glDepthFunc(bgl.GL_ALWAYS)

        if obj.show_in_front:
            bgl.glDepthFunc(bgl.GL_ALWAYS)
            bgl.glEnable(bgl.GL_CULL_FACE)

        shader.bind()
        shader.uniform_float("viewProjectionMatrix", bpy.context.region_data.perspective_matrix)
        shader.uniform_float("worldMatrix", obj.matrix_world)
        shader.uniform_float("alpha", obj.rv_groups_alpha)
        batch.draw(shader)

        bgl.glDepthFunc(bgl.GL_LEQUAL)
        shader.uniform_float("alpha", 1)

        if obj.rv_show_wire:
            wireframe_batch.draw(shader)

        if obj.rv_show_poles:
            bgl.glLineWidth(2)
            pole_batch.draw(shader)

        bgl.glLineWidth(1)
        bgl.glDisable(bgl.GL_DEPTH_TEST)
        bgl.glDisable(bgl.GL_BLEND)

        if obj.rv_backface_culling:
            bgl.glDisable(bgl.GL_CULL_FACE)

    def modal(self, context, event):
        context.area.tag_redraw()

        try:
            if not self.invoked_obj.rv_enabled:
                bpy.types.SpaceView3D.draw_handler_remove(self.overlay_handler, 'WINDOW')
                return {'FINISHED'}
        except ReferenceError:
            bpy.types.SpaceView3D.draw_handler_remove(self.overlay_handler, 'WINDOW')
            return {'FINISHED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        depsgraph = bpy.context.evaluated_depsgraph_get()
        args = (context, depsgraph, context.object)

        self.invoked_obj = context.object
        self.overlay_handler = bpy.types.SpaceView3D.draw_handler_add(self.draw_overlay, args, 'WINDOW', 'POST_VIEW')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}