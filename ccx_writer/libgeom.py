# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2015-2018 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/libgeom/ 包,平铺成一个模块。
#
# 原版 libgeom/__init__.py 就是把子模块星号导出到同一命名空间:
#   from bbox import *
#   from bezier_ops import *
#   from contour import stroke_to_curve
#   from cwrap import *
#   from flattering import get_flattened_paths, flat_paths, flat_path
#   from objs import *
#   from points import *
#   from shaping import intersect_paths, fuse_paths, trim_paths, excluse_paths
#   from text_on_path import set_text_on_path
#   from trafo import *
# 各子模块之间没有同名的不同定义(逐个核过),所以平铺后 libgeom.xxx 解析到的
# 对象与原版相同。下面按上述顺序分节,每节逐行对应原文件;唯一的顺序调整是
# trafo 节提到 flattering 节之前 —— flattering.get_flattened_paths 的默认参数
# trafo=NORMAL_TRAFO 在 def 时求值,平铺后 NORMAL_TRAFO 必须先定义。
#
# 子模块间的隐式相对导入(import cwrap / from points import ... 等)平铺后都是
# 同一命名空间里的名字,删掉;cwrap.xxx 的点号调用改成直接调用,逐处有注释。
#
# 范围裁剪(调用即抛 NotImplementedError,消息说清原因):
#   contour.stroke_to_curve、shaping 的四个布尔运算 —— 未移植(见各桩的说明)
#   objs.get_text_glyphs、text_on_path.set_text_on_path —— 依赖 libpango
#
# Py2 -> Py3 静默差异逐项核过:
#   - round:只有 points.is_equal_points 用到 round(x, ndigits)。_compat.py2round
#     只管 ndigits=0,这里另写 _py2round_ndigits 复现 Py2 的「十进制正确舍入 +
#     半数远离零」,理由见该函数。
#   - 除法:本模块所有 / 都是浮点语境(坐标、长度、角度、/ 2.0),保持 /。
#     少数在「整数坐标」输入下 Py2 会地板除的(bbox_trafo、div_point、
#     circle_center_by_3points),前端不调用,输入也都是浮点,保持 / 并在原处注明。
#   - round_angle_point 里的 // 是浮点地板除,Py2/Py3 语义相同,保持 //。
#   - 没有 dict 遍历、map/filter/zip、basestring/unicode、cmp/sort、xrange。
#   - check_flatness 的生成器解包、to_polar 的条件表达式优先级,Py2/Py3 相同。

import decimal
import math
from copy import deepcopy

from ccx_writer import libcairo, sk2const

# 移植版不要:from uc2 import libpango(只服务 get_text_glyphs,文字不支持)

"""
Package provides basic routines for Bezier curves.

BBOX DEFINITION:
[x0,y0,x1,y1]

RECTANGLE DEFINITION
[x,y,w,h]

PATHS DEFINITION:
[path0, path1, ...]

PATH DEFINITION:
[start_point, points, end_marker]
start_pont - [x,y]
end_marker - is closed CURVE_CLOSED = 1, if not CURVE_OPENED = 0

POINTS DEFINITION:
[point0, point1,...]
line point - [x,y]
curve point - [[x1,y1],[x2,y2],[x3,y3], marker]
marker - NODE_CUSP = 0; NODE_SMOOTH = 1; NODE_SYMMETRICAL = 2
"""


# =====================================================================
# 原 libgeom/bbox.py
# 原导入:import cwrap  -> 平铺后删掉;bbox_trafo 里的 cwrap.multiply_trafo 改直接调用
# =====================================================================

# ------------- Bbox operations -------------

def normalize_bbox(bbox):
    """Normalizes bounding box: sets minimal coords for first point and maximal
    for second point. Returns new bounding box.

    :type bbox: list
    :param bbox: bounding box

    :rtype: list
    :return: new bounding box
    """
    x0, y0, x1, y1 = bbox
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def bbox_to_rect(bbox):
    """Normalize bbox and transform it into rectangle

    :param bbox:
    :return: rectangle
    """
    x0, y0, x1, y1 = normalize_bbox(bbox)
    return [x0, y0, x1 - x0, y1 - y0]


def bbox_points(bbox):
    """Converts bounding box to list of four rectangle corners.

    :type bbox: list
    :param bbox: bounding box

    :rtype: list
    :return: four point list
    """
    x0, y0, x1, y1 = normalize_bbox(bbox)
    return [[x0, y0], [x0, y1], [x1, y0], [x1, y1]]


def bbox_middle_points(bbox):
    """Calcs middle points of bounding box edges.

    :type bbox: list
    :param bbox: bounding box

    :rtype: list
    :return: four point list
    """
    x0, y0, x1, y1 = normalize_bbox(bbox)
    mx = (x1 - x0) / 2.0 + x0
    my = (y1 - y0) / 2.0 + y0
    return [[x0, my], [mx, y1], [x1, my], [mx, y0]]


def bbox_center(bbox):
    """Calcs bounding box center.

    :type bbox: list
    :param bbox: bounding box

    :rtype: list
    :return: point
    """
    x0, y0, x1, y1 = normalize_bbox(bbox)
    mx = (x1 - x0) / 2.0 + x0
    my = (y1 - y0) / 2.0 + y0
    return [mx, my]


def enlarge_bbox(bbox, dx=0.0, dy=0.0):
    """Symmetrically enlarge bounding box.

    :type bbox: list
    :param bbox: bounding box

    :type dx: float
    :param dx: horizontal delta

    :type dy: float
    :param dy: vertical delta

    :rtype: list
    :return: new bounding box
    """
    x0, y0, x1, y1 = bbox
    return [x0 - dx / 2.0, y0 - dy / 2.0, x1 + dx / 2.0, y1 + dy / 2.0]


def bbox_trafo(bbox0, bbox1):
    """Calcs affine transformation for changing one bounding box to another.

    :type bbox0: list
    :param bbox0: initial bounding box

    :type bbox1: list
    :param bbox1: final bounding box

    :rtype: list
    :return: affine transformation matrix
    """
    x0_0, y0_0, x1_0, y1_0 = normalize_bbox(bbox0)
    x0_1, y0_1, x1_1, y1_1 = normalize_bbox(bbox1)
    w0 = x1_0 - x0_0
    h0 = y1_0 - y0_0
    w1 = x1_1 - x0_1
    h1 = y1_1 - y0_1
    # 浮点语境保持 /(Py2 下若两个 bbox 全是 int 会地板除;前端不调用本函数)
    m11 = w1 / w0
    m22 = h1 / h0
    # 原版:cwrap.multiply_trafo(...)
    trafo = multiply_trafo([1.0, 0.0, 0.0, 1.0, -x0_0, -y0_0],
                           [m11, 0.0, 0.0, m22, 0.0, 0.0])
    # 原版:return cwrap.multiply_trafo(trafo, [...])
    return multiply_trafo(trafo, [1.0, 0.0, 0.0, 1.0, x0_1, y0_1])


def bbox_for_point(point, size):
    """Calcs square bounding box for provided center and bounding box size.

    :type point: list
    :param point: bounding box center

    :type size: float
    :param size: size of square bounding box

    :rtype: list
    :return: new bounding box
    """
    x0 = point[0] - size / 2.0
    y0 = point[1] - size / 2.0
    x1 = point[0] + size / 2.0
    y1 = point[1] + size / 2.0
    return [x0, y0, x1, y1]


def is_point_in_bbox(point, bbox):
    """Checks whether is Bezier curve point inside the bounding box or not.

    :type point: list
    :param point: testing Bezier curve point

    :type bbox: list
    :param bbox: bounding box

    :rtype: boolean
    :return: boolean check result
    """
    if not len(point) == 2:
        point = point[2]
    left_cond = point[0] >= bbox[0] and point[1] >= bbox[1]
    right_cond = point[0] <= bbox[2] and point[1] <= bbox[3]
    return left_cond and right_cond


def sum_bbox(bbox1, bbox2):
    """Summarizes two bounding boxes. The result will be bounding box which
    contains both provided bboxes.

    :type bbox1: list
    :param bbox1: first bounding box

    :type bbox2: list
    :param bbox2: second bounding box

    :rtype: list
    :return: new bounding box
    """
    if not bbox1 or not bbox2:
        return bbox1 + bbox2
    x0, y0, x1, y1 = bbox1
    _x0, _y0, _x1, _y1 = bbox2
    new_x0 = min(x0, _x0, x1, _x1)
    new_x1 = max(x0, _x0, x1, _x1)
    new_y0 = min(y0, _y0, y1, _y1)
    new_y1 = max(y0, _y0, y1, _y1)
    return [new_x0, new_y0, new_x1, new_y1]


def is_bbox_in_rect(rect, bbox):
    """Checks whether is second bounding box inside the first
    bounding box or not.

    :type rect: list
    :param rect: second bounding box

    :type bbox: list
    :param bbox: first bounding box

    :rtype: boolean
    :return: boolean check result
    """
    x0, y0, x1, y1 = rect
    _x0, _y0, _x1, _y1 = bbox
    if x0 > _x0 or y0 > _y0 or x1 < _x1 or y1 < _y1:
        return False
    return True


def is_point_in_rect(point, rect):
    """Checks whether is coordinate point inside the rectangle or not.
    Rectangle is defined by bounding box.

    :type point: list
    :param point: testing coordinate point

    :type rect: list
    :param rect: bounding box

    :rtype: boolean
    :return: boolean check result
    """
    x0, y0, x1, y1 = rect
    x, y = point
    if x0 <= x <= x1 and y0 <= y <= y1:
        return True
    return False


def is_point_in_rect2(point, rect_center, rect_w, rect_h):
    """Checks whether is coordinate point inside the rectangle or not.
    Rectangle is defined by center and linear sizes.

    :type point: list
    :param point: testing coordinate point

    :type rect_center: list
    :param rect_center: point, center of rectangle

    :type rect_w: float
    :param rect_w: rectangle width

    :type rect_h: float
    :param rect_h: rectangle height

    :rtype: boolean
    :return: boolean check result
    """
    cx, cy = rect_center
    x, y = point
    if abs(x - cx) <= rect_w / 2.0 and abs(y - cy) <= rect_h / 2.0:
        return True
    return False


def bbox_size(bbox):
    """Calcs bounding box width and height.

    :type bbox: list
    :param bbox: bounding box

    :rtype: tuple
    :return: width and height
    """
    x0, y0, x1, y1 = bbox
    return abs(x1 - x0), abs(y1 - y0)


def is_bbox_overlap(bbox1, bbox2):
    """Checks whether are bounding boxes overlapped or not.

    :type bbox1: list
    :param bbox1: first bounding box

    :type bbox2: list
    :param bbox2: second bounding box

    :rtype: boolean
    :return: boolean check result
    """
    new_bbox = sum_bbox(bbox1, bbox2)
    w1, h1 = bbox_size(bbox1)
    w2, h2 = bbox_size(bbox2)
    w, h = bbox_size(new_bbox)
    return w <= w1 + w2 and h <= h1 + h2


def is_bbox_in_bbox(bbox1, bbox2):
    """Checks whether is one bounding box inside another
    bounding box or not.

    :type bbox1: list
    :param bbox1: first bounding box

    :type bbox2: list
    :param bbox2: second bounding box

    :rtype: boolean
    :return: boolean check result
    """
    new_bbox = sum_bbox(bbox1, bbox2)
    w1, h1 = bbox_size(bbox1)
    w2, h2 = bbox_size(bbox2)
    w, h = bbox_size(new_bbox)
    if w == w2 and h == h2:
        return True
    if w == w1 and h == h1:
        return True
    return False


def bbox_for_points(points):
    """Finds bounding box for provided points.

    :type points: list or tuple
    :param points: sequince of coordinate points

    :rtype: list
    :return: bounding box
    """
    xmin = xmax = points[0][0]
    ymin = ymax = points[0][1]
    for point in points:
        xmin = min(xmin, point[0])
        xmax = max(xmax, point[0])
        ymin = min(ymin, point[1])
        ymax = max(ymax, point[1])
    return [xmin, ymin, xmax, ymax]


# =====================================================================
# 原 libgeom/bezier_ops.py(Copyright (C) 2015-2018)
# 原导入:from copy import deepcopy            -> 模块头
#         from uc2 import sk2const              -> 模块头 from ccx_writer import sk2const
#         from flattering import flat_path      -> 平铺后同一命名空间
#         from points import distance, mult_point, add_points  -> 同上
#         from cwrap import get_cpath_bbox, create_cpath        -> 同上
# =====================================================================

def is_curve_point(point):
    return len(point) != 2


def bezier_base_point(point):
    return [] + point if len(point) == 2 else [] + point[2]


def get_path_length(path, tolerance=0.5):
    fpath = flat_path(path, tolerance)
    ret = 0
    start = fpath[0]
    for item in fpath[1]:
        ret += distance(start, item)
        start = item
    return ret


def get_paths_length(paths):
    return sum(get_path_length(item) for item in paths)


def get_paths_bbox(paths):
    return get_cpath_bbox(create_cpath(paths))


def split_bezier_curve(start_point, end_point, t=0.5):
    p0 = start_point[2] if len(start_point) > 2 else start_point
    p1, p2, p3 = end_point[:3]
    flag = end_point[3] if len(end_point) == 4 else sk2const.NODE_CUSP
    p0_1 = add_points(mult_point(p0, (1.0 - t)), mult_point(p1, t))
    p1_2 = add_points(mult_point(p1, (1.0 - t)), mult_point(p2, t))
    p2_3 = add_points(mult_point(p2, (1.0 - t)), mult_point(p3, t))
    p01_12 = add_points(mult_point(p0_1, (1.0 - t)), mult_point(p1_2, t))
    p12_23 = add_points(mult_point(p1_2, (1.0 - t)), mult_point(p2_3, t))
    p0112_1223 = add_points(mult_point(p01_12, (1.0 - t)),
                            mult_point(p12_23, t))
    new_point = [p0_1, p01_12, p0112_1223, flag]
    new_end_point = [p12_23, p2_3, p3, flag]
    return new_point, new_end_point


def split_bezier_line(start_point, end_point, point):
    if len(start_point) > 2:
        start_point = start_point[2]
    dist1 = distance(start_point, end_point)
    dist2 = distance(start_point, point)
    coef = dist2 / dist1
    x = coef * (end_point[0] - start_point[0]) + start_point[0]
    y = coef * (end_point[1] - start_point[1]) + start_point[1]
    return [x, y]


def reverse_path(path):
    end_marker = path[2]
    points = [path[0], ] + path[1]
    points.reverse()
    data = []
    new_points = []
    for index in range(len(points)):
        if is_curve_point(points[index]) and data:
            p0 = [] + data[1]
            p1 = [] + data[0]
            p2 = [] + points[index][2]
            new_points.append([p0, p1, p2])
            data = deepcopy(points[index])
        elif is_curve_point(points[index]) and not data:
            new_points.append([] + points[index][2])
            data = deepcopy(points[index])
        elif not is_curve_point(points[index]) and data:
            p0 = [] + data[1]
            p1 = [] + data[0]
            p2 = [] + points[index]
            new_points.append([p0, p1, p2])
            data = []
        elif not is_curve_point(points[index]) and not data:
            new_points.append([] + points[index])
    start_point = new_points[0]
    points = new_points[1:]
    return [start_point, points, end_marker]


def reverse_paths(paths):
    return [reverse_path(path) for path in paths]


# =====================================================================
# 原 libgeom/contour.py —— 只导出 stroke_to_curve,未移植
# =====================================================================

def stroke_to_curve(paths, stroke_style):
    # 移植版不要:原 contour.py 整个文件(515 行,描边转轮廓:平行曲线逼近 +
    # 连接/端点 + dash_path/fuse_paths 布尔运算)。前端里只有 svg_translators
    # 的 append_obj 在「描边是渐变/图案」(style_opts['stroke-fill'])时调它。
    # ⚠️ 原调用点包在 try/except Exception 里:本异常会被吞掉、静默走
    #   stroke-fill-color 兜底分支,输出与 Py2 不同却不报错 —— 调用方需先放行
    #   NotImplementedError。
    raise NotImplementedError(
        '渐变/图案描边转轮廓不支持:需要 libgeom.stroke_to_curve'
        '(原 libgeom/contour.py + shaping.py 布尔运算),ccx_writer 未移植')


# =====================================================================
# 原 libgeom/cwrap.py(Copyright (C) 2015-2018)
# 原导入:from uc2 import libcairo  -> 模块头 from ccx_writer import libcairo
# =====================================================================

def create_cpath(cache_paths):
    return libcairo.create_cpath(cache_paths)


def copy_cpath(cache_cpath):
    return libcairo.copy_cpath(cache_cpath)


def get_cpath_bbox(cache_cpath):
    return libcairo.get_cpath_bbox(cache_cpath)


def apply_trafo(cache_cpath, trafo, copy=False):
    return libcairo.apply_trafo(cache_cpath, trafo, copy)


def multiply_trafo(trafo1, trafo2):
    # libcairo.multiply_trafo 的乘法取自 ccx_writer._geom.multiply_trafo
    return libcairo.multiply_trafo(trafo1, trafo2)


def invert_trafo(trafo):
    return libcairo.invert_trafo(trafo)


def get_transformed_path(obj):
    if obj.cache_cpath is None:
        obj.update()
    return None if obj.cache_cpath is None \
        else libcairo.get_path_from_cpath(obj.cache_cpath)


def get_path_from_cpath(cpath):
    return libcairo.get_path_from_cpath(cpath)


# =====================================================================
# 原 libgeom/trafo.py(Copyright (C) 2015-2018)
# ⚠️ 顺序调整:本节在原 __init__ 里排最后,提到 flattering 节之前(理由见文件头)。
# 原导入:import math  -> 模块头
#         import cwrap -> 平铺后删掉;get_transformed_paths 里的
#                         cwrap.get_transformed_path 改直接调用
# =====================================================================

NORMAL_TRAFO = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def trafo_rotate(angle, cx=0.0, cy=0.0):
    m21 = math.sin(angle)
    m11 = m22 = math.cos(angle)
    m12 = -m21
    dx = cx - m11 * cx + m21 * cy
    dy = cy - m21 * cx - m11 * cy
    return [m11, m21, m12, m22, dx, dy]


def trafo_rotate_grad(grad, cx=0.0, cy=0.0):
    angle = math.pi * grad / 180.0
    return trafo_rotate(angle, cx, cy)


def _apply_trafo_to_point(point, trafo):
    x0, y0 = point
    m11, m21, m12, m22, dx, dy = trafo
    x1 = m11 * x0 + m12 * y0 + dx
    y1 = m21 * x0 + m22 * y0 + dy
    return [x1, y1]


def apply_trafo_to_point(point, trafo):
    if len(point) == 2:
        return _apply_trafo_to_point(point, trafo)
    else:
        return [_apply_trafo_to_point(point[0], trafo),
                _apply_trafo_to_point(point[1], trafo),
                _apply_trafo_to_point(point[2], trafo), point[3]]


def apply_trafo_to_points(points, trafo):
    return [apply_trafo_to_point(point, trafo) for point in points]


def apply_trafo_to_path(path, trafo):
    return [apply_trafo_to_point(path[0], trafo),
            [apply_trafo_to_point(point, trafo) for point in path[1]],
            path[2]]


def apply_trafo_to_paths(paths, trafo):
    return [apply_trafo_to_path(path, trafo) for path in paths]


def apply_trafo_to_bbox(bbox, trafo):
    p0, p1 = apply_trafo_to_points([bbox[:2], bbox[2:]], trafo)
    return p0 + p1


def get_transformed_paths(obj):
    if obj.is_curve:
        return apply_trafo_to_paths(obj.paths, obj.trafo)
    elif obj.is_text:
        return obj.get_transformed_paths()
    elif obj.cache_paths:
        return apply_trafo_to_paths(obj.cache_paths, obj.trafo)
    else:
        # 原版:return cwrap.get_transformed_path(obj)
        return get_transformed_path(obj)


# =====================================================================
# 原 libgeom/flattering.py(Copyright (C) 2015-2018)
# 原 __init__ 只导出 get_flattened_paths, flat_paths, flat_path;
# split_segment / base_point / check_flatness / flat_segment 平铺后也在本模块里,
# 与其他节无重名,无影响。
# 原导入:from copy import deepcopy                                -> 模块头
#         from points import add_points, mult_point, get_point_angle -> 同一命名空间
#         from trafo import apply_trafo_to_paths, NORMAL_TRAFO       -> 同上
# =====================================================================

# ------------- Flattering -------------

def split_segment(start_point, end_point, t=0.5):
    p0 = start_point[2] if len(start_point) > 2 else start_point
    p1, p2, p3 = end_point[:3]
    flag = end_point[3] if len(end_point) == 4 else 0
    p0_1 = add_points(mult_point(p0, (1.0 - t)), mult_point(p1, t))
    p1_2 = add_points(mult_point(p1, (1.0 - t)), mult_point(p2, t))
    p2_3 = add_points(mult_point(p2, (1.0 - t)), mult_point(p3, t))
    p01_12 = add_points(mult_point(p0_1, (1.0 - t)), mult_point(p1_2, t))
    p12_23 = add_points(mult_point(p1_2, (1.0 - t)), mult_point(p2_3, t))
    p0112_1223 = add_points(mult_point(p01_12, (1.0 - t)),
                            mult_point(p12_23, t))
    new_point = [p0_1, p01_12, p0112_1223, flag]
    new_end_point = [p12_23, p2_3, p3, flag]
    return new_point, new_end_point


def base_point(point):
    return point if len(point) == 2 else point[2]


def check_flatness(p0, p1, p2, tlr=0.5):
    p0, p1, p2 = (base_point(p) for p in (p0, p1, p2))
    if p0 == p1 or p1 == p2:
        return True
    a1 = get_point_angle(p1, p0)
    a2 = get_point_angle(p2, p1)
    return abs(a2 - a1) < tlr


def flat_segment(start_point, end_point, tlr=0.5):
    ret = []
    p0 = start_point
    p1, p2 = split_segment(start_point, end_point)
    if check_flatness(p0, p1, p2, tlr):
        ret += [base_point(p) for p in (p0, p1, p2)]
    else:
        ret += flat_segment(p0, p1, tlr)[:-1]
        ret += flat_segment(p1, p2, tlr)
    return ret


def flat_path(path, tlr=0.1):
    path = deepcopy(path)
    ret_points = []
    start = path[0]
    for point in path[1]:
        if len(point) == 2:
            ret_points.append(point)
        else:
            ret_points += flat_segment(start, point, tlr)[1:]
        start = point
    if path[2] and path[0] != ret_points[-1]:
        ret_points.append([] + path[0])
    return [path[0], ret_points, path[2]]


def flat_paths(paths, tlr=0.1):
    return [flat_path(path, tlr) for path in paths if path[1]]


def get_flattened_paths(curve_obj, trafo=NORMAL_TRAFO, tolerance=0.1):
    paths = flat_paths(curve_obj.paths, tolerance)
    paths = apply_trafo_to_paths(paths, curve_obj.trafo)
    if trafo != NORMAL_TRAFO:
        paths = apply_trafo_to_paths(paths, trafo)
    return paths


# =====================================================================
# 原 libgeom/objs.py(Copyright (C) 2015)
# 原导入:import math / from copy import deepcopy                   -> 模块头
#         from bezier_ops import split_bezier_curve, bezier_base_point -> 同一命名空间
#         from points import rotate_point                              -> 同上
#         from uc2 import libpango, libcairo, sk2const
#           -> libcairo、sk2const 在模块头;libpango 移植版不要(文字)
# =====================================================================

# ------------- Object specific routines -------------

def normalize_rect(rect):
    x, y, width, height = rect
    if width < 0:
        width = abs(width)
        x -= width
    if height < 0:
        height = abs(height)
        y -= height
    if not width:
        width = .0000000001
    if not height:
        height = .0000000001
    return [x, y, width, height]


# ------------- RECTANGLE -------------

def get_rect_paths(start, width, height, corners):
    mr = min(width, height) / 2.0
    shift = sk2const.CIRCLE_CTRL_SHIFT

    path = []
    points = []

    if corners[0] == 0.0:
        path.append([start[0], start[1]])
    else:
        radius = mr * corners[0]
        path.append([start[0] + radius, start[1]])
        points.append([
            [start[0] + radius * shift, start[1]],
            [start[0], start[1] + radius * shift],
            [start[0], start[1] + radius],
            sk2const.NODE_SMOOTH
        ])

    if corners[1] == 0.0:
        points.append([start[0], start[1] + height])
    else:
        radius = mr * corners[1]
        points.append([start[0], start[1] + height - radius])
        points.append([
            [start[0], start[1] + height - radius * shift],
            [start[0] + radius * shift, start[1] + height],
            [start[0] + radius, start[1] + height],
            sk2const.NODE_SMOOTH
        ])

    if corners[2] == 0.0:
        points.append([start[0] + width, start[1] + height])
    else:
        radius = mr * corners[2]
        points.append([start[0] + width - radius, start[1] + height])
        points.append([
            [start[0] + width - radius * shift, start[1] + height],
            [start[0] + width, start[1] + height - radius * shift],
            [start[0] + width, start[1] + height - radius],
            sk2const.NODE_SMOOTH
        ])

    if corners[3] == 0.0:
        points.append([start[0] + width, start[1]])
    else:
        radius = mr * corners[3]
        points.append([start[0] + width, start[1] + radius])
        points.append([
            [start[0] + width, start[1] + radius * shift],
            [start[0] + width - radius * shift, start[1]],
            [start[0] + width - radius, start[1]],
            sk2const.NODE_SMOOTH
        ])

    if not corners[0]:
        points.append([start[0], start[1]])
    else:
        radius = mr * corners[0]
        points.append([start[0] + radius, start[1]])

    path.append(points)
    path.append(sk2const.CURVE_CLOSED)
    return [path, ]


# ------------- CIRCLE -------------

EXTREME_ANGLES = (0.0, math.pi / 2.0, math.pi, 1.5 * math.pi, 2.0 * math.pi)
START_ANGLES = (0.0, 2.0 * math.pi)


def _get_arc_index(angle):
    ret = 0
    for index in range(4):
        if angle > EXTREME_ANGLES[index]:
            ret = index
        else:
            break
    return ret


def _split_arcs_at_point(angle):
    segments = deepcopy(sk2const.STUB_ARCS)
    index = _get_arc_index(angle)
    if angle in EXTREME_ANGLES:
        index += 1
        if angle in START_ANGLES:
            index = 0
        points = segments[index:] + segments[:index]
        start = bezier_base_point(points[-1])
        return [[start, points, sk2const.CURVE_CLOSED], ]
    else:
        points = segments[index + 1:] + segments[:index]
        seg_start = bezier_base_point(points[-1])
        seg_end = segments[index]
        t = 2.0 * (angle - EXTREME_ANGLES[index]) / math.pi
        new_point, new_end_point = split_bezier_curve(seg_start, seg_end, t)
        new_point[3] = sk2const.NODE_SMOOTH
        new_end_point[3] = sk2const.NODE_SMOOTH
        points[-1][3] = sk2const.NODE_SMOOTH
        start = bezier_base_point(new_point)
        return [[start, [new_end_point, ] + points + [new_point, ],
                 sk2const.CURVE_CLOSED], ]


def _exclude_segment_from_arcs(angle1, angle2):
    segments = deepcopy(sk2const.STUB_ARCS)

    if angle1 in EXTREME_ANGLES:
        start_index = _get_arc_index(angle1) + 1
        if angle1 in START_ANGLES:
            start_index = 0
        start_point = bezier_base_point(segments[start_index - 1])
        points = segments[start_index:] + segments[:start_index]
    else:
        start_index = _get_arc_index(angle1)
        seg_start = bezier_base_point(segments[start_index - 1])
        seg_end = segments[start_index]
        t = 2.0 * (angle1 - EXTREME_ANGLES[start_index]) / math.pi
        new_point, new_end_point = split_bezier_curve(seg_start, seg_end, t)
        new_end_point[3] = sk2const.NODE_SMOOTH
        points = segments[start_index + 1:] + segments[:start_index]
        points = [new_end_point, ] + points + [new_point, ]
        start_point = bezier_base_point(new_point)

    if angle2 in EXTREME_ANGLES and angle1 in EXTREME_ANGLES:
        end_index = _get_arc_index(angle2) + 1
        if angle2 in START_ANGLES:
            end_index = 0
        index = points.index(segments[end_index])
        points = points[:index]
    elif angle2 in EXTREME_ANGLES and angle1 not in EXTREME_ANGLES:
        end_index = _get_arc_index(angle2) + 1
        if angle2 in START_ANGLES:
            end_index = 0
        if segments[end_index] in points:
            index = points.index(segments[end_index])
        else:
            index = -1
        points = points[:index]
    elif angle2 not in EXTREME_ANGLES and angle1 in EXTREME_ANGLES:
        end_index = _get_arc_index(angle2)
        seg_start = bezier_base_point(segments[end_index - 1])
        seg_end = segments[end_index]
        t = 2.0 * (angle2 - EXTREME_ANGLES[end_index]) / math.pi
        new_point = split_bezier_curve(seg_start, seg_end, t)[0]
        index = points.index(segments[end_index])
        points = points[:index]
        points += [new_point, ]
    else:
        end_index = _get_arc_index(angle2)
        if not start_index == end_index:
            seg_start = bezier_base_point(segments[end_index - 1])
            seg_end = segments[end_index]
            t = 2.0 * (angle2 - EXTREME_ANGLES[end_index]) / math.pi
            new_point = split_bezier_curve(seg_start, seg_end, t)[0]
            if segments[end_index] in points:
                index = points.index(segments[end_index])
            else:
                index = -1
            points = points[:index]
            points += [new_point, ]
        elif angle2 > angle1:
            da = angle2 - angle1
            t = da / (math.pi / 2.0 - (angle1 - EXTREME_ANGLES[end_index]))
            seg_start = start_point
            seg_end = points[0]
            new_point = split_bezier_curve(seg_start, seg_end, t)[0]
            points = [new_point, ]
        else:
            da = angle1 - angle2
            t = 1.0 - da / (angle1 - EXTREME_ANGLES[end_index])
            seg_start = bezier_base_point(points[-2])
            seg_end = points[-1]
            points[-1] = split_bezier_curve(seg_start, seg_end, t)[0]
    return [[start_point, points, sk2const.CURVE_CLOSED], ]


def get_circle_paths(angle1, angle2, circle_type):
    if angle1 in START_ANGLES and angle2 in START_ANGLES:
        angle1 = angle2 = 0.0
    if angle1 == angle2:
        paths = _split_arcs_at_point(angle1)
        if circle_type in (sk2const.ARC_PIE_SLICE, sk2const.ARC_CHORD):
            return paths
        else:
            paths[0][2] = sk2const.CURVE_OPENED
            return paths

    paths = _exclude_segment_from_arcs(angle1, angle2)
    start_point = [] + paths[0][0]
    if circle_type == sk2const.ARC_PIE_SLICE:
        paths[0][1].append([0.5, 0.5])
        paths[0][1].append(start_point)
    elif circle_type == sk2const.ARC_CHORD:
        paths[0][1].append(start_point)
    else:
        paths[0][2] = sk2const.CURVE_OPENED
    return paths


# ------------- POLYGON -------------

def get_polygon_paths(corners_num, angle1, angle2, coef1, coef2):
    if corners_num < 3:
        corners_num = 3
    points = []

    center = [0.5, 0.5]
    corner_angle = 2.0 * math.pi / float(corners_num)
    corners_start = [0.5, 0.5 + 0.5 * coef1]
    midpoint_start = [0.5, 0.5 + 0.5 * coef2 * math.cos(corner_angle / 2.0)]

    corner_angle_shift = angle1
    midpoint_angle_shift = corner_angle / 2.0 + angle2

    for i in range(0, corners_num):
        angle = float(i) * corner_angle + corner_angle_shift
        point = rotate_point(center, corners_start, angle)
        points.append(point)

        angle = float(i) * corner_angle + midpoint_angle_shift
        point = rotate_point(center, midpoint_start, angle)
        points.append(point)

    start = points[0]
    points.append([] + start)
    path = [start, points[1:], sk2const.CURVE_CLOSED]
    return [path, ]


# ------------- TEXT -------------

_TEXT_NOT_SUPPORTED = ('文字需在上游先转曲线(如 inkscape --export-text-to-path);'
                       'ccx_writer 不带 pango')


def get_text_glyphs(text, width, text_style, markup):
    # 移植版不要:原体 return libpango.get_text_paths(text, width, text_style, markup)
    raise NotImplementedError(_TEXT_NOT_SUPPORTED)


def get_paths_from_glyph(glyph):
    # 本身不依赖 pango(只是 cpath -> paths 并滤掉空子路径),照原文移植;
    # 但它的输入只能来自 get_text_glyphs,移植版实际走不到这里。
    ret = [item for item in libcairo.get_path_from_cpath(glyph)
           if item and item[1]]
    return ret if ret else None


# =====================================================================
# 原 libgeom/points.py(Copyright (C) 2015-2018)
# 原导入:import math                           -> 模块头
#         from trafo import apply_trafo_to_point -> 同一命名空间
# =====================================================================

# ------------- Point operations -------------

def div_point(p, k):
    # 浮点语境保持 /(Py2 下 int 坐标 / int k 会地板除;前端不调用本函数)
    return [p[0] / k, p[1] / k]


def abs_point(p):
    return math.hypot(p[0], p[1])


def mult_point(p, k):
    return [p[0] * k, p[1] * k]


def normalize_point(p):
    return [p[0] / abs_point(p), p[1] / abs_point(p)]


def midpoint(p0, p1, coef=0.5):
    x = (p1[0] - p0[0]) * coef + p0[0]
    y = (p1[1] - p0[1]) * coef + p0[1]
    return [x, y]


def contra_point(p0, p1, p3=None):
    if not p3:
        return [2.0 * p1[0] - p0[0], 2.0 * p1[1] - p0[1]]
    else:
        lenght = distance(p1, p3)
        lenght1 = distance(p1, p0)
        coef = 1.0 + lenght / lenght1
        dx = coef * (p1[0] - p0[0])
        dy = coef * (p1[1] - p0[1])
        return [p0[0] + dx, p0[1] + dy]


def add_points(p1, p0):
    return [p1[0] + p0[0], p1[1] + p0[1]]


def sub_points(p1, p0):
    return [p1[0] - p0[0], p1[1] - p0[1]]


def mult_points(p0, p1):
    return p0[0] * p1[0] + p0[1] * p1[1]


def cr_points(p0, p1):
    return p0[0] * p1[1] - p0[1] * p1[0]


# 移植新增:Py2 的 round(x, ndigits)。
#
# Py2.7 builtin_round -> _Py_double_round:用 dtoa 做「十进制正确舍入」,但把
# 恰好落在两个 10**-ndigits 倍数正中间的值(2-adic 赋值 == -ndigits-1,例如
# ndigits=8 时的 k/512)按「半数远离零」处理;Py3 的 round(x, n) 在同样的
# 中点上走「半数取偶」。例:round(0.001953125, 8) Py2 得 0.00195313,
# Py3 得 0.00195312 —— is_equal_points(p0, p1, 8) 的真假就可能翻转
# (svg_utils 在每个 Z/z 闭合命令上调它,决定要不要补一个闭合点)。
#
# 做法:Decimal(x) 是 x 的精确十进制值,按 ROUND_HALF_UP(Decimal 的 HALF_UP
# 即半数远离零)量化到 10**-ndigits,再 float() —— 非中点时与 dtoa 的就近舍入
# 相同,中点时与 Py2 的手工进位相同;最后 float(str) 与 _Py_dg_strtod 都是正确
# 舍入,得到同一个 double。返回值与 Py2 一样恒为 float。
_PY2ROUND_CTX = decimal.Context(prec=1100, rounding=decimal.ROUND_HALF_UP)


def _py2round_ndigits(x, ndigits):
    # PyArg_ParseTupleAndKeywords 的 "d":入参先转 double
    x = float(x)
    # nans, infinities and zeros round to themselves
    if math.isinf(x) or math.isnan(x) or x == 0.0:
        return x
    # NDIGITS_MAX = int((DBL_MANT_DIG - DBL_MIN_EXP) * 0.30103) = 323
    # NDIGITS_MIN = -int((DBL_MAX_EXP + 1) * 0.30103) = -308
    if ndigits > 323:
        return x
    elif ndigits < -308:
        return 0.0 * x
    exp = decimal.Decimal((0, (1,), -ndigits))
    rounded = decimal.Decimal(x).quantize(exp, rounding=decimal.ROUND_HALF_UP,
                                          context=_PY2ROUND_CTX)
    return float(rounded)


def is_equal_points(p0, p1, precision=None):
    if precision is None:
        return p1[0] == p0[0] and p1[1] == p0[1]
    # 原版:round(p0[0], precision) == round(p1[0], precision),
    #       round(p0[1], precision) == round(p1[1], precision)
    x_eq = _py2round_ndigits(p0[0], precision) == \
        _py2round_ndigits(p1[0], precision)
    y_eq = _py2round_ndigits(p0[1], precision) == \
        _py2round_ndigits(p1[1], precision)
    return x_eq and y_eq


def distance(p0, p1=None):
    p1 = p1 or [0.0, 0.0]
    x0, y0 = p0
    x1, y1 = p1
    return math.sqrt(math.pow((x1 - x0), 2) + math.pow((y1 - y0), 2))


def rotate_point(center, point, angle):
    m21 = math.sin(angle)
    m11 = m22 = math.cos(angle)
    m12 = -m21
    dx = center[0] - m11 * center[0] + m21 * center[1]
    dy = center[1] - m21 * center[0] - m11 * center[1]
    trafo = [m11, m21, m12, m22, dx, dy]
    return apply_trafo_to_point(point, trafo)


def round_angle_point(center, point, angle):
    if angle:
        angle = math.radians(angle)
        point_angle = get_point_angle(point, center)
        point_angle = (point_angle + angle / 2.0) // angle * angle
        r = distance(point, center)
        # calculate point on circle
        x = r * math.cos(point_angle)
        y = r * math.sin(point_angle)
        point = add_points([x, y], center)
    return point


def get_point_radius(p, center=None):
    return distance(p, center or [0.5, 0.5])


def get_point_angle(p, center=None):
    center = center or [0.5, 0.5]
    x0, y0 = center
    x, y = p
    r = get_point_radius(p, center)
    if x >= x0 and y == y0:
        return 0.0
    elif x < x0 and y == y0:
        return math.pi
    elif x == x0 and y > y0:
        return math.pi / 2.0
    elif x == x0 and y < y0:
        return math.pi / 2.0 + math.pi
    elif x > x0 and y > y0:
        return math.acos((x - x0) / r)
    elif x < x0 and y > y0:
        return math.pi - math.acos((x0 - x) / r)
    elif x < x0 and y < y0:
        return math.pi + math.acos((x0 - x) / r)
    elif x > x0 and y < y0:
        return 2.0 * math.pi - math.acos((x - x0) / r)


def to_polar(point):
    r = distance(point)
    return r, get_point_angle(point, [0.0, 0.0]) if r else 0.0


def circle_center_by_3points(p1, p2, p3):
    # 浮点语境保持 /(Py2 下全 int 坐标会地板除;前端不调用本函数,原版只有 CGM 用)
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    if not x2 - x1 or not x3 - x2:
        return None
    ma = (y2 - y1) / (x2 - x1)
    mb = (y3 - y2) / (x3 - x2)
    if not mb - ma:
        return None
    d0 = ma * mb * (y1 - y3) + mb * (x1 + x2) - ma * (x2 + x3)
    d1 = 2 * mb - 2 * ma
    if not d1:
        return None
    x0 = d0 / d1
    if ma:
        y0 = -(x0 - (x1 + x2) / 2) / ma + (y1 + y2) / 2
    else:
        y0 = -(x0 - (x2 + x3) / 2) / mb + (y2 + y3) / 2
    return [x0, y0]


# =====================================================================
# 原 libgeom/shaping.py —— 只导出四个布尔运算,未移植
# =====================================================================

_BOOLEAN_NOT_SUPPORTED = ('路径布尔运算不支持:原 libgeom/shaping.py(依赖 cairo '
                          '光栅判点 + 交点求解),ccx_writer 未移植')


def intersect_paths(paths1, paths2):
    # 移植版不要:shaping.intersect_paths(只服务 GUI 的布尔运算菜单)
    raise NotImplementedError(_BOOLEAN_NOT_SUPPORTED)


def fuse_paths(paths1, paths2):
    # 移植版不要:shaping.fuse_paths。前端里 svg_translators.parse_clippath 在
    # <clipPath> 含多个子对象时调它合并剪裁路径 —— 这种 SVG 会在这里报错。
    raise NotImplementedError(
        '<clipPath> 含多个子对象不支持:需要 libgeom.fuse_paths 合并剪裁路径;'
        + _BOOLEAN_NOT_SUPPORTED)


def trim_paths(target_paths, source_paths):
    # 移植版不要:shaping.trim_paths(只服务 GUI 的布尔运算菜单)
    raise NotImplementedError(_BOOLEAN_NOT_SUPPORTED)


def excluse_paths(paths1, paths2):
    # 移植版不要:shaping.excluse_paths(只服务 GUI 的布尔运算菜单)
    raise NotImplementedError(_BOOLEAN_NOT_SUPPORTED)


# =====================================================================
# 原 libgeom/text_on_path.py —— 只导出 set_text_on_path,未移植
# =====================================================================

def set_text_on_path(path_obj, text_obj, data):
    # 移植版不要:text_on_path.py 整个文件(路径排字,依赖 Text 的 pango 字形布局)
    raise NotImplementedError(_TEXT_NOT_SUPPORTED)
