import random

import numpy as np
import numpy.random

from Catia_utils import *
from CAD_Class import *
from Geometry_utils import *
import win32com.client
import h5py
import time

INPUT_PATH = './data'
SAVE_PATH = './output'

# 抛物线、双曲线转换概率
PARA_HYPER_LINE_MAP = {'Parabola': 0.15, 'Hyperbola': 0.3, 'Line': 1}
# 椭圆转化概率
ELLIPSE_PROBABILITY = 1 / 4
# 倒圆角转化概率
CHAMFER_FILLET_MAP = {'Chamfer': 1 / 3, 'Fillet': 2 / 3}
# 镜像、旋转中心位置概率
MIRROR_AXIS_MAP = {'Bound': 1 / 2, 'Center': 1}
# 镜像旋转转化概率
MIRROR_PROBABILITY = 0.2
ROTATE_PROBABILITY = 0.2

# 镜像轴角度
AXIS_ANGLE_MAP = {'Uniform': 0.5, '90': 1}
# 旋转角度
ROTATE_MAP = {'Uniform': 0.3, '45': 0.4, '90': 0.5, '135': 0.6, '180': 0.7, '225': 0.8, '270': 0.9, '315': 1}
# 约束数量期望
CONSTRAINT_EXPECTATION = 5
# Line约束补充
LINE_CONSTRAINTS_MAP = {'Angle': 1 / 2, 'Length': 1}
# 其余约束补充概率
LAST_CONSTRAINTS_MAP = {'Fix': 1 / 6, 'Distance': 2 / 6, 'On': 3 / 6, 'Symmetry': 4 / 6, 'Tangency': 4.5 / 6, 'MidPoint': 5 / 6, 'Equidistance': 1}

REMOVE_BUG = True
IS_TEST = True

def get_distance_between_points(pos1, pos2):
    return np.sqrt((pos1[0] - pos2[0]) * (pos1[0] - pos2[0]) + (pos1[1] - pos2[1]) * (pos1[1] - pos2[1]))

def get_normal_distribution(center, scale):
    tmp = -1
    while tmp < center - scale or tmp > center + scale:
        tmp = np.random.normal(center, scale / 3, size=None)
    return tmp

def get_uniform_distribution(center, scale):
    return np.random.randint(center - scale, center + scale)

def get_random_probability():
    return np.random.random()

def create_ellipse(circle_vec):
    # 原始半径作为长轴半径不变，短轴半径以长轴为中心正态分布
    radius = circle_vec[5]
    circle_vec[6] = max(1, get_uniform_distribution(radius, radius))
    circle_vec[0] = ELLIPSE_IDX
    circle_vec[7] = max(1, get_uniform_distribution(128, 128))
    return deepcopy(circle_vec)

def create_parabola(parabola_vec, begin_point):
    # 计算被替换的线的垂直角度，以该角度为center，正态分布确定角度
    end_point = parabola_vec[1:3]
    if end_point[0] == begin_point[0]:
        angle = np.pi / 2
    elif end_point[1] == begin_point[1]:
        angle = 0
    else:
        angle = np.arctan((end_point[1] - begin_point[1]) / (end_point[0] - begin_point[0]))
    angle = (angle + np.pi * 2) % (np.pi * 2)
    vertical_angle = (angle + np.pi / 2) % (np.pi * 2)
    target_angle = get_normal_distribution(vertical_angle, np.pi / 2)
    target_angle = (target_angle + 2 * np.pi) % (2 * np.pi)
    # 有一定概率变为反向
    if np.random.random() < 0.5:
        target_angle = (target_angle + np.pi) % (np.pi * 2)

    target_angle = min(255, int(target_angle / (2 * np.pi) * ARGS_N))

    focal = get_uniform_distribution(30, 29)
    parabola_vec[0] = PARA_IDX
    parabola_vec[8] = target_angle
    parabola_vec[13] = focal
    return deepcopy(parabola_vec)

def create_hyperbola(hyperbola_vec, begin_point):
    # 计算被替换的线的垂直角度，以该角度为center，正态分布确定角度
    end_point = hyperbola_vec[1:3]
    if end_point[0] == begin_point[0]:
        angle = np.pi / 2
    elif end_point[1] == begin_point[1]:
        angle = 0
    else:
        angle = np.arctan((end_point[1] - begin_point[1]) / (end_point[0] - begin_point[0]))
    angle = (angle + np.pi * 2) % (np.pi * 2)
    vertical_angle = (angle + np.pi / 2) % (np.pi * 2)
    target_angle = get_normal_distribution(vertical_angle, np.pi / 2)
    target_angle = (target_angle + 2 * np.pi) % (2 * np.pi)
    # 有一定概率变为反向
    if np.random.random() < 0.5:
        target_angle = (target_angle + np.pi) % (np.pi * 2)
    target_angle = min(255, int(target_angle / (2 * np.pi) * ARGS_N))

    focal_a = get_uniform_distribution(30, 29)
    focal_b = get_uniform_distribution(focal_a, focal_a - 1)
    hyperbola_vec[0] = HYPER_IDX
    hyperbola_vec[8] = target_angle
    hyperbola_vec[5] = focal_a
    hyperbola_vec[6] = focal_b
    return deepcopy(hyperbola_vec)

def create_chamfer(length1, length2, no1, no2, loop_no):
    c1 = get_uniform_distribution(length1, length1 - 1)
    c2 = get_uniform_distribution(length2, length2 - 1)
    target_vec = np.array([[SELECT_IDX, *[PAD_VAL]*(N_ARGS - 7), SELECT_TYPE.index('Wire'), loop_no, no1, *[PAD_VAL]*4],
                  [SELECT_IDX, *[PAD_VAL]*(N_ARGS - 7), SELECT_TYPE.index('Wire'), loop_no, no2, *[PAD_VAL]*4],
                  [CHAMFER_IDX, *[PAD_VAL]*9, c1, c2, *[PAD_VAL]*(N_ARGS - 11)]])
    return deepcopy(target_vec)

def create_fillet(length, no1, no2, loop_no):
    radius = get_uniform_distribution(length, length - 1)
    target_vec = np.array([[SELECT_IDX, *[PAD_VAL]*(N_ARGS - 7), SELECT_TYPE.index('Wire'), loop_no, no1, *[PAD_VAL]*4],
                  [SELECT_IDX, *[PAD_VAL]*(N_ARGS - 7), SELECT_TYPE.index('Wire'), loop_no, no2, *[PAD_VAL]*4],
                  [CHAMFER_IDX, *[PAD_VAL]*11, radius, *[PAD_VAL]*(N_ARGS - 12)]])
    return deepcopy(target_vec)

def create_mirror(loop_no, sketch_box):
    # 要获取草图的边界
    # 按概率决定中心对称还是边界对称
    # 大概率分配到0、45、90、135度
    random_pro = get_random_probability()
    if random_pro < AXIS_ANGLE_MAP['Uniform']:
        axis_angle = min(255, get_uniform_distribution(128, 128))
    else:
        axis_angle = 128

    if get_random_probability() < MIRROR_AXIS_MAP['Bound']:
        mirror_pos_x = min(255, get_uniform_distribution(128, 128))
        mirror_pos_y = min(255, get_uniform_distribution(128, 128))
        while not (mirror_pos_x < sketch_box[0][0] or mirror_pos_x > sketch_box[1][0] or mirror_pos_y < sketch_box[0][1] or mirror_pos_y > sketch_box[1][1]):
            mirror_pos_x = min(255, get_uniform_distribution(128, 128))
            mirror_pos_y = min(255, get_uniform_distribution(128, 128))
    else:
        box_center = [(sketch_box[0][0] + sketch_box[1][0]) / 2, (sketch_box[0][1] + sketch_box[1][1]) / 2]
        mirror_pos_x = int(get_normal_distribution(box_center[0], sketch_box[1][0] - box_center[0]))
        mirror_pos_y = int(get_normal_distribution(box_center[1], sketch_box[1][1] - box_center[1]))

    target_vec = np.array([[SELECT_IDX, *[PAD_VAL]*(N_ARGS - 7), SELECT_TYPE.index('Loop'), loop_no, 0, *[PAD_VAL]*4],
                  [MIRROR_IDX, mirror_pos_x, mirror_pos_y, *[PAD_VAL]*4, axis_angle, *[PAD_VAL]*(N_ARGS - 7)]])
    return deepcopy(target_vec)

def create_rotate(loop_no, sketch_box):
    # 要获取草图的边界
    # 按概率决定中心对称还是边界对称
    # 大概率分配到45、90、135、180、225、270、315度
    random_pro = get_random_probability()
    if random_pro < ROTATE_MAP['Uniform']:
        rotate_angle = min(255, int(get_uniform_distribution(128, 128)))
    elif random_pro < ROTATE_MAP['45']:
        rotate_angle = 32
    elif random_pro < ROTATE_MAP['90']:
        rotate_angle = 64
    elif random_pro < ROTATE_MAP['135']:
        rotate_angle = 96
    elif random_pro < ROTATE_MAP['180']:
        rotate_angle = 128
    elif random_pro < ROTATE_MAP['225']:
        rotate_angle = 160
    elif random_pro < ROTATE_MAP['270']:
        rotate_angle = 192
    else:
        rotate_angle = 224

    if get_random_probability() < MIRROR_AXIS_MAP['Bound']:
        rotate_pos_x = min(255, get_uniform_distribution(128, 128))
        rotate_pos_y = min(255, get_uniform_distribution(128, 128))
        while not (rotate_pos_x < sketch_box[0][0] or rotate_pos_x > sketch_box[1][0] or rotate_pos_y < sketch_box[0][1] or rotate_pos_y > sketch_box[1][1]):
            rotate_pos_x = min(255, get_uniform_distribution(128, 128))
            rotate_pos_y = min(255, get_uniform_distribution(128, 128))
    else:
        box_center = [(sketch_box[0][0] + sketch_box[1][0]) / 2, (sketch_box[0][1] + sketch_box[1][1]) / 2]
        rotate_pos_x = int(get_normal_distribution(box_center[0], sketch_box[1][0] - box_center[0]))
        rotate_pos_y = int(get_normal_distribution(box_center[1], sketch_box[1][1] - box_center[1]))

    target_vec = np.array([[SELECT_IDX, *[PAD_VAL]*(N_ARGS - 7), SELECT_TYPE.index('Loop'), loop_no, 0, *[PAD_VAL]*4],
                  [ROTATE_IDX, rotate_pos_x, rotate_pos_y, *[PAD_VAL]*6, rotate_angle, *[PAD_VAL]*(N_ARGS - 9)]])
    return deepcopy(target_vec)

def create_radius_constraint(curve_vec):
    constraint_vec = [
        [SELECT_IDX, *[PAD_VAL]*(N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'), curve_vec[2], curve_vec[3], *[PAD_VAL]*(N_ARGS_CONSTRAINTS)],
        [CONSTRAINT_IDX, *[PAD_VAL]*(N_ARGS - N_ARGS_CONSTRAINTS), -1, curve_vec[0].radius, -1, CONSTRAINT_VEC_TYPE.index('catCstTypeRadius')]
    ]
    return deepcopy(constraint_vec)

def create_l_r_radius_constraint(curve_vec):
    constraint_vec = [
        [SELECT_IDX, *[PAD_VAL]*(N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'), curve_vec[2], curve_vec[3], *[PAD_VAL]*(N_ARGS_CONSTRAINTS)],
        [CONSTRAINT_IDX, *[PAD_VAL]*(N_ARGS - N_ARGS_CONSTRAINTS), -1, curve_vec[0].l_radius, -1, CONSTRAINT_VEC_TYPE.index('catCstTypeMajorRadius')],
        [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'), curve_vec[2], curve_vec[3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
        [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, curve_vec[0].s_radius, -1, CONSTRAINT_VEC_TYPE.index('catCstTypeMinorRadius')]
    ]
    return deepcopy(constraint_vec)

def create_concentricity_constraint(curve_vec, next_vec):
    constraint_vec = [
        [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
         curve_vec[2], curve_vec[3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
        [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
         next_vec[2], next_vec[3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
        [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1,
         CONSTRAINT_VEC_TYPE.index('catCstTypeConcentricity')]
    ]
    return deepcopy(constraint_vec)

def get_line_angle(one_line):
    if one_line.end_point[0] == one_line.start_point[0]:
        return np.pi / 2
    k = (one_line.end_point[1] - one_line.start_point[1]) / (one_line.end_point[0] - one_line.start_point[0])
    angle = (np.arctan(k) + np.pi) % np.pi
    return angle

def create_parallelism_constraint(curve_vec, next_vec):
    constraint_vec = [
        [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
         curve_vec[2], curve_vec[3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
        [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
         next_vec[2], next_vec[3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
        [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1,
         CONSTRAINT_VEC_TYPE.index('catCstTypeParallelism')]
    ]
    return deepcopy(constraint_vec)

def create_perpendicularity_constraint(curve_vec, next_vec):
    constraint_vec = [
        [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
         curve_vec[2], curve_vec[3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
        [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
         next_vec[2], next_vec[3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
        [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1,
         CONSTRAINT_VEC_TYPE.index('catCstTypePerpendicularity')]
    ]
    return deepcopy(constraint_vec)

def create_horizontality_constraint(curve_vec):
    constraint_vec = [
        [SELECT_IDX, *[PAD_VAL]*(N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'), curve_vec[2], curve_vec[3], *[PAD_VAL]*(N_ARGS_CONSTRAINTS)],
        [CONSTRAINT_IDX, *[PAD_VAL]*(N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1, CONSTRAINT_VEC_TYPE.index('catCstTypeHorizontality')]
    ]
    return deepcopy(constraint_vec)

def create_verticality_constraint(curve_vec):
    constraint_vec = [
        [SELECT_IDX, *[PAD_VAL]*(N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'), curve_vec[2], curve_vec[3], *[PAD_VAL]*(N_ARGS_CONSTRAINTS)],
        [CONSTRAINT_IDX, *[PAD_VAL]*(N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1, CONSTRAINT_VEC_TYPE.index('catCstTypeVerticality')]
    ]
    return deepcopy(constraint_vec)

def create_length_constraint(curve_vec):
    curve = curve_vec[0]
    length = min(255, int(np.sqrt((curve.end_point[0] - curve.start_point[0]) * (curve.end_point[0] - curve.start_point[0]) + (curve.end_point[1] - curve.start_point[1]) * (curve.end_point[1] - curve.start_point[1]))))
    constraint_vec = [
        [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
         curve_vec[2], curve_vec[3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
        [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, length,
         CONSTRAINT_VEC_TYPE.index('catCstTypeLength')]
    ]
    return deepcopy(constraint_vec)

def create_angle_constraint(curve_vec, next_vec):
    angle1 = get_line_angle(curve_vec[0])
    angle2 = get_line_angle(next_vec[0])
    angle = (angle2 - angle1 + np.pi * 2) % (np.pi * 2)
    angle = min(255, round(angle / (np.pi * 2) * ARGS_N))
    constraint_vec = [
        [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
         curve_vec[2], curve_vec[3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
        [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
         next_vec[2], next_vec[3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
        [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), angle, -1, -1,
         CONSTRAINT_VEC_TYPE.index('catCstTypeAngle')]
    ]
    return deepcopy(constraint_vec)

def create_equidistance_constraint(index, vec_list):
    constraint_vec = []
    if vec_list[index][1] == 'Wire' and isinstance(vec_list[index][0], Line):
        # 随机寻找任一其他线，有概率选择轴
        random_wire_index = np.random.randint(-2, len(vec_list))
        while random_wire_index == index or (random_wire_index > -2 and vec_list[random_wire_index][1] != 'Wire'):
            random_wire_index = np.random.randint(-2, len(vec_list))

        if random_wire_index == -2:
            next_select_vec = [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('OriginElements'),
             0, 1, *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        elif random_wire_index == -1:
            next_select_vec = [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('OriginElements'),
             0, 2, *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        else:
            next_select_vec = [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
             vec_list[random_wire_index][2], vec_list[random_wire_index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]

        curve_select_vec = [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
             vec_list[index][2], vec_list[index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]

        equidistance_vec = [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1,
                            CONSTRAINT_VEC_TYPE.index('catCstTypeEquidistance')]

        constraint_vec.append(curve_select_vec)
        constraint_vec.append(next_select_vec)

        # 随机寻找任一其他点，有概率选择原点
        random_point_index = np.random.randint(-1, len(vec_list))
        while random_point_index != -1 and vec_list[random_point_index][1] != 'Point' and vec_list[random_point_index][1] != 'ControlPoint':
            random_point_index = np.random.randint(-1, len(vec_list))

        if random_point_index == -1:
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS),
                 SELECT_TYPE.index('OriginElements'),
                 0, 0, *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )

        elif vec_list[random_point_index][1] == 'Point':
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
                 vec_list[random_point_index][2], vec_list[random_point_index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Point'),
                 0, vec_list[random_point_index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )

        else:
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
                 vec_list[random_point_index][2], vec_list[random_point_index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS),
                 SELECT_TYPE.index('ControlPoint'),
                 0, vec_list[random_point_index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )

        constraint_vec.append(equidistance_vec)

    elif vec_list[index][1] == 'Point' or vec_list[index][1] == 'ControlPoint':
        # Point
        if vec_list[index][1] == 'Point':
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
                 vec_list[index][2], vec_list[index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS),
                 SELECT_TYPE.index('Point'),
                 0, vec_list[index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
        else:
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
                 vec_list[index][2], vec_list[index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS),
                 SELECT_TYPE.index('ControlPoint'),
                 0, vec_list[index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )

        # 随机寻找任一其他点，有概率选择原点
        random_point_index = np.random.randint(-1, len(vec_list))
        while random_point_index == index or (random_point_index != -1 and vec_list[random_point_index][1] != 'Point' and vec_list[random_point_index][1] != 'ControlPoint'):
            random_point_index = np.random.randint(-1, len(vec_list))

        # Point
        if random_point_index == -1:
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('OriginElements'),
                 0, 0, *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
        elif vec_list[random_point_index][1] == 'Point':
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
                 vec_list[random_point_index][2], vec_list[random_point_index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS),
                 SELECT_TYPE.index('Point'),
                 0, vec_list[random_point_index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
        else:
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
                 vec_list[random_point_index][2], vec_list[random_point_index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS),
                 SELECT_TYPE.index('ControlPoint'),
                 0, vec_list[random_point_index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )

        # 随机寻找任一其他点，有概率选择原点
        random_point_between_index = np.random.randint(-1, len(vec_list))
        while random_point_between_index == index or random_point_between_index == random_point_index or (
                random_point_between_index != -1 and vec_list[random_point_between_index][1] != 'Point' and
                vec_list[random_point_between_index][1] != 'ControlPoint'):
            random_point_between_index = np.random.randint(-1, len(vec_list))

        # Point
        if random_point_between_index == -1:
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('OriginElements'),
                 0, 0, *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
        elif vec_list[random_point_between_index][1] == 'Point':
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
                 vec_list[random_point_between_index][2], vec_list[random_point_between_index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS),
                 SELECT_TYPE.index('Point'),
                 0, vec_list[random_point_between_index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
        else:
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
                 vec_list[random_point_index][2], vec_list[random_point_index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS),
                 SELECT_TYPE.index('ControlPoint'),
                 0, vec_list[random_point_index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
        equidistance_vec = [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1,
                            CONSTRAINT_VEC_TYPE.index('catCstTypeEquidistance')]

        constraint_vec.append(equidistance_vec)
    else:
        return None
    return deepcopy(constraint_vec)

def create_fix_constraint(index, vec_list):
    if vec_list[index][1] == 'Wire':
        constraint_vec = [
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
             vec_list[index][2], vec_list[index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
            [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1,
             CONSTRAINT_VEC_TYPE.index('catCstTypeReference')]
        ]
    elif vec_list[index][1] == 'Point':
        constraint_vec = [
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
             vec_list[index][2], vec_list[index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Point'),
             0, vec_list[index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
            [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1,
             CONSTRAINT_VEC_TYPE.index('catCstTypeReference')]
        ]
    else:
        constraint_vec = [
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
             vec_list[index][2], vec_list[index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('ControlPoint'),
             0, vec_list[index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)],
            [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1,
             CONSTRAINT_VEC_TYPE.index('catCstTypeReference')]
        ]
    return deepcopy(constraint_vec)

def create_on_constraint(index, vec_list):
    # 如果是点。。。如果是线。。。
    constraint_vec = []
    if vec_list[index][1] == 'Wire':
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
             vec_list[index][2], vec_list[index][3],
             *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )

        if not isinstance(vec_list[index][0], Spline):
            if isinstance(vec_list[index][0], Line) or isinstance(vec_list[index][0], Arc) or isinstance(vec_list[index][0], Parabola) or isinstance(vec_list[index][0], Hyperbola):
                # 开始点或结束点
                if get_random_probability() < 0.5:
                    point_no = 0
                else:
                    point_no = 1
            else:
                return None

            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
                 vec_list[index][2], vec_list[index][3],
                 *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Point'),
                 0, point_no, *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
        else:
            point_no = np.random.randint(len(vec_list[index][0].point_list))
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
                 vec_list[index][2], vec_list[index][3],
                 *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
            constraint_vec.append(
                [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('ControlPoint'),
                 0, point_no, *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
            )
    else:
        # 若为圆心则不在curve上，返回
        if vec_list[index][4] == 2:
            return None
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
             vec_list[index][2], vec_list[index][3],
             *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )

        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
             vec_list[index][2], vec_list[index][3],
             *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )

        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index(vec_list[index][1]),
             0, vec_list[index][4],
             *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )

    constraint_vec.append(
        [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1, CONSTRAINT_VEC_TYPE.index('catCstTypeOn')]
    )
    return deepcopy(constraint_vec)

def get_distance_between_point_line(point_pos, line):
    if line.end_point[0] != line.start_point[0]:
        k = (line.end_point[1] - line.start_point[1]) / (line.end_point[0] - line.start_point[0])
        distance = np.abs(point_pos[1] - k * (point_pos[0] - line.start_point[0]) - line.start_point[1]) / np.sqrt(1 + k * k)
    else:
        distance = np.abs(line.start_point[0] - point_pos[0])
    return distance

def get_distance_between_element(element1, element2):
    # 无论是否计算一线一点或二点到二线的最短距离
    if element1[1] == 'Wire' and not (isinstance(element1[0], Circle) or isinstance(element1[0], Ellipse)):
        if element2[1] == 'Wire' and not isinstance(element2[0], Circle):
            length1 = get_distance_between_point_line(element1[0].start_point, element2[0])
            length2 = get_distance_between_point_line(element1[0].end_point, element2[0])
            return min(length1, length2)
        elif element2[1] == 'Point' or element2[1] == 'ControlPoint':
            return get_distance_between_point_line(element2[0], element1[0])
        else:
            if isinstance(element2[0], Circle):
                return get_distance_between_point_line(element2[0].center, element1[0]) + element2[0].radius
            else:
                return get_distance_between_point_line(element2[0].center, element1[0]) + element2[0].l_radius
    elif element1[1] == 'Point' or element1[1] == 'ControlPoint':
        if element2[1] == 'Wire' and not (isinstance(element1[0], Circle) or isinstance(element1[0], Ellipse)):
            return get_distance_between_point_line(element1[0], element2[0])
        elif element2[1] == 'Point' or element2[1] == 'ControlPoint':
            return get_distance_between_points(element1[0], element2[0])
        else:
            if isinstance(element2[0], Circle):
                get_distance_between_points(element2[0].center, element1[0]) + element2[0].radius
            else:
                get_distance_between_points(element2[0].center, element1[0]) + element2[0].l_radius
    else:
        if isinstance(element1[0], Circle):
            if element2[1] == 'Wire' and not isinstance(element2[0], Circle):
                return get_distance_between_point_line(element1[0].center, element2[0]) + element1[0].radius
            elif element2[1] == 'Point' or element2[1] == 'ControlPoint':
                return get_distance_between_points(element1[0].center, element2[0]) + element1[0].radius
            else:
                if isinstance(element2[0], Circle):
                    get_distance_between_points(element2[0].center, element1[0].center) + element2[0].radius + element1[0].radius
                else:
                    get_distance_between_points(element2[0].center, element1[0].center) + element2[0].l_radius + element1[0].radius
        else:
            if element2[1] == 'Wire' and not isinstance(element2[0], Circle):
                return get_distance_between_point_line(element1[0].center, element2[0]) + element1[0].l_radius
            elif element2[1] == 'Point' or element2[1] == 'ControlPoint':
                return get_distance_between_points(element1[0].center, element2[0]) + element1[0].l_radius
            else:
                if isinstance(element2[0], Circle):
                    get_distance_between_points(element2[0].center, element1[0].center) + element2[0].radius + element1[0].l_radius
                else:
                    get_distance_between_points(element2[0].center, element1[0].center) + element2[0].l_radius + element1[0].l_radius

def create_distance_constraint(index, vec_list):
    # 似乎不要求平行什么的
    constraint_vec = []
    if vec_list[index][1] == 'Wire':
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'), vec_list[index][2], vec_list[index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
    elif vec_list[index][1] == 'Point':
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'), vec_list[index][2], vec_list[index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Point'), 0, vec_list[index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
    else:
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'), vec_list[index][2], vec_list[index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('ControlPoint'), 0, vec_list[index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )


    # 随机寻找任一其他对象，有概率选择轴, -3为H轴，-2为V轴，-1为原点
    random_wire_index = np.random.randint(-3, len(vec_list))
    while random_wire_index == index:
        random_wire_index = np.random.randint(-3, len(vec_list))

    if random_wire_index == -3:
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('OriginElements'), 0, 1, *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
    elif random_wire_index == -2:
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('OriginElements'), 0, 2, *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
    elif random_wire_index == -1:
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('OriginElements'), 0, 0, *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
    elif vec_list[random_wire_index][1] == 'Wire':
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'), vec_list[random_wire_index][2], vec_list[random_wire_index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
    else:
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'), vec_list[random_wire_index][2], vec_list[random_wire_index][3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index(vec_list[random_wire_index][1]), 0, vec_list[random_wire_index][4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )

    if random_wire_index == -3:
        if vec_list[index][1] == 'Wire' and not isinstance(vec_list[index][0], Circle):
            distance = min(np.abs(vec_list[index][0].start_point[1]), np.abs(np.abs(vec_list[index][0].end_point[1])))
        elif vec_list[index][1] == 'Point':
            distance = np.abs(vec_list[index][0][1])
        else:
            if isinstance(vec_list[index][0], Circle):
                distance = np.abs(vec_list[index][0].center[1]) + vec_list[index][0].radius
            else:
                distance = np.abs(vec_list[index][0].center[1]) + vec_list[index][0].l_radius
    elif random_wire_index == -2:
        if vec_list[index][1] == 'Wire' and not isinstance(vec_list[index][0], Circle):
            distance = min(np.abs(vec_list[index][0].start_point[0]), np.abs(np.abs(vec_list[index][0].end_point[0])))
        elif vec_list[index][1] == 'Point':
            distance = np.abs(vec_list[index][0][0])
        else:
            if isinstance(vec_list[index][0], Circle):
                distance = np.abs(vec_list[index][0].center[0]) + vec_list[index][0].radius
            else:
                distance = np.abs(vec_list[index][0].center[0]) + vec_list[index][0].l_radius
    else:
        distance = min(255, round(get_distance_between_element(vec_list[index], vec_list[random_wire_index])))
    distance_vec = [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, distance, CONSTRAINT_VEC_TYPE.index('catCstTypeDistance')]
    constraint_vec.append(distance_vec)
    return deepcopy(constraint_vec)

def get_select_command(constraint_vec, element_vec):
    if element_vec[1] == 'Wire':
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
             element_vec[2], element_vec[3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
    else:
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index('Wire'),
             element_vec[2], element_vec[3], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS), SELECT_TYPE.index(element_vec[1]),
             0,
             element_vec[4], *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
    return deepcopy(constraint_vec)

def create_symmetry_constraint(index, vec_list):
    constraint_vec = get_select_command([], vec_list[index])
    # 要选择一个和index相同类型的对象，并选择一条线
    # 首先判断是否有同类型的对象，若无则返回
    none_flag = True
    for i in range(len(vec_list)):
        if i != index and isinstance(vec_list[i][0], type(vec_list[index][0])):
            none_flag = False
            break
    if none_flag:
        return None

    next_index = np.random.randint(len(vec_list))
    while not(next_index != index and isinstance(vec_list[index][0], type(vec_list[next_index][0]))):
        next_index = np.random.randint(len(vec_list))

    constraint_vec = get_select_command(constraint_vec, vec_list[next_index])

    # 首先判断是否有Line，若无则返回
    none_flag = True
    for i in range(len(vec_list)):
        if i != index and isinstance(vec_list[i][0], Line):
            none_flag = False
            break
    if none_flag:
        return None

    line_index = np.random.randint(-2, len(vec_list))
    while not((line_index == -2 or line_index == -1) or (line_index != index and isinstance(vec_list[line_index][0], Line))):
        line_index = np.random.randint(-2, len(vec_list))

    if line_index >= 0:
        constraint_vec = get_select_command(deepcopy(constraint_vec), vec_list[line_index])
    else:
        constraint_vec.append(
            [SELECT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_SELECT - N_ARGS_CONSTRAINTS),
             SELECT_TYPE.index('OriginElements'),
             0, np.abs(line_index), *[PAD_VAL] * (N_ARGS_CONSTRAINTS)]
        )
    constraint_vec.append(
        [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1, CONSTRAINT_VEC_TYPE.index('catCstTypeSymmetry')]
    )
    return deepcopy(constraint_vec)

def create_tangency_constraint(index, vec_list):
    # 对象一只能为Wire中的非Line曲线
    # 对象二可以为任意Wire
    if vec_list[index][1] != 'Wire':
        return None
    elif isinstance(vec_list[index][0], Line):
        # 首先检查是否有其他非Line的wire，若无则返回
        none_flag = True
        for i in range(len(vec_list)):
            if i != index and not isinstance(vec_list[i][0], Line):
                none_flag = False
                break
        if none_flag:
            return None

        next_index = np.random.randint(len(vec_list))
        while next_index == index or vec_list[next_index][1] != 'Wire' or isinstance(vec_list[next_index][0], Line):
            next_index = np.random.randint(len(vec_list))
    else:
        # 首先检查是否有其他wire，若无则返回
        none_flag = True
        for i in range(len(vec_list)):
            if i != index and vec_list[i][1] == 'Wire':
                none_flag = False
                break
        if none_flag:
            return None

        next_index = np.random.randint(len(vec_list))
        while next_index == index or vec_list[next_index][1] != 'Wire':
            next_index = np.random.randint(len(vec_list))

    constraint_vec = []
    constraint_vec = get_select_command(deepcopy(constraint_vec), vec_list[index])
    constraint_vec = get_select_command(deepcopy(constraint_vec), vec_list[next_index])
    constraint_vec.append(
        [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1, CONSTRAINT_VEC_TYPE.index('catCstTypeTangency')]
    )
    return deepcopy(constraint_vec)

def create_midpoint_constraint(index, vec_list):
    # 作用于不同的loop

    if vec_list[index][1] != 'Wire':
        point_index = index
        # 随机选择一条Line
        # 首先检查是否有非同一loop的Line，没有则返回
        none_flag = True
        for i in range(len(vec_list)):
            if i != index and isinstance(vec_list[i][0], Line) and vec_list[index][2] != vec_list[i][2]:
                none_flag = False
                break
        if none_flag:
            return None

        wire_index = np.random.randint(len(vec_list))
        while not (isinstance(vec_list[wire_index][0], Line) and vec_list[index][2] != vec_list[wire_index][2]):
            wire_index = np.random.randint(len(vec_list))
    elif isinstance(vec_list[index][0], Line):
        none_flag = True
        for i in range(len(vec_list)):
            if i != index and vec_list[i][1] != 'Wire' and vec_list[i][2] != vec_list[index][2]:
                none_flag = False
                break
        if none_flag:
            return None

        wire_index = index
        point_index = np.random.randint(len(vec_list))
        while not (vec_list[point_index][1] != 'Wire' and vec_list[i][2] != vec_list[index][2]):
            point_index = np.random.randint(len(vec_list))
    else:
        return None

    constraint_vec = []
    constraint_vec = get_select_command(deepcopy(constraint_vec), vec_list[point_index])
    constraint_vec = get_select_command(deepcopy(constraint_vec), vec_list[wire_index])
    constraint_vec.append(
        [CONSTRAINT_IDX, *[PAD_VAL] * (N_ARGS - N_ARGS_CONSTRAINTS), -1, -1, -1,
         CONSTRAINT_VEC_TYPE.index('catCstTypeMidPoint')]
    )
    return deepcopy(constraint_vec)

file_count = 0
input_paths = sorted(os.listdir(INPUT_PATH))
for input_path in input_paths:
    if not os.path.exists(os.path.join(SAVE_PATH, input_path)):
        os.makedirs(os.path.join(SAVE_PATH, input_path))
    truck_root = os.path.join(INPUT_PATH, input_path)

    file_paths = sorted(glob.glob(os.path.join(truck_root, "*.h5")))
    for path in file_paths:
        file_count += 1

        if file_count <= 5908:
            continue

        # 记录重开次数，若大于10则放弃
        remake_count = 0
        # 记录名字用于命名
        name = path[path.find('\\') + 1:-3]
        with h5py.File(path, 'r') as fp:
            if 'vec' in fp.keys():
                origin_vec = fp["vec"][:].astype(np.float)
            else:
                origin_vec = fp["out_vec"][:].astype(np.float)

        if IS_TEST:
            while remake_count < 10:
                changed_flag = False
                try:
                    # 记录当前各操作的数量，用于序号
                    operation_map = {'Sketch': 0, 'Extrude': 0, 'Revolve': 0, 'Chamfer': 0, 'Fillet': 0, 'Shell': 0,
                                     'Mirror': 0, 'Draft': 0, 'Hole': 0}
                    origin_vec_copy = deepcopy(origin_vec)

                    # 需要一个数据结构记录哪些wire因倒圆角导致序号后移:<loop_no, [wire_no]>，指wire_no为新curve，其余需要向后移
                    change_no_map = {}

                    # 遍历，根据开始指令分为n段
                    body_list = []
                    body_indices = np.where(origin_vec_copy[:, 0] == SOL_IDX)[
                        0].tolist() + [-1]
                    for i in range(len(body_indices) - 1):
                        # 将指令处理为21位
                        target_vec = origin_vec_copy[body_indices[i]:body_indices[i + 1]]
                        target_vec = target_vec[:, :21]
                        # 判断是否有多余的拉伸旋转，若有则删去
                        for one_vec in target_vec:
                            if one_vec[0] == 7 or one_vec[0] == 8:
                                target_vec = target_vec[:-1]
                        body_list.append(target_vec)

                    # 对每段分别进行处理
                    for i in range(body_list.__len__()):
                        operation_map['Sketch'] += 1
                        # 计算Scale

                        cur_sketch = Sketch.from_vector(body_list[i], True, ARGS_N)

                        max_scale = cur_sketch.sketch_profile.bbox_size
                        sketch_box = cur_sketch.sketch_profile.bbox

                        for j in range(len(body_list[i])):
                            # 判断是圆还是线, 圆则按概率变成椭圆
                            ############################################################################
                            random_pro = get_random_probability()
                            if body_list[i][j][0] == CIRCLE_IDX and random_pro < ELLIPSE_PROBABILITY:
                                body_list[i][j] = create_ellipse(body_list[i][j])
                                changed_flag = True
                            # 线则按概率变成抛物线、双曲线
                            elif body_list[i][j][0] == LINE_IDX:
                                ############################################################################
                                random_pro = get_random_probability()
                                if random_pro < PARA_HYPER_LINE_MAP['Parabola']:
                                    if j == 1:
                                        body_list[i][j] = create_parabola(body_list[i][j], body_list[i][-1][1:3])
                                    else:
                                        body_list[i][j] = create_parabola(body_list[i][j], body_list[i][j - 1][1:3])
                                    changed_flag = True
                                elif random_pro < PARA_HYPER_LINE_MAP['Hyperbola']:
                                    if j == 1:
                                        body_list[i][j] = create_hyperbola(body_list[i][j], body_list[i][-1][1:3])
                                    else:
                                        body_list[i][j] = create_hyperbola(body_list[i][j], body_list[i][j - 1][1:3])
                                    changed_flag = True

                        # 添加选取步骤
                        # 若存在两线，按概率添加倒圆角，注意添加后序号顺移，因此要记录哪条curve是新增的

                        # 有问题，不能倒角再倒角
                        new_curve_map = {}
                        j = 0
                        # 因倒角圆角产生的序号向后偏移量
                        no_offset = 0
                        while j < len(body_list[i]) - 1:
                            if body_list[i][j][0] == LINE_IDX and body_list[i][j + 1][0] == LINE_IDX:
                                ############################################################################
                                random_pro = get_random_probability()
                                if j == 1:
                                    line1_begin = body_list[i][-1][1:3]
                                else:
                                    line1_begin = body_list[i][j - 1][1:3]
                                line1_end = body_list[i][j][1:3]
                                line2_end = body_list[i][j + 1][1:3]
                                if random_pro < CHAMFER_FILLET_MAP['Chamfer']:
                                    output_vec = create_chamfer(
                                        np.floor(get_distance_between_points(line1_begin, line1_end)),
                                        np.floor(get_distance_between_points(line1_end, line2_end)),
                                        j + no_offset, j + 1 + no_offset, i + 1)

                                    if not (i + 1) in change_no_map.keys():
                                        change_no_map[i + 1] = [j + 1 + no_offset]
                                    else:
                                        change_no_map[i + 1].append(j + 1 + no_offset)

                                    new_curve_map[j + 1] = 'Line'
                                    body_list[i] = np.concatenate([body_list[i], output_vec])
                                    j += 1
                                    no_offset = no_offset + 1
                                    changed_flag = True
                                elif random_pro < CHAMFER_FILLET_MAP['Fillet']:
                                    if j == 1:
                                        line1_begin = body_list[i][-1][1:3]
                                    else:
                                        line1_begin = body_list[i][j - 1][1:3]
                                    line1_end = body_list[i][j][1:3]
                                    line2_end = body_list[i][j + 1][1:3]
                                    radius = min(get_distance_between_points(line1_begin, line1_end),
                                                 get_distance_between_points(line1_end, line2_end))
                                    output_vec = create_fillet(np.floor(radius), j + no_offset, j + 1 + no_offset, i + 1)

                                    if not (i + 1) in change_no_map.keys():
                                        change_no_map[i + 1] = [j + 1 + no_offset]
                                    else:
                                        change_no_map[i + 1].append(j + 1 + no_offset)

                                    new_curve_map[j + 1] = 'Arc'
                                    body_list[i] = np.concatenate([body_list[i], output_vec])
                                    j += 1
                                    no_offset = no_offset + 1
                                    changed_flag = True
                            j += 1
                        # 按概率添加镜像旋转，可能多次添加
                        repeat_factor = MIRROR_PROBABILITY
                        ############################################################################
                        random_pro = get_random_probability()
                        while random_pro < repeat_factor:

                            output_vec = create_mirror(i + 1, sketch_box)
                            repeat_factor = repeat_factor / 2
                            body_list[i] = np.concatenate([body_list[i], output_vec])
                            ############################################################################
                            random_pro = get_random_probability()
                            changed_flag = True

                        repeat_factor = ROTATE_PROBABILITY
                        ############################################################################
                        random_pro = get_random_probability()
                        while random_pro < repeat_factor:
                            output_vec = create_rotate(i + 1, sketch_box)
                            repeat_factor = repeat_factor / 2
                            body_list[i] = np.concatenate([body_list[i], output_vec])
                            ############################################################################
                            random_pro = get_random_probability()
                            changed_flag = True

                        # 判断合法性吗？
                        # 判断个p

                    # 添加约束的思路
                    # 1.先记录全部curve的信息、命名
                    # 2.根据约束的位置关系随机添加

                    loop_no = 0
                    curve_name_list = []

                    # 顺便判断是否合法
                    legal_flag = False

                    while loop_no < len(body_list):
                        wire_point = 0
                        wire_no = 1
                        while wire_point < len(body_list[loop_no]):
                            if body_list[loop_no][wire_point][0] == SOL_IDX:
                                wire_point += 1
                                continue
                            elif body_list[loop_no][wire_point][0] == LINE_IDX:
                                if wire_point == 1:
                                    start_point = np.array(body_list[loop_no][-1][1:3])
                                else:
                                    start_point = np.array(body_list[loop_no][wire_point - 1][1:3])
                                line = CAD_Class.Line.from_vector(body_list[loop_no][wire_point], start_point, is_numerical=True)
                                end_point = body_list[loop_no][wire_point][1:3]

                                wire_no_offset = 0

                                if (loop_no + 1) in change_no_map:
                                    for one_offset in change_no_map[loop_no + 1]:
                                        if wire_no + wire_no_offset >= one_offset:
                                            wire_no_offset += 1

                                curve_name_list.append([Line(start_point, end_point), 'Wire', loop_no + 1, wire_no + wire_no_offset])

                                wire_no += 1
                            elif body_list[loop_no][wire_point][0] == CIRCLE_IDX:
                                circle = CAD_Class.Circle.from_vector(body_list[loop_no][wire_point], [0, 0], is_numerical=True)

                                wire_no_offset = 0

                                if (loop_no + 1) in change_no_map:
                                    for one_offset in change_no_map[loop_no + 1]:
                                        if wire_no + wire_no_offset >= one_offset:
                                            wire_no_offset += 1

                                curve_name_list.append([circle, 'Wire', loop_no + 1, wire_no + wire_no_offset])

                                wire_no += 1

                            elif body_list[loop_no][wire_point][0] == ARC_IDX:
                                if wire_point == 1:
                                    start_point = np.array(body_list[loop_no][-1][1:3])
                                else:
                                    start_point = np.array(body_list[loop_no][wire_point - 1][1:3])
                                end_point = body_list[loop_no][wire_point][1:3]
                                arc = CAD_Class.Arc.from_vector(body_list[loop_no][wire_point], start_point, is_numerical=True)

                                wire_no_offset = 0

                                if (loop_no + 1) in change_no_map:
                                    for one_offset in change_no_map[loop_no + 1]:
                                        if wire_no + wire_no_offset >= one_offset:
                                            wire_no_offset += 1

                                curve_name_list.append([arc, 'Wire', loop_no + 1, wire_no + wire_no_offset])

                                wire_no += 1

                            elif body_list[loop_no][wire_point][0] == SPLINE_IDX:
                                if wire_point == 1:
                                    start_point = np.array(body_list[loop_no][-1][1:3])
                                else:
                                    start_point = np.array(body_list[loop_no][wire_point - 1][1:3])
                                sp_point = wire_point + 1
                                while sp_point < len(body_list[loop_no]) and body_list[loop_no][sp_point][0] == SCP_IDX:
                                    sp_point += 1
                                spline = CAD_Class.Spline.from_vector(body_list[loop_no][wire_point:sp_point], start_point, is_numerical=True)

                                wire_no_offset = 0

                                if (loop_no + 1) in change_no_map:
                                    for one_offset in change_no_map[loop_no + 1]:
                                        if wire_no + wire_no_offset >= one_offset:
                                            wire_no_offset += 1

                                curve_name_list.append([spline, 'Wire', loop_no + 1, wire_no + wire_no_offset])

                                wire_no += 1
                            elif body_list[loop_no][wire_point][0] == ELLIPSE_IDX:
                                ellipse = CAD_Class.Ellipse.from_vector(body_list[loop_no][wire_point], [0, 0], is_numerical=True)

                                wire_no_offset = 0

                                if (loop_no + 1) in change_no_map:
                                    for one_offset in change_no_map[loop_no + 1]:
                                        if wire_no + wire_no_offset >= one_offset:
                                            wire_no_offset += 1

                                curve_name_list.append([ellipse, 'Wire', loop_no + 1, wire_no + wire_no_offset])

                                wire_no += 1
                            elif body_list[loop_no][wire_point][0] == PARA_IDX:
                                if wire_point == 1:
                                    start_point = np.array(body_list[loop_no][-1][1:3])
                                else:
                                    start_point = np.array(body_list[loop_no][wire_point - 1][1:3])
                                parabola = CAD_Class.Parabola.from_vector(body_list[loop_no][wire_point], start_point, is_numerical=True)
                                if np.isnan(parabola.center[0]) or np.isnan(parabola.center[1]):
                                    legal_flag = True
                                wire_no_offset = 0

                                if (loop_no + 1) in change_no_map:
                                    for one_offset in change_no_map[loop_no + 1]:
                                        if wire_no + wire_no_offset >= one_offset:
                                            wire_no_offset += 1

                                curve_name_list.append([parabola, 'Wire', loop_no + 1, wire_no + wire_no_offset])

                                wire_no += 1
                            elif body_list[loop_no][wire_point][0] == HYPER_IDX:
                                if wire_point == 1:
                                    start_point = np.array(body_list[loop_no][-1][1:3])
                                else:
                                    start_point = np.array(body_list[loop_no][wire_point - 1][1:3])
                                hyperbola = CAD_Class.Hyperbola.from_vector(body_list[loop_no][wire_point], start_point, is_numerical=True)

                                if np.isnan(hyperbola.center[0]) or np.isnan(hyperbola.center[1]):
                                    legal_flag = True

                                wire_no_offset = 0

                                if (loop_no + 1) in change_no_map:
                                    for one_offset in change_no_map[loop_no + 1]:
                                        if wire_no + wire_no_offset >= one_offset:
                                            wire_no_offset += 1

                                curve_name_list.append([hyperbola, 'Wire', loop_no + 1, wire_no + wire_no_offset])

                                wire_no += 1
                            wire_point += 1
                        loop_no += 1

                    if legal_flag:
                        remake_count += 1
                        continue

                    constraints_list = []
                    # 将相同类的对象信息存在一起
                    class_name_map = {'Line': [], 'Arc': [], 'Circle': [], 'Ellipse': [], 'Spline': [], 'Parabola': [], 'Hyperbola': [], 'Point': []}
                    for one_curve in curve_name_list:
                        if isinstance(one_curve[0], Line):
                            class_name_map['Line'].append(deepcopy(one_curve))
                        elif isinstance(one_curve[0], Arc):
                            class_name_map['Arc'].append(deepcopy(one_curve))
                        elif isinstance(one_curve[0], Circle):
                            class_name_map['Circle'].append(deepcopy(one_curve))
                        elif isinstance(one_curve[0], Ellipse):
                            class_name_map['Ellipse'].append(deepcopy(one_curve))
                        elif isinstance(one_curve[0], Spline):
                            class_name_map['Spline'].append(deepcopy(one_curve))
                        elif isinstance(one_curve[0], Parabola):
                            class_name_map['Parabola'].append(deepcopy(one_curve))
                        elif isinstance(one_curve[0], Hyperbola):
                            class_name_map['Hyperbola'].append(deepcopy(one_curve))

                    ##############################################################
                    # 注意都还没设置概率！！！！！！！！！！！！！！！！！！！！！！！！！！！！

                    curve_sum = len(curve_name_list)

                    # 将所有点加入考虑,序号问题#######################################
                    for one_curve in class_name_map['Line']:
                        class_name_map['Point'].append([one_curve[0].end_point, 'Point', one_curve[2], one_curve[3], 1])
                    for one_curve in class_name_map['Circle']:
                        class_name_map['Point'].append([one_curve[0].center, 'Point', one_curve[2], one_curve[3], 2])
                    for one_curve in class_name_map['Arc']:
                        class_name_map['Point'].append([one_curve[0].end_point, 'Point', one_curve[2], one_curve[3], 1])
                        class_name_map['Point'].append([one_curve[0].center, 'Point', one_curve[2], one_curve[3], 2])
                    for one_curve in class_name_map['Ellipse']:
                        class_name_map['Point'].append([one_curve[0].center, 'Point', one_curve[2], one_curve[3], 2])
                    for one_curve in class_name_map['Spline']:
                        for one_point in range(len(one_curve[0].point_list)):
                            # 样条点的序号从0开始还是1开始？
                            class_name_map['Point'].append(
                                [one_curve[0].point_list[one_point], 'ControlPoint', one_curve[2], one_curve[3], one_point])
                    for one_curve in class_name_map['Parabola']:
                        class_name_map['Point'].append([one_curve[0].end_point, 'Point', one_curve[2], one_curve[3], 2])
                    for one_curve in class_name_map['Hyperbola']:
                        class_name_map['Point'].append([one_curve[0].end_point, 'Point', one_curve[2], one_curve[3], 2])

                    # 1.有椭圆和圆的话，优先添加长短轴约束，对于圆和椭圆
                    for one_curve in class_name_map['Circle']:
                        if get_random_probability() < CONSTRAINT_EXPECTATION / curve_sum:
                            constraints_list.append(create_radius_constraint(one_curve))
                    for one_curve in class_name_map['Arc']:
                        if get_random_probability() < CONSTRAINT_EXPECTATION / curve_sum:
                            constraints_list.append(create_radius_constraint(one_curve))
                    for one_curve in class_name_map['Ellipse']:
                        if get_random_probability() < CONSTRAINT_EXPECTATION / curve_sum:
                            constraints_list.append(create_l_r_radius_constraint(one_curve))
                    # 2.判断其是否与其他圆同心但半径不同，或与椭圆同心，有的话添加同心约束
                    curve_index = 0
                    while curve_index < len(class_name_map['Circle']):
                        next_index = curve_index + 1
                        while next_index < len(class_name_map['Circle']):
                            if np.allclose(class_name_map['Circle'][curve_index][0].center, class_name_map['Circle'][next_index][0].center) and class_name_map['Circle'][curve_index][0].radius != class_name_map['Circle'][next_index][0].radius:
                                constraints_list.append(create_concentricity_constraint(class_name_map['Circle'][curve_index], class_name_map['Circle'][next_index]))
                            next_index += 1
                        next_index = 0
                        while next_index < len(class_name_map['Ellipse']):
                            if np.allclose(class_name_map['Circle'][curve_index][0].center, class_name_map['Ellipse'][next_index][0].center):
                                constraints_list.append(create_concentricity_constraint(class_name_map['Circle'][curve_index], class_name_map['Ellipse'][next_index]))
                            next_index += 1
                        curve_index += 1

                    curve_index = 0
                    while curve_index < len(class_name_map['Ellipse']):
                        next_index = curve_index + 1
                        while next_index < len(class_name_map['Ellipse']):
                            if np.allclose(class_name_map['Ellipse'][curve_index][0].center, class_name_map['Ellipse'][next_index][0].center):
                                constraints_list.append(create_concentricity_constraint(class_name_map['Ellipse'][curve_index], class_name_map['Ellipse'][next_index]))
                            next_index += 1
                        curve_index += 1

                    # 3.对于Line，优先判断是否有平行、垂直关系（但仅判断同一loop中的关系）
                    #   为计算平行垂直关系，对每条线计算角度后确定关系
                    curve_index = 0
                    while curve_index < len(class_name_map['Line']):
                        if get_random_probability() < CONSTRAINT_EXPECTATION / curve_sum:

                            para_perp_flag = False

                            next_index = curve_index + 1
                            curve_angle = get_line_angle(class_name_map['Line'][curve_index][0])
                            while next_index < len(class_name_map['Line']):
                                ########################
                                if class_name_map['Line'][curve_index][2] == class_name_map['Line'][next_index][2]:
                                    if np.allclose(curve_angle, get_line_angle(class_name_map['Line'][next_index][0])):
                                        constraints_list.append(create_parallelism_constraint(class_name_map['Line'][curve_index], class_name_map['Line'][next_index]))
                                        para_perp_flag = True
                                    elif np.allclose((curve_angle + np.pi / 2) % np.pi, get_line_angle(class_name_map['Line'][next_index][0])):
                                        constraints_list.append(create_perpendicularity_constraint(class_name_map['Line'][curve_index], class_name_map['Line'][next_index]))
                                        para_perp_flag = True
                                next_index += 1

                            # 若没有找到垂直平行，再考虑以下约束
                            if not para_perp_flag:
                                # 随机添加竖直、水平、等距或角度
                                if np.allclose(curve_angle, 0):
                                    constraints_list.append(create_horizontality_constraint(class_name_map['Line'][curve_index]))
                                elif np.allclose(curve_angle, np.pi / 2):
                                    constraints_list.append(create_verticality_constraint(class_name_map['Line'][curve_index]))
                                else:
                                    random_pro = get_random_probability()
                                    if random_pro < LINE_CONSTRAINTS_MAP['Length']:
                                        constraints_list.append(create_length_constraint(class_name_map['Line'][curve_index]))
                                    else:
                                        constraints_list.append(create_angle_constraint(class_name_map['Line'][curve_index], class_name_map['Line'][
                                            (curve_index + 1) % len(class_name_map['Line'])]))
                        curve_index += 1
                    constraints_last = CONSTRAINT_EXPECTATION - len(constraints_list)
                    # 若以上约束未添加够，对所有curve、point以概率添加fix、distance、coincidence、相切约束
                    if constraints_last > 0:
                        for one_curve in range(len(curve_name_list)):
                            if get_random_probability() < constraints_last / curve_sum:
                                random_pro = get_random_probability()
                                if random_pro < LAST_CONSTRAINTS_MAP['Fix']:
                                    constraints_list.append(create_fix_constraint(one_curve, curve_name_list))
                                elif random_pro < LAST_CONSTRAINTS_MAP['Distance']:
                                    # 不存在则返回NULL
                                    tar = create_distance_constraint(one_curve, curve_name_list)
                                    if tar is not None:
                                        constraints_list.append(tar)
                                elif random_pro < LAST_CONSTRAINTS_MAP['On']:
                                    tar = create_on_constraint(one_curve, curve_name_list)
                                    if tar is not None:
                                        constraints_list.append(tar)
                                elif random_pro < LAST_CONSTRAINTS_MAP['Symmetry']:
                                    tar = create_symmetry_constraint(one_curve, curve_name_list)
                                    if tar is not None:
                                        constraints_list.append(tar)

                                elif random_pro < LAST_CONSTRAINTS_MAP['Tangency']:
                                    tar = create_tangency_constraint(one_curve, curve_name_list)
                                    if tar is not None:
                                        constraints_list.append(tar)
                                elif random_pro < LAST_CONSTRAINTS_MAP['MidPoint']:
                                    tar = create_midpoint_constraint(one_curve, curve_name_list)
                                    if tar is not None:
                                        constraints_list.append(tar)
                                elif random_pro < LAST_CONSTRAINTS_MAP['Equidistance']:
                                    tar = create_equidistance_constraint(one_curve, curve_name_list)
                                    if tar is not None:
                                        constraints_list.append(tar)


                    # Catia复现，若合格则保存
                    final_vec = np.concatenate(body_list)
                    if len(constraints_list) <= 0:
                        constraints_vec = None
                        final_vec = np.concatenate([final_vec, np.array([EOS_VEC])])
                    else:
                        constraints_vec = np.concatenate(constraints_list)
                        final_vec = np.concatenate([final_vec, constraints_vec, np.array([EOS_VEC])])
                    cad = Macro_Seq.from_vector(final_vec, is_numerical=True, n=256)
                except Exception as e:
                    print(file_count, ' ', name, ': Failed')
                    print(e)
                    remake_count += 1
                    continue
                # 若未作改动，则不写入
                if not changed_flag and constraints_vec is None:
                    remake_count += 1
                    continue

                catia = win32com.client.Dispatch('catia.application')
                catia.visible = 1
                doc = catia.documents.add('Part')
                part = doc.part
                result = create_CAD_CATIA(cad, catia, doc, part, only_sketch=True)

                if result != 0:
                    print(file_count, ' ', name, ': Failed')
                    remake_count += 1
                    doc.close()
                    continue

                name_path = SAVE_PATH + '/' + name + '.h5'
                # 判断name_count是否已经存在
                if not os.path.exists(name_path):
                    with h5py.File(name_path, 'w') as fp:
                        fp.create_dataset("vec", data=final_vec, dtype=np.int)
                remake_count = 10
                print(file_count, ' ', name, ': OK')
                doc.close()