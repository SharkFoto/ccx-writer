# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(写出侧)
#  Copyright (C) 2019 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植与修复)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。
"""写出链路要用的几何,纯 Python,不依赖 libcairo / pycairo。

原版 `uc2.libgeom` 是 2,600 行的大包,写出侧只用到五个函数。其中四个
(`sum_bbox` / `apply_trafo_to_point(s)` / `apply_trafo_to_paths` / `distance`)
原本就是纯 Python,逐字照搬;只有 `multiply_trafo` 走 pycairo。

⚠️ **`multiply_trafo` 是这一整个移植里唯一凭公式重写的东西。**
浮点乘加的顺序会影响最低位,而我们的验收判据是与 Py2 字节一致 ——
所以它不能靠「数学上等价」交差。`tests/test_trafo_vs_cairo.py` 在
带 pycairo 的 Py2 容器里拿真 cairo 对拍,要求**逐位相等**,不是近似相等。
公式来自 cairo 的 `cairo_matrix_multiply(result, a, b)`:先 a 后 b。
"""
import math

__all__ = ['sum_bbox', 'distance', 'multiply_trafo',
           'apply_trafo_to_point', 'apply_trafo_to_points',
           'apply_trafo_to_path', 'apply_trafo_to_paths']


# --------------------------------------------------------------- 原样照搬

def sum_bbox(bbox1, bbox2):
    """两个包围盒的并集。原版 libgeom/bbox.py:172,逐字照搬。"""
    if not bbox1 or not bbox2:
        return bbox1 + bbox2
    x0, y0, x1, y1 = bbox1
    _x0, _y0, _x1, _y1 = bbox2
    new_x0 = min(x0, _x0, x1, _x1)
    new_x1 = max(x0, _x0, x1, _x1)
    new_y0 = min(y0, _y0, y1, _y1)
    new_y1 = max(y0, _y0, y1, _y1)
    return [new_x0, new_y0, new_x1, new_y1]


def distance(p0, p1=None):
    """原版 libgeom/points.py:83,逐字照搬(含 math.pow,别改成 ** —— 两者
    在 CPython 里走不同的 C 函数,极端值下末位可能不同)。"""
    p1 = p1 or [0.0, 0.0]
    x0, y0 = p0
    x1, y1 = p1
    return math.sqrt(math.pow((x1 - x0), 2) + math.pow((y1 - y0), 2))


def _apply_trafo_to_point(point, trafo):
    """原版 libgeom/trafo.py:40,逐字照搬。"""
    x0, y0 = point
    m11, m21, m12, m22, dx, dy = trafo
    x1 = m11 * x0 + m12 * y0 + dx
    y1 = m21 * x0 + m22 * y0 + dy
    return [x1, y1]


def apply_trafo_to_point(point, trafo):
    if len(point) == 2:
        return _apply_trafo_to_point(point, trafo)
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


# ------------------------------------------------------- 替掉 cairo 的那个

def multiply_trafo(trafo1, trafo2):
    """替代 `libcairo.multiply_trafo` —— 原版是 pycairo 的
    `Matrix(t1).multiply(Matrix(t2))`,即 cairo 的 matrix_multiply(r, a, b),
    语义是「先应用 a,再应用 b」。

    trafo 的分量顺序是 (m11, m21, m12, m22, dx, dy),对应 cairo 的
    (xx, yx, xy, yy, x0, y0)。乘加的书写顺序与 cairo 源码一致,
    不要「化简」—— 浮点加法不满足结合律,换顺序就可能差最低位。
    """
    a11, a21, a12, a22, adx, ady = trafo1
    b11, b21, b12, b22, bdx, bdy = trafo2
    return [
        a11 * b11 + a21 * b12,
        a11 * b21 + a21 * b22,
        a12 * b11 + a22 * b12,
        a12 * b21 + a22 * b22,
        adx * b11 + ady * b12 + bdx,
        adx * b21 + ady * b22 + bdy,
    ]
