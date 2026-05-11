# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.api.OpenMaya as om

class ProjectComponentTool(object):
    def __init__(self):
        self.window_name = "projectCompUI_vFinal"
        self.help_window_name = "projectCompHelpUI"
        self.target_mesh = None
        self.temp_target_mesh = None
        
        # 核心缓存变量
        self.cache = {}
        self.callback_ids = [] 
        self.is_paused = False
        self.is_updating = False 

    def create_ui(self):
        """创建极致平衡恢复版 UI - 解决黑底拉伸对齐，移除 Slider 残影"""
        
        # 1. 仅清理旧窗口，**保留首选项(windowPref)** 以记住上次拖动的位置
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name)
        # 移除下面两行清理首选项的代码，让 Maya 自动接管窗口位置记忆
        # if cmds.windowPref(self.window_name, exists=True):
        #     cmds.windowPref(self.window_name, remove=True)

        # 2. 设定窗口 - 宽度 240, 高度 395 (极致平衡尺寸), 固定边框
        self.window = cmds.window(
            self.window_name, 
            title="组件投影 Pro", 
            widthHeight=(240, 395), 
            bgc=(0.2, 0.2, 0.2), 
            sizeable=False 
        )
        
        cmds.window(self.window, edit=True, cc=self.clear_session)
        
        # 3. 主列布局 - 左右边距锁定为 15px (对齐基准)
        main_col = cmds.columnLayout(adjustableColumn=True, rowSpacing=5, columnAttach=('both', 15))
        
        cmds.separator(style="none", height=8)

        # --- 1. 目标区域 ---
        cmds.rowLayout(nc=2, cw2=(180, 25), adjustableColumn=1)
        self.target_text = cmds.text(label="目标 >  ---", align="left", font="smallPlainLabelFont", h=15)
        cmds.button(label="?", width=22, h=18, backgroundColor=(0.3, 0.3, 0.3), command=self.show_tutorial)
        cmds.setParent('..')

        cmds.iconTextButton(label="  设定吸附目标 / 基底", image="setKeyframe.png", style='iconAndTextHorizontal', 
                            h=32, backgroundColor=(0.28, 0.28, 0.28), command=self.set_target)
        
        cmds.separator(style="in", height=5)

        # --- 2. 投影类型 ---
        cmds.text(label="投影对齐方式", align="left", font="smallPlainLabelFont")
        self.proj_type = cmds.optionMenu(backgroundColor=(0.18, 0.18, 0.18), h=24)
        cmds.menuItem(label="对象轴向 (Object Axis)")
        cmds.menuItem(label="基础法线 (Base Normal)")

        # --- 3. RGB 向量 (对齐下方) ---
        # 4+61, 4+61, 4+61 = 195px
        cmds.rowLayout(numberOfColumns=6, 
                       cw6=(4, 61, 4, 61, 4, 61),
                       columnOffset6=(0, 2, 0, 2, 0, 2))
        
        cmds.text(label="", backgroundColor=(0.8, 0.2, 0.2), height=18)
        self.v_x = cmds.floatField(value=0.0, pre=2, backgroundColor=(0.12, 0.12, 0.12), cc=self.on_ui_change)
        
        cmds.text(label="", backgroundColor=(0.4, 0.7, 0.3), height=18)
        self.v_y = cmds.floatField(value=-1.0, pre=2, backgroundColor=(0.12, 0.12, 0.12), cc=self.on_ui_change)
        
        cmds.text(label="", backgroundColor=(0.2, 0.6, 0.9), height=18)
        self.v_z = cmds.floatField(value=0.0, pre=2, backgroundColor=(0.12, 0.12, 0.12), cc=self.on_ui_change)
        cmds.setParent('..')

        cmds.separator(style="none", height=4)

        # --- 4. 参数行 (核心恢复：使用 floatField 确保黑底完全拉满) ---
        def create_param_row(label, is_target_change=True):
            # 固定标签宽度 110，第二列输入框横向拉伸至 195px 边界
            cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(110, 85), columnAttach2=("both", "both"))
            cmds.text(label=label, align="left")
            return cmds.floatField(value=0.0, pre=2, h=20, backgroundColor=(0.12, 0.12, 0.12), 
                                   cc=self.on_target_ui_change if is_target_change else self.on_ui_change)

        self.t_smooth = create_param_row("目标平滑")
        cmds.setParent('..')
        self.t_inflation = create_param_row("目标膨胀")
        cmds.setParent('..')
        self.t_offset = create_param_row("最终吸附偏移", is_target_change=False)
        cmds.setParent('..')

        # --- 5. 选项开关 ---
        def create_check_row(label, val, cmd):
            cmds.rowLayout(nc=2, adjustableColumn=1, cw2=(170, 25), columnAttach2=("both", "right"))
            cmds.text(label=label, align="left")
            return cmds.checkBox(label="", value=val, cc=cmd)

        self.cb_reverse = create_check_row("反向投影方向", False, self.on_ui_change)
        cmds.setParent('..')
        self.cb_bidi = create_check_row("双向射线探测", True, self.on_ui_change)
        cmds.setParent('..')

        # --- 6. 实时状态控制 ---
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnWidth3=(110, 43, 43))
        cmds.text(label="实时状态控制", align="left")
        self.btn_pause = cmds.button(label="||", width=41, h=22, backgroundColor=(0.28, 0.28, 0.28), command=self.toggle_pause)
        self.btn_reset = cmds.iconTextButton(image="refresh.png", style="iconOnly", width=41, h=22, 
                                             backgroundColor=(0.28, 0.28, 0.28), command=self.reset_state)
        cmds.setParent('..')

        # --- 主按钮上移微调 ---
        cmds.separator(style="none", height=2)

        # --- 7. 主吸附按钮 (修复警告：替换为全版本通用图标) ---
        cmds.iconTextButton(style='iconAndTextHorizontal', image1='polyMoveVertex.png', 
                            label="   开始实时投影吸附", height=48, font="boldLabelFont",
                            backgroundColor=(0.35, 0.35, 0.35), command=self.start_projection_session)
        
        # --- 8. 底部留白平衡 (15px) ---
        cmds.separator(style="none", height=15)

        # 显示窗口
        cmds.showWindow(self.window)
        # 强制锁定尺寸并消除残留滑条
        cmds.window(self.window, edit=True, widthHeight=(240, 395))

    def show_tutorial(self, *args):
        """教程说明 (大字体版)"""
        if cmds.window(self.help_window_name, exists=True):
            cmds.deleteUI(self.help_window_name)
        # 放大教程窗口尺寸以容纳更大的字体
        help_win = cmds.window(self.help_window_name, title="组件投影 Pro - 使用手册", widthHeight=(380, 560), bgc=(0.15, 0.15, 0.15))
        cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAttach=('both', 15))
        
        cmds.separator(style="none", height=2)
        cmds.text(label="📖 详细使用指南", font="boldLabelFont", height=20)
        
        tutorial_text = (
            "【🚀 基本工作流】\n"
            "1. 设定基底：在场景中选中作为目标表面的模型，点击 [设定吸附目标 / 基底]。\n"
            "2. 选择组件：选中你需要吸附的模型顶点、边或面。\n"
            "3. 开启吸附：点击底部的 [开始实时投影吸附] 按钮开启 Live 模式。\n\n"
            
            "【⚙️ 核心参数详解】\n"
            "🔹 投影对齐方式：\n"
            "   - 对象轴向：沿指定的 RGB 向量发射射线（如 0, -1, 0 为向下投影）。\n"
            "   - 基础法线：沿目标模型表面的法向进行吸附。\n"
            "🔹 目标平滑：在内存中临时细分基底模型，使投影表面更圆滑。\n"
            "🔹 目标膨胀：将基底表面法向外扩或内收一定距离后再进行投影。\n"
            "🔹 最终吸附偏移：投影完成后，沿表面额外偏移的距离。极其适合解决模型穿插或面闪烁（Z-Fighting）问题。\n"
            "🔹 反向投影方向：翻转当前设定的射线方向。\n"
            "🔹 双向射线探测：同时向正反两面发射射线，并自动吸附到距离最近的表面。\n\n"
            
            "【⚠️ 实时状态与拓扑修改】\n"
            "⏸️ 暂停 (||)：如果你需要对模型进行加线、挤出等改变拓扑结构的操作，请先点击暂停按钮。操作完成后，重新选中点，并再次点击底部大按钮即可恢复吸附。\n"
            "🔄 重置：清除当前缓存的投影状态与临时节点。"
        )
        
        # 将字体由 smallPlainLabelFont 改为更大更易读的 plainLabelFont，增加文本框高度
        cmds.scrollField(text=tutorial_text, editable=False, height=420, wordWrap=True, backgroundColor=(0.1, 0.1, 0.1), font="plainLabelFont")
        
        # 确认按钮加高 (修复报错：移除了不支持的 font 标志)
        cmds.button(label="💡 我已经完全了解", h=36, backgroundColor=(0.3, 0.4, 0.3), command=lambda x: cmds.deleteUI(help_win))
        cmds.separator(style="none", height=5)
        cmds.showWindow(help_win)

    # ---------------- 核心算法 ---------------- #

    def set_target(self, *args):
        sel = cmds.ls(selection=True, type='transform')
        if not sel: return
        self.target_mesh = sel[0]
        cmds.text(self.target_text, edit=True, label=f"目标 >  {self.target_mesh}")
        if self.cache: self.rebuild_temp_target()

    def toggle_pause(self, *args):
        self.is_paused = not self.is_paused
        if self.is_paused:
            cmds.button(self.btn_pause, edit=True, label="▶", backgroundColor=(0.4, 0.2, 0.2)) 
            if self.cache and 'mesh_fn' in self.cache:
                self.is_updating = True 
                try:
                    if self.cache['mesh_fn'].numVertices == len(self.cache['orig_points']):
                        self.cache['mesh_fn'].setPoints(self.cache['orig_points'], om.MSpace.kObject)
                    cmds.refresh(cv=True, f=True)
                except: pass
                finally: self.is_updating = False
        else:
            cmds.button(self.btn_pause, edit=True, label="||", backgroundColor=(0.2, 0.4, 0.2)) 
            self.update_projection()

    def reset_state(self, *args):
        self.clear_session(reset_points=True)

    def on_ui_change(self, *args):
        self.update_projection()

    def on_target_ui_change(self, *args):
        if self.cache:
            self.rebuild_temp_target()
            self.update_projection()

    def clear_session(self, reset_points=False):
        if self.callback_ids:
            for id in self.callback_ids:
                try: om.MMessage.removeCallback(id)
                except: pass
            self.callback_ids = []
        if reset_points and self.cache:
            try:
                if self.cache['mesh_fn'].numVertices == len(self.cache['orig_points']):
                    self.cache['mesh_fn'].setPoints(self.cache['orig_points'], om.MSpace.kObject)
                    cmds.refresh(cv=True, f=True)
            except: pass
        if self.temp_target_mesh and cmds.objExists(self.temp_target_mesh):
            cmds.delete(self.temp_target_mesh)
        self.temp_target_mesh = None
        if reset_points: self.cache = {}

    def start_projection_session(self, *args):
        if not self.target_mesh: return cmds.warning("请先设置目标模型！")
        sel_comp = cmds.ls(selection=True, flatten=True)
        if not sel_comp: return cmds.warning("请先选择顶点/边/面！")

        self.clear_session(reset_points=False)
        transform = sel_comp[0].split('.')[0]
        sel_list = om.MSelectionList()
        sel_list.add(transform)
        dag_path = sel_list.getDagPath(0)
        
        verts = cmds.polyListComponentConversion(sel_comp, toVertex=True)
        indices = [int(v.split('[')[1].split(']')[0]) for v in cmds.ls(verts, flatten=True)]

        mesh_fn = om.MFnMesh(dag_path)
        self.cache = {
            'transform': transform,
            'dag_path': dag_path,
            'mesh_fn': mesh_fn,
            'orig_points': mesh_fn.getPoints(om.MSpace.kObject), 
            'indices': indices,
            'vert_count': mesh_fn.numVertices 
        }
        self.rebuild_temp_target()
        
        m_obj = dag_path.node()
        self.callback_ids.append(om.MNodeMessage.addNodeDirtyCallback(m_obj, self.api_callback_wrapper))
        
        t_sel = om.MSelectionList()
        t_sel.add(self.target_mesh)
        self.callback_ids.append(om.MNodeMessage.addNodeDirtyCallback(t_sel.getDagPath(0).node(), self.api_callback_wrapper))

        self.is_paused = False
        cmds.button(self.btn_pause, edit=True, label="||", backgroundColor=(0.2, 0.4, 0.2))
        self.update_projection()

    def api_callback_wrapper(self, node, data):
        if not self.is_paused:
            self.update_projection()

    def rebuild_temp_target(self):
        if self.temp_target_mesh and cmds.objExists(self.temp_target_mesh):
            cmds.delete(self.temp_target_mesh)
        s_val = cmds.floatField(self.t_smooth, query=True, value=True)
        i_val = cmds.floatField(self.t_inflation, query=True, value=True)
        target_path = self.target_mesh
        if s_val > 0 or abs(i_val) > 0.0001:
            self.temp_target_mesh = cmds.duplicate(self.target_mesh)[0]
            cmds.hide(self.temp_target_mesh)
            if s_val >= 0.5: cmds.polySmooth(self.temp_target_mesh, divisions=int(s_val), ch=False)
            if abs(i_val) > 0.0001: cmds.polyMoveVertex(self.temp_target_mesh, localTranslateZ=i_val, ch=False)
            target_path = self.temp_target_mesh
        sl = om.MSelectionList()
        sl.add(target_path)
        self.cache['target_fn'] = om.MFnMesh(sl.getDagPath(0))

    def update_projection(self, *args):
        if self.is_paused or not self.cache or self.is_updating: return
        if not cmds.objExists(self.cache['transform']): return self.clear_session()
            
        if self.cache['mesh_fn'].numVertices != self.cache['vert_count']:
            self.toggle_pause() 
            cmds.warning("拓扑已改变！请重新选点同步。")
            return

        self.is_updating = True 
        try:
            vx = cmds.floatField(self.v_x, query=True, value=True)
            vy = cmds.floatField(self.v_y, query=True, value=True)
            vz = cmds.floatField(self.v_z, query=True, value=True)
            offset_val = cmds.floatField(self.t_offset, query=True, value=True)
            rev = cmds.checkBox(self.cb_reverse, query=True, value=True)
            bidi = cmds.checkBox(self.cb_bidi, query=True, value=True)

            world_mat = self.cache['dag_path'].inclusiveMatrix()
            inv_world_mat = world_mat.inverse()
            
            local_ray = om.MVector(vx, vy, vz)
            if rev: local_ray *= -1.0
            world_ray = local_ray * world_mat
            ray_dir = om.MFloatVector(world_ray.x, world_ray.y, world_ray.z)
            ray_dir.normalize()

            new_pts = om.MPointArray(self.cache['orig_points'])
            target_fn = self.cache['target_fn']

            for idx in self.cache['indices']:
                if idx >= len(new_pts): continue
                world_pos = new_pts[idx] * world_mat
                m_pos = om.MFloatPoint(world_pos.x, world_pos.y, world_pos.z)
                
                hit = target_fn.closestIntersection(m_pos, ray_dir, om.MSpace.kWorld, 99999, False)
                dist_p = hit[1] if hit else float('inf')
                best_hit = hit

                if bidi:
                    hit_s = target_fn.closestIntersection(m_pos, ray_dir * -1.0, om.MSpace.kWorld, 99999, False)
                    dist_s = hit_s[1] if hit_s else float('inf')
                    if dist_s < dist_p: best_hit = hit_s

                if best_hit:
                    h_pos = best_hit[0]
                    h_norm = om.MFloatVector(target_fn.getPolygonNormal(best_hit[2], om.MSpace.kWorld))
                    final_w = om.MPoint(h_pos.x + h_norm.x * offset_val, h_pos.y + h_norm.y * offset_val, h_pos.z + h_norm.z * offset_val)
                    new_pts[idx] = final_w * inv_world_mat
                    
            self.cache['mesh_fn'].setPoints(new_pts, om.MSpace.kObject)
            cmds.refresh(cv=True, f=True)
        finally:
            self.is_updating = False 

if __name__ == "__main__":
    tool = ProjectComponentTool()
    tool.create_ui()