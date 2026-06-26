import os
from copy import copy
from copy import deepcopy
import numpy as np
import glob
import json
import h5py
import sys

from CAD_Class import *
from Geometry_utils import *
import trimesh
from trimesh.sample import sample_surface
NORM_FACTOR = 0.75

# 开启草图
def open_sketch(part):
    body = part.bodies.Item(1)

    # 获得草图平面
    hybridShapeFactory = part.HybridShapeFactory
    # 两点，前者为原点，后者用于构成法线
    hybridShapePointCoord1 = hybridShapeFactory.AddNewPointCoord(0, 0, 0)
    hybridShapePointCoord2 = hybridShapeFactory.AddNewPointCoord(0, 0, 1)
    reference1 = part.CreateReferenceFromObject(hybridShapePointCoord1)
    reference2 = part.CreateReferenceFromObject(hybridShapePointCoord2)
    # 法线
    hybridShapeLinePtPt = hybridShapeFactory.AddNewLinePtPt(reference1, reference2)
    reference3 = part.CreateReferenceFromObject(hybridShapeLinePtPt)
    reference4 = part.CreateReferenceFromObject(hybridShapePointCoord1)
    hybridShapePlaneNormal = hybridShapeFactory.AddNewPlaneNormal(reference3, reference4)
    # hybridShapePlaneNormal.name = plane_name

    # 添加定义平面上的草图
    body.InsertHybridShape(hybridShapePlaneNormal)
    # reference5 = body.HybridShapes.Item(plane_name)
    reference5 = body.HybridShapes.Item(body.HybridShapes.Count)
    sketch = body.sketches.add(reference5)

    sketch.SetAbsoluteAxisData(tuple([0, 0, 0,
                                      1, 0, 0,
                                      0, 1, 0]))

    part.InWorkObject = sketch
    arrayOfObject = []
    shapefactory = sketch.openedition()
    return sketch, shapefactory

def close_sketch(sketch):
    sketch.closeedition()


# 绘制草图
def create_Sketch_CATIA(part, extrude_op, shapefactory):
    profile = deepcopy(extrude_op.sketch_profile)  # use copy to prevent changing extrude_op internally
    profile.denormalize(SKETCH_SCALE, size=ARGS_N)

    # 每个loop装在一个map中，最后全部放在all里面
    all_pos_reference_map = []
    
    # 记录spline和control point列表
    spline_control_dic = {}

    arrayOfObject = []

    report_count = 0
    for loop in profile.children:
        start_point = None
        end_point = None
        start_point_coordinate = []
        pos_reference_map = {}
        for curve in loop.children:
            """create a 3D edge"""
            if isinstance(curve, Line):
                cur_line = shapefactory.createline(curve.start_point[0], curve.start_point[1],
                                               curve.end_point[0], curve.end_point[1])
                report_count = report_count + 1
                cur_line.ReportName = report_count
                pos_reference_map[deepcopy(curve)] = cur_line
                # 判断是否为开始
                if start_point == None:
                    start_point = shapefactory.CreatePoint(curve.start_point[0], curve.start_point[1])
                    end_point = start_point
                    start_point_coordinate = [curve.start_point[0], curve.start_point[1]]
                # 判断是否为最后一条线：
                elif np.allclose(start_point_coordinate, curve.end_point):
                    cur_line.StartPoint = end_point
                    cur_line.EndPoint = start_point
                    continue
                cur_point = shapefactory.CreatePoint(curve.end_point[0], curve.end_point[1])
                cur_line.StartPoint = end_point
                cur_line.EndPoint = cur_point
                end_point = cur_point
                part.update()
            elif isinstance(curve, Circle):
                cur_center = shapefactory.CreatePoint(curve.center[0], curve.center[1])
                cur_circle = shapefactory.createclosedcircle(curve.center[0], curve.center[1], curve.radius)
                cur_circle.CenterPoint = cur_center
                report_count = report_count + 1
                cur_circle.ReportName = report_count
                pos_reference_map[deepcopy(curve)] = cur_circle
                part.update()
            elif isinstance(curve, Ellipse):
                cur_center = shapefactory.CreatePoint(curve.center[0], curve.center[1])
                cur_ellipse = shapefactory.createclosedellipse(curve.center[0], curve.center[1],
                                                              curve.l_radius * np.cos(curve.axis_angle), curve.l_radius * np.sin(curve.axis_angle),
                                                              curve.l_radius, curve.s_radius)
                cur_ellipse.CenterPoint = cur_center
                report_count = report_count + 1
                cur_ellipse.ReportName = report_count
                pos_reference_map[deepcopy(curve)] = cur_ellipse
                part.update()
            elif isinstance(curve, Arc):
                # 记录开始点和结束点是否颠倒
                flag = False
                angle_start = vec2arc(curve.start_point, curve.center)
                angle_end = vec2arc(curve.end_point, curve.center)
                angle_mid = curve.mid_arc % (2 * np.pi)
                # 比较两端弧度，重新将小的作为start
                if angle_start > angle_end:
                    angle_start, angle_end = angle_end, angle_start
                    flag = not flag
                if angle_mid < angle_start or angle_mid > angle_end:
                    angle_start, angle_end = angle_end, angle_start
                    flag = not flag
                cur_center = shapefactory.CreatePoint(curve.center[0], curve.center[1])
                cur_arc = shapefactory.CreateCircle(curve.center[0], curve.center[1], curve.radius, angle_start, angle_end)
                cur_arc.CenterPoint = cur_center
                report_count = report_count + 1
                cur_arc.ReportName = report_count
                pos_reference_map[deepcopy(curve)] = cur_arc

                start_point_temp = [curve.start_point[0], curve.start_point[1]]
                end_point_temp = [curve.end_point[0], curve.end_point[1]]

                # 判断是否为开始
                if start_point == None:
                    start_point = shapefactory.CreatePoint(start_point_temp[0], start_point_temp[1])
                    end_point = start_point
                    start_point_coordinate = [start_point_temp[0], start_point_temp[1]]
                # 判断是否为最后一条线：
                elif np.allclose(start_point_coordinate, end_point_temp):
                    if flag:
                        cur_arc.StartPoint = start_point
                        cur_arc.EndPoint = end_point
                    else:
                        cur_arc.StartPoint = end_point
                        cur_arc.EndPoint = start_point
                    continue
                cur_point = shapefactory.CreatePoint(end_point_temp[0], end_point_temp[1])
                if flag:
                    cur_arc.StartPoint = cur_point
                    cur_arc.EndPoint = end_point
                else:
                    cur_arc.StartPoint = end_point
                    cur_arc.EndPoint = cur_point
                end_point = cur_point
                part.update()
            elif isinstance(curve, Spline):
                for i in curve.point_list:
                    arrayOfObject.append(shapefactory.CreateControlPoint(i[0], i[1]))
                cur_spline = shapefactory.CreateSpline(arrayOfObject)
                
                # # 存储样条和controlpoint列表
                # spline_control_dic[cur_spline] = arrayOfObject

                report_count = report_count + 1
                cur_spline.ReportName = report_count
                pos_reference_map[deepcopy(curve)] = cur_spline

                for i in pos_reference_map:
                    if pos_reference_map[i] == cur_spline:
                        spline_control_dic[i] = arrayOfObject

                if not np.allclose(curve.point_list[0], curve.point_list[curve.point_list.__len__() - 1]):
                    # 判断是否为开始
                    if start_point == None:
                        start_point = arrayOfObject[0]
                        end_point = start_point
                        start_point_coordinate = curve.start_point
                    # 判断是否为最后一条线：
                    elif np.allclose(start_point_coordinate, curve.end_point):
                        cur_spline.StartPoint = end_point
                        cur_spline.EndPoint = start_point
                        arrayOfObject = []
                        continue
                    cur_point = arrayOfObject[arrayOfObject.__len__() - 1]
                    cur_spline.StartPoint = end_point
                    cur_spline.EndPoint = cur_point
                    end_point = cur_point
                part.update()
                arrayOfObject = []
            elif isinstance(curve, Parabola):
                # 根据两点及焦距、轴向计算中心
                cur_parabola = shapefactory.CreateParabola(curve.center[0], curve.center[1], np.cos(curve.axis_angle), np.sin(curve.axis_angle), curve.focal_length)

                report_count = report_count + 1
                cur_parabola.ReportName = report_count
                pos_reference_map[deepcopy(curve)] = cur_parabola
                # 判断是否为开始
                if start_point == None:
                    start_point = shapefactory.CreatePoint(curve.start_point[0], curve.start_point[1])
                    end_point = start_point
                    start_point_coordinate = [curve.start_point[0], curve.start_point[1]]
                # 判断是否为最后一条线：
                elif np.allclose(start_point_coordinate, curve.end_point):
                    cur_parabola.StartPoint = end_point
                    cur_parabola.EndPoint = start_point
                    continue
                cur_point = shapefactory.CreatePoint(curve.end_point[0], curve.end_point[1])
                cur_parabola.StartPoint = end_point
                cur_parabola.EndPoint = cur_point
                end_point = cur_point
                part.update()
            elif isinstance(curve, Hyperbola):
                # 根据两点及焦距、轴向计算中心
                cur_hyperbola = shapefactory.CreateHyperbola(curve.center[0], curve.center[1], np.cos(curve.axis_angle), np.sin(curve.axis_angle), curve.major_distance, curve.minor_distance)

                report_count = report_count + 1
                cur_hyperbola.ReportName = report_count
                pos_reference_map[deepcopy(curve)] = cur_hyperbola
                # 判断是否为开始
                if start_point == None:
                    start_point = shapefactory.CreatePoint(curve.start_point[0], curve.start_point[1])
                    end_point = start_point
                    start_point_coordinate = [curve.start_point[0], curve.start_point[1]]
                # 判断是否为最后一条线：
                elif np.allclose(start_point_coordinate, curve.end_point):
                    cur_hyperbola.StartPoint = end_point
                    cur_hyperbola.EndPoint = start_point
                    continue
                cur_point = shapefactory.CreatePoint(curve.end_point[0], curve.end_point[1])
                cur_hyperbola.StartPoint = end_point
                cur_hyperbola.EndPoint = cur_point
                end_point = cur_point
                part.update()
        all_pos_reference_map.append(pos_reference_map)

    part.update()
    return all_pos_reference_map, spline_control_dic

def create_CAD_CATIA(cad_seq: Macro_Seq, catia, doc, part, remove_bug=False, only_sketch=False):
    # 需要一个存储所有curve引用的数据结构，用于查找引用来建立约束
    # 现改为添加位置信息的map，将curve的参数与引用绑定，不再使用profile二次绘制
    pos_reference_map_list = []
    # 以及存储草图引用的数据结构，以便重新进入该草图进行操作
    sketch_reference = []
    
    # 记录spline和control point列表
    spline_control_dic = {}

    sketch, shapefactory = open_sketch(part)

    try:
        all_pos_reference_map, cur_spline_control_dic = create_Sketch_CATIA(part, cad_seq.extrude_operation[0], shapefactory)
        pos_reference_map_list.append(all_pos_reference_map)
        sketch_reference.append(sketch)
        spline_control_dic.update(cur_spline_control_dic)
        for i in cad_seq.extrude_operation[1:]:
            if isinstance(i, Sketch):
                all_pos_reference_map, cur_spline_control_dic = create_Sketch_CATIA(part, i, shapefactory)
                pos_reference_map_list.append(all_pos_reference_map)
                sketch_reference.append(sketch)
                spline_control_dic.update(cur_spline_control_dic)
            else:
                create_Feature_CATIA(sketch, part, i, shapefactory, cad_seq.extrude_operation, sketch_reference, pos_reference_map_list, spline_control_dic)
    # 放大以便观察
    except Exception as e:
        print(e)
        return -1
    close_sketch(sketch)
    specsAndGeomWindow1 = catia.ActiveWindow
    viewer3D1 = specsAndGeomWindow1.ActiveViewer
    viewer3D1.Reframe()
    return 0

# 建立镜像约束
def create_mirror_constrains(sketch, part, entity1, entity2, mirror):
    constraints = sketch.Constraints
    mirror_ref = part.CreateReferenceFromObject(mirror)
    ref1 = part.CreateReferenceFromObject(entity1)
    ref2 = part.CreateReferenceFromObject(entity2)
    # catCstTypeSymmetry = 15
    _ = constraints.AddTriEltCst(15, ref1, ref2, mirror_ref)

# 镜像 旋转 倒圆角 约束
def create_Feature_CATIA(sketch, part, extrude_op, shapefactory, op_list, sketch_reference, pos_reference_map_list, spline_control_dic = None):
    # 每次施加操作后会产生新的curve，需要将这些curve的定义也记录下来，以便后面再次对新对象进行操作
    if isinstance(extrude_op, Mirror):
        extrude_op.start_point = extrude_op.start_point * SKETCH_SCALE
        # 根据镜像轴计算每一个
        for i in extrude_op.select_list:
            if i.select_type == 'Loop':
                sketch_count = 0
                for op in op_list:
                    if isinstance(op, Sketch):
                        sketch_count += 1
                        if sketch_count == i.no:
                            sketch = sketch_reference[i.no - 1]
                            pos_reference_map = pos_reference_map_list[i.no - 1]

                            arrayOfObject = []
                            # 记录原草图共有多少curve，用于后续记录序号
                            # 在镜像中有所不同，因为镜像绘制会变成顺时针顺序，因此reportname应当反序赋值
                            report_count = 0
                            for one_loop in pos_reference_map:
                                report_count += len(one_loop.keys())

                            # 建立镜像轴并设置为虚线
                            mirror_line = shapefactory.createline(extrude_op.start_point[0],
                                                                  extrude_op.start_point[1],
                                                                  extrude_op.start_point[0] + np.cos(extrude_op.oriented_angle),
                                                                  extrude_op.start_point[1] + np.sin(extrude_op.oriented_angle))
                            mirror_line.Construction = True

                            tmp_pos_reference_map = []
                            for loop in pos_reference_map:
                                tmp_pos_reference_map.append(list(loop.keys()))

                            for loop_index in range(len(tmp_pos_reference_map)):
                                op_loop = {}
                                start_point = None
                                end_point = None
                                start_point_coordinate = []
                                report_count_end = report_count + len(tmp_pos_reference_map[loop_index])
                                for curve in tmp_pos_reference_map[loop_index]:
                                    """create a 3D edge"""
                                    if isinstance(curve, Line):
                                        mirror_start_point = get_mirror_point(curve.start_point, extrude_op.start_point, extrude_op.oriented_angle)
                                        mirror_end_point = get_mirror_point(curve.end_point, extrude_op.start_point, extrude_op.oriented_angle)
                                        cur_line = shapefactory.createline(mirror_start_point[0], mirror_start_point[1],
                                                                           mirror_end_point[0], mirror_end_point[1])
                                        cur_line.ReportName = report_count_end
                                        report_count = report_count + 1
                                        report_count_end = report_count_end - 1

                                        op_loop[Line(mirror_start_point, mirror_end_point)] = cur_line
                                        # 判断是否为开始
                                        if start_point == None:
                                            start_point = shapefactory.CreatePoint(mirror_start_point[0],
                                                                                   mirror_start_point[1])
                                            end_point = start_point
                                            start_point_coordinate = [mirror_start_point[0], mirror_start_point[1]]
                                        # 判断是否为最后一条线：
                                        elif np.allclose(start_point_coordinate, mirror_end_point):
                                            cur_line.StartPoint = end_point
                                            cur_line.EndPoint = start_point
                                            part.update()
                                            create_mirror_constrains(sketch, part, cur_line,
                                                                     pos_reference_map[loop_index][curve],
                                                                     mirror_line)

                                            continue
                                        cur_point = shapefactory.CreatePoint(mirror_end_point[0], mirror_end_point[1])
                                        cur_line.StartPoint = end_point
                                        cur_line.EndPoint = cur_point
                                        end_point = cur_point
                                        part.update()
                                        create_mirror_constrains(sketch, part, cur_line, pos_reference_map[loop_index][curve], mirror_line)
                                    elif isinstance(curve, Circle):
                                        mirror_center = get_mirror_point(curve.center, extrude_op.start_point, extrude_op.oriented_angle)

                                        cur_circle = shapefactory.createclosedcircle(mirror_center[0], mirror_center[1],
                                                                                     curve.radius)

                                        cur_circle.ReportName = report_count_end
                                        report_count = report_count + 1
                                        report_count_end = report_count_end - 1

                                        op_loop[Circle(mirror_center, curve.radius)] = cur_circle
                                        part.update()
                                        create_mirror_constrains(sketch, part, cur_circle, pos_reference_map[loop_index][curve], mirror_line)

                                    elif isinstance(curve, Ellipse):
                                        mirror_center = get_mirror_point(curve.center, extrude_op.start_point, extrude_op.oriented_angle)
                                        mirror_axis_angle = get_mirror_angle(curve.axis_angle, extrude_op.oriented_angle)

                                        cur_ellipse = shapefactory.createclosedellipse(mirror_center[0], mirror_center[1],
                                                                                     curve.l_radius * np.cos(
                                                                                        mirror_axis_angle),
                                                                                     curve.l_radius * np.sin(
                                                                                        mirror_axis_angle),
                                                                                     curve.l_radius, curve.s_radius)

                                        cur_ellipse.ReportName = report_count_end
                                        report_count = report_count + 1
                                        report_count_end = report_count_end - 1

                                        op_loop[Ellipse(mirror_center, curve.l_radius, curve.s_radius, mirror_axis_angle)] = cur_ellipse
                                        part.update()
                                        create_mirror_constrains(sketch, part, cur_ellipse, pos_reference_map[loop_index][curve], mirror_line)
                                    elif isinstance(curve, Arc):
                                        # 记录开始点和结束点是否颠倒
                                        flag = False
                                        mirror_start_point = get_mirror_point(curve.start_point, extrude_op.start_point, extrude_op.oriented_angle)
                                        mirror_center = get_mirror_point(curve.center, extrude_op.start_point, extrude_op.oriented_angle)
                                        mirror_end_point = get_mirror_point(curve.end_point, extrude_op.start_point, extrude_op.oriented_angle)
                                        angle_start = vec2arc(mirror_start_point, mirror_center)
                                        angle_end = vec2arc(mirror_end_point, mirror_center)
                                        angle_mid = curve.mid_arc % (2 * np.pi)
                                        # 比较两端弧度，重新将小的作为start
                                        if angle_start > angle_end:
                                            angle_start, angle_end = angle_end, angle_start
                                            flag = not flag
                                        if angle_mid < angle_start or angle_mid > angle_end:
                                            angle_start, angle_end = angle_end, angle_start
                                            flag = not flag

                                        cur_arc = shapefactory.createcircle(mirror_center[0], mirror_center[1],
                                                                            curve.radius, angle_start, angle_end)
                                        cur_arc.ReportName = report_count_end
                                        report_count = report_count + 1
                                        report_count_end = report_count_end - 1


                                        op_loop[Arc(mirror_center, curve.radius, angle_start, angle_end, angle_mid)] = cur_arc

                                        start_point_temp = [mirror_start_point[0], mirror_start_point[1]]
                                        end_point_temp = [mirror_end_point[0], mirror_end_point[1]]

                                        # 判断是否为开始
                                        if start_point == None:
                                            start_point = shapefactory.CreatePoint(start_point_temp[0],
                                                                                   start_point_temp[1])
                                            end_point = start_point
                                            start_point_coordinate = [start_point_temp[0], start_point_temp[1]]
                                        # 判断是否为最后一条线：
                                        elif np.allclose(start_point_coordinate, end_point_temp):
                                            if flag:
                                                cur_arc.StartPoint = start_point
                                                cur_arc.EndPoint = end_point
                                            else:
                                                cur_arc.StartPoint = end_point
                                                cur_arc.EndPoint = start_point
                                            part.update()
                                            create_mirror_constrains(sketch, part, cur_arc,
                                                                     pos_reference_map[loop_index][curve],
                                                                     mirror_line)
                                            continue
                                        cur_point = shapefactory.CreatePoint(end_point_temp[0], end_point_temp[1])
                                        if flag:
                                            cur_arc.StartPoint = cur_point
                                            cur_arc.EndPoint = end_point
                                        else:
                                            cur_arc.StartPoint = end_point
                                            cur_arc.EndPoint = cur_point
                                        end_point = cur_point
                                        part.update()
                                        create_mirror_constrains(sketch, part, cur_arc, pos_reference_map[loop_index][curve], mirror_line)
                                    elif isinstance(curve, Spline):
                                        mirror_scp_list = []
                                        for one_point in curve.point_list:
                                            mirror_scp = get_mirror_point(one_point, extrude_op.start_point, extrude_op.oriented_angle)
                                            mirror_scp_list.append(deepcopy(mirror_scp))
                                            arrayOfObject.append(shapefactory.CreateControlPoint(mirror_scp[0], mirror_scp[1]))
                                        cur_spline = shapefactory.CreateSpline(arrayOfObject)

                                        cur_spline.ReportName = report_count_end
                                        report_count = report_count + 1
                                        report_count_end = report_count_end - 1


                                        op_loop[Spline(mirror_scp_list)] = cur_spline

                                        if not np.allclose(mirror_scp_list[0],
                                                           mirror_scp_list[mirror_scp_list.__len__() - 1]):
                                            # 判断是否为开始
                                            if start_point == None:
                                                start_point = arrayOfObject[0]
                                                end_point = start_point
                                                start_point_coordinate = mirror_scp_list[0]
                                            # 判断是否为最后一条线：
                                            elif np.allclose(start_point_coordinate, mirror_scp_list[mirror_scp_list.__len__() - 1]):
                                                cur_spline.StartPoint = end_point
                                                cur_spline.EndPoint = start_point
                                                arrayOfObject = []

                                                part.update()
                                                create_mirror_constrains(sketch, part, cur_spline,
                                                                         pos_reference_map[loop_index][curve],
                                                                         mirror_line)
                                                continue
                                            cur_point = arrayOfObject[arrayOfObject.__len__() - 1]
                                            cur_spline.StartPoint = end_point
                                            cur_spline.EndPoint = cur_point
                                            end_point = cur_point
                                        part.update()
                                        create_mirror_constrains(sketch, part, cur_spline, pos_reference_map[loop_index][curve], mirror_line)
                                        arrayOfObject = []
                                # pos_reference_map_list[i.no - 1].append(op_loop)
                            part.update()
    elif isinstance(extrude_op, Rotate):
        extrude_op.center = extrude_op.center * SKETCH_SCALE
        # 根据旋转中心计算每一个
        for i in extrude_op.select_list:
            if i.select_type == 'Loop':
                sketch_count = 0
                for op in op_list:
                    if isinstance(op, Sketch):
                        sketch_count += 1
                        if sketch_count == i.no:
                            pos_reference_map = pos_reference_map_list[i.no - 1]
                            arrayOfObject = []
                            # 记录原草图共有多少curve，用于后续记录序号
                            report_count = 0
                            for one_loop in pos_reference_map:
                                report_count += len(one_loop.keys())

                            tmp_pos_reference_map = []
                            for loop in pos_reference_map:
                                tmp_pos_reference_map.append(list(loop.keys()))

                            for loop_index in range(len(tmp_pos_reference_map)):
                                op_loop = {}
                                start_point = None
                                end_point = None
                                start_point_coordinate = []
                                for curve in tmp_pos_reference_map[loop_index]:
                                    """create a 3D edge"""
                                    if isinstance(curve, Line):
                                        rotate_start_point = get_rotate_point(curve.start_point, extrude_op.center,
                                                                              extrude_op.rotate_angle)
                                        rotate_end_point = get_rotate_point(curve.end_point, extrude_op.center,
                                                                              extrude_op.rotate_angle)

                                        cur_line = shapefactory.createline(rotate_start_point[0], rotate_start_point[1],
                                                                           rotate_end_point[0], rotate_end_point[1])
                                        report_count = report_count + 1
                                        cur_line.ReportName = report_count
                                        op_loop[Line(rotate_start_point, rotate_end_point)] = cur_line
                                        # 判断是否为开始
                                        if start_point == None:
                                            start_point = shapefactory.CreatePoint(rotate_start_point[0],
                                                                                   rotate_start_point[1])
                                            end_point = start_point
                                            start_point_coordinate = [rotate_start_point[0], rotate_start_point[1]]
                                        # 判断是否为最后一条线：
                                        elif np.allclose(start_point_coordinate, rotate_end_point):
                                            cur_line.StartPoint = end_point
                                            cur_line.EndPoint = start_point
                                            part.update()

                                            continue
                                        cur_point = shapefactory.CreatePoint(rotate_end_point[0], rotate_end_point[1])
                                        cur_line.StartPoint = end_point
                                        cur_line.EndPoint = cur_point
                                        end_point = cur_point
                                        part.update()
                                    elif isinstance(curve, Circle):
                                        rotate_center = get_rotate_point(curve.center, extrude_op.center,
                                                                         extrude_op.rotate_angle)
                                        cur_circle = shapefactory.createclosedcircle(rotate_center[0], rotate_center[1],
                                                                                     curve.radius)
                                        report_count = report_count + 1
                                        cur_circle.ReportName = report_count
                                        op_loop[Circle(rotate_center, curve.radius)] = cur_circle
                                        part.update()
                                    elif isinstance(curve, Ellipse):
                                        rotate_center = get_rotate_point(curve.center, extrude_op.center,
                                                                         extrude_op.rotate_angle)
                                        rotate_angle = get_rotate_angle(curve.axis_angle, extrude_op.rotate_angle)
                                        cur_ellipse = shapefactory.createclosedellipse(rotate_center[0],
                                                                                       rotate_center[1],
                                                                                       curve.l_radius * np.cos(
                                                                                           rotate_angle),
                                                                                       curve.l_radius * np.sin(
                                                                                           rotate_angle),
                                                                                       curve.l_radius, curve.s_radius)
                                        report_count = report_count + 1
                                        cur_ellipse.ReportName = report_count
                                        op_loop[Ellipse(rotate_center, curve.l_radius, curve.s_radius, rotate_angle)] = cur_ellipse
                                        part.update()
                                    elif isinstance(curve, Arc):
                                        # 记录开始点和结束点是否颠倒
                                        flag = False
                                        rotate_start_point = get_rotate_point(curve.start_point, extrude_op.center,
                                                                              extrude_op.rotate_angle)
                                        rotate_end_point = get_rotate_point(curve.end_point, extrude_op.center,
                                                                              extrude_op.rotate_angle)
                                        rotate_center = get_rotate_point(curve.center, extrude_op.center,
                                                                         extrude_op.rotate_angle)
                                        angle_start = vec2arc(rotate_start_point, rotate_center)
                                        angle_end = vec2arc(rotate_end_point, rotate_center)
                                        angle_mid = curve.mid_arc % (2 * np.pi)
                                        # 比较两端弧度，重新将小的作为start
                                        if angle_start > angle_end:
                                            angle_start, angle_end = angle_end, angle_start
                                            flag = not flag
                                        if angle_mid < angle_start or angle_mid > angle_end:
                                            angle_start, angle_end = angle_end, angle_start
                                            flag = not flag


                                        cur_arc = shapefactory.createcircle(rotate_center[0], rotate_center[1],
                                                                            curve.radius, angle_start, angle_end)
                                        report_count = report_count + 1
                                        cur_arc.ReportName = report_count
                                        op_loop[Arc(rotate_center, curve.radius, angle_start, angle_end, angle_mid)] = cur_arc

                                        start_point_temp = [rotate_start_point[0], rotate_start_point[1]]
                                        end_point_temp = [rotate_end_point[0], rotate_end_point[1]]

                                        # 判断是否为开始
                                        if start_point == None:
                                            start_point = shapefactory.CreatePoint(start_point_temp[0],
                                                                                   start_point_temp[1])
                                            end_point = start_point
                                            start_point_coordinate = [start_point_temp[0], start_point_temp[1]]
                                        # 判断是否为最后一条线：
                                        elif np.allclose(start_point_coordinate, end_point_temp):
                                            if flag:
                                                cur_arc.StartPoint = start_point
                                                cur_arc.EndPoint = end_point
                                            else:
                                                cur_arc.StartPoint = end_point
                                                cur_arc.EndPoint = start_point

                                            part.update()

                                            continue
                                        cur_point = shapefactory.CreatePoint(end_point_temp[0], end_point_temp[1])
                                        if flag:
                                            cur_arc.StartPoint = cur_point
                                            cur_arc.EndPoint = end_point
                                        else:
                                            cur_arc.StartPoint = end_point
                                            cur_arc.EndPoint = cur_point
                                        end_point = cur_point
                                        part.update()
                                    elif isinstance(curve, Spline):
                                        rotate_scp_list = []
                                        for one_point in curve.point_list:
                                            rotate_scp = get_rotate_point(one_point, extrude_op.center,
                                                                          extrude_op.rotate_angle)
                                            rotate_scp_list.append(deepcopy(rotate_scp))
                                            arrayOfObject.append(
                                                shapefactory.CreateControlPoint(rotate_scp[0], rotate_scp[1]))
                                        cur_spline = shapefactory.CreateSpline(arrayOfObject)
                                        report_count = report_count + 1
                                        cur_spline.ReportName = report_count
                                        op_loop[Spline(rotate_scp_list)] = cur_spline
                                        if not np.allclose(rotate_scp_list[0],
                                                           rotate_scp_list[rotate_scp_list.__len__() - 1]):
                                            # 判断是否为开始
                                            if start_point == None:
                                                start_point = arrayOfObject[0]
                                                end_point = start_point
                                                start_point_coordinate = rotate_scp_list[0]
                                            # 判断是否为最后一条线：
                                            elif np.allclose(start_point_coordinate,
                                                             rotate_scp_list[rotate_scp_list.__len__() - 1]):
                                                cur_spline.StartPoint = end_point
                                                cur_spline.EndPoint = start_point
                                                arrayOfObject = []
                                                part.update()

                                                continue
                                            cur_point = arrayOfObject[arrayOfObject.__len__() - 1]
                                            cur_spline.StartPoint = end_point
                                            cur_spline.EndPoint = cur_point
                                            end_point = cur_point

                                        part.update()
                                        arrayOfObject = []
                                # pos_reference_map_list[i.no - 1].append(op_loop)
                            part.update()
    elif isinstance(extrude_op, Chamfer):
        # 目前只限制Line和Line之间的倒圆角
        extrude_op.length1 = extrude_op.length1 * SKETCH_SCALE
        extrude_op.length2 = extrude_op.length2 * SKETCH_SCALE
        # 根据旋转中心计算每一个
        wire_1 = extrude_op.select_list[0]
        wire_2 = extrude_op.select_list[1]
        sketch_count = 0
        for op in op_list:
            if isinstance(op, Sketch):
                sketch_count += 1
                if sketch_count == wire_1.no:
                    pos_reference_map = pos_reference_map_list[wire_1.no - 1]
                    arrayOfObject = []

                    curve_1_ob = None
                    curve_2_ob = None
                    curve_count = 0
                    loop_count = 0
                    loops = []
                    chamfer_loop_index = 0
                    curve_1_ref = None
                    curve_2_ref = None
                    # 在这里顺便重新构建Loop，并记录该倒角在哪个loop中
                    tmp_pos_reference_map = []
                    for loop in pos_reference_map:
                        tmp_pos_reference_map.append(list(loop.keys()))

                    for loop_index in range(len(tmp_pos_reference_map)):
                        for curve in tmp_pos_reference_map[loop_index]:
                            curve_count += 1
                            if curve_count == wire_1.wire_no:
                                curve_1_ob = deepcopy(curve)
                                curve_1_ref = pos_reference_map[loop_index][curve]
                                chamfer_loop_index = loop_count
                            elif curve_count == wire_2.wire_no:
                                curve_2_ob = deepcopy(curve)
                                curve_2_ref = pos_reference_map[loop_index][curve]
                                chamfer_loop_index = loop_count

                        loop_count += 1
                    if curve_1_ob is None or curve_2_ob is None:
                        print("Point is Not Found")
                        return None
                    curve_1_start_pos = curve_1_ob.start_point
                    curve_1_end_pos = curve_1_ob.end_point
                    curve_2_start_pos = curve_2_ob.start_point
                    curve_2_end_pos = curve_2_ob.end_point
                    # 确保二者首尾链接
                    if np.allclose(curve_1_end_pos, curve_2_start_pos):
                        curve_1_end_pos_, curve_2_start_pos_ = get_chamfer_para(curve_1_start_pos, curve_1_end_pos,
                                                                                curve_2_start_pos, curve_2_end_pos,
                                                                                extrude_op.length1, extrude_op.length2)
                        # 绘制
                        # 注意更新reportname时分清原curve的先后
                        start_point_chamfer_ref = shapefactory.CreatePoint(curve_1_end_pos_[0], curve_1_end_pos_[1])
                        end_point_chamfer_ref = shapefactory.CreatePoint(curve_2_start_pos_[0], curve_2_start_pos_[1])

                        curve_1_ref.SetData(curve_1_start_pos[0], curve_1_start_pos[1],
                                            curve_1_end_pos_[0] - curve_1_start_pos[0], curve_1_end_pos_[1] - curve_1_start_pos[1])
                        curve_1_ref.EndPoint = start_point_chamfer_ref

                        curve_chamfer_ref = shapefactory.createline(curve_1_end_pos_[0], curve_1_end_pos_[1],
                                                                    curve_2_start_pos_[0], curve_2_start_pos_[1])
                        curve_chamfer_ref.StartPoint = start_point_chamfer_ref
                        curve_chamfer_ref.EndPoint = end_point_chamfer_ref
                        curve_chamfer_ref.ReportName = curve_1_ref.ReportName + 1
                        # 将引用一并插入记录
                        tmp_chamfer_map = {}
                        for curve_index in range(len(pos_reference_map[chamfer_loop_index].keys())):
                            if curve_index == wire_1.wire_no:
                                tmp_chamfer_map[Line(np.array([curve_1_end_pos_[0], curve_1_end_pos_[1]]),
                                                     np.array([curve_2_start_pos_[0],
                                                               curve_2_start_pos_[1]]))] = curve_chamfer_ref
                            tmp_chamfer_map[list(pos_reference_map[chamfer_loop_index].keys())[curve_index]] = pos_reference_map[chamfer_loop_index][list(pos_reference_map[chamfer_loop_index].keys())[curve_index]]

                        pos_reference_map[chamfer_loop_index] = tmp_chamfer_map

                        curve_2_ref.SetData(curve_2_start_pos_[0], curve_2_start_pos_[1],
                                            curve_2_end_pos[0] - curve_2_start_pos_[0], curve_2_end_pos[1] - curve_2_start_pos_[1])
                        curve_2_ref.StartPoint = end_point_chamfer_ref
                        curve_2_ref.ReportName = curve_2_ref.ReportName + 1
                        # 后续curve的序号依次加一
                        for curve_last in range(wire_2.wire_no, len(tmp_chamfer_map.keys())):
                            tmp_chamfer_map[list(tmp_chamfer_map.keys())[curve_last]].ReportName = tmp_chamfer_map[list(tmp_chamfer_map.keys())[curve_last]].ReportName + 1

                        part.update()
    elif isinstance(extrude_op, Fillet):
        # 目前只限制Line和Line之间的倒圆角
        extrude_op.radius = extrude_op.radius * SKETCH_SCALE
        # 根据旋转中心计算每一个
        wire_1 = extrude_op.select_list[0]
        wire_2 = extrude_op.select_list[1]
        sketch_count = 0
        for op in op_list:
            if isinstance(op, Sketch):
                sketch_count += 1
                if sketch_count == wire_1.no:
                    pos_reference_map = pos_reference_map_list[wire_1.no - 1]
                    curve_1_ref = None
                    curve_2_ref = None
                    curve_1_ob = None
                    curve_2_ob = None
                    curve_count = 0
                    loop_count = 0
                    loops = []
                    fillet_loop_index = 0
                    # 在这里顺便重新构建Loop，并记录该倒角在哪个loop中
                    tmp_pos_reference_map = []
                    for loop in pos_reference_map:
                        tmp_pos_reference_map.append(list(loop.keys()))

                    for loop_index in range(len(tmp_pos_reference_map)):
                        for curve in tmp_pos_reference_map[loop_index]:
                            curve_count += 1
                            if curve_count == wire_1.wire_no:
                                curve_1_ob = deepcopy(curve)
                                curve_1_ref = pos_reference_map[loop_index][curve]
                                fillet_loop_index = loop_count
                            elif curve_count == wire_2.wire_no:
                                curve_2_ob = deepcopy(curve)
                                curve_2_ref = pos_reference_map[loop_index][curve]
                                fillet_loop_index = loop_count

                        loop_count += 1
                    if curve_1_ob is None or curve_2_ob is None:
                        print("Point is Not Found")
                        return None
                    curve_1_start_pos = curve_1_ob.start_point
                    curve_1_end_pos = curve_1_ob.end_point
                    curve_2_start_pos = curve_2_ob.start_point
                    curve_2_end_pos = curve_2_ob.end_point
                    # 确保二者首尾链接
                    if np.allclose(curve_1_end_pos, curve_2_start_pos):
                        curve_1_end_pos_, curve_2_start_pos_, arc_para = get_fillet_para(curve_1_start_pos,
                                                                                         curve_1_end_pos,
                                                                                         curve_2_start_pos,
                                                                                         curve_2_end_pos,
                                                                                         extrude_op.radius)

                        fillet_arc = Arc(arc_para[0], arc_para[1], arc_para[2], arc_para[3], arc_para[4])

                        # 绘制

                        # 注意更新reportname时分清原curve的先后
                        start_point_fillet_ref = shapefactory.CreatePoint(curve_1_end_pos_[0],
                                                                           curve_1_end_pos_[1])
                        end_point_fillet_ref = shapefactory.CreatePoint(curve_2_start_pos_[0],
                                                                         curve_2_start_pos_[1])

                        curve_1_ref.SetData(curve_1_start_pos[0], curve_1_start_pos[1],
                                            curve_1_end_pos_[0] - curve_1_start_pos[0],
                                            curve_1_end_pos_[1] - curve_1_start_pos[1])
                        curve_1_ref.EndPoint = start_point_fillet_ref

                        # 记录开始点和结束点是否颠倒
                        flag = False
                        angle_start = vec2arc(fillet_arc.start_point, fillet_arc.center)
                        angle_end = vec2arc(fillet_arc.end_point, fillet_arc.center)
                        angle_mid = fillet_arc.mid_arc % (2 * np.pi)
                        # 比较两端弧度，重新将小的作为start
                        if angle_start > angle_end:
                            angle_start, angle_end = angle_end, angle_start
                            flag = not flag
                        if angle_mid < angle_start or angle_mid > angle_end:
                            angle_start, angle_end = angle_end, angle_start
                            flag = not flag
                        fillet_arc_ref = shapefactory.CreateCircle(fillet_arc.center[0], fillet_arc.center[1],
                                                                   fillet_arc.radius,
                                                                   angle_start, angle_end)


                        fillet_arc_ref.StartPoint = start_point_fillet_ref
                        fillet_arc_ref.EndPoint = end_point_fillet_ref
                        fillet_arc_ref.ReportName = curve_1_ref.ReportName + 1
                        # 将引用一并插入记录
                        tmp_chamfer_map = {}
                        for curve_index in range(len(pos_reference_map[fillet_loop_index].keys())):
                            if curve_index == wire_1.wire_no:
                                tmp_chamfer_map[fillet_arc] = fillet_arc_ref
                            tmp_chamfer_map[list(pos_reference_map[fillet_loop_index].keys())[curve_index]] = \
                            pos_reference_map[fillet_loop_index][
                                list(pos_reference_map[fillet_loop_index].keys())[curve_index]]

                        pos_reference_map[fillet_loop_index] = tmp_chamfer_map

                        curve_2_ref.SetData(curve_2_start_pos_[0], curve_2_start_pos_[1],
                                            curve_2_end_pos[0] - curve_2_start_pos_[0],
                                            curve_2_end_pos[1] - curve_2_start_pos_[1])
                        curve_2_ref.StartPoint = end_point_fillet_ref
                        curve_2_ref.ReportName = curve_2_ref.ReportName + 1
                        # 后续curve的序号依次加一
                        for curve_last in range(wire_2.wire_no, len(tmp_chamfer_map.keys())):
                            tmp_chamfer_map[list(tmp_chamfer_map.keys())[curve_last]].ReportName = tmp_chamfer_map[list(tmp_chamfer_map.keys())[curve_last]].ReportName + 1

                        part.update()
    elif isinstance(extrude_op, Constraint):
        # if extrude_op.dimension11 is not None:
        #     extrude_op.dimension11 = extrude_op.dimension11 * SKETCH_SCALE
        # if extrude_op.dimension12 is not None:
        #     extrude_op.dimension12 = extrude_op.dimension12 * SKETCH_SCALE
        if extrude_op.dimension21 is not None:
            extrude_op.dimension21 = extrude_op.dimension21 / 2 / np.pi * 360

        # 添加约束（改）
        constraints = sketch.Constraints

        # 创建绝对轴（改）
        geometricElements = sketch.GeometricElements
        axis = geometricElements.Item("AbsoluteAxis")
        lineH = axis.GetItem("HDirection")
        lineV = axis.GetItem("VDirection")
        origin = axis.GetItem("Origin")

        ref_list = []
        flag = False
        for select in extrude_op.select_list:
            cur_sketch_no = int(select.no)
            pos_reference_map = pos_reference_map_list[cur_sketch_no - 1]
            arrayOfObject = []
            if select.select_type == 'Wire':
                for loop_index in range(len(pos_reference_map)):
                    curve_count = 0
                    for curve in pos_reference_map[loop_index]:
                        curve_count += 1
                        if curve_count == select.wire_no:
                            ref_list.append(part.CreateReferenceFromObject(pos_reference_map[loop_index][curve]))
                            flag = True
                            break
                    if flag:
                        break
                    loop_index += 1
            elif select.select_type == 'OriginElements':
                if select.wire_no == 0:
                    ref_list.append(part.CreateReferenceFromObject(origin))
                elif select.wire_no == 1:
                    ref_list.append(part.CreateReferenceFromObject(lineH))
                elif select.wire_no == 2:
                    ref_list.append(part.CreateReferenceFromObject(lineV))
            elif select.select_type == 'Point':
                for loop_index in range(len(pos_reference_map)):                   
                    curve_count = 0
                    for curve in pos_reference_map[loop_index]:
                        curve_count += 1
                        if curve_count == select.body_wire.wire_no:
                            # 01 start_point
                            if select.wire_no == 0:
                                cur_point = pos_reference_map[loop_index][curve].StartPoint
                                ref_list.append(part.CreateReferenceFromObject(cur_point))
                                flag = True
                                break
                            # 02 end_point
                            elif select.wire_no == 1:
                                cur_point = pos_reference_map[loop_index][curve].EndPoint
                                ref_list.append(part.CreateReferenceFromObject(cur_point))
                                flag = True
                                break
                            # 03 center_point
                            elif select.wire_no == 2:
                                cur_point = pos_reference_map[loop_index][curve].CenterPoint
                                ref_list.append(part.CreateReferenceFromObject(cur_point))
                                flag = True
                                break
                    if flag:
                        break
                    loop_index += 1
            elif select.select_type == 'ControlPoint':
                for loop_index in range(len(pos_reference_map)):
                    curve_count = 0
                    for curve in pos_reference_map[loop_index]:
                        curve_count += 1
                        if curve_count == select.body_wire.wire_no:
                            cur_control_point = spline_control_dic[curve][select.wire_no]
                            ref_list.append(part.CreateReferenceFromObject(cur_control_point))
                            flag = True
                            break
                    if flag:
                        break
                    loop_index += 1

        if extrude_op.constraint_type == 'catCstTypeHorizontality':
            ref_list.append(part.CreateReferenceFromObject(lineH))
        if extrude_op.constraint_type == 'catCstTypeVerticality':
            ref_list.append(part.CreateReferenceFromObject(lineV))

        # 判断约束种类
        if extrude_op.constraint_type in CONSTRAINT_MONO_TYPE and len(ref_list) == 1:
            cur_cst = constraints.AddMonoEltCst(CONSTRAINT_TYPE.index(extrude_op.constraint_type), ref_list[0])
        elif extrude_op.constraint_type in CONSTRAINT_BI_TYPE and len(ref_list) == 2:
            cur_cst = constraints.AddBiEltCst(CONSTRAINT_TYPE.index(extrude_op.constraint_type), ref_list[0], ref_list[1])
        elif extrude_op.constraint_type in CONSTRAINT_TRI_TYPE and len(ref_list) == 3:
            cur_cst = constraints.AddTriEltCst(CONSTRAINT_TYPE.index(extrude_op.constraint_type), ref_list[0], ref_list[1], ref_list[2])

        # 赋值
        if extrude_op.dimension11 is not None:
            length = cur_cst.dimension
            length.value = extrude_op.dimension11
        if extrude_op.dimension12 is not None:
            length = cur_cst.dimension
            length.value = extrude_op.dimension12
        if extrude_op.dimension21 is not None:
            cur_cst.AngleSector = 0
            angle = cur_cst.Dimension
            angle.value = extrude_op.dimension21       

        part.update()
        # sketch.closeedition()