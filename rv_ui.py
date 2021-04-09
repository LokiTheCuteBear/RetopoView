import bpy
from bpy.types import UIList, Panel, Menu


class RETOPOVIEW_MT_rv_pie_menu(Menu):
    bl_label = "RetopoView"
    bl_idname = "RETOPOVIEW_MT_rv_pie_menu"

    def draw(self, context):
        pie = self.layout.menu_pie()

        if context.object.type != 'MESH':
            box = pie.box()
            box.label(text='No valid object')
            return

        if not context.mode == 'EDIT_MESH':
            if len(context.object.rv_groups) <= 0:
                pie.operator("retopoview.add_group", text='Add New Group')
            else:
                pie.operator("retopoview.toggle_mode", text='Toggle Overlay')
            return

        if not context.object.rv_enabled:
            pie.operator("retopoview.toggle_mode", text='Toggle Overlay')
        else:
            pie.operator("retopoview.change_selection_group_id", text='Remove').remove = True
            pie.operator("retopoview.handle_face_selection", text='Deselect').deselect = True
            pie.operator("retopoview.add_group", text='Add New Group')
            pie.operator("retopoview.find_parent_group", text='Find Parent Group')
            pie.operator("retopoview.change_selection_group_id", text='Assign').remove = False
            pie.operator("retopoview.handle_face_selection", text='Select').deselect = False
            pie.operator("retopoview.toggle_mode", text='Toggle Mode')


class RETOPOVIEW_UL_group_list(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, "color", text="", emboss=True, icon='COLOR')
        layout.prop(item, "name", text="", emboss=False)


class RETOPOVIEW_PT_rv_tool_menu(Panel):
    bl_label = "Topology Groups"
    bl_idname = "RETOPOVIEW_PT_rv_tool_menu"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_category = 'RetopoView'
    bl_context = 'data'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        obj = context.object

        if obj is None or obj.type != 'MESH':
            layout.label(text='No valid object')
            return

        if len(obj.rv_groups) > 0:
            toggle_text = 'Show' if not obj.rv_enabled else 'Hide'
            toggle_icon = 'HIDE_OFF' if obj.rv_enabled else 'HIDE_ON'

            enable_box = layout.box()
            enable_container = enable_box.row()
            enable_container.operator('retopoview.toggle_mode', text=toggle_text, icon=toggle_icon)
            enable_container.scale_y = 1.5

        layout.separator(factor=0.1)

        list_row = layout.row()
        list_row.template_list("RETOPOVIEW_UL_group_list", "", obj, "rv_groups", obj, "rv_index")

        list_controls = list_row.column(align=True)
        list_controls.operator("retopoview.add_group", text='', icon='ADD')
        list_controls.operator("retopoview.remove_group", text='', icon='REMOVE')

        list_controls.separator()

        list_controls.operator("retopoview.move_group", text='', icon='TRIA_UP').direction = 'UP'
        list_controls.operator("retopoview.move_group", text='', icon='TRIA_DOWN').direction = 'DOWN'

        layout.separator(factor=0.1)

        if len(obj.rv_groups) <= 0:
            return

        active_box = layout.box()

        active_content_row = active_box.row(align=True)
        active_content_row.alignment = 'LEFT'
        active_content_row.label(text='Active: ')

        group_subrow = active_content_row.row(align=True)

        group_subrow.prop(obj.rv_groups[obj.rv_index], 'color', icon_only=True, icon='COLOR')
        group_subrow.label(text=obj.rv_groups[obj.rv_index].name)

        box = layout.box()
        box.enabled = obj.mode == 'EDIT' and obj.rv_enabled
        edit_column = box.column()

        edit_column.separator(factor=0.5)

        assign_row = edit_column.row(align=True)
        assign_row.operator("retopoview.change_selection_group_id", text='Assign').remove = False
        assign_row.operator("retopoview.change_selection_group_id", text='Remove').remove = True

        edit_column.separator(factor=0.1)

        select_row = edit_column.row(align=True)
        select_row.operator("retopoview.handle_face_selection", text='Select').deselect = False
        select_row.operator("retopoview.handle_face_selection", text='Deselect').deselect = True

        edit_column.separator(factor=0.1)

        parent_finder_row = edit_column.row(align=True)
        parent_finder_row.operator("retopoview.find_parent_group", text='Find Parent Group')

        edit_column.separator(factor=0.5)

        layout.separator(factor=0.1)

        quick_access_column = layout.column()
        quick_access_column.prop(obj, 'rv_groups_alpha', text='Overlay Opacity', slider=True)
        quick_access_column.separator(factor=0.2)
        quick_access_column.prop(obj, 'rv_backface_culling', text='Backface Culling')
        quick_access_column.prop(obj, "rv_show_wire", text="Show Wireframe")
        quick_access_column.prop(obj, 'show_in_front', text='Object In Front')
        quick_access_column.prop(obj, 'rv_use_x_mirror', text='X Mirror')
        quick_access_column.prop(obj, 'rv_show_poles', text='Show Poles')

        poles_settings_column = layout.column()

        if obj.rv_show_poles:
            color_row = poles_settings_column.row()
            color_row.prop(obj, 'rv_poles_color', text='Poles Color', icon='COLOR', emboss=True)
            poles_settings_column.separator(factor=0.1)
            poles_settings_column.prop(obj, 'rv_poles_size', text='Poles Size', slider=True)
