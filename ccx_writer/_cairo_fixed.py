# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植
#  Copyright (C) 2026 SharkFoto
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。
"""纯 Python 复刻写出链路用到的那一小片 cairo(Step 5)。

为什么要逐位复刻而不是「算个包围盒就行」:包围盒 -> max_value -> coef ->
**每一个坐标**。差最低一位,整份文件的字节就全变了,Step 6 的等价性就断了。

复刻对象是 cairo **1.15.10**(CI 容器 ubuntu:18.04 里 Py2 原版用的那一版),
逐函数对照源码(scratchpad/cairo-src,出处 gitlab.freedesktop.org/cairo 的 1.15.10 tag):

  _cairo_fixed_from_double    cairo-fixed-private.h:111   魔数法,不是简单四舍五入
  _cairo_path_fixed_*         cairo-path-fixed.c          move_to 延迟生效、共线 line_to 合并、
                                                           退化段丢弃、close 后隐式 move_to
  _cairo_box_add_curve_to     cairo-rectangle.c:273       控制点落在「已累计」包围盒外才求极值
  _cairo_spline_bound         cairo-spline.c:277          导数二次方程 + 可行性剪枝
  _cairo_path_fixed_interpret cairo-path-fixed.c:810      copy_path 吐出的段
  cairo_matrix_invert         cairo-matrix.c              缩放平移特例 + 伴随矩阵

浮点表达式的书写顺序与 C 源码一致 —— 浮点加法不满足结合律,别「化简」。
(ubuntu 的 cairo 包按通用 x86-64 编译,没有 FMA 融合,C 里的 a*b+c 就是两步。)

接口刻意做成 pycairo Context 的形状(new_path / new_sub_path / move_to / line_to /
curve_to / close_path / copy_path / append_path / path_extents / set_matrix),
这样 libcairo.py 可以把 pycairo 原地换掉,调用序列一行不改。
"""
import math
import struct

PATH_MOVE_TO, PATH_LINE_TO, PATH_CURVE_TO, PATH_CLOSE_PATH = 0, 1, 2, 3

FIXED_FRAC_BITS = 8
FIXED_ONE_DOUBLE = float(1 << FIXED_FRAC_BITS)
MAGIC_NUMBER_FIXED = float(1 << (52 - FIXED_FRAC_BITS)) * 1.5
_PACK_D = struct.Struct('<d')
_UNPACK_I = struct.Struct('<i')


def fixed_from_double(d):
    """cairo-fixed-private.h:111。加魔数后取 IEEE 754 位模式的低 32 位。

    union { double d; int32_t i[2]; } u; u.d = d + MAGIC; return u.i[0];
    小端机器上 i[0] 就是低 4 个字节。舍入发生在那一次加法里(FPU 就近舍入),
    所以它**不等于** floor(d*256 + 0.5)——两者在 .5 附近会分叉。
    """
    return _UNPACK_I.unpack(_PACK_D.pack(d + MAGIC_NUMBER_FIXED)[:4])[0]


def fixed_to_double(f):
    """cairo-fixed-private.h:152。"""
    return float(f) / FIXED_ONE_DOUBLE


# ------------------------------------------------------------------ 包围盒

def _box_add_point(box, x, y):
    """cairo-box-inline.h:72。注意是 if / else if —— 照抄。"""
    if x < box[0]:
        box[0] = x
    elif x > box[2]:
        box[2] = x
    if y < box[1]:
        box[1] = y
    elif y > box[3]:
        box[3] = y


def _box_contains_point(box, x, y):
    return box[0] <= x and x <= box[2] and box[1] <= y and y <= box[3]


def _find_extremes(a, b, c, t):
    """cairo-spline.c:337 FIND_EXTREMES 宏。"""
    def add(t0):
        if 0 < t0 and t0 < 1:
            t.append(t0)

    if a == 0:
        if b != 0:
            add(-c / (2 * b))
    else:
        b2 = b * b
        delta = b2 - a * c
        if delta > 0:
            _2ab = 2 * a * b
            if _2ab >= 0:
                feasible = delta > b2 and delta < a * a + b2 + _2ab
            elif -b / a >= 1:
                feasible = delta < b2 and delta > a * a + b2 + _2ab
            else:
                feasible = delta < b2 or delta < a * a + b2 + _2ab
            if feasible:
                sqrt_delta = math.sqrt(delta)
                add((-b - sqrt_delta) / a)
                add((-b + sqrt_delta) / a)
        elif delta == 0:
            add(-b / a)


def _spline_bound(box, p0, p1, p2, p3):
    """cairo-spline.c:277。点是定点整数对。"""
    x0, y0 = fixed_to_double(p0[0]), fixed_to_double(p0[1])
    x1, y1 = fixed_to_double(p1[0]), fixed_to_double(p1[1])
    x2, y2 = fixed_to_double(p2[0]), fixed_to_double(p2[1])
    x3, y3 = fixed_to_double(p3[0]), fixed_to_double(p3[1])
    t = []

    a = -x0 + 3 * x1 - 3 * x2 + x3
    b = x0 - 2 * x1 + x2
    c = -x0 + x1
    _find_extremes(a, b, c, t)

    a = -y0 + 3 * y1 - 3 * y2 + y3
    b = y0 - 2 * y1 + y2
    c = -y0 + y1
    _find_extremes(a, b, c, t)

    _box_add_point(box, p0[0], p0[1])
    for t_1_0 in t:
        t_0_1 = 1 - t_1_0
        t_2_0 = t_1_0 * t_1_0
        t_0_2 = t_0_1 * t_0_1
        t_3_0 = t_2_0 * t_1_0
        t_2_1_3 = t_2_0 * t_0_1 * 3
        t_1_2_3 = t_1_0 * t_0_2 * 3
        t_0_3 = t_0_1 * t_0_2
        x = x0 * t_0_3 + x1 * t_1_2_3 + x2 * t_2_1_3 + x3 * t_3_0
        y = y0 * t_0_3 + y1 * t_1_2_3 + y2 * t_2_1_3 + y3 * t_3_0
        _box_add_point(box, fixed_from_double(x), fixed_from_double(y))
    _box_add_point(box, p3[0], p3[1])


def _box_add_curve_to(box, a, b, c, d):
    """cairo-rectangle.c:273。只有控制点落在**当前已累计**的盒子外才求极值。"""
    _box_add_point(box, d[0], d[1])
    if not _box_contains_point(box, b[0], b[1]) or \
            not _box_contains_point(box, c[0], c[1]):
        _spline_bound(box, a, b, c, d)


# ------------------------------------------------------------------ 定点路径

class FixedPath(object):
    """cairo_path_fixed_t 的写出链路子集。ops 存 (op, [点...]),点是定点整数对。"""

    def __init__(self):
        self.init()

    def init(self):
        """cairo-path-fixed.c:73 _cairo_path_fixed_init。"""
        self.ops = []           # (op, 点数),与 cairo_path_buf_t 的 op 数组对应
        self.points = []        # 平铺的定点点表,与 buf->points 对应
        self.current_point = (0, 0)
        self.last_move_point = (0, 0)
        self.has_current_point = False
        self.needs_move_to = True
        self.has_extents = False
        self.extents = [0, 0, 0, 0]

    def _last_op(self):
        return self.ops[-1][0] if self.ops else None

    def _penultimate_point(self):
        """cairo-path-fixed.c:372,buf->points[num_points - 2]。"""
        return self.points[-2]

    def _drop_line_to(self):
        """cairo-path-fixed.c:388,num_points--、num_ops--。"""
        assert self._last_op() == PATH_LINE_TO
        self.ops.pop()
        self.points.pop()

    def _add(self, op, pts):
        self.ops.append((op, len(pts)))
        self.points.extend(pts)

    def new_sub_path(self):
        """cairo-path-fixed.c:440。填充相关的标志位写出链路不用,略。"""
        if not self.needs_move_to:
            self.needs_move_to = True
        self.has_current_point = False

    def move_to(self, x, y):
        """cairo-path-fixed.c:400。只记当前点,op 延迟到下一次 line/curve 才落。"""
        self.new_sub_path()
        self.has_current_point = True
        self.current_point = (x, y)
        self.last_move_point = self.current_point

    def _move_to_apply(self):
        """cairo-path-fixed.c:415。"""
        if not self.needs_move_to:
            return
        self.needs_move_to = False
        cx, cy = self.current_point
        if self.has_extents:
            _box_add_point(self.extents, cx, cy)
        else:
            self.extents = [cx, cy, cx, cy]
            self.has_extents = True
        self.last_move_point = self.current_point
        self._add(PATH_MOVE_TO, [self.current_point])

    def line_to(self, x, y):
        """cairo-path-fixed.c:471。"""
        if not self.has_current_point:
            return self.move_to(x, y)
        self._move_to_apply()

        if self._last_op() != PATH_MOVE_TO:
            if x == self.current_point[0] and y == self.current_point[1]:
                return

        if self._last_op() == PATH_LINE_TO:
            p = self._penultimate_point()
            cp = self.current_point
            if p[0] == cp[0] and p[1] == cp[1]:
                self._drop_line_to()
            else:
                # cairo-slope-private.h:_cairo_slope_equal / _backwards,64 位整数乘
                pdx, pdy = cp[0] - p[0], cp[1] - p[1]
                sdx, sdy = x - cp[0], y - cp[1]
                if pdy * sdx == sdy * pdx and not (pdx * sdx + pdy * sdy < 0):
                    self._drop_line_to()

        self.current_point = (x, y)
        _box_add_point(self.extents, x, y)
        self._add(PATH_LINE_TO, [(x, y)])

    def curve_to(self, x0, y0, x1, y1, x2, y2):
        """cairo-path-fixed.c:568。"""
        cp = self.current_point
        if cp[0] == x2 and cp[1] == y2:
            if x1 == x2 and x0 == x2 and y1 == y2 and y0 == y2:
                return self.line_to(x2, y2)

        if not self.has_current_point:
            self.move_to(x0, y0)
        self._move_to_apply()

        if self._last_op() == PATH_LINE_TO:
            p = self._penultimate_point()
            if p[0] == self.current_point[0] and p[1] == self.current_point[1]:
                self._drop_line_to()

        pts = [(x0, y0), (x1, y1), (x2, y2)]
        _box_add_curve_to(self.extents, self.current_point, pts[0], pts[1], pts[2])
        self.current_point = pts[2]
        self._add(PATH_CURVE_TO, pts)

    def close_path(self):
        """cairo-path-fixed.c:647。"""
        if not self.has_current_point:
            return
        self.line_to(self.last_move_point[0], self.last_move_point[1])
        if self._last_op() == PATH_LINE_TO:
            self._drop_line_to()
        self.needs_move_to = True
        self._add(PATH_CLOSE_PATH, [])

    def interpret(self):
        """cairo-path-fixed.c:810。末尾「close 过且仍有当前点」时补一个 MOVE_TO。"""
        out, i = [], 0
        for op, n in self.ops:
            out.append((op, self.points[i:i + n]))
            i += n
        if self.needs_move_to and self.has_current_point:
            out.append((PATH_MOVE_TO, [self.current_point]))
        return out


# ------------------------------------------------------------------ Context

# ------------------------------------------------------------------ 模块面
# libcairo.py 只要把 import cairo 换成 from ccx_writer import _cairo_fixed as cairo,
# 用到的名字这里都要有。

FORMAT_RGB24 = 1
version_info = (1, 15, 10)          # 复刻对象的版本,不是 pycairo 的版本


def cairo_version_string():
    return '1.15.10 (ccx_writer 纯 Python 复刻,写出链路子集)'


class ImageSurface(object):
    """原版只为了拿一个 Context 建 1x1 的面,从不往上画。"""

    def __init__(self, fmt, width, height):
        self.fmt, self.width, self.height = fmt, width, height


class Context(object):
    """pycairo Context 的替身。矩阵恒为单位阵(原版 libcairo 每次都
    set_matrix(DIRECT_MATRIX)),所以 user<->backend 变换是恒等,略去。"""

    def __init__(self, *args):
        self._path = FixedPath()

    def set_matrix(self, matrix):
        if tuple(matrix) != (1.0, 0.0, 0.0, 1.0, 0.0, 0.0):
            raise NotImplementedError('写出链路只用单位矩阵;非单位矩阵没有复刻')

    def new_path(self):
        self._path.init()

    def new_sub_path(self):
        self._path.new_sub_path()

    def move_to(self, x, y):
        self._path.move_to(fixed_from_double(x), fixed_from_double(y))

    def line_to(self, x, y):
        self._path.line_to(fixed_from_double(x), fixed_from_double(y))

    def curve_to(self, x1, y1, x2, y2, x3, y3):
        f = fixed_from_double
        self._path.curve_to(f(x1), f(y1), f(x2), f(y2), f(x3), f(y3))

    def close_path(self):
        self._path.close_path()

    def copy_path(self):
        """cairo-path.c:_cpp_*,点按 fixed_to_double 吐出。
        返回 [(type, (x, y, ...)), ...],与遍历 pycairo Path 得到的形状相同。"""
        res = []
        for op, pts in self._path.interpret():
            coords = []
            for x, y in pts:
                coords += [fixed_to_double(x), fixed_to_double(y)]
            res.append((op, tuple(coords)))
        return res

    def append_path(self, segments):
        """cairo-path.c:_cairo_path_append_to_context,逐段调公开 API。"""
        for op, p in segments:
            if op == PATH_MOVE_TO:
                self.move_to(p[0], p[1])
            elif op == PATH_LINE_TO:
                self.line_to(p[0], p[1])
            elif op == PATH_CURVE_TO:
                self.curve_to(p[0], p[1], p[2], p[3], p[4], p[5])
            elif op == PATH_CLOSE_PATH:
                self.close_path()

    def get_tolerance(self, *args):
        raise NotImplementedError('copy_path_flat / tolerance 不在写出链路上,没有复刻')

    set_tolerance = copy_path_flat = get_tolerance

    def path_extents(self):
        """cairo-gstate.c:868。单位矩阵下 backend_to_user_rectangle 是空操作。"""
        path = self._path
        if not path.has_extents:
            return (0.0, 0.0, 0.0, 0.0)
        b = path.extents
        return (fixed_to_double(b[0]), fixed_to_double(b[1]),
                fixed_to_double(b[2]), fixed_to_double(b[3]))


# ------------------------------------------------------------------ Matrix

class Matrix(object):
    """pycairo Matrix 的替身,只实现写出链路用到的:构造、invert、multiply、分量读取。"""

    def __init__(self, xx=1.0, yx=0.0, xy=0.0, yy=1.0, x0=0.0, y0=0.0):
        # pycairo 的构造按 "dddddd" 解析,int 入参会变成 double。libcairo 的
        # get_matrix_from_trafo -> get_trafo 靠这一步把 [1, 0, 0, 1, 0, 0] 这类
        # 整数 trafo 变成浮点 —— 前端对象树比较里 int 与 float 算不一致,必须照做。
        self.xx, self.yx, self.xy, self.yy = float(xx), float(yx), float(xy), float(yy)
        self.x0, self.y0 = float(x0), float(y0)

    def __iter__(self):
        return iter((self.xx, self.yx, self.xy, self.yy, self.x0, self.y0))

    def __getitem__(self, i):
        return tuple(self)[i]

    def invert(self):
        """cairo-matrix.c:cairo_matrix_invert,逐行照抄。"""
        if self.xy == 0. and self.yx == 0.:
            self.x0 = -self.x0
            self.y0 = -self.y0
            if self.xx != 1.:
                if self.xx == 0.:
                    raise ValueError('invalid matrix (not invertible)')
                self.xx = 1. / self.xx
                self.x0 *= self.xx
            if self.yy != 1.:
                if self.yy == 0.:
                    raise ValueError('invalid matrix (not invertible)')
                self.yy = 1. / self.yy
                self.y0 *= self.yy
            return
        a, b, c, d = self.xx, self.yx, self.xy, self.yy
        det = a * d - b * c
        if math.isinf(det) or math.isnan(det) or det == 0:
            raise ValueError('invalid matrix (not invertible)')
        tx, ty = self.x0, self.y0
        # _cairo_matrix_compute_adjoint:init(d, -b, -c, a, c*ty - d*tx, b*tx - a*ty)
        self.xx, self.yx, self.xy, self.yy = d, -b, -c, a
        self.x0, self.y0 = c * ty - d * tx, b * tx - a * ty
        scalar = 1 / det
        self.xx *= scalar
        self.yx *= scalar
        self.xy *= scalar
        self.yy *= scalar
        self.x0 *= scalar
        self.y0 *= scalar

    def multiply(self, other):
        """cairo-matrix.c:cairo_matrix_multiply(r, a=self, b=other),先 a 后 b。"""
        a, b = self, other
        return Matrix(a.xx * b.xx + a.yx * b.xy,
                      a.xx * b.yx + a.yx * b.yy,
                      a.xy * b.xx + a.yy * b.xy,
                      a.xy * b.yx + a.yy * b.yy,
                      a.x0 * b.xx + a.y0 * b.xy + b.x0,
                      a.x0 * b.yx + a.y0 * b.yy + b.y0)
