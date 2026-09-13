# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2011 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/libcairo/__init__.py + uc2/libcairo/_libcairo.c,逐行对应移植。
#
# 为什么不能直接用 pycairo 的 Path:
#   原版 _libcairo.apply_trafo 是 C 里**原地改** cairo_path_t 的 double,
#   pycairo 的 Path 在 Python 里不可改。所以这里用 CPath 承载「copy_path 抽出来的
#   double 段列表」,凡是原版把 pycairo Path 交给 C 扩展或 cairo 的地方,都按下面
#   CI 探针(tests/probe_libcairo.py,Py2 + 真 cairo 1.15.10)测得的结论改写:
#
#   - create_cpath:照原版的 pycairo 调用序列建路径,再 copy_path 抽段。
#     (抽出来的坐标落在 1/256 网格上,是 cairo 24.8 定点化的结果,由真 cairo 完成)
#   - apply_trafo:在抽出来的 double 上按 m11*x + m12*y + dx 顺序乘加,原地改。
#     不经过定点化 —— 与 _libcairo.c:cairo_ApplyTrafoToPath 逐位一致(0/400 差)。
#   - get_cpath_bbox / copy_cpath / get_flattened_cpath:原版 CTX.append_path(path),
#     cairo 的 _cairo_path_append_to_context 就是逐段调 cairo_move_to / line_to /
#     curve_to / close_path;这里按段同构重放(_append_path)。path_extents 继续调
#     pycairo —— 它是贝塞尔紧包围盒且落在 1/256 网格上,**不要自己算**。
#   - get_path_from_cpath:按 _libcairo.c:cairo_GetPDPathFromPath 同构组装(0/400 差)。
#   - invert_trafo / get_trafo_from_matrix:继续用 pycairo.Matrix(.xx .yx .xy .yy .x0 .y0)。
#   - multiply_trafo:乘法取 ccx_writer._geom.multiply_trafo(已在真 pycairo 上对拍
#     2000 组零位差)。
#
# 导入差异:
#   from cStringIO import StringIO   -> 移植版不要(只服务 image_to_surface_n,位图)
#   from uc2 import uc2const         -> 移植版不要(只服务 image_to_surface,位图)
#   import _libcairo                 -> 下面的 _libcairo 类,C 扩展的 Python 同构版
#
# Py2 -> Py3 静默差异逐项核过:
#   - 没有 round / 整数除法 / dict 遍历 / map-filter-zip / basestring / cmp。
#   - reverse_trafo 里的 1.0 / m 是浮点语境,保持 /。
#   - pycairo Py3 遍历 Path 得到的段类型可能是 IntEnum(PathDataType),抽段时统一 int()。

# Step 5:把 pycairo 换成纯 Python 复刻 _cairo_fixed。
# 这一行就是 Step 5 的全部接线 —— _cairo_fixed 暴露了与 pycairo 相同的模块面
# (ImageSurface / FORMAT_RGB24 / Context / Matrix / PATH_* / version_info)。
# 逐位一致性由 tests/probe_cairo_fixed_py3.py 对 cairo 1.15.10 的标准答案、
# 以及端到端字节比对共同保证;换回 pycairo 只需改回 `import cairo`。
from ccx_writer import _cairo_fixed as cairo

from ccx_writer import _geom

# 移植版不要:from cStringIO import StringIO(只服务 image_to_surface_n,位图)
# 移植版不要:from uc2 import uc2const(只服务 image_to_surface,位图)

SURFACE = cairo.ImageSurface(cairo.FORMAT_RGB24, 1, 1)
CTX = cairo.Context(SURFACE)
DIRECT_MATRIX = cairo.Matrix()

# cairo_path_data_type_t,与 _libcairo.c 里 switch 的四个 case 对应
CAIRO_PATH_MOVE_TO = int(cairo.PATH_MOVE_TO)
CAIRO_PATH_LINE_TO = int(cairo.PATH_LINE_TO)
CAIRO_PATH_CURVE_TO = int(cairo.PATH_CURVE_TO)
CAIRO_PATH_CLOSE_PATH = int(cairo.PATH_CLOSE_PATH)


class CPath(object):
    """pycairo Path 的替身:承载 copy_path 抽出来的 double 段。

    data 是 [[type, [x, y, ...]], ...]:
      MOVE_TO / LINE_TO  -> [x, y]
      CURVE_TO           -> [x1, y1, x2, y2, x3, y3]
      CLOSE_PATH         -> []
    对应 cairo_path_t 的 data[] 数组(header + 点),可原地改写(apply_trafo 需要)。
    遍历得到 (type, (x, y, ...)),与遍历 pycairo Path 的形状相同。
    """

    def __init__(self, data):
        self.data = data

    def __iter__(self):
        for kind, points in self.data:
            yield kind, tuple(points)


def _cpath_from_cairo(cairo_path):
    """pycairo Path(copy_path / copy_path_flat 的返回值)-> CPath,double 原样。"""
    return CPath([[int(kind), list(points)] for kind, points in cairo_path])


def _append_path(ctx, cpath):
    """原版 ctx.append_path(cairo_path) 的同构重放。

    cairo 1.15.10 的 cairo_append_path -> _cairo_default_context_append_path ->
    _cairo_path_append_to_context:逐段调用公开 API cairo_move_to / cairo_line_to /
    cairo_curve_to / cairo_close_path。这里走同样的 pycairo 调用,传原样的 double。
    """
    for kind, points in cpath.data:
        if kind == CAIRO_PATH_MOVE_TO:
            ctx.move_to(points[0], points[1])
        elif kind == CAIRO_PATH_LINE_TO:
            ctx.line_to(points[0], points[1])
        elif kind == CAIRO_PATH_CURVE_TO:
            ctx.curve_to(points[0], points[1], points[2], points[3],
                         points[4], points[5])
        elif kind == CAIRO_PATH_CLOSE_PATH:
            ctx.close_path()


class _libcairo(object):
    """原 C 扩展 uc2/libcairo/_libcairo.c 的 Python 同构版(只要前端用到的三个)。

    做成类当命名空间,是为了让下面的调用点保持原文 `_libcairo.xxx(...)` 不变。
    移植版不要:draw_rect(cairo_DrawRectangle,只服务 GUI 渲染)
    移植版不要:get_pixel(cairo_GetSurfaceFirstPixel,只服务 shaping.py 光栅判点)
    移植版不要:draw_rgb_image / draw_rgba_image(位图)
    """

    @staticmethod
    def get_path_from_cpath(pypath):
        """_libcairo.c:cairo_GetPDPathFromPath,逐行同构。

        PyList_New(3) 建出的是三个 NULL 槽,这里用 None 表示 NULL。
        """
        path_counter = 0
        path = pypath.data

        pd_paths = []
        pd_path = [None, None, None]
        pd_points = []

        for data in path:
            kind, point = data
            if kind == CAIRO_PATH_MOVE_TO:
                if path_counter > 0:
                    pd_path[1] = pd_points
                    pd_paths.append(pd_path)

                pd_path = [None, None, None]
                pd_points = []

                pd_point = []
                x0 = point[0]
                y0 = point[1]
                pd_point.append(x0)
                pd_point.append(y0)
                pd_path[0] = pd_point
                pd_path[2] = 0
                path_counter += 1

            elif kind == CAIRO_PATH_LINE_TO:
                pd_point = []
                x0 = point[0]
                y0 = point[1]
                pd_point.append(x0)
                pd_point.append(y0)
                pd_points.append(pd_point)

            elif kind == CAIRO_PATH_CURVE_TO:
                pd_point = []

                pd_subpoint = []
                x0 = point[0]
                y0 = point[1]
                pd_subpoint.append(x0)
                pd_subpoint.append(y0)
                pd_point.append(pd_subpoint)

                pd_subpoint = []
                x1 = point[2]
                y1 = point[3]
                pd_subpoint.append(x1)
                pd_subpoint.append(y1)
                pd_point.append(pd_subpoint)

                pd_subpoint = []
                x2 = point[4]
                y2 = point[5]
                pd_subpoint.append(x2)
                pd_subpoint.append(y2)
                pd_point.append(pd_subpoint)

                pd_point.append(0)
                pd_points.append(pd_point)

            elif kind == CAIRO_PATH_CLOSE_PATH:
                pd_path[2] = 1

        pd_path[1] = pd_points
        pd_paths.append(pd_path)

        return pd_paths

    @staticmethod
    def get_trafo(py_matrix):
        """_libcairo.c:cairo_ConvertMatrixToTrafo。"""
        m11 = py_matrix.xx
        m21 = py_matrix.yx
        m12 = py_matrix.xy
        m22 = py_matrix.yy
        dx = py_matrix.x0
        dy = py_matrix.y0

        return [m11, m21, m12, m22, dx, dy]

    @staticmethod
    def apply_trafo(pypath, m11, m21, m12, m22, dx, dy):
        """_libcairo.c:cairo_ApplyTrafoToPath,原地改 double,乘加顺序照抄。

        C 里 PyArg_ParseTuple 的 "d" 把六个系数转成 double,这里用 float() 对应。
        """
        m11 = float(m11)
        m21 = float(m21)
        m12 = float(m12)
        m22 = float(m22)
        dx = float(dx)
        dy = float(dy)

        path = pypath.data

        for data in path:
            kind, point = data
            if kind == CAIRO_PATH_MOVE_TO:
                x = point[0]
                y = point[1]
                point[0] = m11 * x + m12 * y + dx
                point[1] = m21 * x + m22 * y + dy
            elif kind == CAIRO_PATH_LINE_TO:
                x = point[0]
                y = point[1]
                point[0] = m11 * x + m12 * y + dx
                point[1] = m21 * x + m22 * y + dy
            elif kind == CAIRO_PATH_CURVE_TO:
                x = point[0]
                y = point[1]
                point[0] = m11 * x + m12 * y + dx
                point[1] = m21 * x + m22 * y + dy

                x = point[2]
                y = point[3]
                point[2] = m11 * x + m12 * y + dx
                point[3] = m21 * x + m22 * y + dy

                x = point[4]
                y = point[5]
                point[4] = m11 * x + m12 * y + dx
                point[5] = m21 * x + m22 * y + dy
            elif kind == CAIRO_PATH_CLOSE_PATH:
                pass

        return None


def get_version():
    v0, v1, v2 = cairo.version_info
    return cairo.cairo_version_string(), '%d.%d.%d' % (v0, v1, v2)


def create_cpath(paths, cmatrix=None):
    CTX.set_matrix(DIRECT_MATRIX)
    CTX.new_path()
    for path in paths:
        CTX.new_sub_path()
        start_point = path[0]
        points = path[1]
        end = path[2]
        CTX.move_to(*start_point)

        for point in points:
            if len(point) == 2:
                CTX.line_to(*point)
            else:
                p1, p2, p3 = point[:-1]
                CTX.curve_to(*(p1 + p2 + p3))
        if end:
            CTX.close_path()

    # 原版:cairo_path = CTX.copy_path()(pycairo Path);移植版抽成可原地改的 CPath
    cairo_path = _cpath_from_cairo(CTX.copy_path())
    if cmatrix is not None:
        cairo_path = apply_cmatrix(cairo_path, cmatrix)
    return cairo_path


def get_path_from_cpath(cairo_path):
    return _libcairo.get_path_from_cpath(cairo_path)


def get_flattened_cpath(cairo_path, tolerance=0.1):
    CTX.set_matrix(DIRECT_MATRIX)
    tlr = CTX.get_tolerance()
    CTX.set_tolerance(tolerance)
    CTX.new_path()
    # 原版:CTX.append_path(cairo_path)
    _append_path(CTX, cairo_path)
    # 原版:result = CTX.copy_path_flat()
    result = _cpath_from_cairo(CTX.copy_path_flat())
    CTX.set_tolerance(tlr)
    return result


def apply_cmatrix(cairo_path, cmatrix):
    trafo = get_trafo_from_matrix(cmatrix)
    return apply_trafo(cairo_path, trafo)


def copy_cpath(cairo_path):
    CTX.set_matrix(DIRECT_MATRIX)
    CTX.new_path()
    # 原版:CTX.append_path(cairo_path)
    # 注意这不是深拷贝:重放 + copy_path 会把 apply_trafo 之后的 double 重新
    # 定点化到 1/256 网格,原版就是这样,照做。
    _append_path(CTX, cairo_path)
    # 原版:return CTX.copy_path()
    return _cpath_from_cairo(CTX.copy_path())


def apply_trafo(cairo_path, trafo, copy=False):
    if copy:
        cairo_path = copy_cpath(cairo_path)
    m11, m21, m12, m22, dx, dy = trafo
    _libcairo.apply_trafo(cairo_path, m11, m21, m12, m22, dx, dy)
    return cairo_path


def multiply_trafo(trafo1, trafo2):
    matrix1 = get_matrix_from_trafo(trafo1)
    matrix2 = get_matrix_from_trafo(trafo2)
    # 原版:matrix = matrix1.multiply(matrix2)
    #       return _libcairo.get_trafo(matrix)
    # 移植版:乘法取 _geom.multiply_trafo(cairo_matrix_multiply 的纯 Python 版,
    # 已在真 pycairo 上对拍零位差)。两个 Matrix 仍照原版构造 —— 它负责把
    # 分量按 "d" 转成 double(int 入参在原版返回里也是 float),再原样读回。
    return _geom.multiply_trafo(_libcairo.get_trafo(matrix1),
                                _libcairo.get_trafo(matrix2))


def normalize_bbox(bbox):
    x0, y0, x1, y1 = bbox
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def get_cpath_bbox(cpath):
    CTX.set_matrix(DIRECT_MATRIX)
    CTX.new_path()
    # 原版:CTX.append_path(cpath)
    _append_path(CTX, cpath)
    return normalize_bbox(CTX.path_extents())


# 移植版不要:_get_trafo(解析 str(cairo.Matrix) 的字符串,只服务 reverse_matrix;
#   uc2 里无调用方,GUI 遗留;且依赖 pycairo 的 repr 格式,Py3 版格式不同)


def get_trafo_from_matrix(cmatrix):
    return _libcairo.get_trafo(cmatrix)


def reverse_trafo(trafo):
    m11, m21, m12, m22, dx, dy = trafo
    if m11:
        m11 = 1.0 / m11
    if m12:
        m12 = 1.0 / m12
    if m21:
        m21 = 1.0 / m21
    if m22:
        m22 = 1.0 / m22
    dx = -dx
    dy = -dy
    return [m11, m21, m12, m22, dx, dy]


def get_matrix_from_trafo(trafo):
    m11, m21, m12, m22, dx, dy = trafo
    return cairo.Matrix(m11, m21, m12, m22, dx, dy)


# 移植版不要:reverse_matrix(依赖上面删掉的 _get_trafo;uc2 里无调用方,GUI 遗留)


def invert_trafo(trafo):
    cmatrix = get_matrix_from_trafo(trafo)
    cmatrix.invert()
    return get_trafo_from_matrix(cmatrix)


def apply_trafo_to_point(point, trafo):
    x0, y0 = point
    m11, m21, m12, m22, dx, dy = trafo
    x1 = m11 * x0 + m12 * y0 + dx
    y1 = m21 * x0 + m22 * y0 + dy
    return [x1, y1]


def apply_trafo_to_bbox(bbox, trafo):
    x0, y0, x1, y1 = bbox
    start = apply_trafo_to_point([x0, y0], trafo)
    end = apply_trafo_to_point([x1, y1], trafo)
    return start + end


def convert_bbox_to_cpath(bbox):
    x0, y0, x1, y1 = bbox
    CTX.set_matrix(DIRECT_MATRIX)
    CTX.new_path()
    CTX.move_to(x0, y0)
    CTX.line_to(x1, y0)
    CTX.line_to(x1, y1)
    CTX.line_to(x0, y1)
    CTX.line_to(x0, y0)
    CTX.close_path()
    # 原版:return CTX.copy_path()
    return _cpath_from_cairo(CTX.copy_path())


_RASTER_NOT_SUPPORTED = ('光栅判点不支持:只服务布尔运算(原 libgeom/shaping.py),'
                         'ccx_writer 未移植')
_IMAGE_NOT_SUPPORTED = '位图不支持:CMX v1 写出器不写位图'


def get_surface_pixel(surface):
    # 移植版不要:原体 return _libcairo.get_pixel(surface)(C 读 surface 首像素)
    raise NotImplementedError(_RASTER_NOT_SUPPORTED)


def check_surface_whiteness(surface):
    # 移植版不要:原体 return _libcairo.get_pixel(surface) == [255, 255, 255]
    raise NotImplementedError(_RASTER_NOT_SUPPORTED)


def image_to_surface_n(image):
    # 移植版不要:原体用 cStringIO + PIL 存 PNG 再 create_from_png(位图)
    raise NotImplementedError(_IMAGE_NOT_SUPPORTED)


def image_to_surface(image):
    # 移植版不要:原体用 _libcairo.draw_rgb(a)_image 把 PIL 像素拷进 surface(位图)
    raise NotImplementedError(_IMAGE_NOT_SUPPORTED)
