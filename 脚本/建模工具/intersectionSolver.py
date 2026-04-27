#!/usr/bin/env python
# -*- coding: utf-8 -*-

#********************************
# Copyright 2021 Toshi Kosaka
#
# GORIOSHI SCRIPTS
#********************************
'''****************************************************************************
*** intersectionSolver.py
*** v1.1 - added Fix NaN Verts button
***
*** Scripted in Maya 2018/2022
*** 
*** Please do not copy, distribute, or modify without permission of the author.
****************************************************************************'''

import maya.cmds as mc
import maya.mel as mel
import time
windowName = 'intersectionSolver'
helpWindowName = 'intersectionSolverHelp'
defaultLineOpacity = 0.45
slowSliderRatio = 0.1
ctrlModifierMask = 4
sliderLastValues = {}
sliderSlowMinStep = {
    'nearClipSlider': 0.0001,
    'displayWidthSlider': 0.0005,
    'lineOpacitySlider': 0.001,
}
lineWidthSliderMin = 0.001
lineWidthFineMax = 2.0
lineWidthWideMax = 20.0

def createPfxToon(arg=None):
    sel = mc.ls(mc.listRelatives(c=True), fl=True)
    if mc.objExists('pfxToon_set') !=True:
        mc.sets(sel, n='pfxToon_set')
    else:
        mc.sets(sel, e=True, fe='pfxToon_set')
    target = mc.sets('pfxToon_set', q=True)
    
    if mc.objExists('pfxToonCollisionDetectShape') != True:
        pfxToonNode = mc.createNode('pfxToon', n='pfxToonCollisionDetectShape', p='pfxToonCollisionDetect')
        mc.setAttr(pfxToonNode +'.profileLines', 0)
        mc.setAttr(pfxToonNode +'.creaseLines', 0)
        mc.setAttr(pfxToonNode +'.intersectionLines', 1)
        mc.setAttr(pfxToonNode +'.displayPercent', 100)
        mc.setAttr(pfxToonNode +'.intersectionColor',1,0,0, type='double3')
        mc.setAttr(pfxToonNode +'.selfIntersect', 1)
    else:
        pfxToonNode = 'pfxToonCollisionDetectShape'
    if mc.floatField('lineWidth', exists=True):
        setPfxToonLineWidth(mc.floatField('lineWidth', q=True, v=True))
    if mc.floatSlider('lineOpacitySlider', exists=True):
        setPfxToonOpacity(mc.floatSlider('lineOpacitySlider', q=True, v=True))
    else:
        setPfxToonOpacity(defaultLineOpacity)

    i=0
    for each in target:
        mc.connectAttr(each + '.outMesh', pfxToonNode + '.inputSurface[' + str(i) + '].surface', f=True)
        mc.connectAttr(each + '.worldMatrix[0]', pfxToonNode + '.inputSurface[' + str(i) + '].inputWorldMatrix', f=True)
        i+=1

def removePfxToon(arg=None):
    if mc.objExists('pfxToon_set') == True:
        mc.delete('pfxToon_set')
    if mc.objExists('pfxToonCollisionDetect') == True:
        mc.delete('pfxToonCollisionDetect')

def nearClipChange(arg=None):
    clipVal = getSliderValue('nearClipSlider')
    curCam = 'perspShape'
    for each in mc.getPanel(type='modelPanel'):
        curCam = mc.modelEditor(each, q=True, av=True, cam=True)
    mc.setAttr(curCam + '.nearClipPlane', clipVal)
    mc.text('nearClipValue', e=True, l=str(round(clipVal,3)))

def isCtrlPressed():
    return (mc.getModifiers() & ctrlModifierMask) == ctrlModifierMask

def getSliderValue(sliderName):
    rawVal = mc.floatSlider(sliderName, q=True, v=True)
    lastVal = sliderLastValues.get(sliderName, rawVal)
    minVal = mc.floatSlider(sliderName, q=True, min=True)
    maxVal = mc.floatSlider(sliderName, q=True, max=True)
    if isCtrlPressed():
        delta = rawVal - lastVal
        scaledDelta = delta * slowSliderRatio
        minStep = sliderSlowMinStep.get(sliderName, 0.001)
        if abs(scaledDelta) < minStep and abs(delta) > 0:
            scaledDelta = minStep if delta > 0 else -minStep
        val = max(minVal, min(maxVal, lastVal + scaledDelta))
        mc.floatSlider(sliderName, e=True, v=val)
    else:
        val = rawVal
    sliderLastValues[sliderName] = val
    return val

def setSliderValue(sliderName, val):
    minVal = mc.floatSlider(sliderName, q=True, min=True)
    maxVal = mc.floatSlider(sliderName, q=True, max=True)
    clampedVal = max(minVal, min(maxVal, val))
    sliderLastValues[sliderName] = clampedVal
    mc.floatSlider(sliderName, e=True, v=clampedVal)

def isLineWidthFineMode():
    if mc.checkBox('lineWidthFineMode', exists=True):
        return mc.checkBox('lineWidthFineMode', q=True, v=True)
    return True

def getLineWidthSliderMax():
    if isLineWidthFineMode():
        return lineWidthFineMax
    return lineWidthWideMax

def updateLineWidthSliderRange(arg=None):
    if not mc.floatSlider('displayWidthSlider', exists=True):
        return
    maxVal = getLineWidthSliderMax()
    mc.floatSlider('displayWidthSlider', e=True, min=lineWidthSliderMin, max=maxVal)
    currentVal = mc.floatField('lineWidth', q=True, v=True)
    clampedVal = max(lineWidthSliderMin, min(maxVal, currentVal))
    if clampedVal != currentVal:
        mc.floatField('lineWidth', e=True, v=clampedVal)
        setPfxToonLineWidth(clampedVal)
    setSliderValue('displayWidthSlider', clampedVal)

def displayWidthFieldChange(arg=None):
    val = mc.floatField('lineWidth', q=True, v=True)
    if val > lineWidthFineMax and isLineWidthFineMode():
        mc.checkBox('lineWidthFineMode', e=True, v=False)
        updateLineWidthSliderRange()
    maxVal = getLineWidthSliderMax()
    clampedVal = max(lineWidthSliderMin, min(maxVal, val))
    if clampedVal != val:
        mc.floatField('lineWidth', e=True, v=clampedVal)
    setPfxToonLineWidth(clampedVal)
    setSliderValue('displayWidthSlider', clampedVal)
    
def displayWidthSliderChange(arg=None):
    val = getSliderValue('displayWidthSlider')
    setPfxToonLineWidth(val)
    mc.floatField('lineWidth', e=True, v=val)

def setPfxToonLineWidth(val):
    attr = 'pfxToonCollisionDetectShape.lineWidth'
    if mc.objExists(attr):
        mc.setAttr(attr, val)

def setPfxToonOpacity(val):
    attr = 'pfxToonCollisionDetectShape.lineOpacity'
    if mc.objExists(attr):
        mc.setAttr(attr, val)

def lineOpacityFieldChange(arg=None):
    val = mc.floatField('lineOpacity', q=True, v=True)
    setPfxToonOpacity(val)
    setSliderValue('lineOpacitySlider', val)

def lineOpacitySliderChange(arg=None):
    val = getSliderValue('lineOpacitySlider')
    setPfxToonOpacity(val)
    mc.floatField('lineOpacity', e=True, v=val)

def findCollision(null):
    sel = mc.ls(sl=True, fl=True)
    for each in sel:
        mc.polyTriangulate(each, ch=1)
    mc.ls(sel)
    rigidBodyStr = mc.rigidBody(sel, active=True, m=1, dp=0, sf=0.2, df=0.2, b=0.6, l=0, tf=200, iv=(0,0,0), iav=(0,0,0), c=0, pc=0, i=(0,0,0), imp=(0,0,0), si=(0,0,0), sio='none')

    mc.setAttr('rigidSolver.collisionTolerance', 0.0001)
    mc.select(cl=True)
    mc.currentTime(1);
    mc.currentTime(2);
    mc.currentTime(1);

    global collisionResults
    collisionResults = mc.ls(sl=True)

    mc.delete('rigidBody*')
    mc.delete('rigidSolver')
    mc.delete('polyTriangulate*')
    mc.select(sel)
    mc.DeleteHistory()

    mc.select(collisionResults, r=True)

def selectResults(null):
    global collisionResults
    mc.select(collisionResults)

def applyCollision(none):
    flushCBB()

    start = time.time()

    selOrig = mc.ls(sl=True, fl=True)
    selDup = []
    for each in selOrig:
        selDup.append(mc.duplicate(each, n=each+'_cbbdup')[0])

    dummyPlane = mc.polyPlane(n='dummy_plane', ch=1, o=1, w=1, h=1, sw=1, sh=1, cuv=2)
    mc.setAttr(dummyPlane[0] + '.ty', 999999)
    selDup.insert(0, dummyPlane[0])

    setsList = []
    for each in selDup:
        setsList.append(mc.sets(mc.polyListComponentConversion(each, tf=True), n=each+'_setsCBB'))

    boolMeshName = 'tempMeshBool'
    mc.polyCBoolOp(selDup, op=1, ch=1, n=boolMeshName)

    newSetsList = []
    for i in range(0, len(setsList)):
        newSetsList.append(mc.sets(setsList[i], q=True))
        newSetsList[i] = [x for x in newSetsList[i] if not 'transform' in x]

    mc.select(cl=True)

    #evaluate if selected are full or partial shell, and separate
    for each in newSetsList:
        mc.select(each)
        check1 = mc.polyEvaluate(fc=True)
        mc.ConvertSelectionToShell()
        check2 = mc.polyEvaluate(fc=True)
        if check1 != check2:
            mc.polyChipOff(each, ch=1, kft=1, dup=0, off=0)
    mc.polySeparate(boolMeshName, ch=1)

    #update new sets list
    newSetsList = []
    for i in range(0, len(setsList)):
        newSetsList.append(mc.sets(setsList[i], q=True))
        newSetsList[i] = [x for x in newSetsList[i] if not 'transform' in x]

    mc.DeleteHistory()

    for j in range(0, len(setsList)):
        target = newSetsList[j][0]
        mc.rename(target.split('.')[0], setsList[j].split('_setsCBB')[0])

    mc.delete(dummyPlane[0])
    setsList.pop(0)
    selDup.pop(0)
    allEdges = mc.polyListComponentConversion(te=True)

    fillFaces = []
    for each in allEdges:
        currentFace = mc.polyEvaluate(each.split('.')[0], f=True)
        mc.polyCloseBorder(each, ch=0)
        updatedFace = mc.polyEvaluate(each.split('.')[0], f=True)
        filledFaceNum = updatedFace - currentFace
        mc.select(cl=True)
        for i in range(1, filledFaceNum+1):
            fillFaces.append(each.split('.')[0] + '.f[' + str(updatedFace-i) + ']')

    gapDistanceFloat = mc.floatField('gapDistanceFloat', q=True, v=True)*-1
    for each in fillFaces:
        mc.select(each)
        mc.ConvertSelectionToVertices()
        mc.GrowPolygonSelectionRegion()
        verts = mc.ls(sl=True, fl=True)
        vertsMoveDist = []
        for i in range(0, len(verts)):
            vertsMoveDist.append(gapDistanceFloat)
        mc.moveVertexAlongDirection(verts, n=(vertsMoveDist))

    for i in range(0, len(selOrig)):
        mc.transferAttributes(selDup[i], selOrig[i], pos=1, nml=0, uvs=2, col=2, spa=0, sus='map1', tus='map1', sm=3, fuv=0, clb=1)

    mc.select(selOrig)
    mc.DeleteHistory()
    mc.delete(boolMeshName)

    end = time.time() - start

def relaxBrush(arg=None):
    mel.eval('setMeshSculptTool "Relax";')
    mel.eval('sculptMeshCacheCtx -e -constrainToSurface true sculptMeshCacheContext;')

def relaxFlood(arg=None):
    mel.eval('setMeshSculptTool "Relax";')
    mel.eval('sculptMeshCacheCtx -e -constrainToSurface true sculptMeshCacheContext;')
    mel.eval('sculptMeshFlood; sculptMeshFlood; sculptMeshFlood;')
    mel.eval('SelectToolOptionsMarkingMenu;')
    mel.eval('buildSelectMM; SelectToolOptionsMarkingMenuPopDown;')

def flushCBB(arg=None):
    if mc.objExists('tempMeshBool*'):
        mc.DeleteHistory('tempMeshBool*')
        mc.delete('tempMeshBool*')
    if mc.objExists('dummy_plane*'):
        mc.delete('dummy_plane*')
    if mc.objExists('*_setsCBB*'):
        mc.delete('*_setsCBB*')
    if mc.objExists('*_cbbdup*'):
        mc.delete('*_cbbdup*')
    if mc.objExists('rigidBody*'):
        mc.delete('rigidBody*')
    if mc.objExists('rigidSolver'):
        mc.delete('rigidSolver')

def fixNanVerts(arg=None):
    sel = mc.listRelatives(mc.ls(sl=True, fl=True), c=True, type='mesh')
    selVerts = mc.ls(mc.polyListComponentConversion(sel, tv=True), fl=True)
    for each in selVerts:
        if str(mc.xform(each.split('.vtx[')[0] + '.pnts[' + each.split('.vtx[')[1], q=True, t=True)[0]) == 'nan':
            mc.setAttr(each.split('.vtx[')[0] + '.pnts[' + each.split('.vtx[')[1], 0, 0, 0)

def showHelpWindow(arg=None):
    global helpWindowName
    if mc.window(helpWindowName, exists=True):
        mc.deleteUI(helpWindowName)
    helpWindow = mc.window(helpWindowName, title='穿插修复工具 - 帮助', widthHeight=(460, 460), sizeable=True)
    mc.columnLayout(adjustableColumn=True, rowSpacing=8)
    helpText = (
        "插件用途:\n"
        "- 显示模型穿插线（红色）\n"
        "- 检测碰撞对象并快速选择结果\n"
        "- 对穿插区域执行自动修复与间隙处理\n"
        "- 提供松弛与 NaN 顶点修复辅助工具\n\n"
        "推荐流程:\n"
        "1. 选择要检查的模型\n"
        "2. 点击“显示选中物体穿插线”观察问题区域\n"
        "3. 点击“检测选中物体”并查看“选择结果”\n"
        "4. 设定“间隙距离”后点击“修复穿插”\n"
        "5. 必要时使用“松弛笔刷/整体松弛”做二次优化\n\n"
        "参数说明:\n"
        "- 显示线宽: 调整红色穿插线粗细\n"
        "- 线宽精细模式: 低值区间更容易精确拖动\n"
        "- 穿插线透明度: 调整红线透明程度\n"
        "- 间隙距离: 修复后边界内缩/外扩距离\n"
        "- Ctrl + 左键拖动滑条: 慢速微调数值\n\n"
        "注意事项:\n"
        "- 操作前建议备份模型\n"
        "- 建议先清理历史并检查 UV\n"
        "- 复杂拓扑模型可能需要多次微调参数\n"
        "- 异常中断后可用“清理错误残留”回收临时节点"
    )
    mc.scrollField(editable=False, wordWrap=True, text=helpText, h=390)
    mc.button(l='关闭帮助', c=lambda *_: mc.deleteUI(helpWindowName, window=True), h=28)
    mc.showWindow(helpWindow)

def intersectionSolver():
    global windowName
    global isFaceMode
    
    isFaceMode = 0
    sliderLastValues.clear()
    windowSize = (420, 345)
    if (mc.window(windowName , exists=True)):
        mc.deleteUI(windowName)
    IS_window = mc.window( windowName, title='穿插修复工具', widthHeight=(windowSize[0], windowSize[1]) )
    
    mc.frameLayout('穿插修复工具 v1.1', w=420, bgc=(.1,.1,.1))
    mc.columnLayout( "mainColumn", adjustableColumn=True )
    mc.rowLayout(parent='mainColumn', nc=3)

    curCam = 'perspShape'
    for each in mc.getPanel(type='modelPanel'):
        curCam = mc.modelEditor(each, q=True, av=True, cam=True)
    ncVal = mc.getAttr(curCam + '.nearClipPlane')
    
    mc.text(l='相机近裁剪: ')
    mc.floatSlider('nearClipSlider', w=250, min=0.001, max=100, value=ncVal, s=0.001, dc=nearClipChange)
    sliderLastValues['nearClipSlider'] = ncVal
    mc.text('nearClipValue', l=str(round(ncVal,3)))
    mc.setParent('..')
    mc.text(l='=================================', parent="mainColumn")
    mc.setParent('..')
    mc.rowLayout(p='mainColumn', nc=2)
    mc.button(l='显示选中物体穿插线', c=createPfxToon, bgc=(0,.3,0.2), w=300)
    mc.button(l='帮助', c=showHelpWindow, w=110)
    mc.setParent('..')
    mc.rowLayout(p='mainColumn', nc=3)
    mc.text(l='显示线宽: ')
    mc.floatField('lineWidth', w=45, min=lineWidthSliderMin, max=lineWidthWideMax, v=1, pre=3, cc=displayWidthFieldChange)
    mc.floatSlider('displayWidthSlider', w=250, min=lineWidthSliderMin, max=lineWidthFineMax, value=1, dc=displayWidthSliderChange)
    sliderLastValues['displayWidthSlider'] = 1
    mc.setParent('..')
    mc.rowLayout(p='mainColumn', nc=1)
    mc.checkBox('lineWidthFineMode', l='线宽精细模式 (0.001-2.0)', v=True, cc=updateLineWidthSliderRange)
    mc.setParent('..')
    updateLineWidthSliderRange()
    mc.rowLayout(p='mainColumn', nc=3)
    mc.text(l='穿插线透明度: ')
    mc.floatField('lineOpacity', w=45, min=0.05, max=1, v=defaultLineOpacity, pre=3, cc=lineOpacityFieldChange)
    mc.floatSlider('lineOpacitySlider', w=250, min=0.05, max=1, value=defaultLineOpacity, dc=lineOpacitySliderChange)
    sliderLastValues['lineOpacitySlider'] = defaultLineOpacity
    mc.setParent('..')
    mc.button(l='移除穿插线显示', c=removePfxToon, bgc=(.3,0,0))
    
    mc.columnLayout( "mainColumn", rowSpacing=0, columnWidth=420,)
    mc.text(l='=================================', parent="mainColumn")
    mc.text(l='请确认 UV 干净，并已删除历史')
    
    mc.rowLayout("nameRowLayout04", numberOfColumns = 3, parent = "mainColumn")
    mc.button(l='检测选中物体', parent = "nameRowLayout04", command=findCollision, bgc=(0,.3,0.2))
    mc.button('选择结果', parent='nameRowLayout04', command=selectResults)
    
    mc.rowLayout("nameRowLayout01", numberOfColumns = 2, parent = "mainColumn")
    mc.text(l='间隙距离: ')
    mc.floatField('gapDistanceFloat', w=40, v=.1, pre=2, parent='nameRowLayout01')
    
    mc.rowLayout(numberOfColumns = 2, parent = "mainColumn")
    mc.button( label='修复穿插', h=30, command = applyCollision, bgc=(0,.2,.4))
    mc.button(l='清理错误残留', command=flushCBB, bgc=(.3,0,0))

    mc.text(l='=================================', parent="mainColumn")
    mc.rowLayout("nameRowLayout03", numberOfColumns = 3, parent = "mainColumn")
    mc.button( label='松弛笔刷', parent = "nameRowLayout03", command = relaxBrush)
    mc.button( label='整体松弛', parent = "nameRowLayout03", command = relaxFlood)
    mc.button( label='修复 NaN 顶点', parent = "nameRowLayout03", command = fixNanVerts)
    
    mc.showWindow(IS_window)
    
if __name__ == "__main__":
    intersectionSolver()
