from copy import copy, deepcopy

import numpy as np

from macro_new import *
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

from Geometry_utils import construct_curve_from_vector, angle_from_vector_to_x, polar_parameterization_inverse, polar2cartesian, vec2arc, get_center_from_Parabola, get_center_from_Hyperbola

##########################   base  ###########################
class SketchBase(object):
    """Base class for sketch (a collection of curves). """
    def __init__(self, children, reorder=True):
        self.children = children

        if reorder:
            self.reorder()

    @staticmethod
    def from_dict(stat):
        """construct sketch from json data

        Args:
            stat (dict): dict from json data
        """
        raise NotImplementedError

    @staticmethod
    def from_vector(vec, start_point, is_numerical=True):
        """construct sketch from vector representation

        Args:
            vec (np.array): (seq_len, n_args)
            start_point (np.array): (2, ). If none, implicitly defined as the last end point.
        """
        raise NotImplementedError

    def reorder(self):
        """rearrange the curves to follow counter-clockwise direction"""
        raise NotImplementedError

    @property
    def start_point(self):
        return self.children[0].start_point

    @property
    def end_point(self):
        return self.children[-1].end_point

    @property
    def bbox(self):
        """compute bounding box (min/max points) of the sketch"""
        all_points = np.concatenate([child.bbox for child in self.children], axis=0)
        return np.stack([np.min(all_points, axis=0), np.max(all_points, axis=0)], axis=0)

    @property
    def bbox_size(self):
        """compute bounding box size (max of height and width)"""
        bbox_min, bbox_max = self.bbox[0], self.bbox[1]
        bbox_size = np.max(np.abs(np.concatenate([bbox_max - self.start_point, bbox_min - self.start_point])))
        return bbox_size

    @property
    def global_trans(self):
        """start point + sketch size (bbox_size)"""
        return np.concatenate([self.start_point, np.array([self.bbox_size])])

    def transform(self, translate, scale):
        """linear transformation"""
        for child in self.children:
            child.transform(translate, scale)

    def flip(self, axis):
        for child in self.children:
            child.flip(axis)
        self.reorder()

    def numericalize(self, n=256):
        """quantize curve parameters into integers"""
        for child in self.children:
            child.numericalize(n)

    def denumericalize(self, n=256):
        for child in self.children:
            child.denumericalize(n)

    def normalize(self, bbox=-1, size=256):
        """normalize within the given size, with start_point in the middle center"""
        if bbox == -1:
            cur_size = self.bbox_size
            trans_pos = -self.start_point
        else:
            cur_size = bbox
            trans_pos = np.array([0, 0])
        scale = (size / 2 * NORM_FACTOR - 1) / cur_size # prevent potential overflow if data augmentation applied
        self.transform(trans_pos, scale)
        self.transform(np.array((size / 2, size / 2)), 1)

    def denormalize(self, bbox_size, size=256):
        """inverse procedure of normalize method"""
        scale = bbox_size / (size / 2 * NORM_FACTOR - 1)
        self.transform(-np.array((size / 2, size / 2)), scale)

    def to_vector(self):
        """convert to vector representation"""
        raise NotImplementedError

    def draw(self, ax):
        """draw sketch on matplotlib ax"""
        raise NotImplementedError

    def to_image(self):
        """convert to image"""
        fig, ax = plt.subplots()
        self.draw(ax)
        ax.axis('equal')
        fig.canvas.draw()
        X = np.array(fig.canvas.renderer.buffer_rgba())[:, :, :3]
        plt.close(fig)
        return X

    def sample_points(self, n=32):
        """uniformly sample points from the sketch"""
        raise NotImplementedError

####################### loop & profile #######################
class Loop(SketchBase):
    """Sketch loop, a sequence of connected curves."""
    def __str__(self):
        s = "Loop:"
        for curve in self.children:
            s += "\n      -" + str(curve)
        return s

    @staticmethod
    def from_vector(vec, start_point=None, is_numerical=True):
        all_curves = []
        if start_point is None:
            # FIXME: explicit for loop can be avoided here
            for i in range(vec.shape[0]):
                if vec[i][0] == EOS_IDX:
                    start_point = vec[i - 1][1:3]
                    break
        i = 0
        while i < vec.shape[0]:
            type = vec[i][0]
            if type == SOL_IDX:
                i = i + 1
                continue
            elif type == EOS_IDX:
                break
            # 若为Spline，则合并
            elif type == SPLINE_IDX:
                j = i + 1
                while j < vec.shape[0] and vec[j][0] == SCP_IDX:
                    j = j + 1
                curve = construct_curve_from_vector(vec[i:j], start_point, is_numerical=is_numerical)
                start_point = curve.end_point
                i = j - 1
            else:
                curve = construct_curve_from_vector(vec[i], start_point, is_numerical=is_numerical)
                start_point = vec[i][1:3]  # current curve's end_point serves as next curve's start_point
            all_curves.append(curve)
            i = i + 1
        return Loop(all_curves, reorder=False)

    def reorder(self):
        """reorder by starting left most and counter-clockwise"""
        if len(self.children) <= 1:
            return

        start_curve_idx = -1
        sx, sy = 10000, 10000

        # correct start-end point order
        if np.allclose(self.children[0].start_point, self.children[1].start_point) or \
            np.allclose(self.children[0].start_point, self.children[1].end_point):
            self.children[0].reverse()

        # correct start-end point order and find left-most point
        for i, curve in enumerate(self.children):
            if i < len(self.children) - 1 and np.allclose(curve.end_point, self.children[i + 1].end_point):
                self.children[i + 1].reverse()
            if round(curve.start_point[0], 6) < round(sx, 6) or \
                    (round(curve.start_point[0], 6) == round(sx, 6) and round(curve.start_point[1], 6) < round(sy, 6)):
                start_curve_idx = i
                sx, sy = curve.start_point

        self.children = self.children[start_curve_idx:] + self.children[:start_curve_idx]

        # ensure mostly counter-clock wise
        if isinstance(self.children[0], Circle) or isinstance(self.children[-1], Circle): # FIXME: hard-coded
            return
        start_vec = self.children[0].direction()
        end_vec = self.children[-1].direction(from_start=False)
        if np.cross(end_vec, start_vec) <= 0:
            for curve in self.children:
                curve.reverse()
            self.children.reverse()

    def to_vector(self, max_len=None, add_sol=True, add_eos=True):
        sta = []
        for curve in self.children:
            sta.append(curve.to_vector())
        sta = np.concatenate(sta, axis=0)
        loop_vec = np.stack(sta, axis=0)
        if add_sol:
            loop_vec = np.concatenate([SOL_VEC[np.newaxis], loop_vec], axis=0)
        if add_eos:
            loop_vec = np.concatenate([loop_vec, EOS_VEC[np.newaxis]], axis=0)
        if max_len is None:
            return loop_vec

        if loop_vec.shape[0] > max_len:
            return None
        elif loop_vec.shape[0] < max_len:
            pad_vec = np.tile(EOS_VEC, max_len - loop_vec.shape[0]).reshape((-1, len(EOS_VEC)))
            loop_vec = np.concatenate([loop_vec, pad_vec], axis=0) # (max_len, 1 + N_ARGS)
        return loop_vec

    def draw(self, ax):
        colors = ['red', 'blue', 'green', 'brown', 'pink', 'yellow', 'purple', 'black'] * 10
        for i, curve in enumerate(self.children):
            curve.draw(ax, colors[i])

    def sample_points(self, n=32):
        points = np.stack([curve.sample_points(n) for curve in self.children], axis=0) # (n_curves, n, 2)
        return points

class Profile(SketchBase):
    """Sketch profile，a closed region formed by one or more loops.
    The outer-most loop is placed at first."""
    @staticmethod
    def from_dict(stat):
        all_loops = [Loop.from_dict(item) for item in stat['loops']]
        return Profile(all_loops)

    def __str__(self):
        s = "Profile:"
        for loop in self.children:
            s += "\n    -" + str(loop)
        return s

    @staticmethod
    def from_vector(vec, start_point=None, is_numerical=True):
        all_loops = []
        command = vec[:, 0]
        end_idx = command.tolist().index(EOS_IDX)
        indices = np.where(command[:end_idx] == SOL_IDX)[0].tolist() + [end_idx]
        for i in range(len(indices) - 1):
            loop_vec = vec[indices[i]:indices[i + 1]]
            loop_vec = np.concatenate([loop_vec, EOS_VEC[np.newaxis]], axis=0)
            if loop_vec[0][0] == SOL_IDX and loop_vec[1][0] not in [SOL_IDX, EOS_IDX]:
                all_loops.append(Loop.from_vector(loop_vec, is_numerical=is_numerical))
        return Profile(all_loops, reorder=False)

    def reorder(self):
        if len(self.children) <= 1:
            return
        all_loops_bbox_min = np.stack([loop.bbox[0] for loop in self.children], axis=0).round(6)
        ind = np.lexsort(all_loops_bbox_min.transpose()[[1, 0]])
        self.children = [self.children[i] for i in ind]

    def draw(self, ax):
        for i, loop in enumerate(self.children):
            loop.draw(ax)
            ax.text(loop.start_point[0], loop.start_point[1], str(i))

    def to_vector(self, max_n_loops=None, max_len_loop=None, pad=True):
        loop_vecs = [loop.to_vector(None, add_eos=False) for loop in self.children]
        # if max_n_loops is not None and len(loop_vecs) > max_n_loops:
        #     return None
        # for vec in loop_vecs:
        #     if max_len_loop is not None and vec.shape[0] > max_len_loop:
        #         return None
        profile_vec = np.concatenate(loop_vecs, axis=0)
        profile_vec = np.concatenate([profile_vec, EOS_VEC[np.newaxis]], axis=0)
        if pad:
            pad_len = max_n_loops * max_len_loop - profile_vec.shape[0]
            profile_vec = np.concatenate([profile_vec, EOS_VEC[np.newaxis].repeat(pad_len, axis=0)], axis=0)
        return profile_vec

    def sample_points(self, n=32):
        points = np.concatenate([loop.sample_points(n) for loop in self.children], axis=0)
        return points

class Line():
    def __init__(self, start_point, end_point, reportName=0):
        self.start_point = start_point
        self.end_point = end_point
        self.reportName = reportName

    def reverse(self):
        self.start_point, self.end_point = self.end_point, self.start_point

    def direction(self, from_start=True):
        return self.end_point - self.start_point

    def transform(self, translation, scale):
        self.start_point = (self.start_point + translation) * scale
        self.end_point = (self.end_point + translation) * scale

    def numericalize(self, n=256):
        self.start_point, _ = Get_integer_and_fraction(self.start_point)
        self.end_point, _ = Get_integer_and_fraction(self.end_point)

    def denumericalize(self, n=256):
        pass

    @staticmethod
    def from_vector(vec, start_point, is_numerical=True):
        end_point = vec[1:3]
        return Line(start_point, end_point)

    def to_vector(self):
        vec = [LINE_IDX, self.end_point[0], self.end_point[1]]
        vec = np.array(vec + [PAD_VAL] * (1 + N_ARGS - len(vec)))
        vec = np.array([vec])
        return vec

    @property
    def bbox(self):
        points = np.stack([self.start_point, self.end_point], axis=0)
        return np.stack([np.min(points, axis=0), np.max(points, axis=0)], axis=0)

class Arc(object):
    def __init__(self, center, radius, start_arc, end_arc, mid_arc, reportName=0):
        self.center = center
        self.radius = radius
        self.start_arc = start_arc
        self.end_arc = end_arc
        self.reportName = reportName
        self.mid_arc = mid_arc
        self.mid_point = self.center + self.radius * np.array([np.cos(self.mid_arc), np.sin(self.mid_arc)])
        self.start_point = np.array([self.center[0] + np.cos(self.start_arc) * self.radius, self.center[1] + np.sin(self.start_arc) * self.radius])
        self.end_point = np.array([self.center[0] + np.cos(self.end_arc) * self.radius, self.center[1] + np.sin(self.end_arc) * self.radius])

    @property
    def ref_vec(self):
        if self.clock_sign == 0:
            tmp = self.end_point - self.center
        else:
            tmp = self.start_point - self.center
        return tmp / np.linalg.norm(tmp)

    @property
    def clock_sign(self):
        """get a boolean sign indicating whether the arc is on top of s->e """
        s2e = self.end_point - self.start_point
        s2m = self.mid_point - self.start_point
        sign = np.cross(s2m, s2e) >= 0 # counter-clockwise
        return sign

    def reverse(self):
        self.start_arc, self.end_arc = self.end_arc, self.start_arc
        self.start_point, self.end_point = self.end_point, self.start_point

    def numericalize(self, n=256):
        # 先将弧度规定在0~2pi
        self.start_arc = self.start_arc % (2 * np.pi)
        self.end_arc = self.end_arc % (2 * np.pi)
        tmp = np.array([self.start_arc, self.end_arc])
        self.start_arc, self.end_arc = tmp / (2 * np.pi) * n

        self.start_point, _ = Get_integer_and_fraction(self.start_point)
        self.end_point, _ = Get_integer_and_fraction(self.end_point)
        self.center, _ = Get_integer_and_fraction(self.center)
        self.mid_point, _ = Get_integer_and_fraction(self.mid_point)
        self.start_arc, _ = Get_integer_and_fraction(self.start_arc)
        self.end_arc, _ = Get_integer_and_fraction(self.end_arc)

    def denumericalize(self, n=256):
        pass

    def to_vector(self):
        if self.clock_sign:
            sweep_angle = (self.end_arc - self.start_arc + ARGS_N) % ARGS_N
        else:
            sweep_angle = (self.start_arc - self.end_arc + ARGS_N) % ARGS_N
        # sweep_angle = max(abs(self.start_arc - self.end_arc), 1)
        vec = np.array([ARC_IDX, self.end_point[0], self.end_point[1], sweep_angle, int(self.clock_sign), PAD_VAL,
                        *[PAD_VAL] * (N_ARGS - N_ARGS_SKETCH)])
        return np.array([vec])

    @staticmethod
    def from_vector(vec, start_point, is_numerical=True):
        end_point = vec[1:3]
        # 添加fraction
        sweep_angle = vec[3] / ARGS_N * 2 * np.pi if is_numerical else vec[3]
        clock_sign = vec[4]
        s2e_vec = end_point - start_point
        if np.linalg.norm(s2e_vec) == 0:
            return None
        radius = (np.linalg.norm(s2e_vec) / 2) / np.sin(sweep_angle / 2)
        s2e_mid = (start_point + end_point) / 2
        vertical = np.cross(s2e_vec, [0, 0, 1])[:2]
        vertical = vertical / np.linalg.norm(vertical)
        if clock_sign == 0:
            vertical = -vertical
        center_point = s2e_mid - vertical * (radius * np.cos(sweep_angle / 2))

        start_arc = vec2arc(start_point, center_point)
        end_arc = vec2arc(end_point, center_point)
        if clock_sign == 0:
            if end_arc < start_arc:
                mid_arc = (start_arc + end_arc) / 2
            else:
                mid_arc = (start_arc + end_arc + 2 * np.pi) / 2
        else:
            if start_arc < end_arc:
                mid_arc = (start_arc + end_arc) / 2
            else:
                mid_arc = (start_arc + end_arc + 2 * np.pi) / 2

        return Arc(center_point, radius, start_arc, end_arc, mid_arc)


    def transform(self, translation, scale):
        self.start_point = (self.start_point + translation) * scale
        self.mid_point = (self.mid_point + translation) * scale
        self.end_point = (self.end_point + translation) * scale
        self.center = (self.center + translation) * scale
        if isinstance(scale * 1.0, float):
            self.radius = abs(self.radius * scale)

    def get_angles_counterclockwise(self, eps=1e-8):
        c2s_vec = (self.start_point - self.center) / (np.linalg.norm(self.start_point - self.center) + eps)
        c2m_vec = (self.mid_point - self.center) / (np.linalg.norm(self.mid_point - self.center) + eps)
        c2e_vec = (self.end_point - self.center) / (np.linalg.norm(self.end_point - self.center) + eps)
        angle_s, angle_m, angle_e = angle_from_vector_to_x(c2s_vec), angle_from_vector_to_x(c2m_vec), \
                                    angle_from_vector_to_x(c2e_vec)
        angle_s, angle_e = min(angle_s, angle_e), max(angle_s, angle_e)
        if not angle_s < angle_m < angle_e:
            angle_s, angle_e = angle_e - np.pi * 2, angle_s
        return angle_s, angle_e

    @property
    def clock_sign(self):
        """get a boolean sign indicating whether the arc is on top of s->e """
        s2e = self.end_point - self.start_point
        s2m = self.mid_point - self.start_point
        sign = np.cross(s2m, s2e) >= 0 # counter-clockwise
        return sign

    @property
    def bbox(self):
        points = [self.start_point, self.end_point]
        angle_s, angle_e = self.get_angles_counterclockwise()
        if angle_s < 0 < angle_e:
            points.append(np.array([self.center[0] + self.radius, self.center[1]]))
        if angle_s < np.pi / 2 < angle_e or angle_s < -np.pi / 2 * 3 < angle_e:
            points.append(np.array([self.center[0], self.center[1] + self.radius]))
        if angle_s < np.pi < angle_e or angle_s < -np.pi < angle_e:
            points.append(np.array([self.center[0] - self.radius, self.center[1]]))
        if angle_s < np.pi / 2 * 3 < angle_e or angle_s < -np.pi/2 < angle_e:
            points.append(np.array([self.center[0], self.center[1] - self.radius]))
        points = np.stack(points, axis=0)
        return np.stack([np.min(points, axis=0), np.max(points, axis=0)], axis=0)

    def direction(self, from_start=True):
        if from_start:
            return self.mid_point - self.start_point
        else:
            return self.end_point - self.mid_point

class Circle(object):
    def __init__(self, center, radius, reportName=0):
        self.center = center
        self.radius = radius
        self.reportName = reportName

    def transform(self, translation, scale):
        self.center = (self.center + translation) * scale
        self.radius = self.radius * scale

    def numericalize(self, n=256):
        self.center, _ = Get_integer_and_fraction(self.center)
        self.radius, _ = Get_integer_and_fraction(self.radius)

    def denumericalize(self, n=256):
        pass

    @staticmethod
    def from_vector(vec, start_point=None, is_numerical=True):
        return Circle(vec[1:3], vec[5])

    def to_vector(self):
        vec = [CIRCLE_IDX, self.center[0], self.center[1], PAD_VAL, PAD_VAL, self.radius]
        vec = np.array(np.array(vec + [PAD_VAL] * (1 + N_ARGS - len(vec))))
        return np.array([vec])

    @property
    def bbox(self):
        return np.stack([self.center - self.radius, self.center + self.radius], axis=0)

    @property
    def start_point(self):
        return np.array([self.center[0] - self.radius, self.center[1]])

    @property
    def end_point(self):
        return np.array([self.center[0] + self.radius, self.center[1]])

    def direction(self, from_start=True):
        return self.center - self.start_point

class Ellipse(object):
    def __init__(self, center, l_radius, s_radius, axis_angle, reportName=0):
        self.center = center
        self.l_radius = l_radius
        self.s_radius = s_radius
        self.axis_angle = axis_angle
        self.reportName = reportName

    def transform(self, translation, scale):
        self.center = (self.center + translation) * scale
        self.l_radius = self.l_radius * scale
        self.s_radius = self.s_radius * scale

    def numericalize(self, n=256):
        self.center, _ = Get_integer_and_fraction(self.center)
        self.l_radius, _ = Get_integer_and_fraction(self.l_radius)
        self.s_radius, _ = Get_integer_and_fraction(self.s_radius)
        self.axis_angle = self.axis_angle / np.pi * ARGS_N
        self.axis_angle, _ = Get_integer_and_fraction(self.axis_angle)

    def denumericalize(self, n=256):
        self.axis_angle = self.axis_angle / ARGS_N * np.pi

    @staticmethod
    def from_vector(vec, start_point=None, is_numerical=True):
        return Ellipse(vec[1:3], vec[5], vec[6], vec[7])

    def to_vector(self):
        vec = [ELLIPSE_IDX, self.center[0], self.center[1], PAD_VAL, PAD_VAL, self.l_radius, self.s_radius, self.axis_angle]
        vec = np.array(np.array(vec + [PAD_VAL] * (1 + N_ARGS - len(vec))))
        return np.array([vec])

    @property
    def bbox(self):
        return np.stack([self.center - self.l_radius, self.center + self.l_radius], axis=0)

    @property
    def start_point(self):
        angle = (self.axis_angle * 2 / ARGS_N - 1) * np.pi
        return np.array([self.center[0] - self.l_radius * np.cos(angle), self.center[1] - self.l_radius * np.sin(angle)])

    @property
    def end_point(self):
        angle = (self.axis_angle * 2 / ARGS_N - 1) * np.pi
        return np.array([self.center[0] + self.l_radius * np.cos(angle), self.center[1] + self.l_radius * np.sin(angle)])

    def direction(self, from_start=True):
        return self.center - self.start_point

class Spline(object):
    def __init__(self, point_list, reportName=0, no_in_loop=0):
        self.point_list = point_list
        self.reportName = reportName
        self.no_in_loop = no_in_loop

    def reverse(self):
        self.point_list = np.flipud(self.point_list)

    def direction(self, from_start=True):
        return self.end_point - self.start_point

    def transform(self, translation, scale):
        new_point_list = []
        for i in self.point_list:
            new_point_list.append((i + translation) * scale)
        self.point_list = np.array(new_point_list)

    def numericalize(self, n=256):
        new_point_list = []
        for i in self.point_list:
            i, _ = Get_integer_and_fraction(i)
            new_point_list.append(i)
        self.point_list = new_point_list

    def denumericalize(self, n=256):
        pass

    @staticmethod
    def from_vector(vec, start_point, is_numerical=True):
        point_list = [start_point]
        for i in vec[1:]:
            point_list.append(i[1:3])
        point_list = np.array(point_list)
        return Spline(point_list)

    def to_vector(self):
        vec = [SPLINE_VEC]
        for i in self.point_list[1:]:
            tmp = [SCP_IDX, i[0], i[1]]
            vec.append(tmp + [PAD_VAL] * (1 + N_ARGS - len(tmp)))
        vec = np.array(vec)
        return vec

    @property
    def bbox(self):
        # 挑出最左、最右、最上、最下的坐标，然后将左右距离和上下对比，看哪个更长
        min_x = 0x3f3f3f3f
        min_y = 0x3f3f3f3f
        max_x = -0x3f3f3f3f
        max_y = -0x3f3f3f3f
        min_x_point = -1
        min_y_point = -1
        max_x_point = -1
        max_y_point = -1
        for i in range(self.point_list.__len__()):
            if min_x > np.abs(self.point_list[i][0]):
                min_x = np.abs(self.point_list[i][0])
                min_x_point = i
            if min_y > np.abs(self.point_list[i][1]):
                min_y = np.abs(self.point_list[i][1])
                min_y_point = i
            if max_x < np.abs(self.point_list[i][0]):
                max_x = np.abs(self.point_list[i][0])
                max_x_point = i
            if max_y < np.abs(self.point_list[i][1]):
                max_y = np.abs(self.point_list[i][1])
                max_y_point = i
        x_dis = max_x - min_x
        y_dis = max_y - min_y
        if x_dis > y_dis:
            return np.stack([self.point_list[min_x_point], self.point_list[max_x_point]], axis=0)
        else:
            return np.stack([self.point_list[min_y_point], self.point_list[max_y_point]], axis=0)

    @property
    def start_point(self):
        return self.point_list[0]

    @property
    def end_point(self):
        return self.point_list[self.point_list.__len__() - 1]

class Hyperbola(object):
    def __init__(self, start_point, end_point, axis_angle, major_distance, minor_distance):
        self.start_point = start_point
        self.end_point = end_point
        self.axis_angle = axis_angle
        self.major_distance = major_distance
        self.minor_distance = minor_distance
        self.center = get_center_from_Hyperbola(self.start_point, self.end_point, self.axis_angle, self.major_distance, self.minor_distance)

    def transform(self, translation, scale):
        self.start_point = (self.start_point + translation) * scale
        self.end_point = (self.end_point + translation) * scale
        self.center = (self.center + translation) * scale
        self.major_distance = self.major_distance * scale
        self.minor_distance = self.minor_distance * scale

    def numericalize(self, n=256):
        self.start_point = Get_integer_and_fraction(self.start_point, n)
        self.end_point = Get_integer_and_fraction(self.end_point, n)
        self.major_distance = Get_integer_and_fraction(self.major_distance)
        self.minor_distance = Get_integer_and_fraction(self.minor_distance)
        self.axis_angle = self.axis_angle / 2 / np.pi * ARGS_N

    def denumericalize(self, n=256):
        self.axis_angle = self.axis_angle / ARGS_N * 2 * np.pi

    @staticmethod
    def from_vector(vec, start_point=None, is_numerical=True):
        return Hyperbola(start_point, vec[1:3], vec[8], vec[5], vec[6])

    def to_vector(self):
        return np.array([HYPER_IDX, self.start_point[0], self.start_point[1], *[PAD_VAL]*2, self.major_distance, self.minor_distance, *[PAD_VAL]*1, self.axis_angle, *[PAD_VAL]*(8 + N_ARGS_CONSTRAINTS)])

class Parabola(object):
    def __init__(self, start_point, end_point, axis_angle, focal_length):
        self.start_point = start_point
        self.end_point = end_point
        self.focal_length = focal_length
        # 0~2pi
        self.axis_angle = axis_angle
        self.center = get_center_from_Parabola(start_point, end_point, axis_angle, focal_length)

    def transform(self, translation, scale):
        self.start_point = (self.start_point + translation) * scale
        self.end_point = (self.end_point + translation) * scale
        self.center = (self.center + translation) * scale
        self.focal_length = self.focal_length * scale

    def numericalize(self, n=256):
        self.start_point = Get_integer_and_fraction(self.start_point, n)
        self.end_point = Get_integer_and_fraction(self.end_point, n)
        self.focal_length = Get_integer_and_fraction(self.focal_length)
        self.axis_angle = self.axis_angle / 2 / np.pi * ARGS_N

    def denumericalize(self, n=256):
        self.axis_angle = self.axis_angle / ARGS_N * 2 * np.pi

    @staticmethod
    def from_vector(vec, start_point=None, is_numerical=True):
        return Parabola(start_point, vec[1:3], vec[8], vec[13])

    def to_vector(self):
        return np.array([PARA_IDX, self.start_point[0], self.start_point[1], *[PAD_VAL]*5, self.axis_angle, *[PAD_VAL]*4, self.focal_length, *[PAD_VAL]*(3 + N_ARGS_CONSTRAINTS)])

    # 不太对
    @property
    def bbox(self):
        points = np.stack([self.start_point, self.end_point], axis=0)
        return np.stack([np.min(points, axis=0), np.max(points, axis=0)], axis=0)

class Mirror(object):
    def __init__(self, start_point, oriented_angle, select_list=[]):
        self.start_point = start_point
        self.oriented_angle = oriented_angle
        self.select_list = select_list

    def transform(self, translation, scale):
        self.start_point = (self.start_point + translation) * scale

    def numericalize(self, n=256):
        for i in self.select_list:
            i.numericalize(n)
        self.start_point = (self.start_point + 1) / 2 * ARGS_N
        self.oriented_angle = self.oriented_angle / np.pi * ARGS_N
        self.start_point, _ = Get_integer_and_fraction(self.start_point, n)
        self.oriented_angle, _ = Get_integer_and_fraction(self.oriented_angle, n)

    def denumericalize(self, n=256):
        self.start_point = self.start_point / ARGS_N * 2 - 1
        self.oriented_angle = self.oriented_angle / ARGS_N * np.pi
        for i in self.select_list:
            i.denumericalize()


    @staticmethod
    def from_vector(vec, is_numerical=False, n=256):
        select_vec = deepcopy(vec[:-1])
        select_list = Select.from_vector(select_vec, is_numerical=True, n=256)

        mirror = Mirror(vec[-1][1:3], vec[-1][7], deepcopy(select_list))

        mirror.denumericalize(n=256)

        return mirror

    def to_vector(self, max_n_loops=None, max_len_loop=None, pad=True):
        all_vec = None
        for select in self.select_list:
            select_vec = select.to_vector(max_n_loops, max_len_loop, pad=False, is_last=True)
            # 转np.array
            select_vec_np = np.array(select_vec)
            if all_vec is None:
                all_vec = select_vec_np
            else:
                all_vec = np.concatenate([all_vec, select_vec_np], axis=0)
        mirror_vec = np.array([[MIRROR_IDX, self.start_point[0], self.start_point[1], *[PAD_VAL]*4, self.oriented_angle, *[PAD_VAL]*(9 + N_ARGS_CONSTRAINTS)]])
        return np.concatenate([all_vec, mirror_vec])

class Rotate(object):
    def __init__(self, center, rotate_angle, select_list=[]):
        self.center = center
        self.rotate_angle = rotate_angle
        self.select_list = select_list

    def transform(self, translation, scale):
        self.start_point = (self.start_point + translation) * scale

    def numericalize(self, n=256):
        for i in self.select_list:
            i.numericalize(n)
        self.center = (self.center + 1) / 2 * ARGS_N
        self.rotate_angle = self.rotate_angle / 2 / np.pi * ARGS_N
        self.center, _ = Get_integer_and_fraction(self.center, n)
        self.rotate_angle, _ = Get_integer_and_fraction(self.rotate_angle, n)

    def denumericalize(self, n=256):
        self.center = self.center / ARGS_N * 2 - 1
        self.rotate_angle = self.rotate_angle / ARGS_N * 2 * np.pi
        for i in self.select_list:
            i.denumericalize()


    @staticmethod
    def from_vector(vec, is_numerical=False, n=256):
        select_vec = deepcopy(vec[:-1])
        select_list = Select.from_vector(select_vec, is_numerical=True, n=256)

        rotate = Rotate(vec[-1][1:3], vec[-1][9], deepcopy(select_list))

        rotate.denumericalize(n=256)

        return rotate

    def to_vector(self, max_n_loops=None, max_len_loop=None, pad=True):
        all_vec = None
        for select in self.select_list:
            select_vec = select.to_vector(max_n_loops, max_len_loop, pad=False, is_last=True)
            # 转np.array
            select_vec_np = np.array(select_vec)
            if all_vec is None:
                all_vec = select_vec_np
            else:
                all_vec = np.concatenate([all_vec, select_vec_np], axis=0)
        rotate_vec = np.array([[ROTATE_IDX, self.center[0], self.center[1], *[PAD_VAL]*6, self.rotate_angle, *[PAD_VAL]*(7 + N_ARGS_CONSTRAINTS)]])
        return np.concatenate([all_vec, rotate_vec])

class Chamfer(object):
    def __init__(self, length1, length2, select_list=[]):
        self.length1 = length1
        self.length2 = length2
        self.select_list = select_list

    def transform(self, translation, scale):
        self.length1 = self.length1 * scale
        self.length2 = self.length2 * scale

    def numericalize(self, n=256):
        for i in self.select_list:
            i.numericalize(n)
        self.length1 = self.length1 * ARGS_N
        self.length2 = self.length2 * ARGS_N
        self.length1 = Get_integer_and_fraction(self.length1, n)
        self.length2 = Get_integer_and_fraction(self.length2, n)

    def denumericalize(self, n=256):
        self.length1 = self.length1 / ARGS_N
        self.length2 = self.length2 / ARGS_N
        for i in self.select_list:
            i.denumericalize()

    @staticmethod
    def from_vector(vec, is_numerical=False, n=256):
        select_vec = deepcopy(vec[:-1])
        select_list = Select.from_vector(select_vec, is_numerical=True, n=256)
        chamfer = Chamfer(vec[-1][10], vec[-1][11], select_list)

        chamfer.denumericalize()

        return chamfer

    def to_vector(self):
        return np.array([CHAMFER_IDX, *[PAD_VAL]*9, self.length1, self.length2, *[PAD_VAL]*(1 + N_ARGS_SELECT + N_ARGS_CONSTRAINTS)])

class Fillet(object):
    def __init__(self, radius, select_list=[]):
        self.radius = radius
        self.select_list = select_list

    def transform(self, translation, scale):
        self.radius = self.radius * scale

    def numericalize(self, n=256):
        for i in self.select_list:
            i.numericalize(n)
        self.radius = self.radius * ARGS_N
        self.radius = Get_integer_and_fraction(self.radius, n)

    def denumericalize(self, n=256):
        self.radius = self.radius / ARGS_N
        for i in self.select_list:
            i.denumericalize()

    @staticmethod
    def from_vector(vec, is_numerical=False, n=256):
        select_vec = deepcopy(vec[:-1])
        select_list = Select.from_vector(select_vec, is_numerical=True, n=256)

        fillet = Fillet(vec[-1][12], select_list)

        fillet.denumericalize()

        return fillet

    def to_vector(self):
        return np.array([FILLET_IDX, *[PAD_VAL]*11, self.radius, *[PAD_VAL]*(N_ARGS_SELECT + N_ARGS_CONSTRAINTS)])

class Select(object):
    # def __init__(self, select_type, no, wire_no, sub_list=[]):
    #     self.select_type = select_type
    #     self.no = no
    #     self.wire_no = wire_no
    #     self.sub_list = sub_list

    def __init__(self, select_type, no, wire_no, body_wire=None):
        self.select_type = select_type
        self.no = no
        # 对point来说：wire_no=0: start  wire_no=1: end  wire_no=2: center
        self.wire_no = wire_no
        self.body_wire = body_wire

    @staticmethod
    def from_vector(vec, is_numerical=False, n=256):
        select_list = []
        for i in vec:
            if i[-(3 + N_ARGS_CONSTRAINTS)] == SELECT_TYPE.index('Loop') or i[-(3 + N_ARGS_CONSTRAINTS)] == SELECT_TYPE.index('Wire')or i[-(3 + N_ARGS_CONSTRAINTS)] == SELECT_TYPE.index('OriginElements'):
                select_list.append(Select(int(i[-(3 + N_ARGS_CONSTRAINTS)]), int(i[-(2 + N_ARGS_CONSTRAINTS)]), int(i[-(1 + N_ARGS_CONSTRAINTS)])))
            elif i[-(3 + N_ARGS_CONSTRAINTS)] == SELECT_TYPE.index('Point') or i[-(3 + N_ARGS_CONSTRAINTS)] == SELECT_TYPE.index('ControlPoint'):
                body_wire = select_list.pop()
                select_list.append(Select(int(i[-(3 + N_ARGS_CONSTRAINTS)]), int(i[-(2 + N_ARGS_CONSTRAINTS)]), int(i[-(1 + N_ARGS_CONSTRAINTS)]), body_wire))
        return deepcopy(select_list)

    def to_vector(self, max_n_loops=6, max_len_loop=15, pad=True, is_last=False, no_shared=False, all_oriented_type=0, partially_shared=False):
        return np.array([[*[PAD_VAL]*(1 + N_ARGS - 3), self.select_type, self.no, self.wire_no, *[PAD_VAL]*N_ARGS_CONSTRAINTS]])

    def denumericalize(self, n=256):
        self.select_type = SELECT_TYPE[int(self.select_type)]
        # for i in self.sub_list:
        #     i.denumericalize()
        if self.body_wire is not None:
            self.body_wire.denumericalize()

    def numericalize(self, n=256):
        self.select_type = int(SELECT_TYPE.index(self.select_type))

class CoordSystem(object):
    def __init__(self, origin, theta, phi, gamma, y_axis=None, is_numerical=False):
        self.is_numerical = is_numerical
        # 直接在初始化中增加小数部分
        self.origin = origin
        self._theta = theta  # 0~pi
        self._phi = phi  # -pi~pi
        self._gamma = gamma  # -pi~pi
        self._y_axis = y_axis  # (theta, phi)

    def transform(self, translation, scale):
        self.origin = (self.origin + translation) * scale

    def numericalize(self, n=256):
        """NOTE: shall only be called after normalization"""
        self.origin = (self.origin + 1.0) / 2 * n
        tmp = np.array([self._theta, self._phi, self._gamma])
        self._theta, self._phi, self._gamma = (tmp / np.pi + 1.0) / 2 * n

        self.origin, _ = Get_integer_and_fraction(self.origin)
        self._theta, _ = Get_integer_and_fraction(self._theta)
        self._phi, _ = Get_integer_and_fraction(self._phi)
        self._gamma, _ = Get_integer_and_fraction(self._gamma)

    def denumericalize(self, n=256):
        self.origin = self.origin / n * 2 - 1.0
        tmp = np.array([self._theta, self._phi, self._gamma])
        self._theta, self._phi, self._gamma = (tmp / n * 2 - 1.0) * np.pi
        self.is_numerical = False

    def to_vector(self):
        return np.array([*self.origin, self._theta, self._phi, self._gamma])

    @staticmethod
    def from_vector(vec, is_numerical=False, n=256):
        origin = vec[3:]
        theta, phi, gamma = vec[:3]
        system = CoordSystem(origin, theta, phi, gamma)
        if is_numerical:
            system.denumericalize(n)
        return system

    @property
    def normal(self):
        return polar2cartesian([self._theta, self._phi])

    @property
    def x_axis(self):
        normal_3d, x_axis_3d = polar_parameterization_inverse(self._theta, self._phi, self._gamma)
        return x_axis_3d

    @property
    def y_axis(self):
        if self._y_axis is None:
            return np.cross(self.normal, self.x_axis)
        return polar2cartesian(self._y_axis)

class Sketch(object):
    def __init__(self, sketch_profile):
        self.sketch_profile = sketch_profile

    def numericalize(self, n=256):
        self.sketch_profile.numericalize(n)

    def denumericalize(self, n=256):
        self.sketch_profile.denumericalize(n)

    @staticmethod
    def from_vector(vec, is_numerical=False, n=256):
        vec = np.concatenate([vec, [EOS_VEC]])
        profile = Profile.from_vector(vec, is_numerical=is_numerical)


        res = Sketch(profile)
        if is_numerical:
            res.denumericalize(n)
        return res

    def to_vector(self, max_n_loops=6, max_len_loop=15, pad=True):
        vec = self.sketch_profile.to_vector(max_n_loops, max_len_loop, pad=False)[:-1]
        return vec

class Macro_Seq(object):
    def __init__(self, extrude_operation, bounding_size=0):
        self.bounding_size = bounding_size
        self.extrude_operation = extrude_operation

    def normalize(self, size=1.0):
        """(1)normalize the shape into unit cube (-1~1). """
        scale = size * NORM_FACTOR / np.abs(self.bounding_size)
        self.transform(0.0, scale)

    def transform(self, translation, scale):
        """linear transformation"""
        # 拉伸/旋转体
        for item in self.extrude_operation:
            item.transform(translation, scale)

    def numericalize(self, n=256):
        for item in self.extrude_operation:
            item.numericalize(n)

    @staticmethod
    def from_vector(vec, is_numerical=False, n=256):
        commands = vec[:, 0]
        operation_indices = np.where((commands == SOL_IDX) | (commands == EOS_IDX) | (commands == SELECT_IDX) |
                                     (commands == CHAMFER_IDX) | (commands == FILLET_IDX))[0].tolist()
        operation_seq = []
        i = 0
        while i < len(operation_indices) - 1:
            start, end = operation_indices[i], operation_indices[i + 1]
            if commands[end - 1] == SELECT_IDX:
                # 说明有多个选取对象，将其一并加入
                while commands[operation_indices[i + 1] - 1] == SELECT_IDX:
                    i += 1
                end = operation_indices[i + 1]

            if commands[end - 1] == MIRROR_IDX:
                operation_seq.append(Mirror.from_vector(vec[start:end], is_numerical, n))
            elif commands[end - 1] == ROTATE_IDX:
                operation_seq.append(Rotate.from_vector(vec[start:end], is_numerical, n))
            elif commands[end - 1] == CHAMFER_IDX:
                operation_seq.append(Chamfer.from_vector(vec[start:end], is_numerical, n))
            elif commands[end - 1] == FILLET_IDX:
                operation_seq.append(Fillet.from_vector(vec[start:end], is_numerical, n))
            elif commands[end - 1] == CONSTRAINT_IDX:
                operation_seq.append(Constraint.from_vector(vec[start:end], is_numerical, n))
            else:
                operation_seq.append(Sketch.from_vector(vec[start:end], is_numerical, n))
            i += 1
        cad_seq = Macro_Seq(operation_seq)
        return cad_seq

    def to_vector(self, max_n_ext=10, max_n_loops=6, max_len_loop=15, max_total_len=60, pad=False):
        vec_sequence = []

        for item in self.extrude_operation:
            vec = item.to_vector(max_n_loops, max_len_loop, pad=False)
            if vec is None:
                return None
            vec_sequence.append(vec)

        vec_sequence = np.concatenate(vec_sequence, axis=0)
        vec_sequence = np.concatenate([vec_sequence, EOS_VEC[np.newaxis]], axis=0)

        # add EOS padding
        if pad and vec_sequence.shape[0] < max_total_len:
            pad_len = max_total_len - vec_sequence.shape[0]
            vec_sequence = np.concatenate([vec_sequence, EOS_VEC[np.newaxis].repeat(pad_len, axis=0)], axis=0)
        return vec_sequence
    
class Constraint(object):
    def __init__(self, constraint_name, sketch_name, select_list, constraint_type, dimension11=None, dimension12=None, dimension21=None):
        self.constraint_name = constraint_name
        self.sketch_name = sketch_name
        self.select_list = select_list

        self.constraint_type = constraint_type

        self.dimension11 = dimension11   # 长度维度（Radius/Diameter，Semimajor axis，Semiminor axis）
        self.dimension12 = dimension12   # 长度维度（Distance、Length）
        self.dimension21 = dimension21   # 角度维度
    
    def transform(self, translation, scale):
        if self.dimension11 is not None:
            self.dimension11 = self.dimension11 * scale
        if self.dimension12 is not None:
            self.dimension12 = self.dimension12 * scale

    def numericalize(self, n=256):
        for i in self.select_list:
            i.numericalize(n)
        if self.dimension11 is not None:
            self.dimension11 = self.dimension11 * ARGS_N
            self.dimension11 = Get_integer_and_fraction(self.dimension11, n)
        if self.dimension12 is not None:
            self.dimension12 = self.dimension12 * ARGS_N
            self.dimension12 = Get_integer_and_fraction(self.dimension12, n)
        if self.dimension21 is not None:
            self.dimension21 = self.dimension21 / 2 / np.pi * ARGS_N
            # self.dimension21 = self.dimension21 / 360 * ARGS_N
            self.dimension21, _ = Get_integer_and_fraction(self.dimension21, n)

    def denumericalize(self, n=256):
        for i in self.select_list:
            i.denumericalize()
        scale = SKETCH_SCALE / (ARGS_N / 2 * NORM_FACTOR - 1)
        if self.dimension11 is not None:
            # self.dimension11 = self.dimension11 / ARGS_N
            self.dimension11 = self.dimension11 * scale
        if self.dimension12 is not None:
            # self.dimension12 = self.dimension12 / ARGS_N
            self.dimension12 = self.dimension12 * scale
        if self.dimension21 is not None:
            self.dimension21 = self.dimension21 / ARGS_N * 2 * np.pi
            # self.dimension21 = self.dimension21 / ARGS_N * 360
    
    @staticmethod
    def from_vector(vec, is_numerical=False, n=256):
        # 获得选择向量
        select_vec = deepcopy(vec[:-1])
        select_list = Select.from_vector(select_vec, is_numerical=True, n=256)

        constraint_type = CONSTRAINT_VEC_TYPE[int(vec[-1][20])]
        constraint = Constraint('', '', select_list, constraint_type)
        if vec[-1][18] != -1:
            constraint.dimension11 = vec[-1][18]
        if vec[-1][19] != -1:
            constraint.dimension12 = vec[-1][19]
        if vec[-1][17] != -1:
            constraint.dimension21 = vec[-1][17]
        constraint.denumericalize()
        return constraint

    def to_vector(self, max_n_loops=6, max_len_loop=15, pad=True):
        all_vec = None
        for select in self.select_list:
            select_vec = select.to_vector(max_n_loops, max_len_loop, pad=False, is_last=True)
            # 转np.array
            select_vec_np = np.array(select_vec)
            if all_vec is None:
                all_vec = select_vec_np
            else:
                all_vec = np.concatenate([all_vec, select_vec_np], axis=0)
        # 其他
        if self.dimension11==None and self.dimension12==None and self.dimension21==None:
            vec = np.array([np.array([CONSTRAINT_IDX, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, CONSTRAINT_VEC_TYPE.index(self.constraint_type)])])
        # Distance、Length
        elif self.dimension11 is not None and self.dimension12==None and self.dimension21==None:
            vec = np.array([np.array([CONSTRAINT_IDX, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, self.dimension11, -1, CONSTRAINT_VEC_TYPE.index(self.constraint_type)])])
        # Radius/Diameter、Semimajor axis、Semiminor axis
        elif self.dimension11==None and self.dimension12 is not None and self.dimension21==None:
            vec = np.array([np.array([CONSTRAINT_IDX, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, self.dimension12, CONSTRAINT_VEC_TYPE.index(self.constraint_type)])])
        # Angle
        elif self.dimension11==None and self.dimension12==None and self.dimension21 is not None:
            vec = np.array([np.array([CONSTRAINT_IDX, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, self.dimension21, -1, -1, CONSTRAINT_VEC_TYPE.index(self.constraint_type)])])
        return np.concatenate([all_vec, vec], axis=0)