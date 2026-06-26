import numpy as np

import CAD_Class
from macro_new import *
import math
from plyfile import PlyData, PlyElement

def construct_curve_from_vector(vec, start_point, is_numerical=True):
    if vec.shape.__len__() == 1:
        type = vec[0]
    else:
        type = vec[0][0]
    if type == LINE_IDX:
        return CAD_Class.Line.from_vector(vec, start_point, is_numerical=is_numerical)
    elif type == CIRCLE_IDX:
        return CAD_Class.Circle.from_vector(vec, start_point, is_numerical=is_numerical)
    elif type == ARC_IDX:
        res = CAD_Class.Arc.from_vector(vec, start_point, is_numerical=is_numerical)
        if res is None: # for visualization purpose, replace illed arc with line
            return CAD_Class.Line.from_vector(vec, start_point, is_numerical=is_numerical)
        return res
    elif type == SPLINE_IDX:
        res = CAD_Class.Spline.from_vector(vec, start_point, is_numerical=is_numerical)
        return res
    elif type == ELLIPSE_IDX:
        res = CAD_Class.Ellipse.from_vector(vec, start_point, is_numerical=is_numerical)
        return res
    elif type == PARA_IDX:
        res = CAD_Class.Parabola.from_vector(vec, start_point, is_numerical=is_numerical)
        return res
    elif type == HYPER_IDX:
        res = CAD_Class.Hyperbola.from_vector(vec, start_point, is_numerical=is_numerical)
        return res
    else:
        raise NotImplementedError("curve type not supported yet: command idx {}".format(vec[0]))

def angle_from_vector_to_x(vec):
    """computer the angle (0~2pi) between a unit vector and positive x axis"""
    angle = 0.0
    # 2 | 1
    # -------
    # 3 | 4
    if vec[0] >= 0:
        if vec[1] >= 0:
            # Qadrant 1
            angle = math.asin(vec[1])
        else:
            # Qadrant 4
            angle = 2.0 * math.pi - math.asin(-vec[1])
    else:
        if vec[1] >= 0:
            # Qadrant 2
            angle = math.pi - math.asin(vec[1])
        else:
            # Qadrant 3
            angle = math.pi + math.asin(-vec[1])
    return angle

def polar_parameterization_inverse(theta, phi, gamma):
    """build a coordinate system by the given rotation from the standard 3D coordinate system"""
    normal_3d = polar2cartesian([theta, phi])
    ref_x = rotate_by_z(rotate_by_y(np.array([1, 0, 0]), theta), phi)
    ref_y = np.cross(normal_3d, ref_x)
    x_axis_3d = ref_x * np.cos(gamma) + ref_y * np.sin(gamma)
    return normal_3d, x_axis_3d

def cartesian2polar(vec, with_radius=False):
    vec = vec.round(6)
    norm = np.linalg.norm(vec)
    theta = np.arccos(vec[2] / norm) # (0, pi)
    phi = np.arctan(vec[1] / (vec[0] + 1e-15)) # (-pi, pi) # FIXME: -0.0 cannot be identified here
    if not with_radius:
        return np.array([theta, phi])
    else:
        return np.array([theta, phi, norm])

def rotate_by_y(vec, theta):
    mat = np.array([[np.cos(theta), 0, np.sin(theta)],
                    [0, 1, 0],
                    [-np.sin(theta), 0, np.cos(theta)]])
    return np.dot(mat, vec)

def rotate_by_z(vec, phi):
    mat = np.array([[np.cos(phi), -np.sin(phi), 0],
                    [np.sin(phi), np.cos(phi), 0],
                    [0, 0, 1]])
    return np.dot(mat, vec)

def polar2cartesian(vec):
    """convert a vector in polar(spherical) coordinates to cartesian coordinates"""
    r = 1 if len(vec) == 2 else vec[2]
    theta, phi = vec[0], vec[1]
    x = r * np.sin(theta) * np.cos(phi)
    y = r * np.sin(theta) * np.sin(phi)
    z = r * np.cos(theta)
    return np.array([x, y, z])

def polar_parameterization(normal_3d, x_axis_3d):
    normal_polar = cartesian2polar(normal_3d)
    theta = normal_polar[0]
    phi = normal_polar[1]

    ref_x = rotate_by_z(rotate_by_y(np.array([1, 0, 0]), theta), phi)

    gamma = np.arccos(np.dot(x_axis_3d, ref_x).round(6))
    if np.dot(np.cross(ref_x, x_axis_3d), normal_3d) < 0:
        gamma = -gamma
    return theta, phi, gamma

def vec2arc(pos, center):
    angle = 0
    vec = pos - center
    vec_np = np.array([vec[0], vec[1]])
    # x轴基准
    x_np = np.array([1, 0])
    # y轴基准
    y_np = np.array([0, 1])
    # 向量绝对值
    L = np.sqrt(vec_np.dot(vec_np))
    Lx = np.sqrt(x_np.dot(x_np))
    Ly = np.sqrt(y_np.dot(y_np))
    cos_x = vec_np.dot(x_np) / (L * Lx)
    cos_y = vec_np.dot(y_np) / (L * Ly)

    # 开始位置判断象限
    # 象限一、二
    if cos_y > 0:
        angle = np.arccos(cos_x)
    # 象限三、四
    elif cos_y < 0:
        angle = 2 * np.pi - np.arccos(cos_x)
    # 在坐标轴上
    elif cos_y == 0:
        if cos_x > 0:
            return 0
        else:
            return np.pi
    return angle % (2 * np.pi)

def float_equal(a, b):
    if np.abs(a - b) < 0.001:
        return True
    else:
        return False

def read_ply(path):
    with open(path, 'rb') as f:
        plydata = PlyData.read(f)
        x = np.array(plydata['vertex']['x'])
        y = np.array(plydata['vertex']['y'])
        z = np.array(plydata['vertex']['z'])
        vertex = np.stack([x, y, z], axis=1)
    return vertex

# 根据草图镜像轴得到目标点的镜像点
def get_mirror_point(pos, mirror_pos, mirror_angle):
    if np.allclose(mirror_angle, np.pi / 2) or np.allclose(mirror_angle % (np.pi / 2), np.pi / 2):
        return np.array([2 * mirror_pos[0] - pos[0], pos[1]])
    else:
        k = np.tan(mirror_angle)
        b = mirror_pos[1] - k * mirror_pos[0]
        x_mirror = (pos[0] + k * (pos[1] - b)) / (k * k + 1)
        y_mirror = k * x_mirror + b
        return np.array([2 * x_mirror - pos[0], 2 * y_mirror - pos[1]])

# 根据草图镜像轴得到目标轴方向的镜像轴的角度
def get_mirror_angle(angle, mirror_angle):
    target_angle = 2 * np.arctan(mirror_angle) - np.arctan(angle)
    if target_angle < 0:
        return target_angle + 2 * np.pi
    elif target_angle > 2 * np.pi:
        return target_angle % (2 * np.pi)
    else:
        return target_angle

# 根据旋转中心得到旋转后的点，注意默认旋转为逆时针
def get_rotate_point(pos, rotate_pos, rotate_angle):
    if np.allclose(pos, rotate_pos):
        return pos
    rotate_angle = rotate_angle % (2 * np.pi)
    radius = np.sqrt((pos[0] - rotate_pos[0]) * (pos[0] - rotate_pos[0]) + (pos[1] - rotate_pos[1]) * (pos[1] - rotate_pos[1]))
    origin_angle = vec2arc(pos, rotate_pos)
    target_x = rotate_pos[0] + radius * np.cos(origin_angle + rotate_angle)
    target_y = rotate_pos[1] + radius* np.sin(origin_angle + rotate_angle)
    return np.array([target_x, target_y])

def get_rotate_angle(angle, rotate_angle):
    return (angle + rotate_angle) % (2 * np.pi)

# 输入倒角长度、两线段原来的开始点、结束点，默认二者是逆时针顺序
# 输出产生的新的两线段的开始点、结束点（倒角线自然得出）
def get_chamfer_para(curve1_start_pos, curve1_end_pos, curve2_start_pos, curve2_end_pos, length1, length2):
    # 确认两线首尾相接
    if np.allclose(curve1_end_pos, curve2_start_pos):
        curve1_length = np.sqrt((curve1_end_pos[0] - curve1_start_pos[0]) * (curve1_end_pos[0] - curve1_start_pos[0]) +
                                (curve1_end_pos[1] - curve1_start_pos[1]) * (curve1_end_pos[1] - curve1_start_pos[1]))
        curve2_length = np.sqrt((curve2_end_pos[0] - curve2_start_pos[0]) * (curve2_end_pos[0] - curve2_start_pos[0]) +
                                (curve2_end_pos[1] - curve2_start_pos[1]) * (curve2_end_pos[1] - curve2_start_pos[1]))
        curve1_end_x_ = (curve1_length - length1) / curve1_length * (curve1_end_pos[0] - curve1_start_pos[0]) + \
                        curve1_start_pos[0]
        curve1_end_y_ = (curve1_length - length1) / curve1_length * (curve1_end_pos[1] - curve1_start_pos[1]) + \
                        curve1_start_pos[1]
        curve2_start_x_ = length2 / curve2_length * (curve2_end_pos[0] - curve2_start_pos[0]) + curve2_start_pos[0]
        curve2_start_y_ = length2 / curve2_length * (curve2_end_pos[1] - curve2_start_pos[1]) + curve2_start_pos[1]
        return np.array([curve1_end_x_, curve1_end_y_]), np.array([curve2_start_x_, curve2_start_y_])
    # 有可能二者是颠倒关系
    else:
        print('Order Error!')
        return None

# 输入原有的两线端点坐标
# 返回新的与弧线相接的坐标，以及弧的参数
def get_fillet_para(curve1_start_pos, curve1_end_pos, curve2_start_pos, curve2_end_pos, radius):
    # 确认两线首尾相接
    if np.allclose(curve1_end_pos, curve2_start_pos):
        # 以两线相交处为中心计算两线弧度
        angle_1 = vec2arc(curve1_start_pos, curve1_end_pos)
        angle_2 = vec2arc(curve2_end_pos, curve2_start_pos)
        fillet_center_angle = np.abs((angle_1 - angle_2) / 2)

        fillet_center_k = np.tan((angle_1 + angle_2) / 2)

        if curve1_start_pos[0] != curve1_end_pos[0]:
            curve1_end_x_ = curve1_end_pos[0] + radius / np.tan(fillet_center_angle) / (np.sqrt((curve1_start_pos[0] - curve1_end_pos[0]) * (curve1_start_pos[0] - curve1_end_pos[0]) + (curve1_start_pos[1] - curve1_end_pos[1]) * (curve1_start_pos[1] - curve1_end_pos[1]))) * (curve1_start_pos[0] - curve1_end_pos[0])
        else:
            curve1_end_x_ = curve1_end_pos[0]

        if curve1_start_pos[1] != curve1_end_pos[1]:
            curve1_end_y_ = curve1_end_pos[1] + radius / np.tan(fillet_center_angle) / (np.sqrt((curve1_start_pos[0] - curve1_end_pos[0]) * (curve1_start_pos[0] - curve1_end_pos[0]) + (curve1_start_pos[1] - curve1_end_pos[1]) * (curve1_start_pos[1] - curve1_end_pos[1]))) * (curve1_start_pos[1] - curve1_end_pos[1])
        else:
            curve1_end_y_ = curve1_end_pos[1]

        if curve2_start_pos[0] != curve2_end_pos[0]:
            curve2_start_x_ = curve2_start_pos[0] + radius / np.tan(fillet_center_angle) / (np.sqrt((curve2_start_pos[0] - curve2_end_pos[0]) * (curve2_start_pos[0] - curve2_end_pos[0]) + (curve2_start_pos[1] - curve2_end_pos[1]) * (curve2_start_pos[1] - curve2_end_pos[1]))) * (curve2_end_pos[0] - curve2_start_pos[0])
        else:
            curve2_start_x_ = curve2_start_pos[0]

        if curve2_start_pos[1] != curve2_end_pos[1]:
            curve2_start_y_ = curve2_start_pos[1] + radius / np.tan(fillet_center_angle) / (np.sqrt((curve2_start_pos[0] - curve2_end_pos[0]) * (curve2_start_pos[0] - curve2_end_pos[0]) + (curve2_start_pos[1] - curve2_end_pos[1]) * (curve2_start_pos[1] - curve2_end_pos[1]))) * (curve2_end_pos[1] - curve2_start_pos[1])
        else:
            curve2_start_y_ = curve2_start_pos[1]
        # curve1_end_x_ = curve1_end_pos[0] + radius / (fillet_center_angle * np.sqrt(1 + k_1 * k_1))
        # curve1_end_y_ = k_1 * (curve1_end_x_ - curve1_end_pos[0]) + curve1_end_pos[1]
        # curve2_start_x_ = curve2_start_pos[0] + radius / (fillet_center_angle * np.sqrt(1 + k_2 * k_2))
        # curve2_start_y_ = k_2 * (curve2_start_x_ - curve2_start_pos[0]) + curve2_start_pos[1]

        # 粗略算出圆心到交点x和y的相对差距，然后通过角度一一比较
        if not np.isclose(fillet_center_k, np.Inf):
            fillet_center_theta_x = radius / np.abs(np.sin(fillet_center_angle)) * np.abs(np.cos(np.arctan(fillet_center_k)))
            fillet_center_x_candidate1 = curve2_start_pos[0] + fillet_center_theta_x
            fillet_center_x_candidate2 = curve2_start_pos[0] - fillet_center_theta_x
            fillet_center_y_candidate1 = fillet_center_k * (fillet_center_x_candidate1 - curve2_start_pos[0]) + curve2_start_pos[1]
            fillet_center_y_candidate2 = fillet_center_k * (fillet_center_x_candidate2 - curve2_start_pos[0]) + curve2_start_pos[1]

            # 因为做圆角一定是圆角向内，所以交点与正确的圆心所称的向量应与交点与任一开始点所称向量为锐角
            if (fillet_center_x_candidate1 - curve1_end_pos[0]) * (curve1_start_pos[0] - curve1_end_pos[0]) + \
                    (fillet_center_y_candidate1 - curve1_end_pos[1]) * (curve1_end_pos[1] - curve1_end_pos[1]) > 0:
                fillet_center_x = fillet_center_x_candidate1
                fillet_center_y = fillet_center_y_candidate1
            else:
                fillet_center_x = fillet_center_x_candidate2
                fillet_center_y = fillet_center_y_candidate2

        # fillet_center_x = curve2_start_pos[0] + radius / np.sin(fillet_center_angle) / (1 + fillet_center_k * fillet_center_k)
        # fillet_center_y = fillet_center_k * (fillet_center_x - curve2_start_pos[0]) + curve2_start_pos[1]

        fillet_center_pos = np.array([fillet_center_x, fillet_center_y])
        curve1_end_pos_ = np.array([curve1_end_x_, curve1_end_y_])
        curve2_start_pos_ = np.array([curve2_start_x_, curve2_start_y_])

        curve_1_arc = vec2arc(curve1_end_pos_, fillet_center_pos)
        curve_2_arc = vec2arc(curve2_start_pos_, fillet_center_pos)
        mid_arc = vec2arc(curve1_end_pos, fillet_center_pos)

        if curve_1_arc < curve_2_arc:
            if curve_1_arc < mid_arc < curve_2_arc:
                start_arc = curve_1_arc
                end_arc = curve_2_arc
            else:
                start_arc = curve_2_arc
                end_arc = curve_1_arc
        else:
            if curve_2_arc < mid_arc < curve_1_arc:
                start_arc = curve_2_arc
                end_arc = curve_1_arc
            else:
                start_arc = curve_1_arc
                end_arc = curve_2_arc
        return curve1_end_pos_, curve2_start_pos_, [fillet_center_pos, radius, start_arc, end_arc, mid_arc]

#纯手算我是真的牛批
def get_center_from_Parabola(start_point_pos, end_point_pos, axis_angle, focal_distance):
    alpha = axis_angle / ARGS_N * 2 * np.pi
    k1 = np.sin(-alpha)
    k2 = np.cos(-alpha)
    x1 = start_point_pos[0]
    y1 = start_point_pos[1]
    x2 = end_point_pos[0]
    y2 = end_point_pos[1]
    f = focal_distance
    if np.isclose(k1, 0):
        y0 = (y1 + y2 - 4 * f * (x1 - x2) / k2 / (y1 - y2)) / 2
        x0 = x1 - k2 * (y1 - y0) * (y1 - y0) / 4 / f
    elif np.isclose(k2, 0):
        x0 = (x1 + x2 - 4 * f * (y2 - y1) / k1 / (x1 - x2)) / 2
        y0 = y1 + k1 * (x1 - x0) * (x1 - x0) / 4 / f
    else:
        b1 = (k2 * (y1 + y2) + k1 * (x1 + x2) - 4 * f * (k2 * (x1 - x2) - k1 * (y1 - y2)) / (k2 * (y1 - y2) + k1 * (x1 - x2))) / 2
        b2 = k2 * x1 - k1 * y1 - (k2 * y1 + k1 * x1 - b1) * (k2 * y1 + k1 * x1 - b1) / 4 / f
        x0 = (b1 * k1 + b2 * k2) / (k1 * k1 + k2 * k2)
        y0 = b1 / k2 - x0 * k1 / k2
    return np.array([x0, y0])

def get_center_from_Hyperbola(start_point_pos, end_point_pos, axis_angle, major_distance, minor_distance):
    alpha = axis_angle / ARGS_N * 2 * np.pi
    k1 = np.sin(-alpha)
    k2 = np.cos(-alpha)
    x1 = start_point_pos[0]
    y1 = start_point_pos[1]
    x2 = end_point_pos[0]
    y2 = end_point_pos[1]
    a = major_distance
    b = minor_distance
    b1 = k2 * (x1 - x2) - k1 * (y1 - y2)
    b2 = k2 * (y1 - y2) + k1 * (x1 - x2)

    if np.isclose(b2 * a * a * k2 + b1 * b * b * k1, 0):
        x0 = (x1 + x2) / 2
        v = k2 * (x1 - x2) / 2

        if np.isclose(b * b * k1 * k1 - a * a * k2 * k2, 0):

            u = (b * b * k2 * k2 * v * v - a * a * k1 * k1 * v * v - a * a * b * b) / (
                        2 * k1 * k2 * v * (a * a + b * b))
            y0 = y1 - u
            return np.array([x0, y0])
        else:
            u_1 = (k1 * k2 * v * (a * a + b * b) + np.sqrt(
                (k1 * k2 * v * (a * a + b * b)) * (k1 * k2 * v * (a * a + b * b)) - (b * b * k1 * k1 - a * a * k2 * k2) * (
                            b * b * k2 * k2 * v * v - a * a * k1 * k1 * v * v - a * a * b * b))) / (
                              b * b * k1 * k1 - a * a * k2 * k2)

            u_2 = (k1 * k2 * v * (a * a + b * b) - np.sqrt(
                (k1 * k2 * v * (a * a + b * b)) * (k1 * k2 * v * (a * a + b * b)) - (b * b * k1 * k1 - a * a * k2 * k2) * (
                            b * b * k2 * k2 * v * v - a * a * k1 * k1 * v * v - a * a * b * b))) / (
                              b * b * k1 * k1 - a * a * k2 * k2)

            y0_1 = y1 - u_1
            y0_2 = y1 - u_2

            if k2 * (x1 - x0) - k1 * (y1 - y0_1) > 0 and k2 * (x2 - x0) - k1 * (y2 - y0_1) > 0:
                return np.array([x0, y0_1])
            elif k2 * (x1 - x0) - k1 * (y1 - y0_2) > 0 and k2 * (x2 - x0) - k1 * (y2 - y0_2) > 0:
                return np.array([x0, y0_2])
            return None

    else:

        k0 = (b1 * b * b * k2 - b2 * a * a * k1) / (b2 * a * a * k2 + b1 * b * b * k1)
        b0 = ((b2 * a * a * (k2 * (y1 + y2) + k1 * (x1 + x2)) - b1 * b * b * (k2 * (x1 + x2) - k1 * (y1 + y2))) / (b2 * a * a * k2 + b1 * b * b * k1)) / 2
        u1 = k1 * k0 - k2
        v1 = k2 * x1 - k1 * y1 + k1 * b0
        u2 = k2 * k0 + k1
        v2 = k2 * y1 - k2 * b0 + k1 * x1

        x0_1 = (u2 * v2 / b / b - u1 * v1 / a / a + np.sqrt(
            (u1 * v1 / a / a - u2 * v2 / b / b) * (u1 * v1 / a / a - u2 * v2 / b / b) - (
                        u1 * u1 / a / a - u2 * u2 / b / b) * (v1 * v1 / a / a - v2 * v2 / b / b - 1))) / (
                           u1 * u1 / a / a - u2 * u2 / b / b)

        x0_2 = (u2 * v2 / b / b - u1 * v1 / a / a - np.sqrt(
            (u1 * v1 / a / a - u2 * v2 / b / b) * (u1 * v1 / a / a - u2 * v2 / b / b) - (
                        u1 * u1 / a / a - u2 * u2 / b / b) * (v1 * v1 / a / a - v2 * v2 / b / b - 1))) / (
                           u1 * u1 / a / a - u2 * u2 / b / b)
        y0_1 = k0 * x0_1 + b0
        y0_2 = k0 * x0_2 + b0

        X1_1 = k2 * (x1 - x0_1) - k1 * (y1 - y0_1)
        X2_1 = k2 * (x2 - x0_1) - k1 * (y2 - y0_1)
        X1_2 = k2 * (x1 - x0_2) - k1 * (y1 - y0_2)
        X2_2 = k2 * (x2 - x0_2) - k1 * (y2 - y0_2)

        if k2 * (x1 - x0_1) - k1 * (y1 - y0_1) > 0 and k2 * (x2 - x0_1) - k1 * (y2 - y0_1) > 0:
            return np.array([x0_1, y0_1])
        elif k2 * (x1 - x0_2) - k1 * (y1 - y0_2) > 0 and k2 * (x2 - x0_2) - k1 * (y2 - y0_2) > 0:
            return np.array([x0_2, y0_2])
        return None