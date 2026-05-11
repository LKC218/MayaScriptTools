# -*- coding: utf-8 -*-
import maya.cmds as cmds
import maya.api.OpenMaya as om
import re

class LatticeResizer(object):
    def __init__(self):
        self.window_name = "LatticeResizerWindow"
        # 预定义 UI 文本，使用转义符防止工具架乱码
        self.txt = {
            "title": u"\u5c0f\u5b66\u667a\u6676\u683c\u5206\u6bb5\u4fee\u6539\u5668 V2.2", # 小学智晶格分段修改器 V2.2
            "help_btn": u"\u2753", # ❓
            "main_desc": u"\u8bf7\u9009\u62e9\u573a\u666f\u4e2d\u7684 \u6676\u683c (Lattice)\n\u7136\u540e\u62d6\u52a8\u6ed1\u5757\u8bbe\u7f6e\u65b0\u7684\u5206\u6bb5\u6570:", 
            "s_div": u"S \u5206\u6bb5\u6570", # S 分段数
            "t_div": u"T \u5206\u6bb5\u6570", # T 分段数
            "u_div": u"U \u5206\u6bb5\u6570", # U 分段数
            "create": u"\u2728 \u4e3a\u6240\u9009\u6a21\u578b\u521b\u5efa\u65b0\u6676\u683c", # ✨ 为所选模型创建新晶格
            "get_div": u"\u83b7\u53d6\u5f53\u524d\u9009\u4e2d\u6676\u683c\u7684\u5206\u6bb5", # 获取当前选中晶格的分段
            "reset": u"\u23ea \u56de\u9000\u5230\u672a\u7f16\u8f91\u72b6\u6001 (\u91cd\u7f6e\u6676\u683c)", # ⏪ 回退到未编辑状态 (重置晶格)
            "apply": u"\u5e94\u7528\u65b0\u5206\u6bb5 (\u4fdd\u6301\u5f62\u72b6)" # 应用新分段 (保持形状)
        }
        self.build_ui()

    def build_ui(self):
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name)

        cmds.window(self.window_name, title=self.txt["title"], widthHeight=(320, 380), sizeable=True)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAttach=('both', 10))
        
        # 顶部布局：左侧帮助按钮，右侧提示文字
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(35, 250), columnAlign2=('left', 'center'))
        cmds.button(label=self.txt["help_btn"], width=30, height=30, command=self.show_help, backgroundColor=(0.35, 0.35, 0.35))
        cmds.text(label=self.txt["main_desc"], align='center', font="boldLabelFont")
        cmds.setParent('..')
        
        # 核心更新：同时绑定 changeCommand (释放鼠标触发) 和 dragCommand (拖拽实时触发)
        self.s_slider = cmds.intSliderGrp(label=self.txt["s_div"], field=True, minValue=2, maxValue=20, fieldMinValue=2, fieldMaxValue=100, value=2, 
                                          columnWidth3=[60, 50, 170], 
                                          changeCommand=self.on_slider_changed, 
                                          dragCommand=self.on_slider_changed)
                                          
        self.t_slider = cmds.intSliderGrp(label=self.txt["t_div"], field=True, minValue=2, maxValue=20, fieldMinValue=2, fieldMaxValue=100, value=5, 
                                          columnWidth3=[60, 50, 170], 
                                          changeCommand=self.on_slider_changed, 
                                          dragCommand=self.on_slider_changed)
                                          
        self.u_slider = cmds.intSliderGrp(label=self.txt["u_div"], field=True, minValue=2, maxValue=20, fieldMinValue=2, fieldMaxValue=100, value=4, 
                                          columnWidth3=[60, 50, 170], 
                                          changeCommand=self.on_slider_changed, 
                                          dragCommand=self.on_slider_changed)
        
        cmds.separator(style='none', height=5)
        cmds.button(label=self.txt["create"], command=self.create_new_lattice, height=35, backgroundColor=(0.25, 0.45, 0.65))
        cmds.separator(style='in')
        
        cmds.button(label=self.txt["get_div"], command=self.get_current_divisions, height=30)
        cmds.separator(style='none', height=2)
        
        cmds.button(label=self.txt["reset"], command=self.reset_lattice, height=30, backgroundColor=(0.65, 0.45, 0.25))
        cmds.separator(style='none', height=2)
        
        cmds.button(label=self.txt["apply"], command=self.apply_new_lattice, height=40, backgroundColor=(0.2, 0.6, 0.3))

        cmds.showWindow(self.window_name)

    def show_help(self, *args):
        """显示帮助面板"""
        help_text = (
            u"\u3010\u5c0f\u5b66\u667a\u6676\u683c\u5206\u6bb5\u4fee\u6539\u5668 V2.2 - \u4f7f\u7528\u8bf4\u660e\u3011\n\n"
            u"\ud83d\udca1 \u5b9e\u65f6\u65e0\u635f\u4fee\u6539\uff1a\u9009\u4e2d\u6676\u683c\uff0c\u62d6\u52a8\u6ed1\u5757\u5373\u53ef\u3010\u5b9e\u65f6\u3011\u770b\u5230\u5206\u6bb5\u53d8\u5316\uff0c\u6a21\u578b\u5f62\u72b6\u4fdd\u6301\u4e0d\u53d8\u3002\n\n"
            u"\ud83d\udca1 \u667a\u80fd\u521b\u5efa\uff1a\u9009\u4e2d\u6a21\u578b\u70b9\u51fb\u3010\u521b\u5efa\u65b0\u6676\u683c\u3011\u3002\u5982\u679c\u6a21\u578b\u5df2\u6709\u6676\u683c\uff0c\u4f1a\u81ea\u52a8\u8f6c\u4e3a\u4fee\u6539\u6a21\u5f0f\u3002\n\n"
            u"\ud83d\udca1 \u4e00\u952e\u91cd\u7f6e\uff1a\u3010\u91cd\u7f6e\u6676\u683c\u3011\u53ef\u5c06\u6240\u6709\u6676\u683c\u70b9\u6062\u590d\u5230\u521d\u59cb\u65b9\u6b63\u72b6\u6001\u3002\n\n"
            u"\ud83d\udca1 \u6e05\u7406\u673a\u5236\uff1a\u4fee\u6539\u5206\u6bb5\u540e\u4f1a\u81ea\u52a8\u6e05\u7406\u65e7\u8282\u70b9\u548c\u7a7a\u7ec4\uff0c\u4fdd\u6301\u5927\u7eb2\u89c6\u56fe\u6574\u6d01\u3002"
        )
        cmds.confirmDialog(title="Help", message=help_text, button=["OK"])

    def match_transform(self, source, target):
        if not source or not target or not cmds.objExists(source) or not cmds.objExists(target):
            return
        try:
            mat = cmds.xform(source, q=True, ws=True, matrix=True)
            cmds.xform(target, ws=True, matrix=mat)
        except:
            t = cmds.xform(source, q=True, ws=True, t=True)
            r = cmds.xform(source, q=True, ws=True, ro=True)
            s = cmds.xform(source, q=True, ws=True, s=True)
            cmds.xform(target, ws=True, t=t)
            cmds.xform(target, ws=True, ro=r)
            cmds.xform(target, ws=True, s=s)

    def on_slider_changed(self, *args):
        sel = cmds.ls(selection=True)
        if not sel: return
        lattice_transform = sel[0].split('.')[0]
        lattice_shape = cmds.listRelatives(lattice_transform, shapes=True)
        if lattice_shape and cmds.nodeType(lattice_shape[0]) == 'lattice':
            self.apply_new_lattice(auto=True)

    def create_new_lattice(self, *args):
        sel = cmds.ls(selection=True)
        if not sel:
            cmds.warning("Please select a model first!")
            return

        models_without_lattice = []
        lattices_to_modify = []

        for obj in sel:
            shapes = cmds.listRelatives(obj, shapes=True)
            if shapes and cmds.nodeType(shapes[0]) in ['lattice', 'baseLattice']:
                continue
            
            has_lattice = False
            all_shapes = cmds.listRelatives(obj, allDescendents=True, shapes=True, noIntermediate=True) or [obj]
            history = cmds.listHistory(all_shapes)
            if history:
                ffds = cmds.ls(history, type='ffd')
                if ffds:
                    lat_shapes = cmds.listConnections(ffds[0], type='lattice')
                    if lat_shapes:
                        lat_parents = cmds.listRelatives(lat_shapes[0], parent=True)
                        lat_trans = lat_parents[0] if lat_parents else lat_shapes[0]
                        if lat_trans not in lattices_to_modify:
                            lattices_to_modify.append(lat_trans)
                        has_lattice = True

            if not has_lattice:
                models_without_lattice.append(obj)

        cmds.undoInfo(openChunk=True)
        try:
            final_sel = []
            if lattices_to_modify:
                for lat in lattices_to_modify:
                    cmds.select(lat, replace=True)
                    self.apply_new_lattice(auto=True)
                    curr_sel = cmds.ls(selection=True)
                    if curr_sel: final_sel.append(curr_sel[0])
            
            if models_without_lattice:
                s = cmds.intSliderGrp(self.s_slider, q=True, value=True)
                t = cmds.intSliderGrp(self.t_slider, q=True, value=True)
                u = cmds.intSliderGrp(self.u_slider, q=True, value=True)
                new_lattice_data = cmds.lattice(models_without_lattice, divisions=(s, t, u), objectCentered=True, ldv=(2,2,2))
                if len(new_lattice_data) > 1:
                    final_sel.append(new_lattice_data[1])

            if final_sel: cmds.select(final_sel, replace=True)
        finally:
            cmds.undoInfo(closeChunk=True)

    def get_current_divisions(self, *args):
        sel = cmds.ls(selection=True)
        if not sel: return
        lattice_transform = sel[0].split('.')[0]
        lattice_shapes = cmds.listRelatives(lattice_transform, shapes=True)
        if lattice_shapes and cmds.nodeType(lattice_shapes[0]) == 'lattice':
            shape = lattice_shapes[0]
            s = cmds.getAttr(shape + ".sDivisions")
            t = cmds.getAttr(shape + ".tDivisions")
            u = cmds.getAttr(shape + ".uDivisions")
            cmds.intSliderGrp(self.s_slider, edit=True, value=s)
            cmds.intSliderGrp(self.t_slider, edit=True, value=t)
            cmds.intSliderGrp(self.u_slider, edit=True, value=u)

    def reset_lattice(self, *args):
        sel = cmds.ls(selection=True)
        if not sel: return
        lattice_transform = sel[0].split('.')[0]
        lattice_shapes = cmds.listRelatives(lattice_transform, shapes=True)
        if not lattice_shapes: return
        shape = lattice_shapes[0]
        s_div, t_div, u_div = [cmds.getAttr(shape + ".%sDivisions"%x) for x in 'stu']
        target_pts = cmds.ls(shape + ".pt[*][*][*]", flatten=True)
        cmds.undoInfo(openChunk=True)
        try:
            for pt in target_pts:
                match = re.search(r'\[([0-9]+)\]\[([0-9]+)\]\[([0-9]+)\]', pt)
                if match:
                    i, j, k = map(int, match.groups())
                    x = -0.5 + (float(i) / (s_div - 1)) if s_div > 1 else 0.0
                    y = -0.5 + (float(j) / (t_div - 1)) if t_div > 1 else 0.0
                    z = -0.5 + (float(k) / (u_div - 1)) if u_div > 1 else 0.0
                    cmds.xform(pt, objectSpace=True, translation=(x, y, z))
            cmds.select(lattice_transform) 
        finally:
            cmds.undoInfo(closeChunk=True)

    def apply_new_lattice(self, *args, **kwargs):
        auto = kwargs.get('auto', False)
        sel = cmds.ls(selection=True)
        if not sel: return
        old_lattice = sel[0].split('.')[0]
        old_lattice_shapes = cmds.listRelatives(old_lattice, shapes=True)
        if not old_lattice_shapes or cmds.nodeType(old_lattice_shapes[0]) != 'lattice':
            return
        old_shape = old_lattice_shapes[0]
        new_s = cmds.intSliderGrp(self.s_slider, q=True, value=True)
        new_t = cmds.intSliderGrp(self.t_slider, q=True, value=True)
        new_u = cmds.intSliderGrp(self.u_slider, q=True, value=True)
        
        # 避免无效重复计算
        curr_s = cmds.getAttr(old_shape + ".sDivisions")
        curr_t = cmds.getAttr(old_shape + ".tDivisions")
        curr_u = cmds.getAttr(old_shape + ".uDivisions")
        if curr_s == new_s and curr_t == new_t and curr_u == new_u:
            return

        ffd_nodes = cmds.listConnections(old_shape + ".worldMatrix[0]", type="ffd")
        if not ffd_nodes: return
        old_ffd = ffd_nodes[0]
        base_nodes = cmds.listConnections(old_ffd + ".baseLatticeMatrix", type="baseLattice")
        if not base_nodes: return
        base_parents = cmds.listRelatives(base_nodes[0], parent=True)
        old_base = base_parents[0] if base_parents else base_nodes[0]
        geo_shapes = cmds.deformer(old_ffd, q=True, geometry=True)
        if not geo_shapes: return
        geo_transforms = list(set([cmds.listRelatives(x, p=True)[0] if cmds.nodeType(x)!='transform' else x for x in geo_shapes]))

        cmds.undoInfo(openChunk=True)
        try:
            cmds.setAttr(old_ffd + ".nodeState", 1)
            new_lattice_data = cmds.lattice(geo_transforms, divisions=(new_s, new_t, new_u), objectCentered=True, ldv=(2,2,2))
            if len(new_lattice_data) < 3: return
            new_lattice, new_base = new_lattice_data[1], new_lattice_data[2]
            self.match_transform(old_base, new_base)
            self.match_transform(old_lattice, new_lattice)
            cmds.setAttr(old_ffd + ".nodeState", 0)
            cmds.lattice(old_ffd, edit=True, geometry=new_lattice)
            cmds.dgdirty(new_lattice)
            new_points = cmds.ls(new_lattice + ".pt[*][*][*]", flatten=True)
            baked_positions = [cmds.xform(pt, q=True, ws=True, t=True) for pt in new_points]
            cmds.lattice(old_ffd, edit=True, remove=True, geometry=new_lattice)
            for i, pt in enumerate(new_points):
                cmds.xform(pt, ws=True, t=baked_positions[i])
            cmds.delete(old_ffd)
            if cmds.objExists(old_lattice):
                p_grp = cmds.listRelatives(old_lattice, p=True)
                if p_grp and 'LatticeGroup' in p_grp[0]: cmds.delete(p_grp[0])
                else: 
                    cmds.delete(old_lattice)
                    if old_base and cmds.objExists(old_base): cmds.delete(old_base)
            cmds.select(new_lattice)
        except:
            pass
        finally:
            cmds.undoInfo(closeChunk=True)

# 启动
LatticeResizer()