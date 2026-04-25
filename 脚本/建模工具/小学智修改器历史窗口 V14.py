# -*- coding: utf-8 -*-
import maya.cmds as cmds

class ModifierStackWindow(object):
    def __init__(self):
        self.window_name = "XiaoXueZhiModifierStackUI"
        
        # 升级为 V14 版本：根据现代DCC软件全面重构高级扁平化UI
        self.version = "V14"
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
        for old_v in ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11", "V12", "V13"]:
            old_ws = f"{self.window_name}_{old_v}_Workspace"
            if cmds.workspaceControl(old_ws, exists=True): cmds.deleteUI(old_ws, control=True)
            
        if cmds.workspaceControl(self.workspace_name, exists=True):
            cmds.deleteUI(self.workspace_name, control=True)
            
        self.window = cmds.workspaceControl(self.workspace_name, label=self.window_title, retain=False, floating=True)
        cmds.setParent(self.workspace_name)
        
        # 主框架：零间隙纯粹背景
        self.main_layout = cmds.columnLayout(adjustableColumn=True, backgroundColor=self.theme['bg'], rowSpacing=0)
        
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
        
        # 工具栏第二排：材质管理
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnWidth3=(90, 90, 90), columnAttach=[(1, 'both', 0), (2, 'both', 0), (3, 'both', 0)])
        cmds.button(label="复制材质", command=lambda x: self.copy_material(), height=24, backgroundColor=self.theme['btn'])
        cmds.button(label="关联粘贴", command=lambda x: self.paste_material(is_duplicate=False), height=24, backgroundColor=self.theme['btn'])
        cmds.button(label="独立粘贴", command=lambda x: self.paste_material(is_duplicate=True), height=24, backgroundColor=self.theme['btn'])
        cmds.setParent("..")
        
        cmds.setParent("..") # 结束 Toolbar
        
        cmds.separator(height=8, style='none')
        
        # 【List：斑马线历史列表】
        self.scroll_layout = cmds.scrollLayout(childResizable=True, height=400, backgroundColor=self.theme['bg'])
        bg_menu = cmds.popupMenu(parent=self.scroll_layout, button=3)
        cmds.menuItem(parent=bg_menu, label="粘贴历史组合 (Paste Modifiers)", command=lambda x: self.paste_to_model())
        
        self.stack_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=0) # 无缝隙紧凑排列

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
            import maya.mel as mel
            try: mel.eval('if (!`isUIComponentVisible "Attribute Editor"`) { setUIComponentVisible "Attribute Editor" 1; }')
            except: pass

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
        if not self.current_root or not cmds.objExists(self.current_root): return
        cmds.iconTextButton(self.header_text, edit=True, manage=False)
        cmds.textField(self.header_rename_field, edit=True, manage=True, text=self.current_root)
        cmds.setFocus(self.header_rename_field)

    def apply_rename(self):
        if not cmds.control(self.header_rename_field, query=True, manage=True): return
        new_name = cmds.textField(self.header_rename_field, query=True, text=True).strip()
        self.cancel_rename_mode()
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

    def show_help(self):
        help_text = "【小学智修改器 V14 - 核心指南】\n\n1. 史诗级多选与批量复制：\n   - 【Shift键连选】/【Ctrl键加选】。\n   - 选中后右键【复制选中项】，去另一个模型粘贴完美复刻。\n\n2. 基础交互：\n   - 【双击重命名】：双击顶部“对象区”，回车或点击空白生效！\n\n3. 高级工具：\n   - 【独立复制】：连带历史克隆独立新模型。\n   - 【批量传UV】：选中源模型加选白模，基于点序号拓扑防翻转传递！\n   - 【材质粘贴】：支持'关联'和'独立(全新克隆)'两模式！"
        cmds.confirmDialog(title=f"帮助与说明 - {self.version}", message=help_text, button=['我知道了'])

ModifierStackWindow()