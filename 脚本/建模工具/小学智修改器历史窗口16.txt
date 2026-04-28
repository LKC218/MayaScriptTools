# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om
import random
import math
import sys
import os
import shutil

class ModifierStackWindow(object):
    def __init__(self):
        self.window_name = "XiaoXueZhiModifierStackUI"
        
        # 升级为 V15 版本：根据现代DCC软件全面重构高级扁平化UI，并加入大量拓展工具箱
        self.version = "V15"
        self.plugin_name = "小学智修改器历史窗口"
        self.window_title = f"{self.plugin_name} {self.version}"
        self.job_num = None
        
        self.current_root = None 
        self.row_uis = {}
        self.copied_shading_group = None
        
        # --- 全局高级色彩主题库 (根据参考图定制) ---
        self.theme = {
            'bg': [0.14, 0.14, 0.14],           # 全局深色底
            'panel': [0.18, 0.18, 0.18],        # 模块底色
            'accent': [0.27, 0.47, 0.73],       # 经典强调蓝
            'accent_dark': [0.20, 0.35, 0.55],  # 经典强调蓝(暗)
            'btn': [0.24, 0.24, 0.24],          # 按钮灰
            'btn_tb': [0.30, 0.40, 0.22],       # TB材质专属按钮色(绿)
            'row_odd': [0.22, 0.22, 0.22],      # 列表单数行(浅)
            'row_even': [0.18, 0.18, 0.18],     # 列表双数行(深)
            'selected': [0.28, 0.45, 0.65],     # 选中高亮蓝
            'disabled': [0.12, 0.12, 0.12]      # 关闭状态极暗灰
        }
        
        # --- 多选系统状态 ---
        self.ordered_modifiers = []
        self.selected_modifiers = []
        self.last_clicked = None
        self.clipboard = [] 
        
        # 图标路径
        self.icon_on = "图层 4.png"  
        self.icon_off = "图层 5.png" 
        
        self.node_name_dict = {
            'polyCube': '多边形立方体', 'polySphere': '多边形球体', 'polyCylinder': '多边形圆柱体',
            'polyPlane': '多边形平面', 'polyTorus': '多边形圆环',
            'polyExtrudeFace': '挤出面', 'polyExtrudeEdge': '挤出边', 'polyExtrudeVertex': '挤出顶点',
            'polyBevel': '倒角', 'polyBevel2': '倒角', 'polyBevel3': '倒角',
            'polySmoothFace': '平滑', 'polyTweak': '软选择位移',
            'polyBoolOp': '布尔运算', 'polyCBoolOp': '布尔运算',
            'polyMergeVert': '合并顶点', 'polyMergeEdge': '合并边',
            'polyMirror': '镜像', 'polySeparate': '分离', 'polyUnite': '结合',
            'polyCut': '切割', 'polySplit': '分割',
            'polySubdFace': '细分面', 'polyTriangulate': '三角化', 'polyQuad': '四边形化',
            'deleteComponent': '删除组件', 'transform': '变换', 'mesh': '网格',
            'blendShape': '融合变形', 'skinCluster': '蒙皮簇', 'tweak': '调整节点'
        }
        
        self.workspace_name = f"{self.window_name}_{self.version}_Workspace"
        
        self.build_ui()
        self.create_script_job()
        self.force_refresh()

    def build_ui(self):
        if cmds.window(self.window_name, exists=True): cmds.deleteUI(self.window_name)
        # 清理旧版本缓存面板
        for old_v in ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11", "V12", "V13", "V14", "V15"]:
            old_ws = f"{self.window_name}_{old_v}_Workspace"
            if cmds.workspaceControl(old_ws, exists=True): cmds.deleteUI(old_ws, control=True)
            
        if cmds.workspaceControl(self.workspace_name, exists=True):
            cmds.deleteUI(self.workspace_name, control=True)
            
        self.window = cmds.workspaceControl(self.workspace_name, label=self.window_title, retain=False, floating=True)
        cmds.setParent(self.workspace_name)
        
        # 主框架：使用 formLayout 让窗口内容可随意拉伸
        self.main_layout = cmds.formLayout(backgroundColor=self.theme['bg'])
        self.top_layout = cmds.columnLayout(adjustableColumn=True, backgroundColor=self.theme['bg'], rowSpacing=0)
        
        cmds.separator(height=6, style='none')
        
        # 【Header：高亮对象重命名区】
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnWidth3=(40, 200, 30), columnAttach=[(1, 'both', 4), (2, 'both', 0), (3, 'both', 4)])
        cmds.button(label="帮助", command=lambda x: self.show_help(), height=24, backgroundColor=self.theme['accent'], annotation="查看使用方法")
        
        self.header_wrapper = cmds.columnLayout(adjustableColumn=True)
        self.header_text = cmds.iconTextButton(style='textOnly', label="当前未选择对象", font="boldLabelFont", align="center", backgroundColor=self.theme['panel'], height=24, doubleClickCommand=lambda: self.enable_rename_mode(), annotation="双击重命名")
        self.header_rename_field = cmds.textField(manage=False, height=24, backgroundColor=self.theme['panel'], font="boldLabelFont", enterCommand=lambda x: self.apply_rename(), changeCommand=lambda x: self.apply_rename(), alwaysInvokeEnterCommandOnReturn=True)
        cmds.setParent("..")
        
        cmds.button(label="↻", command=lambda x: self.force_refresh(), height=24, backgroundColor=self.theme['btn'], annotation="刷新列表")
        cmds.setParent("..")
        
        cmds.separator(height=6, style='none')
        
        # 【Toolbar：扁平化工具矩阵】
        cmds.columnLayout(adjustableColumn=True, rowSpacing=1, backgroundColor=self.theme['bg'])
        
        # 工具栏第一排：模型与UV
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(140, 140), columnAttach=[(1, 'both', 0), (2, 'both', 0)])
        cmds.button(label="独立复制(带历史)", command=lambda x: self.duplicate_with_history(), height=24, backgroundColor=self.theme['btn'], annotation="原地复制模型并独立继承历史")
        cmds.button(label="批量拓扑传 UV", command=lambda x: self.batch_transfer_uvs(), height=24, backgroundColor=self.theme['btn'], annotation="基于点序号精准传递UV防翻转")
        cmds.setParent("..")
        
        # 工具栏第二排：全局材质管理
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=1, columnWidth4=(65, 65, 65, 65), columnAttach=[(1, 'both', 0), (2, 'both', 0), (3, 'both', 0), (4, 'both', 0)])
        cmds.button(label="复制材质", command=lambda x: self.copy_material(), height=24, backgroundColor=self.theme['btn'])
        cmds.button(label="关联粘贴", command=lambda x: self.paste_material(is_duplicate=False), height=24, backgroundColor=self.theme['btn'])
        cmds.button(label="独立粘贴", command=lambda x: self.paste_material(is_duplicate=True), height=24, backgroundColor=self.theme['btn'])
        cmds.button(label="一键法线", command=lambda x: self.quick_assign_normal_action(), height=24, backgroundColor=self.theme['btn_tb'], annotation="一键为模型/材质连接法线，自动锁定 Raw 色彩与切线空间")
        cmds.setParent("..")

        # 工具栏第三排：优化与清理扩展系统
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=1, columnWidth4=(80, 80, 80, 80), columnAttach=[(1, 'both', 0), (2, 'both', 0), (3, 'both', 0), (4, 'both', 0)])
        cmds.button(label="随机ID", command=lambda x: self.generate_mat_ids(), height=24, backgroundColor=self.theme['btn_tb'], annotation="智能识别：按 UV 壳为物体分配材质ID，或为选中面分配")
        cmds.button(label="清理未用", command=lambda x: self.clean_unused_nodes(), height=24, backgroundColor=self.theme['btn'], annotation="一键删除所有未分配使用的材质球及无用节点")
        cmds.button(label="删空组", command=lambda x: self.delete_empty_groups(), height=24, backgroundColor=self.theme['btn'], annotation="深度清理：删除空组、无点网格模型、无子级节点")
        cmds.button(label="删命名空间", command=lambda x: self.delete_all_namespaces(), height=24, backgroundColor=self.theme['btn'], annotation="一键删除所有名称空间并提取内容到根目录")
        cmds.setParent("..")

        # 工具栏第四排：智能选择辅助
        cmds.rowLayout(numberOfColumns=1, adjustableColumn=1, columnAttach=[(1, 'both', 0)])
        cmds.button(label="智能选内壳 (分离被包裹的零件)", command=lambda x: self.select_inner_parts(), height=24, backgroundColor=self.theme['accent_dark'], annotation="框选全部模型：智能提取并选中那些完全包裹在外壳内部的独立物体（如枪械内管、模型内构）")
        cmds.setParent("..")
        
        # 工具栏第五排：贴图检查与光照模式 (V15 新增)
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=1, columnWidth4=(80, 65, 65, 90), columnAttach=[(1, 'both', 0), (2, 'both', 0), (3, 'both', 0), (4, 'both', 0)])
        cmds.button(label="Map 2", command=lambda x: self.apply_map2(), height=24, backgroundColor=self.theme['btn_tb'], annotation="一键赋予方向检查贴图 (Checker)")
        cmds.button(label="贴图 +45°", command=lambda x: self.spin_texture(45), height=24, backgroundColor=self.theme['btn_tb'], annotation="将选中物体材质上的2D纹理顺时针旋转 45 度")
        cmds.button(label="贴图 -45°", command=lambda x: self.spin_texture(-45), height=24, backgroundColor=self.theme['btn_tb'], annotation="将选中物体材质上的2D纹理逆时针旋转 45 度")
        cmds.button(label="无光照 Flat", command=lambda x: self.toggle_base_color_mode(), height=24, backgroundColor=[0.35, 0.60, 0.75], annotation="一键切换当前视图为无光照(Base Color)模式或默认光照模式")
        cmds.setParent("..")
        
        cmds.setParent("..") # 结束 Toolbar
        
        cmds.separator(height=8, style='none')
        cmds.setParent(self.main_layout)
        
        # 【核心架构：可拖拽分割面板用于容纳历史列表与动态参数面板】
        self.pane_layout = cmds.paneLayout(configuration='horizontal2', separatorThickness=4, paneSize=[(1, 100, 55), (2, 100, 45)])
        
        # ====== 上半部分：斑马线历史列表 ======
        self.scroll_layout = cmds.scrollLayout(childResizable=True, backgroundColor=self.theme['bg'])
        bg_menu = cmds.popupMenu(parent=self.scroll_layout, button=3)
        cmds.menuItem(parent=bg_menu, label="粘贴历史组合 (Paste Modifiers)", command=lambda x: self.paste_to_model())
        
        self.stack_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=0) # 无缝隙紧凑排列
        cmds.setParent("..") # 结束 stack_layout
        cmds.setParent("..") # 结束 scroll_layout

        # ====== 下半部分：Mini AE (动态内嵌参数面板) ======
        self.mini_ae_scroll = cmds.scrollLayout(childResizable=True, backgroundColor=self.theme['bg'])
        self.mini_ae_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=0)
        self.clear_mini_ae()
        cmds.setParent("..") # 结束 mini_ae_layout
        cmds.setParent("..") # 结束 mini_ae_scroll
        
        cmds.setParent("..") # 结束 pane_layout

        cmds.formLayout(
            self.main_layout,
            edit=True,
            attachForm=[
                (self.top_layout, 'top', 0),
                (self.top_layout, 'left', 0),
                (self.top_layout, 'right', 0),
                (self.pane_layout, 'left', 0),
                (self.pane_layout, 'right', 0),
                (self.pane_layout, 'bottom', 0)
            ],
            attachControl=[
                (self.pane_layout, 'top', 0, self.top_layout)
            ]
        )

    def create_script_job(self):
        self.job_num = cmds.scriptJob(event=["SelectionChanged", self.on_selection_changed], parent=self.workspace_name)

    def get_transform(self, node):
        if not node: return None
        if '.' in node: node = node.split('.')[0]
        if not cmds.objExists(node): return None
        if cmds.objectType(node, isAType='transform'): return node
        elif cmds.objectType(node, isAType='shape'):
            parents = cmds.listRelatives(node, parent=True, fullPath=True)
            if parents: return parents[0]
        return None

    def get_selected_transforms(self):
        sel = cmds.ls(selection=True, long=True) or []
        transforms = []
        for node in sel:
            transform = self.get_transform(node)
            if transform and transform not in transforms:
                transforms.append(transform)
        return transforms

    def on_selection_changed(self):
        self.cancel_rename_mode()
        sel = cmds.ls(selection=True)
        if not sel:
            self.current_root = None
            self.populate_stack()
            return
        node = sel[0]
        transform = self.get_transform(node)
        if transform:
            if transform != self.current_root:
                self.current_root = transform
            self.populate_stack()
        else:
            node_name = node.split('.')[0]
            if self.current_root:
                hist = cmds.listHistory(self.current_root) or []
                if node_name in hist:
                    if node_name not in self.selected_modifiers:
                        self.selected_modifiers = [node_name]
                        self.last_clicked = node_name
                    self.refresh_highlights()
                    return
            self.current_root = node_name
            self.populate_stack()

    def force_refresh(self):
        sel = cmds.ls(selection=True)
        if sel:
            transform = self.get_transform(sel[0])
            self.current_root = transform if transform else sel[0].split('.')[0]
        else:
            self.current_root = None
        self.populate_stack()

    def clear_mini_ae(self):
        """清空底部的动态参数面板"""
        if cmds.control(self.mini_ae_layout, exists=True):
            children = cmds.layout(self.mini_ae_layout, query=True, childArray=True) or []
            for child in children:
                cmds.deleteUI(child)
            cmds.setParent(self.mini_ae_layout)
            cmds.separator(height=20, style='none')
            cmds.text(label="请在上方列表中点击节点以调节参数", align="center", font="smallPlainLabelFont")

    def populate_mini_ae(self, node):
        """智能生成选中历史节点的各项参数控制滑杆 (Mini AE)"""
        if not cmds.control(self.mini_ae_layout, exists=True):
            return
            
        children = cmds.layout(self.mini_ae_layout, query=True, childArray=True) or []
        for child in children:
            cmds.deleteUI(child)
            
        cmds.setParent(self.mini_ae_layout)
        
        if not node or not cmds.objExists(node):
            self.clear_mini_ae()
            return
            
        node_type = cmds.nodeType(node)
        display_name = self.node_name_dict.get(node_type, node_type)
        
        # 构建头部标签
        cmds.frameLayout(label=f" ⚙️ {display_name} 节点参数 ({node})", collapsable=False, backgroundColor=self.theme['panel'], font="boldLabelFont", borderVisible=False)
        cmds.separator(height=5, style='none')
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4, columnAttach=('both', 10))
        
        # 智能提取关键参数
        attrs = cmds.listAttr(node, keyable=True) or []
        cb_attrs = cmds.listAttr(node, channelBox=True) or []
        all_attrs = []
        for a in (attrs + cb_attrs):
            if a not in all_attrs:
                all_attrs.append(a)
                
        # 过滤掉无需展示的系统或底层属性
        ignore = ['nodeState', 'caching', 'isHistoricallyInteresting', 'frozen', 'message', 'binMembership', 'weightList', 'colorSet', 'uvSet']
        
        count = 0
        for attr in all_attrs:
            if attr in ignore or '[' in attr: 
                continue
            plug = f"{node}.{attr}"
            if not cmds.objExists(plug):
                continue
                
            try:
                # 核心黑科技：直接利用原生引擎生成带有标准中文翻译和限制范围的控件
                cmds.attrControlGrp(attribute=plug)
                count += 1
            except Exception:
                pass
                
        if count == 0:
            cmds.separator(height=10, style='none')
            cmds.text(label="该节点没有常规的可调参数。", align="center", font="smallPlainLabelFont")
            cmds.separator(height=10, style='none')
            
        cmds.setParent("..")
        cmds.setParent("..")

    def cancel_rename_mode(self):
        if cmds.control(self.header_rename_field, exists=True) and cmds.control(self.header_rename_field, query=True, manage=True):
            cmds.textField(self.header_rename_field, edit=True, manage=False)
            cmds.iconTextButton(self.header_text, edit=True, manage=True)

    def populate_stack(self):
        self.cancel_rename_mode()
        for child in cmds.layout(self.stack_layout, query=True, childArray=True) or []:
            cmds.deleteUI(child)
        self.row_uis = {}
        self.ordered_modifiers = []
        cmds.setParent(self.stack_layout)
        
        if not self.current_root or not cmds.objExists(self.current_root):
            # 空状态样式
            cmds.rowLayout(numberOfColumns=1, adjustableColumn=1, height=40, backgroundColor=self.theme['panel'])
            cmds.text(label="当前模型无修改记录", align="center", font="smallPlainLabelFont")
            cmds.setParent("..")
            cmds.iconTextButton(self.header_text, edit=True, label="当前未选择对象", backgroundColor=self.theme['panel'])
            self.clear_mini_ae()
            return
            
        cmds.iconTextButton(self.header_text, edit=True, label=f" {self.current_root}", align="center", backgroundColor=self.theme['accent_dark'])
        history = cmds.listHistory(self.current_root, pruneDagObjects=True) or []
        ignore_types = ['shadingEngine', 'materialInfo', 'objectSet', 'groupId', 'groupParts', 'hyperLayout']
        
        valid_modifiers = []
        for node in history:
            if cmds.nodeType(node) in ignore_types: continue
            if not cmds.attributeQuery('nodeState', node=node, exists=True): continue
            valid_modifiers.append(node)
            
        if not valid_modifiers:
            cmds.rowLayout(numberOfColumns=1, adjustableColumn=1, height=40, backgroundColor=self.theme['panel'])
            cmds.text(label="当前模型无修改记录", align="center", font="smallPlainLabelFont")
            cmds.setParent("..")
            self.clear_mini_ae()
            return

        self.ordered_modifiers = valid_modifiers

        # 【核心视觉更新：生成斑马线高颜值列表】
        for index, mod in enumerate(valid_modifiers):
            node_type = cmds.nodeType(mod)
            display_type = self.node_name_dict.get(node_type, node_type)
            
            try: state = cmds.getAttr(f"{mod}.nodeState"); is_on = (state == 0)
            except: is_on = True 
            
            # 计算隔行背景色
            base_color = self.theme['row_even'] if index % 2 == 0 else self.theme['row_odd']
            bg_color = base_color if is_on else self.theme['disabled']
                
            row = cmds.rowLayout(numberOfColumns=4, columnWidth4=(24, 160, 80, 24), adjustableColumn=2, 
                                 columnAttach=[(1, 'both', 2), (2, 'both', 0), (3, 'both', 4), (4, 'both', 2)],
                                 height=26, backgroundColor=bg_color)
            
            try: current_icon = self.icon_on if is_on else self.icon_off
            except: current_icon = 'menuIconDisplay.png'
                
            chk = cmds.iconTextCheckBox(style='iconOnly', image1=current_icon, value=is_on, width=20, height=20)
            name_btn = cmds.iconTextButton(style='textOnly', label="  " + mod, align='left', font="plainLabelFont", command=lambda m=mod: self.select_modifier(m))
                                
            pop_menu = cmds.popupMenu(parent=name_btn, button=3)
            cmds.menuItem(parent=pop_menu, label="重命名 (Rename)", command=lambda x, m=mod: self.rename_modifier(m))
            cmds.menuItem(parent=pop_menu, divider=True)
            cmds.menuItem(parent=pop_menu, label="全选所有步骤 (Select All)", command=lambda x: self.select_all())
            cmds.menuItem(parent=pop_menu, label="复制选中项参数 (Copy Selected)", command=lambda x, m=mod: self.copy_modifiers(m))
            cmds.menuItem(parent=pop_menu, label="粘贴历史组合 (Paste)", command=lambda x: self.paste_to_model())
            cmds.menuItem(parent=pop_menu, divider=True)
            cmds.menuItem(parent=pop_menu, label="删除选中项 (Delete)", command=lambda x, m=mod: self.delete_modifier(m))
            
            type_ui = cmds.text(label=display_type, align="right", font="smallPlainLabelFont", enable=is_on)
            del_btn = cmds.iconTextButton(style='iconOnly', image1='SP_TrashIcon.png', width=18, height=18, annotation="删除此操作", command=lambda m=mod: self.delete_modifier(m))
            
            # 绑定状态切换
            cmds.iconTextCheckBox(chk, edit=True, changeCommand=lambda val, m=mod, r=row, t=type_ui, c=chk, idx=index: self.toggle_node(m, val, r, t, c, idx))
            cmds.setParent("..")
            
            self.row_uis[mod] = (row, type_ui, index) # 记录index用于计算颜色

        sel = cmds.ls(selection=True)
        if sel: 
            sel_node = sel[0].split('.')[0]
            if sel_node in self.ordered_modifiers and sel_node not in self.selected_modifiers:
                self.selected_modifiers = [sel_node]
                self.last_clicked = sel_node
        self.refresh_highlights()

        # 自动展示最后点击的节点参数
        if self.last_clicked and cmds.objExists(self.last_clicked):
            self.populate_mini_ae(self.last_clicked)
        else:
            self.clear_mini_ae()

    def select_all(self):
        self.selected_modifiers = list(self.ordered_modifiers)
        self.refresh_highlights()

    def select_modifier(self, mod):
        mods = cmds.getModifiers()
        is_shift = (mods & 1) > 0
        is_ctrl = (mods & 4) > 0

        if is_ctrl:
            if mod in self.selected_modifiers: self.selected_modifiers.remove(mod)
            else: self.selected_modifiers.append(mod)
            self.last_clicked = mod
        elif is_shift and self.last_clicked in self.ordered_modifiers:
            idx1 = self.ordered_modifiers.index(self.last_clicked)
            idx2 = self.ordered_modifiers.index(mod)
            start = min(idx1, idx2)
            end = max(idx1, idx2)
            self.selected_modifiers = self.ordered_modifiers[start:end+1]
        else:
            self.selected_modifiers = [mod]
            self.last_clicked = mod

        self.refresh_highlights()
        
        if cmds.objExists(mod):
            cmds.select(mod, replace=True)
            # 在底部区域动态生成对应参数的调节面板，不再强制弹窗！
            self.populate_mini_ae(mod)

    def refresh_highlights(self):
        """【智能刷新】根据斑马线算法和选中状态更新UI颜色"""
        for node, row_data in self.row_uis.items():
            if not cmds.objExists(node): continue
            row_layout, type_ui, index = row_data
            try:
                state = cmds.getAttr(f"{node}.nodeState"); is_on = (state == 0)
                
                base_color = self.theme['row_even'] if index % 2 == 0 else self.theme['row_odd']
                bg_color = base_color if is_on else self.theme['disabled']
                
                if node in self.selected_modifiers: 
                    cmds.rowLayout(row_layout, edit=True, backgroundColor=self.theme['selected'])
                else: 
                    cmds.rowLayout(row_layout, edit=True, backgroundColor=bg_color)
            except: pass

    def delete_modifier(self, right_clicked_node):
        nodes_to_del = self.selected_modifiers if right_clicked_node in self.selected_modifiers else [right_clicked_node]
        success_count = 0
        for node in nodes_to_del:
            if cmds.objExists(node):
                try: cmds.delete(node); success_count += 1
                except: pass
        if success_count > 0:
            self.selected_modifiers = []
            self.populate_stack()

    def rename_modifier(self, node):
        result = cmds.promptDialog(title='重命名修改器', message=f'新名称:', text=node, button=['确定', '取消'], defaultButton='确定', cancelButton='取消')
        if result == '确定':
            new_name = cmds.promptDialog(query=True, text=True).strip()
            if new_name and new_name != node:
                try: cmds.rename(node, new_name); self.populate_stack()
                except: pass

    def extract_node_data(self, node):
        clip_data = {'node': node, 'type': cmds.nodeType(node), 'attrs': {}, 'comp_type': 'obj'}
        try:
            comps = cmds.getAttr(node + '.inputComponents')
            if comps:
                comp_str = str(comps[0])
                if 'e[' in comp_str: clip_data['comp_type'] = 'e'
                elif 'f[' in comp_str: clip_data['comp_type'] = 'f'
                elif 'vtx[' in comp_str: clip_data['comp_type'] = 'vtx'
        except: pass

        attrs = cmds.listAttr(node, settable=True) or []
        blacklist = {'message', 'caching', 'isHistoricallyInteresting', 'nodeState', 'binMembership', 'inputPolymesh', 'inputComponents', 'output', 'inMesh', 'outMesh', 'weightList', 'colorSet', 'uvSet', 'blindData', 'uvSetName', 'colorSetName', 'blindDataNodes', 'outputGeometry', 'taperCurve', 'profileCurve'}
        safe_types = {'bool', 'long', 'short', 'byte', 'char', 'enum', 'float', 'double', 'doubleAngle', 'doubleLinear', 'string', 'time', 'angle', 'linear', 'distance', 'float2', 'float3', 'double2', 'double3', 'long2', 'long3', 'short2', 'short3'}
        
        for attr in attrs:
            if any(b in attr for b in blacklist) or '[' in attr or ']' in attr: continue
            if attr.startswith('input') and attr != 'inputComponents': continue 
            plug = f"{node}.{attr}"
            if not cmds.objExists(plug): continue
            if cmds.listConnections(plug, source=True, destination=False): continue
            try:
                if cmds.getAttr(plug, type=True) in safe_types:
                    val = cmds.getAttr(plug)
                    if val is not None: clip_data['attrs'][attr] = val
            except: pass
        return clip_data

    def copy_modifiers(self, right_clicked_node):
        if right_clicked_node not in self.selected_modifiers:
            self.selected_modifiers = [right_clicked_node]
            self.last_clicked = right_clicked_node
            self.refresh_highlights()

        self.clipboard = []
        ordered_sel = [n for n in reversed(self.ordered_modifiers) if n in self.selected_modifiers]
        for node in ordered_sel:
            self.clipboard.append(self.extract_node_data(node))
                
        cmds.inViewMessage(amg=f"已成功组合打包 <hl>{len(self.clipboard)}</hl> 个操作!", pos='midCenter', fade=True)

    def paste_attributes(self, target_node, clip_data, silent=True):
        target_type = cmds.nodeType(target_node)
        src_base = clip_data['type'].rstrip('0123456789')
        dst_base = target_type.rstrip('0123456789')
        if src_base != dst_base: return False
            
        for attr, val in clip_data['attrs'].items():
            plug = f"{target_node}.{attr}"
            if not cmds.objExists(plug): continue
            try:
                if cmds.getAttr(plug, lock=True): continue
                if isinstance(val, list) and len(val) > 0:
                    if isinstance(val[0], (tuple, list)): cmds.setAttr(plug, *val[0])
                    else: cmds.setAttr(plug, *val)
                elif isinstance(val, tuple): cmds.setAttr(plug, *val)
                else: cmds.setAttr(plug, val)
            except: pass
        return True

    def paste_to_model(self):
        if not self.clipboard: return cmds.warning("剪贴板为空！")
        active_sel = cmds.ls(selection=True)
        if not active_sel: return cmds.warning("请选择目标模型或组件！")
            
        first_sel = active_sel[0]
        base_obj = self.get_transform(first_sel)
        is_transform = '.' not in first_sel
        
        success_nodes = []
        generators = {'polyCube', 'polySphere', 'polyCylinder', 'polyPlane', 'polyTorus'}
        
        for i, clip_data in enumerate(self.clipboard):
            node_type = clip_data['type']
            if node_type in generators: continue
            
            if i == 0 and not is_transform: cmds.select(active_sel, replace=True)
            else:
                comp_type = clip_data.get('comp_type', 'obj')
                if comp_type == 'e': cmds.select(base_obj + '.e[*]', replace=True)
                elif comp_type == 'f': cmds.select(base_obj + '.f[*]', replace=True)
                elif comp_type == 'vtx': cmds.select(base_obj + '.vtx[*]', replace=True)
                else: cmds.select(base_obj, replace=True)
            
            overrides = {'polySmoothFace': 'polySmooth', 'polyExtrudeFace': 'polyExtrudeFacet', 'polyMirror': 'polyMirrorFace', 'polySubdFace': 'polySubdivideFacet', 'polyMergeVert': 'polyMergeVertex'}
            cmd_str = overrides.get(node_type, node_type if hasattr(cmds, node_type) else node_type.rstrip('0123456789'))
                    
            if not cmd_str or not hasattr(cmds, cmd_str): continue
                
            try:
                res = getattr(cmds, cmd_str)()
                new_node = None
                if isinstance(res, (list, tuple)):
                    for r in res:
                        if cmds.objectType(r) not in ['transform', 'mesh']: new_node = r; break
                else: new_node = res
                    
                if new_node and cmds.objExists(new_node):
                    self.paste_attributes(new_node, clip_data, silent=True)
                    success_nodes.append(new_node)
            except: pass

        if success_nodes: cmds.inViewMessage(amg=f"成功粘贴了 <hl>{len(success_nodes)}</hl> 个操作。", pos='midCenter', fade=True)
        if cmds.objExists(base_obj):
            cmds.select(base_obj, replace=True)
            self.current_root = base_obj
            self.populate_stack()

    def toggle_node(self, node, val, row_layout, type_ui, chk_ui, index):
        try:
            cmds.setAttr(f"{node}.nodeState", 0 if val else 1)
            try: new_icon = self.icon_on if val else self.icon_off
            except: new_icon = 'menuIconDisplay.png'
            if cmds.control(chk_ui, exists=True): cmds.iconTextCheckBox(chk_ui, edit=True, image1=new_icon)
            if cmds.control(type_ui, exists=True): cmds.text(type_ui, edit=True, enable=val)
            self.refresh_highlights()
        except: pass

    def duplicate_with_history(self):
        if not self.current_root or not cmds.objExists(self.current_root): return cmds.warning("请选择要复制的模型")
        try:
            new_nodes = cmds.duplicate(self.current_root, upstreamNodes=True, returnRootsOnly=True)
            if new_nodes:
                cmds.select(new_nodes[0], replace=True)
                self.force_refresh()
        except: pass

    def batch_transfer_uvs(self):
        sel = cmds.ls(selection=True)
        if len(sel) < 2: return cmds.warning("请至少选择2个模型！")
        source_obj, target_objs = sel[0], sel[1:]
        success_count = 0
        for target in target_objs:
            try:
                cmds.transferAttributes(source_obj, target, transferPositions=0, transferNormals=0, transferUVs=2, transferColors=0, sampleSpace=4, sourceUvSpace="map1", targetUvSpace="map1", searchMethod=3, flipUVs=0, colorBorders=1)
                success_count += 1
            except: pass
        if success_count > 0:
            cmds.inViewMessage(amg=f"成功传递UV给 <hl>{success_count}</hl> 个模型!", pos='midCenter', fade=True)
            self.force_refresh()

    def enable_rename_mode(self):
        selected_transforms = self.get_selected_transforms()
        if not selected_transforms and (not self.current_root or not cmds.objExists(self.current_root)):
            return
        cmds.iconTextButton(self.header_text, edit=True, manage=False)
        if len(selected_transforms) > 1:
            default_text = selected_transforms[0].split('|')[-1]
        else:
            default_text = selected_transforms[0].split('|')[-1] if selected_transforms else self.current_root
        cmds.textField(self.header_rename_field, edit=True, manage=True, text=default_text)
        cmds.setFocus(self.header_rename_field)

    def apply_rename(self):
        if not cmds.control(self.header_rename_field, query=True, manage=True): return
        new_name = cmds.textField(self.header_rename_field, query=True, text=True).strip()
        self.cancel_rename_mode()
        if not new_name:
            return

        selected_transforms = self.get_selected_transforms()
        if len(selected_transforms) > 1:
            renamed = []
            pad = max(2, len(str(len(selected_transforms))))
            for index, node in enumerate(selected_transforms, 1):
                target_name = f"{new_name}_{str(index).zfill(pad)}"
                try:
                    renamed.append(cmds.rename(node, target_name))
                except:
                    pass
            if renamed:
                cmds.select(renamed, replace=True)
                self.current_root = renamed[0]
                cmds.inViewMessage(amg=f"成功批量重命名 <hl>{len(renamed)}</hl> 个物体!", pos='midCenter', fade=True)
                self.force_refresh()
            return

        if new_name and new_name != self.current_root:
            try:
                final_name = cmds.rename(self.current_root, new_name)
                cmds.select(final_name, replace=True)
                self.current_root = final_name
                self.force_refresh()
            except: pass

    def copy_material(self):
        sel = cmds.ls(selection=True)
        if not sel: return cmds.warning("请选中带有材质的模型或面！")
        import maya.mel as mel
        mel.eval('hyperShade -smn;')
        mats = cmds.ls(selection=True)
        if not mats:
            cmds.select(sel, replace=True)
            return cmds.warning("未找到有效材质！")
        mat_name = mats[0]
        cmds.select(mat_name, replace=True)
        sgs = cmds.listConnections(f"{mat_name}.outColor", destination=True, source=False)
        if sgs:
            self.copied_shading_group = sgs[0]
            mel.eval(f'global string $m341_copyShadingGroup[]; $m341_copyShadingGroup[0] = "{sgs[0]}";')
            cmds.select(sel, replace=True)
            cmds.inViewMessage(amg=f"已复制材质: <hl>{mat_name}</hl>", pos='midCenter', fade=True)
        else:
            cmds.select(sel, replace=True)

    def paste_material(self, is_duplicate=False):
        sel = cmds.ls(selection=True)
        if not sel: return cmds.warning("请选中要粘贴材质的模型或面！")
        target_sg = self.copied_shading_group
        import maya.mel as mel
        if not target_sg:
            try: target_sg = mel.eval('global string $m341_copyShadingGroup[]; $temp = $m341_copyShadingGroup[0];')
            except: pass
        if not target_sg or not cmds.objExists(target_sg): return cmds.warning("剪贴板为空！")
        try:
            if is_duplicate:
                mats = cmds.listConnections(f"{target_sg}.surfaceShader", source=True, destination=False)
                if mats:
                    new_mat = cmds.duplicate(mats[0], upstreamNodes=True)[0]
                    cmds.select(sel, replace=True)
                    cmds.hyperShade(assign=new_mat)
                    cmds.inViewMessage(amg=f"成功粘贴【独立新材质】: <hl>{new_mat}</hl>", pos='midCenter', fade=True)
            else:
                cmds.sets(sel, edit=True, forceElement=target_sg)
                cmds.inViewMessage(amg=f"成功粘贴【关联材质】！", pos='midCenter', fade=True)
        except: pass

    # =======================================================
    # 【扩展模块】 贴图检查与视图控制 (Map2, Spin, BaseColor)
    # =======================================================
    def apply_map2(self, *args):
        """一键赋予检查贴图 (Checker)"""
        sel = cmds.ls(selection=True)
        if not sel:
            sel = cmds.ls(type="mesh")
            if sel: cmds.select(sel)

        shader_name = "Custom_CheckerMap2_MAT"
        sg_name = "Custom_CheckerMap2_SG"
        file_name = "Custom_CheckerMap2_FILE"
        place2d_name = "Custom_CheckerMap2_PLACE2D"

        if not cmds.objExists(shader_name):
            cmds.shadingNode('lambert', asShader=True, name=shader_name)
            cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=sg_name)
            cmds.connectAttr(f"{shader_name}.outColor", f"{sg_name}.surfaceShader", force=True)

            cmds.shadingNode('file', asTexture=True, name=file_name)
            cmds.shadingNode('place2dTexture', asUtility=True, name=place2d_name)

            p2d_attrs = ["coverage", "translateFrame", "rotateFrame", "mirrorU", "mirrorV", "stagger", "wrapU", "wrapV", "repeatUV", "offset", "rotateUV", "noiseUV", "vertexUvOne", "vertexUvTwo", "vertexUvThree", "vertexCameraOne"]
            for attr in p2d_attrs:
                try: cmds.connectAttr(f"{place2d_name}.{attr}", f"{file_name}.{attr}", force=True)
                except: pass
                
            cmds.connectAttr(f"{place2d_name}.outUV", f"{file_name}.uvCoord", force=True)
            cmds.connectAttr(f"{place2d_name}.outUvFilterSize", f"{file_name}.uvFilterSize", force=True)
            cmds.connectAttr(f"{file_name}.outColor", f"{shader_name}.color", force=True)

            tex_path = "C:/m341_temp/checker2.png"
            if os.path.exists(tex_path):
                cmds.setAttr(f"{file_name}.fileTextureName", tex_path, type="string")
            else:
                cmds.warning(u"未找到 C:/m341_temp/checker2.png，已应用默认空白纹理。可手动替换 File 节点图片。")

        if sel:
            for obj in sel:
                try: cmds.sets(obj, edit=True, forceElement=sg_name)
                except: pass
            cmds.inViewMessage(amg=u"<hl>已应用 Map2</hl> 检查贴图！", pos='midCenter', fade=True)

    def spin_texture(self, angle, *args):
        """旋转材质中关联的 2D 纹理节点"""
        sel = cmds.ls(selection=True)
        if not sel:
            return cmds.warning(u"请先选中需要旋转贴图的物体。")

        shapes = cmds.ls(sel, objectsOnly=True, dag=True, shapes=True) or []
        if not shapes:
            shapes = sel

        sgs = cmds.listConnections(shapes, type="shadingEngine") or []
        if not sgs: return cmds.warning(u"选中的物体上没有找到任何材质连接。")

        mats = cmds.ls(cmds.listConnections(sgs), materials=True) or []
        if not mats: return cmds.warning(u"未找到对应的材质球。")

        place2d_nodes = cmds.ls(cmds.listHistory(mats), type="place2dTexture") or []
        place2d_nodes = list(set(place2d_nodes))

        if not place2d_nodes:
            return cmds.warning(u"该物体的材质上没有找到任何 place2dTexture (2D纹理放置) 节点！")

        for node in place2d_nodes:
            try:
                curr_rot = cmds.getAttr(f"{node}.rotateUV")
                cmds.setAttr(f"{node}.rotateUV", curr_rot + angle)
            except: pass

        cmds.inViewMessage(amg=u"已将所选物体的纹理旋转 <hl>{} 度</hl>。".format(angle), pos='midCenter', fade=True)

    def toggle_base_color_mode(self, *args):
        """一键切换当前视图的无光照 (Flat) 模式"""
        current_panel = cmds.getPanel(withFocus=True)

        # 尝试寻找有效的模型面板
        if cmds.getPanel(typeOf=current_panel) != "modelPanel":
            vis_panels = cmds.getPanel(visiblePanels=True) or []
            for panel in vis_panels:
                if cmds.getPanel(typeOf=panel) == "modelPanel":
                    current_panel = panel
                    break

        if cmds.getPanel(typeOf=current_panel) == "modelPanel":
            light_mode = cmds.modelEditor(current_panel, q=True, displayLights=True)

            if light_mode != "flat":
                cmds.modelEditor(current_panel, e=True, displayLights="flat")
                cmds.modelEditor(current_panel, e=True, displayTextures=True)
                cmds.inViewMessage(amg=u"<hl>Base Color Mode: 已开启</hl> (仅显示基础颜色)", pos='midCenter', fade=True)
            else:
                cmds.modelEditor(current_panel, e=True, displayLights="default")
                cmds.inViewMessage(amg=u"Base Color Mode: <hl>已关闭</hl> (恢复默认光照)", pos='midCenter', fade=True)
        else:
            cmds.warning(u"未找到激活的模型视图面板。请将鼠标移至模型视图中重试。")

    # =======================================================
    # 【扩展模块】 一键法线链接工具 (自动构建节点并指定法线贴图)
    # =======================================================
    def _get_materials_from_selection(self):
        selection = cmds.ls(selection=True)
        materials = []
        for obj in selection:
            mats = cmds.ls(obj, materials=True)
            if mats:
                materials.extend(mats)
                continue
            shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
            if not shapes:
                shapes = [obj] 
            for shape in shapes:
                sgs = cmds.listConnections(shape, type='shadingEngine')
                if sgs:
                    connected_mats = cmds.ls(cmds.listConnections(sgs), materials=True)
                    if connected_mats:
                        materials.extend(connected_mats)
        return list(set(materials))

    def _create_normal_file_node(self, filepath):
        file_node = cmds.shadingNode('file', asTexture=True, isColorManaged=True)
        cmds.setAttr(f"{file_node}.fileTextureName", filepath, type="string")
        try:
            cmds.setAttr(f"{file_node}.colorSpace", "Raw", type="string")
            cmds.setAttr(f"{file_node}.ignoreColorSpaceFileRules", 1)
        except: pass 
        p2d = cmds.shadingNode('place2dTexture', asUtility=True)
        p2d_attrs = ["coverage", "translateFrame", "rotateFrame", "mirrorU", "mirrorV", "stagger", "wrapU", "wrapV", "repeatUV", "offset", "rotateUV", "noiseUV", "vertexUvOne", "vertexUvTwo", "vertexUvThree", "vertexCameraOne"]
        for attr in p2d_attrs:
            try: cmds.connectAttr(f"{p2d}.{attr}", f"{file_node}.{attr}", force=True)
            except: pass
        cmds.connectAttr(f"{p2d}.outUV", f"{file_node}.uvCoord", force=True)
        cmds.connectAttr(f"{p2d}.outUvFilterSize", f"{file_node}.uvFilterSize", force=True)
        return file_node

    def _connect_normal_to_material(self, material, filepath):
        mat_type = cmds.nodeType(material)
        if mat_type not in ['aiStandardSurface', 'standardSurface', 'lambert', 'blinn', 'phong']:
            cmds.warning(f"材质 [{material}] 的类型暂不支持自动连接法线。")
            return False
        file_node = self._create_normal_file_node(filepath)
        bump_node = cmds.shadingNode('bump2d', asUtility=True)
        cmds.setAttr(f"{bump_node}.bumpInterp", 1) 
        cmds.connectAttr(f"{file_node}.outAlpha", f"{bump_node}.bumpValue", force=True)
        try:
            cmds.connectAttr(f"{bump_node}.outNormal", f"{material}.normalCamera", force=True)
            return True
        except Exception as e:
            print(f"法线连接失败: {e}")
            return False

    def quick_assign_normal_action(self):
        materials = self._get_materials_from_selection()
        if not materials:
            cmds.warning("未找到材质！请先在场景中选择模型或材质球。")
            return
        file_path = cmds.fileDialog2(fileMode=1, dialogStyle=2, caption="选择法线贴图文件", fileFilter="Images (*.png *.jpg *.jpeg *.tif *.tiff *.exr *.tga)")
        if not file_path:
            return 
        selected_file = file_path[0]
        success_count = 0
        for mat in materials:
            if self._connect_normal_to_material(mat, selected_file):
                success_count += 1
        if success_count > 0:
            cmds.inViewMessage(amg=f"<hl>成功</hl> 为 {success_count} 个材质指定了法线贴图！", pos='midCenter', fade=True)

    # =======================================================
    # 【扩展模块】 TB Exporter 面级与UV壳材质拓展
    # =======================================================
    def get_shells(self):
        import maya.mel as mel
        result = []
        selected_objs = cmds.ls(sl=True, o=True) or []
        for obj in selected_objs:
            if cmds.nodeType(obj) != "mesh":
                continue
            active_uv_shells = mel.eval('polyEvaluate -aus "{}"'.format(obj))
            if not active_uv_shells:
                continue
            for s in active_uv_shells:
                uvs_in_shell = mel.eval('polyEvaluate -uis {} "{}"'.format(s, obj))
                if uvs_in_shell:
                    result.append(uvs_in_shell)
        return result

    def _create_random_material(self, name_prefix):
        mat_name = name_prefix + "_M"
        sg_name = name_prefix + "_SG"
        
        if cmds.objExists(mat_name) and cmds.objExists(sg_name):
            mat = mat_name
            sg = sg_name
        else:
            mat_type = "blinn"
            if "LT" in cmds.about(product=True):
                mat_type = "phong"
            mat = cmds.shadingNode(mat_type, asShader=True, name=mat_name)
            sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=sg_name)
            cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader", force=True)
        
        r, g, b = random.random(), random.random(), random.random()
        cmds.setAttr(mat + ".diffuse", 1)
        cmds.setAttr(mat + ".color", r, g, b, type="double3")
        return sg

    def generate_mat_ids(self, *args):
        faces = cmds.filterExpand(ex=True, sm=34) or []
        if faces:
            cmds.ConvertSelectionToFaces()
            shell_faces = cmds.ls(sl=True)
            shape_nodes = cmds.ls(sl=True, objectsOnly=True)
            obj_names = cmds.listRelatives(shape_nodes[0], parent=True)
            obj_name = obj_names[0] if obj_names else shape_nodes[0]
            
            sg = self._create_random_material(obj_name)
            cmds.select(shell_faces)
            cmds.sets(forceElement=sg)
            cmds.inViewMessage(amg=u"<hl>已应用 1 个随机材质</hl>到选中的面上", pos='midCenter', fade=True)
        else:
            selected_objs = cmds.ls(sl=True) or []
            if not selected_objs:
                cmds.warning(u"请先选择物体或面！")
                return
            for item in selected_objs:
                cmds.select(item)
                uv_sets = cmds.polyUVSet(q=True, currentUVSet=True)
                current_uv_set = uv_sets[0] if uv_sets else "map1"
                
                cmds.polyCopyUV(uvSetNameInput="map1", uvSetName="m341_tempMatIDsDelete", createNewMap=True, ch=True)
                cmds.ConvertSelectionToFaces()
                cmds.polyProjection(ch=True, type="Planar", ibd=True, kir=True, md="z")
                
                cmds.ConvertSelectionToUVs()
                cmds.ConvertSelectionToUVShell()
                
                find_shells = self.get_shells()
                
                for shell_idx, shell_uvs in enumerate(find_shells):
                    cmds.select(shell_uvs)
                    cmds.ConvertSelectionToFaces()
                    shell_faces = cmds.ls(sl=True)
                    sg = self._create_random_material("{}_shell{}".format(item, shell_idx))
                    cmds.select(shell_faces)
                    cmds.sets(forceElement=sg)
                    
                cmds.DeleteCurrentUVSet()
                cmds.polyUVSet(currentUVSet=True, uvSet=current_uv_set)
                cmds.selectMode(object=True)
                cmds.delete(item, constructionHistory=True)
                
            cmds.select(selected_objs)
            cmds.inViewMessage(amg=u"成功为 <hl>{}</hl> 个物体按 UV 壳分配了材质 ID！".format(len(selected_objs)), pos='midCenter', fade=True)

    # =======================================================
    # 【扩展模块】 优化与清理系统
    # =======================================================
    def clean_unused_nodes(self):
        import maya.mel as mel
        try:
            mel.eval('MLdeleteUnused;')
            cmds.inViewMessage(amg="<hl>成功清理</hl> 场景中所有未使用的材质球和无用节点！", pos='midCenter', fade=True)
        except Exception as e:
            cmds.warning(f"清理失败: {e}")

    def delete_empty_groups(self):
        import maya.mel as mel
        try: mel.eval('BakeAllNonDefHistory;')
        except: pass
        try: mel.eval('source cleanUpScene; deleteEmptyGroups; deleteUnusedSets;')
        except: pass

        all_meshes = cmds.ls(exactType='mesh', long=True) or []
        to_delete = []
        for m in all_meshes:
            if m.endswith('Orig'): continue
            try:
                vtx_count = cmds.polyEvaluate(m, vertex=True)
                if not vtx_count or vtx_count == 0:
                    to_delete.append(m)
            except: pass
        if to_delete:
            try: cmds.delete(to_delete)
            except: pass
            
        try: mel.eval('deleteEmptyGroups;')
        except: pass

        all_transforms = cmds.ls(exactType='transform', long=True) or []
        cameras = cmds.ls(type='camera', long=True) or []
        cam_transforms = set()
        for cam in cameras:
            parent = cmds.listRelatives(cam, parent=True, fullPath=True)
            if parent: cam_transforms.add(parent[0])
            
        to_delete_xforms = []
        for t in all_transforms:
            if t in cam_transforms: continue
            children = cmds.listRelatives(t, children=True, fullPath=True)
            if not children:
                to_delete_xforms.append(t)
                
        if to_delete_xforms:
            try: cmds.delete(to_delete_xforms)
            except: pass
            
        try: mel.eval('deleteEmptyGroups;')
        except: pass
        
        cmds.select(clear=True)
        cmds.inViewMessage(amg="<hl>深度清理完成</hl>：已彻底删除所有空组及无效网格！", pos='midCenter', fade=True)

    def delete_all_namespaces(self):
        import maya.mel as mel
        try:
            all_namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)
        except Exception as e:
            cmds.warning(u"无法获取命名空间列表 - " + unicode(e))
            return
        
        system_namespaces = [u'UI', u'shared']
        user_namespaces = [ns for ns in all_namespaces if ns not in system_namespaces]
        
        if not user_namespaces:
            cmds.inViewMessage(amg=u"当前场景中没有需要删除的用户命名空间", pos='midCenter', fade=True)
            return
        
        sorted_namespaces = sorted(user_namespaces, key=lambda ns: ns.count(u':'), reverse=True)
        success_list = []
        fail_list = []
        
        for ns in sorted_namespaces:
            try:
                contents = cmds.namespaceInfo(ns, listNamespace=True)
                if contents:
                    cmds.namespace(mv=[ns, u':'], force=True)
                cmds.namespace(rm=ns)
                success_list.append(ns)
            except Exception as e:
                try:
                    cmds.namespace(rm=ns, force=True)
                    success_list.append(ns)
                except Exception as e2:
                    fail_list.append((ns, unicode(e2)))
        
        report = []
        if success_list:
            names_str = u", ".join(success_list)
            report.append(u"成功删除的命名空间 (%d个): %s" % (len(success_list), names_str))
        else:
            report.append(u"没有命名空间被成功删除")
        
        if fail_list:
            report.append(u"")
            report.append(u"删除失败的命名空间 (%d个):" % len(fail_list))
            for ns, error in fail_list:
                report.append(u"  %s - 原因: %s" % (ns, error))
        
        try:
            remaining = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
            remaining_user = [ns for ns in remaining if ns not in system_namespaces]
            if remaining_user:
                report.append(u"")
                remaining_str = u", ".join(remaining_user)
                report.append(u"警告: 仍有用户命名空间存在 (%d个): %s" % (len(remaining_user), remaining_str))
                cmds.inViewMessage(amg=u"<hl>清理完成，但有遗留！</hl> 请查看脚本编辑器了解详情。", pos='midCenter', fade=True)
            else:
                report.append(u"")
                report.append(u"状态: 所有用户命名空间已成功移除")
                cmds.inViewMessage(amg=u"<hl>命名空间清理成功！</hl> 所有内容已移至根目录。", pos='midCenter', fade=True)
        except:
            report.append(u"")
            report.append(u"警告: 无法验证剩余命名空间状态")
        
        for line in report:
            if line.strip() == u"":
                continue
            try:
                if sys.version_info[0] < 3:
                    line_gbk = line.encode('gbk')
                else:
                    line_gbk = line
                if line.startswith(u"成功删除") or line == u"状态: 所有用户命名空间已成功移除":
                    mel.eval('print "\\n// {}";'.format(line_gbk))
                else:
                    cmds.warning(line_gbk)
            except Exception:
                cmds.warning("Namespace cleanup report (encoding issue)")

    # =======================================================
    # 【扩展模块】 智能计算包围盒选中内部物体 (OpenMaya API)
    # =======================================================
    def _get_world_matrix(self, obj):
        mat_list = cmds.xform(obj, q=True, matrix=True, worldSpace=True)
        return om.MMatrix(mat_list)

    def _get_local_bbox(self, obj):
        bb = cmds.xform(obj, q=True, bb=True, objectSpace=True)
        return om.MPoint(bb[0], bb[1], bb[2]), om.MPoint(bb[3], bb[4], bb[5])

    def _get_global_bbox_center(self, obj):
        min_pt, max_pt = self._get_local_bbox(obj)
        local_center = om.MPoint(
            (min_pt.x + max_pt.x) / 2.0,
            (min_pt.y + max_pt.y) / 2.0,
            (min_pt.z + max_pt.z) / 2.0
        )
        world_mat = self._get_world_matrix(obj)
        global_center = local_center * world_mat
        return global_center

    def _is_point_inside_bbox(self, point_global, obj_outer):
        world_mat = self._get_world_matrix(obj_outer)
        inv_world_mat = world_mat.inverse()
        point_local = point_global * inv_world_mat
        min_pt, max_pt = self._get_local_bbox(obj_outer)
        
        tol = 0.001 
        return (min_pt.x - tol <= point_local.x <= max_pt.x + tol) and \
               (min_pt.y - tol <= point_local.y <= max_pt.y + tol) and \
               (min_pt.z - tol <= point_local.z <= max_pt.z + tol)

    def _get_size(self, obj):
        bb = cmds.exactWorldBoundingBox(obj)
        dx = bb[3] - bb[0]
        dy = bb[4] - bb[1]
        dz = bb[5] - bb[2]
        return math.sqrt(dx*dx + dy*dy + dz*dz)

    def select_inner_parts(self):
        objs = cmds.ls(selection=True, type='transform')
        if not objs or len(objs) < 2:
            return cmds.warning("请框选多个物体（至少需要包含一个外壳和一个内管）！")

        objs_sorted = sorted(objs, key=lambda o: self._get_size(o), reverse=True)
        inner_parts = []
        outer_shells = []

        for i, obj in enumerate(objs_sorted):
            is_inner = False
            obj_center = self._get_global_bbox_center(obj)
            
            for larger_obj in objs_sorted[:i]:
                if self._is_point_inside_bbox(obj_center, larger_obj):
                    is_inner = True
                    break 
            
            if is_inner:
                inner_parts.append(obj)
            else:
                outer_shells.append(obj)

        cmds.select(clear=True)
        if inner_parts:
            cmds.select(inner_parts, replace=True)
            self.force_refresh()
            
        result_msg = f"共发现 <hl>{len(outer_shells)}</hl> 个外壳，已智能提取 <hl>{len(inner_parts)}</hl> 个内部独立模型！"
        cmds.inViewMessage(amg=result_msg, pos='midCenter', fade=True)
        print("✅ " + result_msg.replace("<hl>", "").replace("</hl>", ""))

    def show_help(self):
        help_text = "【小学智修改器 V15 - 核心指南】\n\n1. 多选与复刻：\n   - 【Shift键连选】/【Ctrl键加选】。\n   - 选中历史节点后右键【复制选中项】，去另一个模型粘贴复刻。\n\n2. 材质与贴图：\n   - 【Map 2 / 贴图旋转】：一键赋予检查图或旋转贴图，配合无光照模式(Flat)效果绝佳。\n   - 【一键法线】：自动锁定 Raw 色彩与切线空间，杜绝渲染黑边。\n   - 【随机ID】：极其方便烘焙 ID 图。\n\n3. 高级建模/清理：\n   - 【智能选内壳】：框选物体自动剥离选中被包裹的内部零件。\n   - 【清理未用/删空组/命名空间】：终极冗余节点优化工具链。"
        cmds.confirmDialog(title=f"帮助与说明 - {self.version}", message=help_text, button=['我知道了'])

# 启动入口函数 (更安全的外部调用方式)
def run():
    ModifierStackWindow()


# ===========================================================================
# 【安装模块】 Maya 拖拽自动静默安装与升级系统 (Drag & Drop Installer)
# ===========================================================================
def onMayaDroppedPythonFile(*args):
    """
    当用户将此 .py 文件拖入 Maya 视口时，将自动触发此函数。
    实现：1.自动拷贝文件到 scripts 目录；2.自动在当前工具架创建防乱码调用按钮。
    """
    import os
    import shutil
    import maya.cmds as cmds
    import maya.mel as mel

    try:
        source_file = __file__
    except NameError:
        source_file = args[0] if args else None

    if not source_file or not os.path.exists(source_file):
        cmds.warning(u"无法获取源文件路径，自动安装失败！请手动拷贝安装。")
        return

    scripts_dir = cmds.internalVar(userScriptDir=True)
    file_name = os.path.basename(source_file)
    target_file = os.path.join(scripts_dir, file_name)

    if os.path.normpath(source_file) != os.path.normpath(target_file):
        try:
            shutil.copy2(source_file, target_file)
            print(u"✅ 成功将脚本静默拷贝至: {}".format(target_file))
        except Exception as e:
            cmds.warning(u"拷贝文件到 scripts 目录失败: {}".format(e))
            return

    module_name = os.path.splitext(file_name)[0]
    command_str = (
        "import {0}\n"
        "import sys\n"
        "if sys.version_info[0] >= 3:\n"
        "    import importlib\n"
        "    importlib.reload({0})\n"
        "else:\n"
        "    reload({0})\n"
        "{0}.run()\n"
    ).format(module_name)

    try:
        current_shelf = mel.eval('tabLayout -q -selectTab $gShelfTopLevel')
    except:
        current_shelf = None

    if not current_shelf:
        cmds.warning(u"找不到当前激活的工具架，无法自动创建按钮！")
        return

    buttons = cmds.shelfLayout(current_shelf, q=True, childArray=True) or []
    button_exists = False
    button_label = u"小学智修改器"
    
    for btn in buttons:
        if cmds.objectTypeUI(btn) == "shelfButton":
            btn_cmd = cmds.shelfButton(btn, q=True, command=True) or ""
            if module_name in btn_cmd:
                cmds.shelfButton(btn, edit=True, command=command_str, imageOverlayLabel="XXZ", annotation=u"小学智修改器 V15 (已更新)")
                button_exists = True
                break
    
    if not button_exists:
        cmds.shelfButton(
            parent=current_shelf,
            label=button_label,
            annotation=u"小学智修改器 V15",
            imageOverlayLabel="XXZ",
            image="pythonFamily.png", 
            command=command_str,
            sourceType="python"
        )

    run()
    msg = u"<hl>全自动安装与升级成功！</hl><br>已在工具架自动生成防乱码按钮，且原文件已保存至 scripts 目录。"
    cmds.inViewMessage(amg=msg, pos='midCenter', fade=True, fadeStayTime=4000)
    print(u"✅ 小学智修改器全自动部署完成！")

if __name__ == "__main__":
    run()
