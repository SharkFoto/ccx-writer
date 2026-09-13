# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2016 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/formats/svg/svg_utils.py,逐行对应移植。
#
# 与原版的差异:
#   - 导入:uc2 / uc2.formats.svg / uc2.formats.xml_.xml_model / uc2.libgeom
#     -> ccx_writer 下的绝对导入。
#   - get_svg_trafo 里的 `exec code`:Py3 没有 exec 语句,也不能用 exec() 改函数局部
#     变量。换成文件末尾的 _py2_exec_trafo —— 按 Py2.7 tokenizer/parser/parsenumber
#     的规则把 'tr=trafo_xxx(...)' 这一小段 Python 解释执行(数字字面量含八进制
#     '010'=8、'08' 语法错、'1L'、'.5'、'1.e5';一元/二元 + - * /;调用;元组)。
#     详见该段的注释。
#   - float(属性值) -> py2float(...);属性值 .strip() / .lstrip() -> 显式传
#     _PY2_STR_WHITESPACE。理由:Py2 原版的 SVG 属性值和文本节点是 utf-8 **字节串**
#     (generic_filters.AbstractXMLLoader.startElement / characters 里 encode 过),
#     float(str) 与 str.strip() 都是 ASCII 语义;Py3 的 str 版本还认下划线分组
#     ('1_0')、全角/各国数字、U+00A0/U+3000 等 Unicode 空白。
#   - 只服务「保存 SVG」(SK2_to_SVG_Translator)的 create_rect / translate_style_dict /
#     point_to_str / translate_paths_to_d 删掉,原处留注释。
#
# Py2 -> Py3 静默差异逐项核过:
#   - round:保留下来的函数里没有(point_to_str 里的 round 随函数删掉);
#     libgeom.is_equal_points 内部的 round(x, 8) 归 libgeom 处理。
#   - 除法:全部是浮点语境(rx / ry、l / 2.0、2.0 * k / l、x / 100.0),保持 /。
#   - re:只有 re.sub('  *', ' ', ...) —— 字面空格,不涉及 \d \w \s 的 ASCII 语义。
#   - map / filter / zip / dict 视图 / basestring / unicode / long / cmp / has_key:没有。
#   - str(float):保留下来的函数里没有 float -> str(create_rect 随函数删掉)。
#   - dict 顺序:parse_svg_stops 的 style 只按键取值,不遍历。

import logging
import math
import re
from copy import deepcopy

from ccx_writer import uc2const, libgeom, cms, sk2const
from ccx_writer import svg_colors
from ccx_writer.xml_model import XMLObject, XmlContentText
from ccx_writer.libgeom import add_points, sub_points, mult_point

PATH_STUB = [[], [], sk2const.CURVE_OPENED]
F13 = 1.0 / 3.0
F23 = 2.0 / 3.0
LOG = logging.getLogger(__name__)

# 移植新增:Py2 字节串 str.strip() 剥的空白(C 的 isspace,C locale)
_PY2_STR_WHITESPACE = ' \t\n\r\x0b\x0c'

# 移植新增:Py2 的 float(字节串) 不认、Py3 的 float(str) 却认的字符 ——
# 下划线(PEP 515)、U+001C..U+001F(Py3 视作空白)、一切非 ASCII(全角/各国数字、
# Unicode 空白;在 Py2 里它们是 >= 0x80 的 UTF-8 字节,必然 ValueError)。
_PY2_FLOAT_REJECT = re.compile(r'[_\x1c-\x1f]|[^\x00-\x7f]')


def py2float(val):
    """移植新增:Py2 的 float(utf-8 字节串)。

    ASCII 范围内 Py2 与 Py3 的 float() 完全一致(同一套 dtoa,首尾剥 ASCII 空白,
    认 inf / infinity / nan);差别只在 _PY2_FLOAT_REJECT 那几类字符,遇到就抛
    ValueError —— 与 Py2 原版在同一处抛同一类异常。非 str(int / float)原样交给 float()。
    """
    if isinstance(val, str) and _PY2_FLOAT_REJECT.search(val):
        raise ValueError('could not convert string to float: %r' % val)
    return float(val)


def check_svg_attr(svg_obj, attr, value=None):
    if value is None: return attr in svg_obj.attrs
    if attr in svg_obj.attrs and svg_obj.attrs[attr] == value:
        return True
    return False


def trafo_skewX(grad=0.0):
    angle = math.pi * grad / 180.0
    return [1.0, 0.0, math.tan(angle), 1.0, 0.0, 0.0]


def trafo_skewY(grad=0.0):
    angle = math.pi * grad / 180.0
    return [1.0, math.tan(angle), 0.0, 1.0, 0.0, 0.0]


def trafo_rotate(grad, cx=0.0, cy=0.0):
    return libgeom.trafo_rotate_grad(grad, cx, cy)


def trafo_scale(m11, m22=None):
    if m22 is None: m22 = m11
    return [m11, 0.0, 0.0, m22, 0.0, 0.0]


def trafo_translate(dx, dy=0.0):
    LOG.debug('translate %s', [1.0, 0.0, 0.0, 1.0, dx, dy])
    return [1.0, 0.0, 0.0, 1.0, dx, dy]


def trafo_matrix(m11, m21, m12, m22, dx, dy):
    return [m11, m21, m12, m22, dx, dy]


def get_svg_trafo(strafo):
    trafo = [] + libgeom.NORMAL_TRAFO
    trs = strafo.split(') ')
    trs.reverse()
    for tr in trs:
        tr += ')'
        tr = tr.replace(', ', ',').replace(' ', ',').replace('))', ')')
        try:
            # 原版:
            #     code = compile('tr=trafo_' + tr, '<string>', 'exec')
            #     exec code
            # Py2 的函数体里有裸 exec 时,exec 会改写局部变量 tr;失败(SyntaxError /
            # NameError / TypeError ...)被下面的 except: 吞掉,tr 保持字符串。
            tr = _py2_exec_trafo('tr=trafo_' + tr)
        except:
            continue
        # 移植补:原版 multiply_trafo 先做 cairo.Matrix(*tr),pycairo 对非实数抛
        # TypeError(在 try 之外,向上抛);_geom.multiply_trafo 是纯 Python,
        # 会让 complex('1j' 字面量)悄悄算过去,所以在这里把 pycairo 的检查补上。
        _py2_cairo_matrix_check(tr)
        trafo = libgeom.multiply_trafo(trafo, tr)
    return trafo


def get_svg_level_trafo(svg_obj, trafo):
    tr = [] + libgeom.NORMAL_TRAFO
    if svg_obj.tag == 'use':
        if 'x' in svg_obj.attrs:
            tr[4] += py2float(svg_obj.attrs['x'])
        if 'y' in svg_obj.attrs:
            tr[5] += py2float(svg_obj.attrs['y'])
    if 'transform' in svg_obj.attrs:
        tr1 = get_svg_trafo(svg_obj.attrs['transform'])
        tr = libgeom.multiply_trafo(tr, tr1)
    tr = libgeom.multiply_trafo(tr, trafo)
    return tr


def parse_svg_points(spoints):
    points = []
    spoints = re.sub('  *', ' ', spoints)
    spoints = spoints.replace('-', ',-').replace('e,-', 'e-')
    spoints = spoints.replace(', ,', ',').replace(' ', ',')
    pairs = spoints.replace(',,', ',').split(',')
    if not pairs[0]: pairs = pairs[1:]
    pairs = [pairs[i:i + 2] for i in range(0, len(pairs), 2)]
    for pair in pairs:
        try:
            points.append([py2float(pair[0]), py2float(pair[1])])
        except:
            continue
    return points


def parse_svg_coords(scoords):
    # 原版 .strip():Py2 字节串语义,只剥 ASCII 空白
    scoords = scoords.strip(_PY2_STR_WHITESPACE).replace(',', ' ').replace('-', ' -')
    scoords = scoords.replace('e -', 'e-').strip(_PY2_STR_WHITESPACE)
    scoords = re.sub('  *', ' ', scoords)
    if scoords:
        processed_items = []
        for item in scoords.split(' '):
            count = item.count('.')
            if count > 1:
                subitems = item.rsplit('.', count - 1)
                processed_items.append(subitems[0])
                processed_items += ['.' + s for s in subitems[1:]]
            else:
                processed_items.append(item)
        return [py2float(item) for item in processed_items]
    return None


def parse_svg_color(sclr, alpha=1.0, current_color=''):
    clr = deepcopy(svg_colors.SVG_COLORS['black'])
    clr[2] = alpha
    if sclr == 'currentColor' and current_color:
        sclr = current_color
    if sclr[0] == '#':
        if 'icc-color' in sclr:
            vals = sclr.split('icc-color(')[1].replace(')', '').split(',')
            if len(vals) == 5:
                color_vals = []
                try:
                    color_vals = [py2float(x) for x in vals[1:]]
                except:
                    pass
                if color_vals and len(color_vals) == 4:
                    return [uc2const.COLOR_CMYK, color_vals, alpha, '']
        elif 'device-cmyk' in sclr:
            vals = sclr.split('device-cmyk(')[1].replace(')', '').split(',')
            if len(vals) in (3, 4):
                color_vals = []
                try:
                    color_vals = [py2float(x) for x in vals[1:]]
                except:
                    pass
                if color_vals and len(color_vals) in (3, 4):
                    if len(color_vals) == 3: color_vals.append(0.0)
                    return [uc2const.COLOR_CMYK, color_vals, alpha, '']

        sclr = sclr.split(' ')[0]
        try:
            vals = cms.hexcolor_to_rgb(sclr)
            clr = [uc2const.COLOR_RGB, vals, alpha, '']
        except:
            pass
    elif sclr[:4] == 'rgb(':
        vals = sclr[4:].split(')')[0].split(',')
        if len(vals) == 3:
            decvals = []
            for val in vals:
                # 原版 val.strip():Py2 字节串语义,只剥 ASCII 空白
                val = val.strip(_PY2_STR_WHITESPACE)
                if '%' in val:
                    decval = py2float(val.replace('%', ''))
                    if decval > 100.0: decval = 100.0
                    if decval < 0.0: decval = 0.0
                    decval = decval / 100.0
                else:
                    decval = py2float(val)
                    if decval > 255.0: decval = 255.0
                    if decval < 0.0: decval = 0.0
                    decval = decval / 255.0
                decvals.append(decval)
            clr = [uc2const.COLOR_RGB, decvals, alpha, '']
    else:
        if sclr in svg_colors.SVG_COLORS:
            clr = deepcopy(svg_colors.SVG_COLORS[sclr])
            clr[2] = alpha
    return clr


def base_point(point):
    if len(point) == 2: return [] + point
    return [] + point[-1]


def parse_svg_path_cmds(pathcmds):
    index = 0
    last = None
    last_index = 0
    cmds = []
    pathcmds = re.sub('  *', ' ', pathcmds)
    for item in pathcmds:
        if item in 'MmZzLlHhVvCcSsQqTtAa':
            if last:
                coords = parse_svg_coords(pathcmds[last_index + 1:index])
                cmds.append((last, coords))
            last = item
            last_index = index
        index += 1

    coords = parse_svg_coords(pathcmds[last_index + 1:index])
    cmds.append([last, coords])

    paths = []
    path = []
    cpoint = []
    rel_flag = False
    last_cmd = 'M'
    last_quad = None

    for cmd in cmds:
        if cmd[0] in 'Mm':
            if path: paths.append(path)
            path = deepcopy(PATH_STUB)
            rel_flag = cmd[0] == 'm'
            points = [cmd[1][i:i + 2] for i in range(0, len(cmd[1]), 2)]
            for point in points:
                if cpoint and rel_flag:
                    point = add_points(base_point(cpoint), point)
                if not path[0]:
                    path[0] = point
                else:
                    path[1].append(point)
                cpoint = point
        elif cmd[0] in 'Zz':
            p0 = [] + base_point(cpoint)
            p1 = [] + path[0]
            if not libgeom.is_equal_points(p0, p1, 8):
                path[1].append([] + path[0])
            path[2] = sk2const.CURVE_CLOSED
            cpoint = [] + path[0]
        elif cmd[0] in 'Cc':
            rel_flag = cmd[0] == 'c'
            points = [cmd[1][i:i + 2] for i in range(0, len(cmd[1]), 2)]
            points = [points[i:i + 3] for i in range(0, len(points), 3)]
            for point in points:
                if rel_flag:
                    point = [add_points(base_point(cpoint), point[0]),
                        add_points(base_point(cpoint), point[1]),
                        add_points(base_point(cpoint), point[2])]
                qpoint = [] + point
                qpoint.append(sk2const.NODE_CUSP)
                path[1].append(qpoint)
                cpoint = point
        elif cmd[0] in 'Ll':
            rel_flag = cmd[0] == 'l'
            points = [cmd[1][i:i + 2] for i in range(0, len(cmd[1]), 2)]
            for point in points:
                if rel_flag:
                    point = add_points(base_point(cpoint), point)
                path[1].append(point)
                cpoint = point
        elif cmd[0] in 'Hh':
            rel_flag = cmd[0] == 'h'
            for x in cmd[1]:
                dx, y = base_point(cpoint)
                if rel_flag:
                    point = [x + dx, y]
                else:
                    point = [x, y]
                path[1].append(point)
                cpoint = point
        elif cmd[0] in 'Vv':
            rel_flag = cmd[0] == 'v'
            for y in cmd[1]:
                x, dy = base_point(cpoint)
                if rel_flag:
                    point = [x, y + dy]
                else:
                    point = [x, y]
                path[1].append(point)
                cpoint = point
        elif cmd[0] in 'Ss':
            rel_flag = cmd[0] == 's'
            points = [cmd[1][i:i + 2] for i in range(0, len(cmd[1]), 2)]
            points = [points[i:i + 2] for i in range(0, len(points), 2)]
            for point in points:
                q = cpoint
                p = cpoint
                if len(cpoint) > 2:
                    q = cpoint[1]
                    p = cpoint[2]
                p1 = sub_points(add_points(p, p), q)
                if rel_flag:
                    p2 = add_points(base_point(cpoint), point[0])
                    p3 = add_points(base_point(cpoint), point[1])
                else:
                    p2, p3 = point
                point = [p1, p2, p3]
                qpoint = [] + point
                qpoint.append(sk2const.NODE_CUSP)
                path[1].append(qpoint)
                cpoint = point

        elif cmd[0] in 'Qq':
            rel_flag = cmd[0] == 'q'
            groups = [cmd[1][i:i + 4] for i in range(0, len(cmd[1]), 4)]
            for vals in groups:
                p = base_point(cpoint)
                if rel_flag:
                    q = add_points(p, [vals[0], vals[1]])
                    p3 = add_points(p, [vals[2], vals[3]])
                else:
                    q = [vals[0], vals[1]]
                    p3 = [vals[2], vals[3]]
                p1 = add_points(mult_point(p, F13), mult_point(q, F23))
                p2 = add_points(mult_point(p3, F13), mult_point(q, F23))

                point = [p1, p2, p3]
                qpoint = [] + point
                qpoint.append(sk2const.NODE_CUSP)
                path[1].append(qpoint)
                cpoint = point
                last_quad = q

        elif cmd[0] in 'Tt':
            rel_flag = cmd[0] == 't'
            groups = [cmd[1][i:i + 2] for i in range(0, len(cmd[1]), 2)]
            if last_cmd not in 'QqTt' or last_quad is None:
                last_quad = base_point(cpoint)
            for vals in groups:
                p = base_point(cpoint)
                q = sub_points(mult_point(p, 2.0), last_quad)
                if rel_flag:
                    p3 = add_points(p, [vals[0], vals[1]])
                else:
                    p3 = [vals[0], vals[1]]
                p1 = add_points(mult_point(p, F13), mult_point(q, F23))
                p2 = add_points(mult_point(p3, F13), mult_point(q, F23))

                point = [p1, p2, p3]
                qpoint = [] + point
                qpoint.append(sk2const.NODE_CUSP)
                path[1].append(qpoint)
                cpoint = point
                last_quad = q

        elif cmd[0] in 'Aa':
            rel_flag = cmd[0] == 'a'
            arcs = [cmd[1][i:i + 7] for i in range(0, len(cmd[1]), 7)]

            for arc in arcs:
                cpoint = base_point(cpoint)
                rev_flag = False
                rx, ry, xrot, large_arc_flag, sweep_flag, x, y = arc
                rx = abs(rx)
                ry = abs(ry)
                if rel_flag:
                    x += cpoint[0]
                    y += cpoint[1]
                if cpoint == [x, y]: continue
                if not rx or not ry:
                    path[1].append([x, y])
                    continue

                vector = [[] + cpoint, [x, y]]
                if sweep_flag:
                    vector = [[x, y], [] + cpoint]
                    rev_flag = True
                cpoint = [x, y]

                dir_tr = libgeom.trafo_rotate_grad(-xrot)

                if rx > ry:
                    tr = [1.0, 0.0, 0.0, rx / ry, 0.0, 0.0]
                    r = rx
                else:
                    tr = [ry / rx, 0.0, 0.0, 1.0, 0.0, 0.0]
                    r = ry

                dir_tr = libgeom.multiply_trafo(dir_tr, tr)
                vector = libgeom.apply_trafo_to_points(vector, dir_tr)

                l = libgeom.distance(*vector)

                if l > 2.0 * r: r = l / 2.0

                mp = libgeom.midpoint(*vector)

                tr0 = libgeom.trafo_rotate(math.pi / 2.0, mp[0], mp[1])
                pvector = libgeom.apply_trafo_to_points(vector, tr0)

                k = math.sqrt(r * r - l * l / 4.0)
                if large_arc_flag:
                    center = libgeom.midpoint(mp,
                        pvector[1], 2.0 * k / l)
                else:
                    center = libgeom.midpoint(mp,
                        pvector[0], 2.0 * k / l)

                angle1 = libgeom.get_point_angle(vector[0], center)
                angle2 = libgeom.get_point_angle(vector[1], center)

                da = angle2 - angle1
                start = angle1
                end = angle2
                if large_arc_flag:
                    if -math.pi >= da or da <= math.pi:
                        start = angle2
                        end = angle1
                        rev_flag = not rev_flag
                else:
                    if -math.pi <= da or da >= math.pi:
                        start = angle2
                        end = angle1
                        rev_flag = not rev_flag

                pth = libgeom.get_circle_paths(start, end,
                    sk2const.ARC_ARC)[0]

                if rev_flag:
                    pth = libgeom.reverse_path(pth)

                points = pth[1]
                for point in points:
                    if len(point) == 3:
                        point.append(sk2const.NODE_CUSP)

                tr0 = [1.0, 0.0, 0.0, 1.0, -0.5, -0.5]
                points = libgeom.apply_trafo_to_points(points, tr0)

                tr1 = [2.0 * r, 0.0, 0.0, 2.0 * r, 0.0, 0.0]
                points = libgeom.apply_trafo_to_points(points, tr1)

                tr2 = [1.0, 0.0, 0.0, 1.0, center[0], center[1]]
                points = libgeom.apply_trafo_to_points(points, tr2)

                tr3 = libgeom.invert_trafo(dir_tr)
                points = libgeom.apply_trafo_to_points(points, tr3)

                for point in points:
                    path[1].append(point)

        last_cmd = cmd[0]

    if path: paths.append(path)
    return paths


def parse_svg_stops(stops, current_color):
    sk2_stops = []
    for stop in stops:
        if not stop.tag == 'stop': continue
        offset = stop.attrs['offset']
        if offset[-1] == '%':
            offset = py2float(offset[:-1]) / 100.0
        else:
            offset = py2float(offset)

        alpha = 1.0
        sclr = 'black'
        if 'stop-opacity' in stop.attrs:
            alpha = py2float(stop.attrs['stop-opacity'])
        if 'stop-color' in stop.attrs:
            sclr = stop.attrs['stop-color']

        if 'style' in stop.attrs:
            style = {}
            stls = stop.attrs['style'].split(';')
            for stl in stls:
                vals = stl.split(':')
                if len(vals) == 2:
                    # 原版 .strip():Py2 字节串语义,只剥 ASCII 空白
                    style[vals[0].strip(_PY2_STR_WHITESPACE)] = vals[1].strip(_PY2_STR_WHITESPACE)
            if 'stop-opacity' in style:
                alpha = py2float(style['stop-opacity'])
            if 'stop-color' in style:
                sclr = style['stop-color'].strip(_PY2_STR_WHITESPACE)

        clr = parse_svg_color(sclr, alpha, current_color)
        sk2_stops.append([offset, clr])
    return sk2_stops


def parse_svg_text(objs):
    ret = ''
    for obj in objs:
        if obj.is_content():
            text = obj.text.replace('\n', '').replace('\r', '')
            ret += re.sub('  *', ' ', text)
        elif obj.childs:
            ret += parse_svg_text(obj.childs)
            if 'sodipodi:role' in obj.attrs and \
                            obj.attrs['sodipodi:role'].strip(_PY2_STR_WHITESPACE) == 'line':
                ret += '\n'
    # 原版 ret.lstrip():Py2 字节串语义,只剥 ASCII 空白(U+3000 全角空格等不剥)
    ret = ret.lstrip(_PY2_STR_WHITESPACE)
    if ret and ret[-1] == '\n': ret = ret[:-1]
    return ret


def create_xmlobj(tag, attrs={}):
    obj = XMLObject(tag)
    if attrs: obj.attrs = attrs
    return obj


def create_nl():
    return create_spacer()


def create_spacer(txt='\n'):
    return XmlContentText(txt)


# 移植版不要:create_rect(只被 SK2_to_SVG_Translator 用于保存 SVG;内含 str(float))


# 移植版不要:translate_style_dict(只被 SK2_to_SVG_Translator 用于保存 SVG)


# 移植版不要:point_to_str(只被 translate_paths_to_d 用于保存 SVG;内含 round/str(float))


# 移植版不要:translate_paths_to_d(只被 SK2_to_SVG_Translator 用于保存 SVG)


# ===========================================================================
# 移植新增:get_svg_trafo 里 `exec code` 的显式实现
# ===========================================================================
#
# 原版把 transform 属性切块后拼成 'tr=trafo_' + 块,compile + exec。于是
# 「怎么解析 transform」实际上等于「Py2.7 怎么编译执行这一小段 Python」,例如:
#   translate(10) scale(2)      -> 逐块执行,正常
#   translate(10)  scale(2)     -> 第二块变成 'tr=trafo_,scale(2)',NameError,被跳过
#   translate(10)scale(2)       -> SyntaxError,整条 transform 被丢掉
#   translate(10-5)             -> svgo 压缩写法,本意 (10,-5),Py2 算成 10-5=5
#   translate(010)              -> Py2 八进制,dx=8;translate(08) 语法错被跳过
#   matrix(1,0,0,1,0,0)         -> 整数字面量得 int(与 cairo 转 double 后一致)
# 这里把 Py2.7 的 Parser/tokenizer.c(数字 / 名字 / 运算符 / 换行与括号续行 / 注释)、
# Grammar 的相关子集、Python/ast.c:parsenumber 的取值规则按原样实现,
# 先整段「编译」(任何一处语法错都不执行),再逐语句求值。
#
# 支持的子集(SVG transform 里可能出现的一切都在内):
#   NUMBER(十进制 / 0x / 0o / 0b / 老式八进制 / 浮点 / 指数 / l L 后缀 / j 虚数)、
#   NAME、( ) , = + - * /、空格 \t \f、换行(括号内续行)、# 注释。
# 不支持、按「编译失败 -> 跳过」处理的(原版里要么同样失败,要么只有非法 SVG 才会写出):
#   字符串、[ ] { } . 属性访问、% ** // 比较与位运算、; 分号、\ 续行、关键字参数、
#   关键字语义(if/not/lambda/print ...,都当普通名字 -> NameError)、
#   除 6 个 trafo_* 以外的一切名字(原版能从模块全局 / 函数局部捞到 F13、math、trafo 等,
#   SVG 里不会出现)。
# 这同时去掉了原版的代码执行面:transform="translate(__import__('os')...)" 在原版里
# 真的会执行,移植版只会跳过。


class _Py2CompileError(Exception):
    """对应原版 compile() 抛的 SyntaxError / IndentationError / TypeError(空字节)。"""


def _py2_is_digit(c):
    # c 可能是 ''(越界);'0' <= '' 为 False
    return '0' <= c <= '9'


def _py2_is_xdigit(c):
    return c != '' and c in '0123456789abcdefABCDEF'


def _py2_is_octdigit(c):
    return '0' <= c < '8'


def _py2_is_name_start(c):
    return ('a' <= c <= 'z') or ('A' <= c <= 'Z') or c == '_'


def _py2_is_name_char(c):
    return _py2_is_name_start(c) or _py2_is_digit(c)


def _py2_scan_number(src, i):
    """从 src[i] 起扫一个 NUMBER token,返回结束下标(不含)。

    逐分支对应 Py2.7 Parser/tokenizer.c 的数字部分,goto fraction / exponent /
    imaginary 用 state 表示。调用方保证 src[i] 是数字,或是 '.' 且后面跟数字。
    """
    n = len(src)

    def at(k):
        return src[k] if k < n else ''

    c = at(i)
    state = None
    if c == '.':
        state = 'fraction'
    elif c == '0':
        # Hex, octal or binary -- maybe.
        i += 1
        c = at(i)
        if c == '.':
            state = 'fraction'
        elif c in ('j', 'J'):
            state = 'imaginary'
        elif c in ('x', 'X'):
            i += 1
            c = at(i)
            if not _py2_is_xdigit(c):
                raise _Py2CompileError('invalid token')
            while _py2_is_xdigit(c):
                i += 1
                c = at(i)
        elif c in ('o', 'O'):
            i += 1
            c = at(i)
            if not _py2_is_octdigit(c):
                raise _Py2CompileError('invalid token')
            while _py2_is_octdigit(c):
                i += 1
                c = at(i)
        elif c in ('b', 'B'):
            i += 1
            c = at(i)
            if c not in ('0', '1'):
                raise _Py2CompileError('invalid token')
            while c in ('0', '1'):
                i += 1
                c = at(i)
        else:
            found_decimal = False
            # Octal; c is first char of it
            while _py2_is_octdigit(c):
                i += 1
                c = at(i)
            if _py2_is_digit(c):
                found_decimal = True
                while _py2_is_digit(c):
                    i += 1
                    c = at(i)
            if c == '.':
                state = 'fraction'
            elif c in ('e', 'E'):
                state = 'exponent'
            elif c in ('j', 'J'):
                state = 'imaginary'
            elif found_decimal:
                raise _Py2CompileError('invalid token')
        if state is None:
            if c in ('l', 'L'):
                i += 1
            return i
    else:
        # Decimal
        while _py2_is_digit(c):
            i += 1
            c = at(i)
        if c in ('l', 'L'):
            return i + 1
        if c == '.':
            state = 'fraction'
        elif c in ('e', 'E'):
            state = 'exponent'
        elif c in ('j', 'J'):
            state = 'imaginary'
        else:
            return i

    if state == 'fraction':
        # do { c = tok_nextc(tok); } while (isdigit(c)); —— 先吃掉 '.'
        i += 1
        c = at(i)
        while _py2_is_digit(c):
            i += 1
            c = at(i)
        if c in ('e', 'E'):
            state = 'exponent'
        elif c in ('j', 'J'):
            state = 'imaginary'
        else:
            return i
    if state == 'exponent':
        i += 1
        c = at(i)
        if c in ('+', '-'):
            i += 1
            c = at(i)
        if not _py2_is_digit(c):
            raise _Py2CompileError('invalid token')
        while _py2_is_digit(c):
            i += 1
            c = at(i)
        if c in ('j', 'J'):
            state = 'imaginary'
        else:
            return i
    # imaginary
    return i + 1


def _py2_number_value(text):
    """Py2.7 Python/ast.c:parsenumber 的取值(token 已由 _py2_scan_number 保证合法)。

    - 'j' 结尾:complex(0, PyOS_string_to_double(前缀))—— 前缀按十进制,'017j' = 17j
    - 'l' 结尾:PyLong_FromString(s, base=0),与不带后缀的整数同值
    - 整数:strtol / strtoul(base=0):0x 十六进制、0o 八进制、0b 二进制、
      其余以 0 开头的是老式八进制('010' = 8)
    - 其余(含 '.' 或指数):PyOS_string_to_double —— 与 Py3 的 float() 同一套 dtoa,
      对 ASCII 字面量逐位相同;前导零照常是十进制('017.5' = 17.5)
    """
    last = text[-1]
    if last in ('j', 'J'):
        return complex(0.0, float(text[:-1]))
    if last in ('l', 'L'):
        text = text[:-1]
    if text[:2] in ('0x', '0X'):
        return int(text[2:], 16)
    if '.' in text or 'e' in text or 'E' in text:
        return float(text)
    if len(text) > 1 and text[0] == '0':
        if text[1] in ('o', 'O'):
            return int(text[2:], 8)
        if text[1] in ('b', 'B'):
            return int(text[2:], 2)
        return int(text, 8)
    return _py2_decimal_int(text)


def _py2_decimal_int(digits):
    """审查修正:十进制整数字面量取值,不受 Py3.11+ 的 int_max_str_digits 限制。

    Py2 的 PyLong_FromString 没有位数上限;Py3.11+(及 3.7.14+ 等安全版本)的
    int(str, 10) 超过 4300 位抛 ValueError,会让 'translate(1<4300 个 0>/1<4300 个 0>)'
    这类串在移植版被跳过(Py2 得 dx=1)。按块拼接得到同一个整数。
    """
    if len(digits) <= 4000:
        return int(digits, 10)
    value = 0
    for k in range(0, len(digits), 4000):
        chunk = digits[k:k + 4000]
        value = value * (10 ** len(chunk)) + int(chunk, 10)
    return value


def _py2_tokenize(src):
    """把源码切成 [(kind, text)],kind 取 NAME / NUMBER / OP / NEWLINE / ENDMARKER。"""
    if '\x00' in src:
        # Py2 compile():TypeError: compile() expected string without null bytes
        raise _Py2CompileError('null byte')
    # Py2.7 compile() 字符串源码:translate_newlines(\r\n、\r -> \n,末尾补 \n)
    src = src.replace('\r\n', '\n').replace('\r', '\n')
    if not src.endswith('\n'):
        src += '\n'
    toks = []
    n = len(src)
    i = 0
    level = 0
    atbol = True
    blankline = False
    while i < n:
        if atbol:
            # 行首:算缩进(空格 +1、\t 到下一个 8 的倍数、\f 归零)
            atbol = False
            col = 0
            while i < n and src[i] in ' \t\x0c':
                if src[i] == ' ':
                    col += 1
                elif src[i] == '\t':
                    col = (col // 8 + 1) * 8
                else:
                    col = 0
                i += 1
            blankline = i >= n or src[i] in '#\n'
            if not blankline and level == 0 and col != 0:
                raise _Py2CompileError('unexpected indent')
            continue
        c = src[i]
        if c in ' \t\x0c':
            i += 1
            continue
        if c == '#':
            while i < n and src[i] != '\n':
                i += 1
            continue
        if c == '\n':
            i += 1
            atbol = True
            if blankline or level > 0:
                continue
            toks.append(('NEWLINE', '\n'))
            continue
        if _py2_is_name_start(c):
            j = i + 1
            while j < n and _py2_is_name_char(src[j]):
                j += 1
            toks.append(('NAME', src[i:j]))
            i = j
            continue
        if _py2_is_digit(c) or \
                (c == '.' and i + 1 < n and _py2_is_digit(src[i + 1])):
            j = _py2_scan_number(src, i)
            toks.append(('NUMBER', src[i:j]))
            i = j
            continue
        if c in '(),=+-*/':
            nxt = src[i + 1] if i + 1 < n else ''
            # Py2 的双字符运算符(== += -= *= /= ** //)不在子集内
            if (c in '=+-*/' and nxt == '=') or \
                    (c == '*' and nxt == '*') or (c == '/' and nxt == '/'):
                raise _Py2CompileError('unsupported operator')
            if c == '(':
                level += 1
            elif c == ')':
                level -= 1
            toks.append(('OP', c))
            i += 1
            continue
        raise _Py2CompileError('invalid syntax')
    toks.append(('ENDMARKER', ''))
    return toks


class _Py2Parser(object):
    """Py2 Grammar 子集的递归下降:

    file_input: (NEWLINE | expr_stmt NEWLINE)* ENDMARKER
    expr_stmt:  testlist ('=' testlist)*        (赋值目标只能是 NAME)
    testlist:   test (',' test)* [',']
    test:       arith
    arith:      term (('+'|'-') term)*
    term:       factor (('*'|'/') factor)*
    factor:     ('+'|'-') factor | power
    power:      atom trailer*       trailer: '(' [test (',' test)* [',']] ')'
    atom:       '(' [testlist] ')' | NAME | NUMBER
    """

    def __init__(self, toks):
        self.toks = toks
        self.pos = 0

    def peek(self):
        return self.toks[self.pos]

    def take(self):
        tok = self.toks[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind, text=None):
        tok = self.take()
        if tok[0] != kind or (text is not None and tok[1] != text):
            raise _Py2CompileError('invalid syntax')
        return tok

    def starts_test(self):
        tok = self.peek()
        return tok[0] in ('NAME', 'NUMBER') or tok in (('OP', '('), ('OP', '+'),
                                                        ('OP', '-'))

    def file_input(self):
        stmts = []
        while self.peek()[0] != 'ENDMARKER':
            if self.peek()[0] == 'NEWLINE':
                self.pos += 1
                continue
            stmts.append(self.expr_stmt())
            self.expect('NEWLINE')
        return stmts

    def expr_stmt(self):
        lists = [self.testlist()]
        while self.peek() == ('OP', '='):
            self.pos += 1
            lists.append(self.testlist())
        targets = []
        for node in lists[:-1]:
            if node[0] != 'name':
                # Py2:SyntaxError: can't assign to ...(子集只收 NAME 目标)
                raise _Py2CompileError("can't assign")
            targets.append(node[1])
        return targets, lists[-1]

    def testlist(self):
        first = self.test()
        if self.peek() != ('OP', ','):
            return first
        items = [first]
        while self.peek() == ('OP', ','):
            self.pos += 1
            if not self.starts_test():
                break
            items.append(self.test())
        return ('tuple', items)

    def test(self):
        node = self.term()
        while self.peek() in (('OP', '+'), ('OP', '-')):
            op = self.take()[1]
            node = ('bin', op, node, self.term())
        return node

    def term(self):
        node = self.factor()
        while self.peek() in (('OP', '*'), ('OP', '/')):
            op = self.take()[1]
            node = ('bin', op, node, self.factor())
        return node

    def factor(self):
        if self.peek() in (('OP', '+'), ('OP', '-')):
            op = self.take()[1]
            return ('unary', op, self.factor())
        return self.power()

    def power(self):
        node = self.atom()
        while self.peek() == ('OP', '('):
            self.pos += 1
            args = []
            while self.peek() != ('OP', ')'):
                args.append(self.test())
                if self.peek() == ('OP', ','):
                    self.pos += 1
                else:
                    break
            self.expect('OP', ')')
            node = ('call', node, args)
        return node

    def atom(self):
        kind, text = self.take()
        if kind == 'NUMBER':
            # Py2 在编译期就把字面量转成值;'-' 紧跟字面量时 ast.c 会把 "-" + 字面量
            # 一起 parsenumber,取值与「先转值再取负」逐位相同(含 -0 -> 0、-0.0 -> -0.0)
            return ('num', _py2_number_value(text))
        if kind == 'NAME':
            return ('name', text)
        if (kind, text) == ('OP', '('):
            if self.peek() == ('OP', ')'):
                self.pos += 1
                return ('tuple', [])
            node = self.testlist()
            self.expect('OP', ')')
            return node
        raise _Py2CompileError('invalid syntax')


def _py2_binop(op, left, right):
    if op == '+':
        return left + right
    if op == '-':
        return left - right
    if op == '*':
        return left * right
    # Py2 经典除法:两个整数是地板除,否则真除(浮点语境)
    if isinstance(left, int) and isinstance(right, int):
        return left // right
    return left / right


def _py2_eval(node, local_vars):
    kind = node[0]
    if kind == 'num':
        return node[1]
    if kind == 'name':
        name = node[1]
        if name in local_vars:
            return local_vars[name]
        if name in _PY2_EXEC_GLOBALS:
            return _PY2_EXEC_GLOBALS[name]
        raise NameError("name '%s' is not defined" % name)
    if kind == 'tuple':
        return tuple([_py2_eval(item, local_vars) for item in node[1]])
    if kind == 'unary':
        val = _py2_eval(node[2], local_vars)
        return -val if node[1] == '-' else +val
    if kind == 'bin':
        # 审查修正:沿左结合链迭代求值。原先逐层递归,'1+1+...+1' 约 1000 项就
        # RecursionError 被跳过;Py2 的 ast_for_binop 是迭代的、编译器 C 递归无此上限,
        # 照常算出结果。求值顺序不变:最左操作数,然后逐个右操作数 + 运算。
        spine = []
        while node[0] == 'bin':
            spine.append(node)
            node = node[2]
        value = _py2_eval(node, local_vars)
        for bnode in reversed(spine):
            right = _py2_eval(bnode[3], local_vars)
            value = _py2_binop(bnode[1], value, right)
        return value
    # call:先求被调对象,再从左到右求实参(与 Py2 字节码顺序一致)
    func = _py2_eval(node[1], local_vars)
    args = [_py2_eval(item, local_vars) for item in node[2]]
    return func(*args)


def _py2_exec_trafo(source):
    """原版 `code = compile(source, '<string>', 'exec'); exec code` 的显式实现。

    返回执行后局部变量 tr 的值(第一句总是 'tr=...',执行成功就一定有)。
    任何失败都抛异常,由 get_svg_trafo 的 except: 吞掉。
    """
    stmts = _Py2Parser(_py2_tokenize(source)).file_input()
    local_vars = {}
    for targets, value_node in stmts:
        value = _py2_eval(value_node, local_vars)
        for name in targets:
            local_vars[name] = value
    return local_vars['tr']


def _py2_cairo_matrix_check(tr):
    """原版 libcairo.multiply_trafo -> get_matrix_from_trafo:
        m11, m21, m12, m22, dx, dy = trafo
        return cairo.Matrix(m11, m21, m12, m22, dx, dy)
    pycairo 的 'dddddd' 只收 int / long / float(bool 是 int 子类),其余 TypeError。
    """
    m11, m21, m12, m22, dx, dy = tr
    for val in (m11, m21, m12, m22, dx, dy):
        if not isinstance(val, (int, float)):
            raise TypeError('a float is required')


# exec 里能解析到的名字:原版 trafo_* 六个函数(见 _py2_exec_trafo 的注释)
_PY2_EXEC_GLOBALS = {
    'trafo_skewX': trafo_skewX,
    'trafo_skewY': trafo_skewY,
    'trafo_rotate': trafo_rotate,
    'trafo_scale': trafo_scale,
    'trafo_translate': trafo_translate,
    'trafo_matrix': trafo_matrix,
}
