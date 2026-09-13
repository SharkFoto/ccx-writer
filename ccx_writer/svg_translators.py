# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2016-2018 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

import logging
import re
# 移植版不要:os(get_image 拼位图文件路径;位图不支持)
# 移植版不要:base64.b64decode / b64encode(get_image 解 data URI、SK2_to_SVG_Translator 写位图)
# 移植版不要:cStringIO.StringIO(get_image 把解码后的位图喂给 PIL)
from copy import deepcopy

# 移植版不要:PIL.Image(位图不支持:CMX v1 写出器不写位图)

from ccx_writer import uc2const, libgeom, sk2const
# 移植版不要:libpango(文字不支持,ccx_writer 不带 pango)
# 移植版不要:cms、utils(SVG_to_SK2_Translator 一次都没用到,原版是给 SK2_to_SVG_Translator 的)
# 移植版不要:fsutils(get_image 判断位图文件是否存在)
from ccx_writer import sk2_model
from ccx_writer import svg_const, svg_utils
from ccx_writer.svg_utils import get_svg_trafo, check_svg_attr, \
    parse_svg_points, parse_svg_coords, parse_svg_color, parse_svg_stops, \
    get_svg_level_trafo


LOG = logging.getLogger(__name__)

SK2_UNITS = {
    svg_const.SVG_PX: uc2const.UNIT_PX,
    svg_const.SVG_PC: uc2const.UNIT_PX,
    svg_const.SVG_PT: uc2const.UNIT_PT,
    svg_const.SVG_MM: uc2const.UNIT_MM,
    svg_const.SVG_CM: uc2const.UNIT_CM,
    svg_const.SVG_M: uc2const.UNIT_M,
    svg_const.SVG_IN: uc2const.UNIT_IN,
    svg_const.SVG_FT: uc2const.UNIT_FT,
}

FONT_COEFF = 0.938

SK2_FILL_RULE = {
    'nonzero': sk2const.FILL_NONZERO,
    'evenodd': sk2const.FILL_EVENODD,
}

SK2_LINE_JOIN = {
    'miter': sk2const.JOIN_MITER,
    'round': sk2const.JOIN_ROUND,
    'bevel': sk2const.JOIN_BEVEL,
}

SK2_LINE_CAP = {
    'butt': sk2const.CAP_BUTT,
    'round': sk2const.CAP_ROUND,
    'square': sk2const.CAP_SQUARE,
}

SK2_TEXT_ALIGN = {
    'start': sk2const.TEXT_ALIGN_LEFT,
    'middle': sk2const.TEXT_ALIGN_CENTER,
    'end': sk2const.TEXT_ALIGN_RIGHT,
}

SK2_GRAD_EXTEND = {
    'pad': sk2const.GRADIENT_EXTEND_PAD,
    'reflect': sk2const.GRADIENT_EXTEND_REFLECT,
    'repeat': sk2const.GRADIENT_EXTEND_REPEAT,
}


class SVG_to_SK2_Translator(object):
    page = None
    layer = None
    traffo = []
    dpi_coeff = 1.0
    user_space = []
    style_opts = {}
    classes = {}
    profiles = {}
    unit_mapping = None
    current_color = ''
    svg_doc = None
    sk2_doc = None
    svg_mt = None
    sk2_mt = None
    sk2_mtds = None
    svg_mtds = None
    id_map = None

    def translate(self, svg_doc, sk2_doc):
        self.svg_doc = svg_doc
        self.sk2_doc = sk2_doc
        self.svg_mt = svg_doc.model
        self.sk2_mt = sk2_doc.model
        self.sk2_mtds = sk2_doc.methods
        self.svg_mtds = svg_doc.methods
        self.classes = {}
        self.id_map = self.svg_mt.id_map
        self.profiles = {}
        self.current_color = ''
        self.define_units()
        self.translate_units()
        self.translate_page()
        for item in self.svg_mt.childs:
            style = self.get_level_style(self.svg_mt, svg_const.SVG_STYLE)
            self.translate_obj(self.layer, item, self.trafo, style)
        if len(self.page.childs) > 1 and not self.layer.childs:
            self.page.childs.remove(self.layer)
        self.sk2_mt.do_update()
        self._clear_objs()

    def _clear_objs(self):
        # Py3:keys() 是视图;循环里给 __dict__ 赋值,先 list(...) 快照
        for item in list(self.__dict__.keys()):
            obj = self.__dict__[item]
            if isinstance(obj, list):
                self.__dict__[item] = []
            elif isinstance(obj, dict):
                self.__dict__[item] = {}
            else:
                self.__dict__[item] = None
        self.dpi_coeff = 1.0
        self.current_color = ''

    # --- Utility methods

    def define_units(self):
        if not self.svg_doc.config.svg_dpi:
            if 'width' in self.svg_mt.attrs and \
                    self.svg_mtds.get_units(self.svg_mt.attrs['width']) not in \
                    (svg_const.SVG_PX, svg_const.SVG_PC):
                self.svg_doc.config.svg_dpi = 90.0

        dpi_coeff = self.svg_doc.config.svg_dpi / svg_const.SVG_DPI \
            if self.svg_doc.config.svg_dpi else 1.0

        self.unit_mapping = {
            svg_const.SVG_PX: svg_const.svg_px_to_pt / dpi_coeff,
            svg_const.SVG_PT: 1.0,
            svg_const.SVG_PC: 15.0 * svg_const.svg_px_to_pt / dpi_coeff,
            svg_const.SVG_MM: uc2const.mm_to_pt,
            svg_const.SVG_CM: uc2const.cm_to_pt,
            svg_const.SVG_IN: uc2const.in_to_pt,
            svg_const.SVG_M: uc2const.m_to_pt,
        }
        self.dpi_coeff = dpi_coeff

    def recalc_size(self, val):
        if not val:
            return None
        unit = self.svg_mtds.get_units(val)
        # float() -> _py2_float():Py2 下属性值是 UTF-8 字节串,见文件末尾
        size = _py2_float(val.replace(unit, ''))
        return size * self.unit_mapping[unit] * self.dpi_coeff

    def get_font_size(self, sval):
        val = self.recalc_size(sval) / self.dpi_coeff
        pts = [[0.0, 0.0], [0.0, val]]
        pts = libgeom.apply_trafo_to_points(pts, self.trafo)
        return libgeom.distance(*pts)

    def get_viewbox(self, vbox):
        vbox = vbox.replace(',', ' ').replace('  ', ' ')
        # vbox.split() -> _py2_split(vbox):Py2 字节串只按 ASCII 空白切
        return [self.recalc_size(item) for item in _py2_split(vbox)]

    def parse_def(self, svg_obj):
        if 'color' in svg_obj.attrs:
            if svg_obj.attrs['color'] == 'inherit':
                pass
            else:
                self.current_color = svg_obj.attrs['color']
        stops = []
        if svg_obj.tag == 'linearGradient':
            if 'xlink:href' in svg_obj.attrs:
                # [1:] -> _py2_bslice(..., 1):Py2 按 UTF-8 字节切
                cid = _py2_bslice(svg_obj.attrs['xlink:href'], 1)
                if cid in self.id_map:
                    stops = self.parse_def(self.id_map[cid])[2][2]
                    if not stops:
                        return []
            elif svg_obj.childs:
                stops = parse_svg_stops(svg_obj.childs, self.current_color)
                if not stops:
                    return []
            else:
                return []

            x1 = 0.0
            y1 = 0.0
            x2 = self.user_space[2]
            y2 = 0.0
            if 'x1' in svg_obj.attrs:
                x1 = self.recalc_size(svg_obj.attrs['x1'])
            if 'y1' in svg_obj.attrs:
                y1 = self.recalc_size(svg_obj.attrs['y1'])
            if 'x2' in svg_obj.attrs:
                x2 = self.recalc_size(svg_obj.attrs['x2'])
            if 'y2' in svg_obj.attrs:
                y2 = self.recalc_size(svg_obj.attrs['y2'])

            if 'gradientTransform' in svg_obj.attrs:
                strafo = svg_obj.attrs['gradientTransform']
                self.style_opts['grad-trafo'] = get_svg_trafo(strafo)

            extend = sk2const.GRADIENT_EXTEND_PAD
            if 'spreadMethod' in svg_obj.attrs:
                val = svg_obj.attrs['spreadMethod']
                if val in SK2_GRAD_EXTEND:
                    extend = SK2_GRAD_EXTEND[val]

            vector = [[x1, y1], [x2, y2]]
            return [0, sk2const.FILL_GRADIENT,
                    [sk2const.GRADIENT_LINEAR, vector, stops, extend]]

        elif svg_obj.tag == 'radialGradient':
            if 'xlink:href' in svg_obj.attrs:
                # [1:] -> _py2_bslice(..., 1):Py2 按 UTF-8 字节切
                cid = _py2_bslice(svg_obj.attrs['xlink:href'], 1)
                if cid in self.id_map:
                    stops = self.parse_def(self.id_map[cid])[2][2]
                    if not stops:
                        return []
            elif svg_obj.childs:
                stops = parse_svg_stops(svg_obj.childs, self.current_color)
                if not stops:
                    return []
            else:
                return []

            cx = self.user_space[2] / 2.0 + self.user_space[0]
            cy = self.user_space[3] / 2.0 + self.user_space[1]
            if 'cx' in svg_obj.attrs:
                cx = self.recalc_size(svg_obj.attrs['cx'])
            if 'cy' in svg_obj.attrs:
                cy = self.recalc_size(svg_obj.attrs['cy'])

            r = self.user_space[2] / 2.0 + self.user_space[0]
            if 'r' in svg_obj.attrs:
                r = self.recalc_size(svg_obj.attrs['r'])

            if 'gradientTransform' in svg_obj.attrs:
                strafo = svg_obj.attrs['gradientTransform']
                self.style_opts['grad-trafo'] = get_svg_trafo(strafo)

            extend = sk2const.GRADIENT_EXTEND_PAD
            if 'spreadMethod' in svg_obj.attrs:
                val = svg_obj.attrs['spreadMethod']
                if val in SK2_GRAD_EXTEND:
                    extend = SK2_GRAD_EXTEND[val]

            vector = [[cx, cy], [cx + r, cy]]
            return [0, sk2const.FILL_GRADIENT,
                    [sk2const.GRADIENT_RADIAL, vector, stops, extend]]

        return []

    def parse_clippath(self, svg_obj):
        if svg_obj.tag == 'clipPath' and svg_obj.childs:
            container = sk2_model.Container(self.layer.config)
            style = self.get_level_style(self.svg_mt, svg_const.SVG_STYLE)
            for child in svg_obj.childs:
                trafo = [] + libgeom.NORMAL_TRAFO
                self.translate_obj(container, child, trafo, style)
            if not container.childs:
                return None

            if len(container.childs) > 1:
                curves = []
                for item in container.childs:
                    item.update()
                    curve = item.to_curve()
                    pths = curve.get_initial_paths()
                    pths = libgeom.apply_trafo_to_paths(pths, curve.trafo)
                    curves.append(pths)
                paths = curves[0]
                for item in curves[1:]:
                    paths = libgeom.fuse_paths(paths, item)
            else:
                container.childs[0].update()
                curve = container.childs[0].to_curve()
                pths = curve.get_initial_paths()
                paths = libgeom.apply_trafo_to_paths(pths, curve.trafo)
            if not paths:
                return None
            curve = sk2_model.Curve(container.config, container, paths)
            container.childs = [curve, ]
            return container
        return None

    def get_level_style(self, svg_obj, style_in):
        if 'color' in svg_obj.attrs:
            if svg_obj.attrs['color'] == 'inherit':
                pass
            else:
                self.current_color = svg_obj.attrs['color']
        style = deepcopy(style_in)
        for item in svg_const.SVG_STYLE.keys():
            if item in svg_obj.attrs:
                val = svg_obj.attrs[item]
                if not val == 'inherit':
                    style[item] = val
        if 'class' in svg_obj.attrs:
            class_names = svg_obj.attrs['class'].split(' ')
            for class_name in class_names:
                if class_name in self.classes:
                    class_ = self.classes[class_name]
                    for item in class_.keys():
                        if item == 'opacity' and item in style_in:
                            op = _py2_float(class_[item]) * \
                                _py2_float(style_in[item])
                            # str(op) -> _py2_str_float(op):Py2 只留 12 位有效数字
                            style['opacity'] = _py2_str_float(op)
                        else:
                            style[item] = class_[item]
        if 'style' in svg_obj.attrs:
            stls = svg_obj.attrs['style'].split(';')
            for stl in stls:
                vals = stl.split(':')
                if len(vals) == 2:
                    # .strip() -> _py2_strip():Py2 字节串只去 ASCII 空白
                    key = _py2_strip(vals[0])
                    val = _py2_strip(vals[1])
                    if key == 'opacity' and key in style_in:
                        op = _py2_float(val) * _py2_float(style_in[key])
                        style['opacity'] = _py2_str_float(op)
                    else:
                        style[key] = val
        return style

    def _parse_dasharray(self, sval):
        """Step 7 修复 #16 的 SVG 规范解析,返回用户单位的长度列表。"""
        tokens = [t for t in re.split(r'[\s,]+', sval.strip()) if t]
        if not tokens or tokens[0] in ('none', 'inherit'):
            return []
        vals = []
        for tok in tokens:
            if tok.endswith('%'):
                return []
            try:
                v = self.recalc_size(tok)
            except (KeyError, ValueError):
                return []
            if v is None or v < 0 or v != v or v in (float('inf'), float('-inf')):
                return []
            vals.append(v)
        if not any(vals):
            return []
        if len(vals) % 2:
            vals = vals + vals
        if not any(vals[1::2]):
            # 间隙全为 0 等价于实线(审查确认:"5 0" 原本会写成带缝的虚线)
            return []
        return vals

    def get_sk2_style(self, svg_obj, style, text_style=False):
        sk2_style = [[], [], [], []]
        style = self.get_level_style(svg_obj, style)
        self.style_opts = {}

        if 'display' in style and style['display'] == 'none':
            return sk2_style
        if 'visibility' in style and \
                style['visibility'] in ('hidden', 'collapse'):
            return sk2_style

        # fill parsing
        if not style['fill'] == 'none':
            fillrule = SK2_FILL_RULE[style['fill-rule']]
            fill = style['fill'].replace('"', '')
            alpha = _py2_float(style['fill-opacity']) * \
                _py2_float(style['opacity'])

            def_id = ''
            if len(fill) > 3 and fill[:3] == 'url':
                # fill[5:] -> _py2_bslice(fill, 5):Py2 按 UTF-8 字节切
                val = _py2_bslice(fill, 5).split(')')[0]
                if val in self.id_map:
                    def_id = val
            elif fill[0] == '#' and fill[1:] in self.id_map:
                def_id = fill[1:]

            if def_id:
                sk2_style[0] = self.parse_def(self.id_map[def_id])
                if sk2_style[0]:
                    sk2_style[0][0] = fillrule
                    if sk2_style[0][1] == sk2const.FILL_GRADIENT:
                        for stop in sk2_style[0][2][2]:
                            color = stop[1]
                            color[2] *= alpha
                if 'grad-trafo' in self.style_opts:
                    tr = [] + self.style_opts['grad-trafo']
                    self.style_opts['fill-grad-trafo'] = tr
            else:
                clr = parse_svg_color(fill, alpha, self.current_color)
                if clr:
                    sk2_style[0] = [fillrule, sk2const.FILL_SOLID, clr]

        # stroke parsing
        if not style['stroke'] == 'none':
            stroke = style['stroke'].replace('"', '')
            stroke_rule = sk2const.STROKE_MIDDLE
            stroke_width = self.recalc_size(style['stroke-width'])
            if not self.svg_doc.config.uc2_compat and stroke_width is None:
                # 审查确认:stroke-width="" 时 recalc_size 返回 None。原版在下一行的除法里抛 TypeError,
                # 被 translate_obj 接住、只丢这一个对象;修复版删了那次除法,None 一路带到 do_update
                # 才炸,整份转换失败。按 SVG 规范,无效值取初始值 1。
                stroke_width = self.recalc_size('1')
            if self.svg_doc.config.uc2_compat:
                # 原版缺陷:recalc_size 返回的已是用户单位,这里又除一次 dpi_coeff
                stroke_width = stroke_width / self.dpi_coeff
            # Step 7 修复 #7:删掉上面那次除法。sk2 描边宽度的语义是用户单位,
            # 由 stroke_trafo(对象的完整变换)缩放 —— 这个设计是对的,错的只有这一行。
            # 实测(f7/f7b/f7c):原版无单位描边一律细 0.8 倍(=72/90),与 viewBox 缩放无关。
            stroke_linecap = SK2_LINE_CAP[style['stroke-linecap']]
            stroke_linejoin = SK2_LINE_JOIN[style['stroke-linejoin']]
            stroke_miterlimit = _py2_float(style['stroke-miterlimit'])
            alpha = _py2_float(style['stroke-opacity']) * \
                _py2_float(style['opacity'])

            dash = []
            if style['stroke-dasharray'] != 'none':
                # 原版:code = compile('dash=[' + style['stroke-dasharray'] + ']',
                #                      '<string>', 'exec'); exec code
                #       (except Exception: dash = [])
                # Py2 的 exec 语句改得到函数局部变量 dash,原版拿到的是把属性值
                # 当 Python 2 表达式列表求值的结果。移植版不执行代码,显式复现这个值,
                # 详见文件末尾 _py2_exec_dasharray。
                if self.svg_doc.config.uc2_compat:
                    dash = _py2_exec_dasharray(style['stroke-dasharray'])
                else:
                    # 修复 #16:原版把属性值拼成 Python 代码 exec 求值。SVG 里最常见的
                    # "4 2"(空格分隔)是语法错误 -> dash = [],虚线静默全丢;带单位的
                    # "4px,2px" 同样失败。按 SVG 规范解析:逗号/空白分隔的长度列表,
                    # 奇数个时重复一遍补成偶数;有负值、百分比或全为 0 时视为无虚线。
                    dash = self._parse_dasharray(style['stroke-dasharray'])
                    if not stroke_width:
                        dash = []
            if dash:
                sk2_dash = []
                for item in dash:
                    sk2_dash.append(item / stroke_width)
                dash = sk2_dash

            def_id = ''
            if len(stroke) > 3 and stroke[:3] == 'url':
                # stroke[5:] -> _py2_bslice(stroke, 5):Py2 按 UTF-8 字节切
                val = _py2_bslice(stroke, 5).split(')')[0]
                if val in self.id_map:
                    def_id = val
            elif stroke[0] == '#' and stroke[1:] in self.id_map:
                def_id = stroke[1:]

            if def_id:
                stroke_fill = self.parse_def(self.id_map[def_id])
                if stroke_fill:
                    stroke_fill[0] = sk2const.FILL_NONZERO
                    if stroke_fill[1] == sk2const.FILL_GRADIENT:
                        for stop in stroke_fill[2][2]:
                            color = stop[1]
                            color[2] *= alpha
                    self.style_opts['stroke-fill'] = stroke_fill
                    self.style_opts['stroke-fill-color'] = stroke_fill[2][2][0][
                        1]
                    clr = parse_svg_color('black')
                    sk2_style[1] = [stroke_rule, stroke_width, clr, dash,
                                    stroke_linecap, stroke_linejoin,
                                    stroke_miterlimit, 0, 1, []]
                    if 'grad-trafo' in self.style_opts:
                        tr = [] + self.style_opts['grad-trafo']
                        self.style_opts['stroke-grad-trafo'] = tr
            else:
                clr = parse_svg_color(stroke, alpha, self.current_color)
                if clr:
                    sk2_style[1] = [stroke_rule, stroke_width, clr, dash,
                                    stroke_linecap, stroke_linejoin,
                                    stroke_miterlimit, 0, 1, []]

        if text_style:
            # 移植版不要:字体族 / 字面 / 字号 / 对齐解析(依赖 libpango.get_fonts;
            # 只有 translate_text 会传 text_style=True,而它在入口就抛了)
            raise NotImplementedError(_TEXT_NOT_SUPPORTED)

        return sk2_style

    def get_image(self, svg_obj):
        # 移植版不要:get_image 原体(PIL 解 data URI / 读位图文件)
        raise NotImplementedError(_IMAGE_NOT_SUPPORTED)

    # --- Translation metods

    def translate_units(self):
        units = SK2_UNITS[self.svg_mtds.doc_units()]
        self.sk2_mt.doc_units = units

    def translate_page(self):
        width = height = 0.0
        vbox = []
        if 'viewBox' in self.svg_mt.attrs:
            vbox = self.get_viewbox(self.svg_mt.attrs['viewBox'])

        if 'width' in self.svg_mt.attrs:
            if not self.svg_mt.attrs['width'][-1] == '%':
                width = self.recalc_size(self.svg_mt.attrs['width'])
            else:
                if vbox:
                    width = vbox[2]
            if 'height' in self.svg_mt.attrs and \
                    not self.svg_mt.attrs['height'][-1] == '%':
                height = self.recalc_size(self.svg_mt.attrs['height'])
            else:
                if vbox:
                    height = vbox[3]
        elif vbox:
            width = vbox[2]
            height = vbox[3]

        if not width:
            width = self.recalc_size('210mm')
        if not height:
            height = self.recalc_size('297mm')

        page_fmt = ['Custom', (width / self.dpi_coeff, height / self.dpi_coeff),
                    uc2const.LANDSCAPE if width > height else uc2const.PORTRAIT]

        pages_obj = self.sk2_mtds.get_pages_obj()
        pages_obj.page_format = page_fmt
        self.page = sk2_model.Page(pages_obj.config, pages_obj, 'SVG page')
        self.page.page_format = deepcopy(page_fmt)
        pages_obj.childs = [self.page, ]
        pages_obj.page_counter = 1

        self.layer = sk2_model.Layer(self.page.config, self.page)
        self.page.childs = [self.layer, ]

        # Document trafo calculation
        self.trafo = [1 / self.dpi_coeff, 0.0, 0.0,
                      1 / self.dpi_coeff, 0.0, 0.0]

        dx = -width / 2.0
        dy = height / 2.0
        tr = [1.0, 0.0, 0.0, -1.0, dx, dy]
        self.user_space = [0.0, 0.0, width, height]
        self.trafo = libgeom.multiply_trafo(tr, self.trafo)

        if vbox:
            dx = -vbox[0]
            dy = -vbox[1]
            xx = width / vbox[2]
            yy = height / vbox[3]
            if 'xml:space' in self.svg_mt.attrs and \
                    self.svg_mt.attrs['xml:space'] == 'preserve':
                xx = yy = min(xx, yy)
            tr = [xx, 0.0, 0.0, yy, 0.0, 0.0]
            tr = libgeom.multiply_trafo([1.0, 0.0, 0.0, 1.0, dx, dy], tr)
            self.trafo = libgeom.multiply_trafo(tr, self.trafo)
            self.user_space = vbox

    def translate_obj(self, parent, svg_obj, trafo, style):
        obj_mapping = {
            'g': self.translate_g,
            'rect': self.translate_rect,
            'circle': self.translate_circle,
            'ellipse': self.translate_ellipse,
            'line': self.translate_line,
            'polyline': self.translate_polyline,
            'polygon': self.translate_polygon,
            'path': self.translate_path,
            'use': self.translate_use,
            'text': self.translate_text,
            'image': self.translate_image,
        }

        if svg_obj.attrs.get('display') == 'none':
            return
        try:
            if svg_obj.tag == 'defs':
                self.translate_defs(svg_obj)
            elif svg_obj.tag == 'sodipodi:namedview':
                self.translate_namedview(svg_obj)
            elif svg_obj.tag == 'sodipodi:guide':
                self.translate_guide(svg_obj)
            elif svg_obj.tag in obj_mapping:
                obj_mapping[svg_obj.tag](parent, svg_obj, trafo, style)
            elif svg_obj.tag == 'linearGradient':
                return
            elif svg_obj.tag == 'radialGradient':
                return
            elif svg_obj.tag == 'style':
                self.translate_style(svg_obj)
            elif svg_obj.tag == 'pattern':
                return
            elif svg_obj.tag == 'clipPath':
                return
            elif svg_obj.childs:
                self.translate_unknown(parent, svg_obj, trafo, style)
        except NotImplementedError:
            # 移植版新增:范围裁剪(文字 / 位图 / 色彩管理 / 复现不了的 dasharray)
            # 必须报出来。原版的 except Exception 会把它吞成一条日志,悄悄产出缺内容的文件。
            raise
        except Exception as e:
            # LOG.warn -> LOG.warning(warn 在 Py3 已弃用,输出相同)
            LOG.warning('Cannot translate <%s> object, tag <%s>',
                        repr(svg_obj), svg_obj.tag)
            if 'id' in svg_obj.attrs:
                LOG.warning('Object id: %s', svg_obj.attrs['id'])
            LOG.warning('Error traceback: %s', e)

    def translate_defs(self, svg_obj):
        for item in svg_obj.childs:
            if item.tag == 'style':
                self.translate_style(item)
            elif item.tag == 'color-profile':
                self.translate_color_profile(item)

    def translate_namedview(self, svg_obj):
        for item in svg_obj.childs:
            self.translate_obj(None, item, None, None)

    def translate_guide(self, svg_obj):
        position = parse_svg_points(svg_obj.attrs['position'])[0]
        position = libgeom.apply_trafo_to_point(position, self.trafo)
        orientation = parse_svg_points(svg_obj.attrs['orientation'])[0]
        if position and orientation:
            if not orientation[0] and orientation[1]:
                orientation = uc2const.HORIZONTAL
                position = -position[1]
            elif not orientation[1] and orientation[0]:
                orientation = uc2const.VERTICAL
                position = position[0]
            else:
                return
            guide_layer = self.sk2_mtds.get_guide_layer()
            guide = sk2_model.Guide(guide_layer.config, guide_layer,
                                    position, orientation)
            guide_layer.childs.append(guide)

    def translate_style(self, svg_obj):
        items = []
        for item in svg_obj.childs:
            if item.is_content():
                val = _py2_strip(item.text)
                if val:
                    items.append(val)
        if not items:
            return
        items = ' '.join(items)
        if '.' not in items:
            return
        items = items.split('.')[1:]
        for item in items:
            if '{' not in item:
                continue
            class_, stylestr = item.split('{')
            stylestr = stylestr.replace('}', '')
            stls = stylestr.split(';')
            style = {}
            for stl in stls:
                vals = stl.split(':')
                if len(vals) == 2:
                    style[_py2_strip(vals[0])] = _py2_strip(vals[1])
            self.classes[_py2_strip(class_)] = style

    def translate_color_profile(self, svg_obj):
        self.profiles[svg_obj.attrs['name']] = svg_obj

    def translate_g(self, parent, svg_obj, trafo, style):
        tr = get_svg_level_trafo(svg_obj, trafo)
        stl = self.get_level_style(svg_obj, style)
        container = None

        if 'inkscape:groupmode' in svg_obj.attrs:
            if svg_obj.attrs['inkscape:groupmode'] == 'layer':
                name = 'Layer %d' % len(self.page.childs)
                if 'inkscape:label' in svg_obj.attrs:
                    name = svg_obj.attrs['inkscape:label']
                if not self.layer.childs:
                    self.page.childs.remove(self.layer)
                self.layer = sk2_model.Layer(self.page.config, self.page, name)
                self.page.childs.append(self.layer)
                if check_svg_attr(svg_obj, 'sodipodi:insensitive', 'true'):
                    self.layer.properties[1] = 0
                if 'display' in stl and stl['display'] == 'none':
                    self.layer.properties[0] = 0
                for item in svg_obj.childs:
                    self.translate_obj(self.layer, item, tr, stl)
                self.layer = sk2_model.Layer(self.page.config, self.page)
                self.page.childs.append(self.layer)
                return

        elif 'clip-path' in svg_obj.attrs:
            clip_id = _py2_strip(_py2_bslice(svg_obj.attrs['clip-path'], 5, -1))
            if clip_id in self.id_map:
                container = self.parse_clippath(self.id_map[clip_id])

            if container:
                container.childs[0].trafo = [] + tr
                for item in svg_obj.childs:
                    self.translate_obj(container, item, tr, stl)
                if len(container.childs) > 1:
                    parent.childs.append(container)
                    return

        if not svg_obj.childs:
            return

        group = sk2_model.Group(parent.config, parent)
        for item in svg_obj.childs:
            self.translate_obj(group, item, tr, stl)
        if group.childs:
            if len(group.childs) == 1:
                parent.childs.append(group.childs[0])
            else:
                parent.childs.append(group)

    def translate_unknown(self, parent, svg_obj, trafo, style):
        group = sk2_model.Group(parent.config, parent)
        tr = get_svg_level_trafo(svg_obj, trafo)
        stl = self.get_level_style(svg_obj, style)
        for item in svg_obj.childs:
            self.translate_obj(group, item, tr, stl)
        if group.childs:
            parent.childs.append(group)

    def append_obj(self, parent, svg_obj, obj, trafo, style):
        obj.stroke_trafo = [] + trafo
        if style[0] and style[0][1] == sk2const.FILL_GRADIENT:
            obj.fill_trafo = [] + trafo
            if 'fill-grad-trafo' in self.style_opts:
                tr0 = self.style_opts['fill-grad-trafo']
                obj.fill_trafo = libgeom.multiply_trafo(tr0, trafo)

        curve = None
        if style[1] and 'stroke-fill' in self.style_opts:
            obj.update()
            stroke_obj = obj.to_curve()
            pths = libgeom.apply_trafo_to_paths(stroke_obj.get_initial_paths(),
                                                stroke_obj.trafo)
            try:
                pths = libgeom.stroke_to_curve(pths, obj.style[1])
                obj_style = [self.style_opts['stroke-fill'], [], [], []]
                curve = sk2_model.Curve(parent.config, parent, pths,
                                        style=obj_style)
                obj.style[1] = []
                curve.fill_trafo = [] + trafo
                if 'stroke-grad-trafo' in self.style_opts:
                    tr0 = self.style_opts['stroke-grad-trafo']
                    curve.fill_trafo = libgeom.multiply_trafo(tr0, trafo)
            except NotImplementedError:
                # 移植版新增:理由同 translate_obj,范围裁剪不许被这里的兜底吞掉
                raise
            except Exception:
                if 'stroke-fill-color' in self.style_opts:
                    obj.style[1][2] = self.style_opts['stroke-fill-color']
                else:
                    obj.style[1] = []

        container = None
        if 'clip-path' in svg_obj.attrs:
            clip_id = _py2_strip(_py2_bslice(svg_obj.attrs['clip-path'], 5, -1))
            if clip_id in self.id_map:
                container = self.parse_clippath(self.id_map[clip_id])
                if container:
                    container.childs[0].trafo = [] + trafo

        if container:
            container.childs.append(obj)
            if curve:
                container.childs.append(curve)
            parent.childs.append(container)
        else:
            parent.childs.append(obj)
            if curve:
                parent.childs.append(curve)

    def translate_rect(self, parent, svg_obj, trafo, style):
        cfg = parent.config
        sk2_style = self.get_sk2_style(svg_obj, style)
        tr = get_svg_level_trafo(svg_obj, trafo)

        x = y = w = h = 0
        if 'x' in svg_obj.attrs:
            x = self.recalc_size(svg_obj.attrs['x'])
        if 'y' in svg_obj.attrs:
            y = self.recalc_size(svg_obj.attrs['y'])
        if 'width' in svg_obj.attrs:
            w = self.recalc_size(svg_obj.attrs['width'])
        if 'height' in svg_obj.attrs:
            h = self.recalc_size(svg_obj.attrs['height'])

        if not w or not h:
            return

        corners = [] + sk2const.CORNERS
        rx = ry = None
        if 'rx' in svg_obj.attrs:
            rx = self.recalc_size(svg_obj.attrs['rx'])
        if 'ry' in svg_obj.attrs:
            ry = self.recalc_size(svg_obj.attrs['ry'])
        if rx is None and ry is not None:
            rx = ry
        elif ry is None and rx is not None:
            ry = rx
        if not rx or not ry:
            rx = ry = None

        if rx is not None:
            rx = abs(rx)
            ry = abs(ry)
            if rx > w / 2.0:
                rx = w / 2.0
            if ry > h / 2.0:
                ry = h / 2.0
            coeff = rx / ry
            w = w / coeff
            trafo = [1.0, 0.0, 0.0, 1.0, -x, -y]
            trafo1 = [coeff, 0.0, 0.0, 1.0, 0.0, 0.0]
            trafo2 = [1.0, 0.0, 0.0, 1.0, x, y]
            trafo = libgeom.multiply_trafo(trafo, trafo1)
            trafo = libgeom.multiply_trafo(trafo, trafo2)
            tr = libgeom.multiply_trafo(trafo, tr)
            corners = [2.0 * ry / min(w, h), ] * 4

        rect = sk2_model.Rectangle(cfg, parent, [x, y, w, h], tr,
                                   sk2_style, corners)
        self.append_obj(parent, svg_obj, rect, tr, sk2_style)

    def translate_ellipse(self, parent, svg_obj, trafo, style):
        cfg = parent.config
        sk2_style = self.get_sk2_style(svg_obj, style)
        tr = get_svg_level_trafo(svg_obj, trafo)

        cx = cy = rx = ry = 0.0
        if 'cx' in svg_obj.attrs:
            cx = self.recalc_size(svg_obj.attrs['cx'])
        if 'cy' in svg_obj.attrs:
            cy = self.recalc_size(svg_obj.attrs['cy'])
        if 'rx' in svg_obj.attrs:
            rx = self.recalc_size(svg_obj.attrs['rx'])
        if 'ry' in svg_obj.attrs:
            ry = self.recalc_size(svg_obj.attrs['ry'])
        if not rx or not ry:
            return
        rect = [cx - rx, cy - ry, 2.0 * rx, 2.0 * ry]

        ellipse = sk2_model.Circle(cfg, parent, rect, style=sk2_style)
        ellipse.trafo = libgeom.multiply_trafo(ellipse.trafo, tr)
        self.append_obj(parent, svg_obj, ellipse, tr, sk2_style)

    def translate_circle(self, parent, svg_obj, trafo, style):
        cfg = parent.config
        sk2_style = self.get_sk2_style(svg_obj, style)
        tr = get_svg_level_trafo(svg_obj, trafo)

        cx = cy = r = 0.0
        if 'cx' in svg_obj.attrs:
            cx = self.recalc_size(svg_obj.attrs['cx'])
        if 'cy' in svg_obj.attrs:
            cy = self.recalc_size(svg_obj.attrs['cy'])
        if 'r' in svg_obj.attrs:
            r = self.recalc_size(svg_obj.attrs['r'])
        if not r:
            return
        rect = [cx - r, cy - r, 2.0 * r, 2.0 * r]

        ellipse = sk2_model.Circle(cfg, parent, rect, style=sk2_style)
        ellipse.trafo = libgeom.multiply_trafo(ellipse.trafo, tr)
        self.append_obj(parent, svg_obj, ellipse, tr, sk2_style)

    def translate_line(self, parent, svg_obj, trafo, style):
        cfg = parent.config
        sk2_style = self.get_sk2_style(svg_obj, style)
        tr = get_svg_level_trafo(svg_obj, trafo)

        x1 = y1 = x2 = y2 = 0.0
        if 'x1' in svg_obj.attrs:
            x1 = self.recalc_size(svg_obj.attrs['x1'])
        if 'y1' in svg_obj.attrs:
            y1 = self.recalc_size(svg_obj.attrs['y1'])
        if 'x2' in svg_obj.attrs:
            x2 = self.recalc_size(svg_obj.attrs['x2'])
        if 'y2' in svg_obj.attrs:
            y2 = self.recalc_size(svg_obj.attrs['y2'])

        paths = [[[x1, y1], [[x2, y2], ], sk2const.CURVE_OPENED], ]

        curve = sk2_model.Curve(cfg, parent, paths, tr, sk2_style)
        self.append_obj(parent, svg_obj, curve, tr, sk2_style)

    def _line(self, point1, point2):
        paths = [[[] + point1, [[] + point2, ], sk2const.CURVE_OPENED], ]
        tr = [] + self.trafo
        style = [[], self.layer.config.default_stroke, [], []]
        curve = sk2_model.Curve(self.layer.config, self.layer, paths, tr, style)
        self.layer.childs.append(curve)

    def _point(self, point, trafo=None):
        if not trafo:
            trafo = [] + self.trafo
        style = [[], self.layer.config.default_stroke, [], []]
        rect = sk2_model.Rectangle(self.layer.config, self.layer,
                                   point + [1.0, 1.0],
                                   trafo, style=style)
        self.layer.childs.append(rect)

    def translate_polyline(self, parent, svg_obj, trafo, style):
        cfg = parent.config
        sk2_style = self.get_sk2_style(svg_obj, style)
        tr = get_svg_level_trafo(svg_obj, trafo)

        if 'points' not in svg_obj.attrs:
            return
        points = parse_svg_points(svg_obj.attrs['points'])
        if not points or len(points) < 2:
            return
        paths = [[points[0], points[1:], sk2const.CURVE_OPENED], ]

        curve = sk2_model.Curve(cfg, parent, paths, tr, sk2_style)
        self.append_obj(parent, svg_obj, curve, tr, sk2_style)

    def translate_polygon(self, parent, svg_obj, trafo, style):
        cfg = parent.config
        sk2_style = self.get_sk2_style(svg_obj, style)
        tr = get_svg_level_trafo(svg_obj, trafo)

        if 'points' not in svg_obj.attrs:
            return
        points = parse_svg_points(svg_obj.attrs['points'])
        if not points or len(points) < 3:
            return
        points.append([] + points[0])
        paths = [[points[0], points[1:], sk2const.CURVE_CLOSED], ]

        curve = sk2_model.Curve(cfg, parent, paths, tr, sk2_style)
        self.append_obj(parent, svg_obj, curve, tr, sk2_style)

    def translate_path(self, parent, svg_obj, trafo, style):
        cfg = parent.config
        sk2_style = self.get_sk2_style(svg_obj, style)
        tr = get_svg_level_trafo(svg_obj, trafo)

        if check_svg_attr(svg_obj, 'sodipodi:type', 'arc'):
            cx = self.recalc_size(svg_obj.attrs['sodipodi:cx'])
            cy = self.recalc_size(svg_obj.attrs['sodipodi:cy'])
            rx = self.recalc_size(svg_obj.attrs['sodipodi:rx'])
            ry = self.recalc_size(svg_obj.attrs['sodipodi:ry'])
            angle1 = angle2 = 0.0
            if 'sodipodi:start' in svg_obj.attrs:
                angle1 = _py2_float(svg_obj.attrs['sodipodi:start'])
            if 'sodipodi:end' in svg_obj.attrs:
                angle2 = _py2_float(svg_obj.attrs['sodipodi:end'])
            circle_type = sk2const.ARC_PIE_SLICE
            if check_svg_attr(svg_obj, 'sodipodi:open', 'true'):
                circle_type = sk2const.ARC_ARC
            rect = [cx - rx, cy - ry, 2.0 * rx, 2.0 * ry]
            curve = sk2_model.Circle(cfg, parent, rect, angle1, angle2,
                                     circle_type, sk2_style)
            curve.trafo = libgeom.multiply_trafo(curve.trafo, tr)
            self.append_obj(parent, svg_obj, curve, tr, sk2_style)
        elif 'd' in svg_obj.attrs:
            paths = svg_utils.parse_svg_path_cmds(svg_obj.attrs['d'])
            if not paths:
                return

            curve = sk2_model.Curve(cfg, parent, paths, tr, sk2_style)
            self.append_obj(parent, svg_obj, curve, tr, sk2_style)

    def translate_use(self, parent, svg_obj, trafo, style):
        tr = get_svg_level_trafo(svg_obj, trafo)
        stl = self.get_level_style(svg_obj, style)
        if 'xlink:href' in svg_obj.attrs:
            # [1:] -> _py2_bslice(..., 1):Py2 按 UTF-8 字节切
            obj_id = _py2_bslice(svg_obj.attrs['xlink:href'], 1)
            if obj_id in self.id_map:
                self.translate_obj(parent, self.id_map[obj_id], tr, stl)
            else:
                LOG.warning('<use> object id %s is not found', obj_id)

    def translate_text(self, parent, svg_obj, trafo, style):
        # 移植版不要:translate_text 原体(sk2_model.Text 靠 libpango 排版、转曲)
        raise NotImplementedError(_TEXT_NOT_SUPPORTED)

    def translate_image(self, parent, svg_obj, trafo, style):
        # 移植版不要:translate_image 原体(get_image 读位图 + sk2_model.Pixmap,
        # 依赖 PIL / ImageMagick 与文档 cms)
        raise NotImplementedError(_IMAGE_NOT_SUPPORTED)


# 移植版不要:SVG_FILL_RULE / SVG_LINE_JOIN / SVG_LINE_CAP / SVG_GRAD_EXTEND /
# SK2_to_SVG_Translator(原文件 1072-1402 行,只服务「sk2 -> 保存 SVG」)


# ============================================================================
# 以下全部是移植版新增:范围裁剪文案 + Py2 语义复现助手
# ============================================================================

_TEXT_NOT_SUPPORTED = ('文字需在上游先转曲线(如 inkscape --export-text-to-path);'
                       'ccx_writer 不带 pango')
_IMAGE_NOT_SUPPORTED = '位图不支持:CMX v1 写出器不写位图'


# ----------------------------------------------------------------------------
# 属性值的字节串语义
#
# 原版在 Py2 下,SVG 属性值和 <style> 文本都是 UTF-8 **字节串**:
# generic_filters.AbstractXMLLoader.startElement / characters 把 sax 给的 unicode
# 逐个 .encode('utf-8')。字节串的 strip() / split() 只认 ASCII 空白
# ' \t\n\r\x0b\x0c',float() 只认 ASCII。移植版里它们是 str,内置方法会认
# Unicode 空白(NBSP、全角空格……)与 Unicode 数字,Py3.6+ 的 float() 还认下划线
# '1_0' —— 对 ASCII 输入逐位一致,对这几类输入会静默给出与原版不同的值。

_PY2_WHITESPACE = ' \t\n\r\x0b\x0c'


def _py2_strip(val):
    """Py2 <字节串>.strip()。"""
    return val.strip(_PY2_WHITESPACE)


def _py2_split(val):
    """Py2 <字节串>.split()(无参数):按 ASCII 空白的连续段切,丢弃空串。"""
    for ch in _PY2_WHITESPACE[1:]:
        val = val.replace(ch, ' ')
    return [item for item in val.split(' ') if item]


def _py2_bslice(val, start, stop=None):
    """Py2 <UTF-8 字节串>[start:stop](审查补上)。

    原版按字节下标切 'xlink:href'[1:]、'url(#'[5:]、clip-path[5:-1],移植版 str 按
    码点切;被切掉的位置上有非 ASCII 字符时两者不同 —— 例如 xlink:href="éabc":
    Py2 得 '\\xa9abc'(残缺 UTF-8,查不到任何 id),Py3 得 'abc',会命中 id="abc"
    多画出对象 / 多拿到渐变色标。这里先编码成 UTF-8 再切,残缺字节用 surrogateescape
    还原成孤立代理码点:切出来的串只用于查 id_map(键是合法 Unicode,残缺串必然查不到,
    与 Py2 一致)和写日志。切口两侧都是 ASCII 时结果与直接切 str 相同。
    """
    return val.encode('utf-8')[start:stop].decode('utf-8', 'surrogateescape')


def _py2_float(val):
    """Py2 float(<字节串>)。

    Py2.7 PyFloat_FromString:两端跳过 ASCII 空白,中间交给 PyOS_string_to_double,
    剩下任何字符都是 ValueError。Py3 float(str) 与之相比多接受三类:
    下划线(3.6+)、非 ASCII 的 Unicode 数字与空白、ASCII 的 \\x1c-\\x1f(Py3 当空白)。
    这三类在 Py2 字节串上全都是 ValueError,在这里先挡掉;其余交给内置 float(),
    两者都用正确舍入的 dtoa,数值逐位一致。
    """
    if isinstance(val, str):
        for ch in val:
            if ch == '_' or ch > '\x7f' or '\x1c' <= ch <= '\x1f':
                raise ValueError('could not convert string to float: %r' % val)
    return float(val)


def _py2_str_float(val):
    """Py2.7 的 str(float)。

    Py2.7 float_str = PyOS_double_to_string(x, 'g', 12, Py_DTSF_ADD_DOT_0):
    只留 12 位有效数字,结果看起来像整数时补 '.0'(inf / nan 不补)。
    Py3 的 str(float) 是最短往返表示 —— 原版 get_level_style 把 opacity 乘积
    str() 之后再 float() 回来,12 位截断会改变数值(0.7 * 0.9 在 Py2 回来是 0.63,
    在 Py3 是 0.6300000000000001),所以必须复现。
    """
    text = '%.12g' % val
    if text.lstrip('-').isdigit():
        text += '.0'
    return text


# ----------------------------------------------------------------------------
# stroke-dasharray:原版 get_sk2_style 第 384-391 行
#
#     code = compile('dash=[' + style['stroke-dasharray'] + ']', '<string>', 'exec')
#     exec code
#     ...
#     except Exception:
#         dash = []
#
# 【复现的是哪种行为】Py2 下 exec **改得到**局部变量 dash。
#
# Py2 的 exec 是语句。函数体里出现不带 `in` 的 exec 时,ceval.c 的 exec_statement
# 先 PyEval_GetLocals()(内部 PyFrame_FastToLocals,把快速局部变量抄进 f_locals 字典)
# 当执行命名空间,执行完再 PyFrame_LocalsToFast 把字典抄回快速局部槽。exec 出来的
# `dash=[...]` 写进字典,随即写回 dash —— 原版拿到的就是「把属性值当 Python 2 表达式
# 列表求值」的结果。同一机制的实证:svg_utils.get_svg_trafo 靠 exec 把局部变量 tr
# 从字符串换成矩阵;Py2 录制的 f4_styles 里 transform="translate(120 85) rotate(20)"
# 那组对象的 trafo 确实带旋转分量。要是 exec 改不到局部变量,那里会拿字符串去乘矩阵、
# 抛错、整组丢失。(Py3 的 exec() 是函数,改不到函数局部变量 —— 照抄就永远得到 [],
# 所以不能照抄。)
#
# 【怎么复现】移植版不执行任何代码(原版这里是 SVG 可控的代码注入,见 found_bugs):
#   1. 按 Python 2.7 Parser/tokenizer.c 的规则切词。数字字面量规则与 Py3 不同:
#      '010' 是八进制 8、'08' 是词法错误、'5L' 是长整数、'1_0' 是数字 1 后面跟名字 _0。
#   2. 能用子集文法解析的,按 Py2 语义求值:
#        列表    := [ 算术式 (',' 算术式)* [','] ]
#        算术式  := 项 (('+'|'-') 项)*
#        项      := 因子 (('*'|'/'|'//'|'%') 因子)*
#        因子    := ('+'|'-'|'~') 因子 | 数字 | 名字 | 名字 '(' [参数表] ')' | '(' 算术式 ')'
#      int / int 是地板除;~ 作用于 float 是 TypeError;
#      名字按 Py2 exec 的 LOAD_NAME 查找链(get_sk2_style 的局部变量 -> 原版模块全局
#      -> Py2 builtins):查不到 = NameError;查得到的(True、None、min、stroke_width……)
#      原版会拿到一个真实对象,移植版无法复现,抛 NotImplementedError。
#      求值中的 NameError / ZeroDivisionError / OverflowError / TypeError 在原版都落进
#      except Exception -> dash = []。
#   3. 子集文法解析不了的:能**确证** Py2 编译必定 SyntaxError 的 -> [];
#      确证不了(可能是合法的 Python 表达式)-> NotImplementedError,绝不静默猜。
#      确证规则见 _py2_certain_syntax_error,每条在 Py2 任何语法位置上都成立。
#
# 真实 SVG 的 dasharray —— '4,2' '4, 2' '4 2' '4px,2px' '50%' '5% 3%' 'inherit'
# 'revert-layer' 'var(--dash)' 'calc(2px*3)' '0.5em' —— 全部落在 2 的精确求值或
# 3 的 [] 分支,与 Py2 逐值一致。注意 '4 2'(空格分隔,Inkscape/Illustrator 的常见
# 写法)在原版是 SyntaxError -> [],虚线整个丢失 —— 这是原版行为,原样复现。

_DASH_NOT_EMULATED = ('stroke-dasharray=%r:原版会把它当 Python 2 代码 exec 求值,'
                      '%s;移植版不执行代码,无法给出与原版一致的结果')

_PY2_KEYWORDS = frozenset((
    'and', 'as', 'assert', 'break', 'class', 'continue', 'def', 'del', 'elif',
    'else', 'except', 'exec', 'finally', 'for', 'from', 'global', 'if',
    'import', 'in', 'is', 'lambda', 'not', 'or', 'pass', 'print', 'raise',
    'return', 'try', 'while', 'with', 'yield',
))

# 原版 get_sk2_style 的全部局部变量名(取超集,不管 exec 那一刻是否已绑定;
# 未绑定的在 Py2 是 NameError,这里多报一个 NotImplementedError,只会更响不会更错)
_PY2_EXEC_LOCALS = (
    'self', 'svg_obj', 'style', 'text_style', 'sk2_style', 'fillrule', 'fill',
    'alpha', 'def_id', 'val', 'stop', 'color', 'tr', 'clr', 'stroke',
    'stroke_rule', 'stroke_width', 'stroke_linecap', 'stroke_linejoin',
    'stroke_miterlimit', 'dash', 'code', 'sk2_dash', 'item', 'font_family',
    'font_face', 'faces', 'bold', 'italic', 'font_size', 'alignment',
)

# 原版 uc2/formats/svg/svg_translators.py 的全部模块级名字
_PY2_EXEC_GLOBALS = (
    '__builtins__', '__doc__', '__file__', '__name__', '__package__',
    'logging', 'os', 'b64decode', 'b64encode', 'StringIO', 'deepcopy', 'Image',
    'uc2const', 'libgeom', 'libpango', 'cms', 'sk2const', 'utils', 'fsutils',
    'sk2_model', 'svg_const', 'svg_utils', 'get_svg_trafo', 'check_svg_attr',
    'parse_svg_points', 'parse_svg_coords', 'parse_svg_color',
    'parse_svg_stops', 'get_svg_level_trafo', 'LOG', 'SK2_UNITS', 'FONT_COEFF',
    'SK2_FILL_RULE', 'SK2_LINE_JOIN', 'SK2_LINE_CAP', 'SK2_TEXT_ALIGN',
    'SK2_GRAD_EXTEND', 'SVG_to_SK2_Translator', 'SVG_FILL_RULE',
    'SVG_LINE_JOIN', 'SVG_LINE_CAP', 'SVG_GRAD_EXTEND', 'SK2_to_SVG_Translator',
)

# Python 2.7 的 __builtin__(含 site.py 注入的 exit/quit/help/copyright/credits/
# license;WindowsError 一并算上,取超集)
_PY2_BUILTINS = (
    'ArithmeticError', 'AssertionError', 'AttributeError', 'BaseException',
    'BufferError', 'BytesWarning', 'DeprecationWarning', 'EOFError',
    'Ellipsis', 'EnvironmentError', 'Exception', 'False', 'FloatingPointError',
    'FutureWarning', 'GeneratorExit', 'IOError', 'ImportError',
    'ImportWarning', 'IndentationError', 'IndexError', 'KeyError',
    'KeyboardInterrupt', 'LookupError', 'MemoryError', 'NameError', 'None',
    'NotImplemented', 'NotImplementedError', 'OSError', 'OverflowError',
    'PendingDeprecationWarning', 'ReferenceError', 'RuntimeError',
    'RuntimeWarning', 'StandardError', 'StopIteration', 'SyntaxError',
    'SyntaxWarning', 'SystemError', 'SystemExit', 'TabError', 'True',
    'TypeError', 'UnboundLocalError', 'UnicodeDecodeError',
    'UnicodeEncodeError', 'UnicodeError', 'UnicodeTranslateError',
    'UnicodeWarning', 'UserWarning', 'ValueError', 'Warning', 'WindowsError',
    'ZeroDivisionError', '__debug__', '__import__', 'abs', 'all', 'any',
    'apply', 'basestring', 'bin', 'bool', 'buffer', 'bytearray', 'bytes',
    'callable', 'chr', 'classmethod', 'cmp', 'coerce', 'compile', 'complex',
    'copyright', 'credits', 'delattr', 'dict', 'dir', 'divmod', 'enumerate',
    'eval', 'execfile', 'exit', 'file', 'filter', 'float', 'format',
    'frozenset', 'getattr', 'globals', 'hasattr', 'hash', 'help', 'hex', 'id',
    'input', 'int', 'intern', 'isinstance', 'issubclass', 'iter', 'len',
    'license', 'list', 'locals', 'long', 'map', 'max', 'memoryview', 'min',
    'next', 'object', 'oct', 'open', 'ord', 'pow', 'print', 'property', 'quit',
    'range', 'raw_input', 'reduce', 'reload', 'repr', 'reversed', 'round',
    'set', 'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super',
    'tuple', 'type', 'unichr', 'unicode', 'vars', 'xrange', 'zip',
)

_PY2_EXEC_NAMES = frozenset(_PY2_EXEC_LOCALS + _PY2_EXEC_GLOBALS + _PY2_BUILTINS)


class _Py2SyntaxError(Exception):
    """Py2 compile() 必定失败(原版落进 except Exception -> dash = [])。"""


class _Py2EvalError(Exception):
    """Py2 exec 求值时抛错(原版同样落进 except Exception -> dash = [])。"""


class _Py2DashSubsetMismatch(Exception):
    """子集文法解析不了 —— 不代表 Py2 一定编译失败,交给 _py2_certain_syntax_error。"""


_DIGITS = '0123456789'
_OCTDIGITS = '01234567'
_HEXDIGITS = '0123456789abcdefABCDEF'
_LETTERS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
_EOF = '\0'  # 越界哨兵;含 NUL 的输入在入口已经排除,不会和真字符混淆

# Python 2.7 PyToken_ThreeChars / PyToken_TwoChars / PyToken_OneChar 认识的运算符。
# 其余单字符('$' '?' '!' 控制字符、非 ASCII)在 Py2 分词为通用 OP,语法分析必定拒绝。
_PY2_THREE_CHAR_OPS = ('<<=', '>>=', '**=', '//=')
_PY2_TWO_CHAR_OPS = ('==', '!=', '<>', '<=', '<<', '>=', '>>', '+=', '-=',
                     '*=', '**', '/=', '//', '|=', '%=', '&=', '^=')
_PY2_ONE_CHAR_OPS = '()[]{}:,;+-*/|&<>=.%`^~@'


def _at(src, k):
    return src[k] if k < len(src) else _EOF


def _py2_lex_number(src, i):
    """从 src[i] 起切一个 Py2 数字字面量,返回 (结束下标, 种类)。

    逐支对照 Python 2.7 tokenizer.c tok_get 的数字部分(含 goto fraction /
    exponent / imaginary)。种类:int / oldoct / hex / oct / bin(均可带 L 后缀)、
    float、imag。
    """
    j = i
    kind = 'int'
    goto = ''
    c = _at(src, j)
    if c == '.':
        goto = 'fraction'
    elif c == '0':
        # Hex, octal or binary -- maybe.
        j += 1
        c = _at(src, j)
        if c == '.':
            goto = 'fraction'
        elif c in 'jJ':
            goto = 'imaginary'
        elif c in 'xX':
            j += 1
            if _at(src, j) not in _HEXDIGITS:
                raise _Py2SyntaxError()
            while _at(src, j) in _HEXDIGITS:
                j += 1
            kind = 'hex'
        elif c in 'oO':
            j += 1
            if _at(src, j) not in _OCTDIGITS:
                raise _Py2SyntaxError()
            while _at(src, j) in _OCTDIGITS:
                j += 1
            kind = 'oct'
        elif c in 'bB':
            j += 1
            if _at(src, j) not in '01':
                raise _Py2SyntaxError()
            while _at(src, j) in '01':
                j += 1
            kind = 'bin'
        else:
            # Octal; c is first char of it
            found_dig = False
            while _at(src, j) in _OCTDIGITS:
                j += 1
            if _at(src, j) in _DIGITS:
                found_dig = True
                while _at(src, j) in _DIGITS:
                    j += 1
            c = _at(src, j)
            if c == '.':
                goto = 'fraction'
            elif c in 'eE':
                goto = 'exponent'
            elif c in 'jJ':
                goto = 'imaginary'
            elif found_dig:
                raise _Py2SyntaxError()
            else:
                kind = 'oldoct'
        if not goto and _at(src, j) in 'lL':
            j += 1
    else:
        # Decimal
        while _at(src, j) in _DIGITS:
            j += 1
        c = _at(src, j)
        if c in 'lL':
            j += 1
        elif c == '.':
            goto = 'fraction'
        elif c in 'eE':
            goto = 'exponent'
        elif c in 'jJ':
            goto = 'imaginary'
    if goto == 'fraction':
        kind = 'float'
        j += 1
        while _at(src, j) in _DIGITS:
            j += 1
        c = _at(src, j)
        if c in 'eE':
            goto = 'exponent'
        elif c in 'jJ':
            goto = 'imaginary'
        else:
            goto = ''
    if goto == 'exponent':
        kind = 'float'
        j += 1
        if _at(src, j) in '+-':
            j += 1
        if _at(src, j) not in _DIGITS:
            raise _Py2SyntaxError()
        while _at(src, j) in _DIGITS:
            j += 1
        goto = 'imaginary' if _at(src, j) in 'jJ' else ''
    if goto == 'imaginary':
        kind = 'imag'
        j += 1
    return j, kind


def _py2_lex_string(src, q):
    """src[q] 是开引号,返回字符串词结束后的下标。对照 tokenizer.c letter_quote。"""
    quote = src[q]
    n = len(src)
    if src[q + 1:q + 3] == quote * 2:
        # 三引号
        k = q + 3
        count = 0
        while True:
            if k >= n:
                raise _Py2SyntaxError()  # E_EOFS
            c = src[k]
            if c == quote:
                count += 1
                k += 1
                if count == 3:
                    return k
            elif c == '\\':
                count = 0
                if k + 1 >= n:
                    raise _Py2SyntaxError()
                k += 2
            else:
                count = 0
                k += 1
    if src[q + 1:q + 2] == quote:
        return q + 2  # 空串
    k = q + 1
    while True:
        if k >= n:
            raise _Py2SyntaxError()  # E_EOLS
        c = src[k]
        if c == '\n':
            raise _Py2SyntaxError()  # E_EOLS
        if c == quote:
            return k + 1
        if c == '\\':
            if k + 1 >= n:
                raise _Py2SyntaxError()
            k += 2
        else:
            k += 1


def _py2_tokenize(src):
    """按 Py2.7 规则把 S 切成 [(种类, 文本, 附加)]。

    种类:num(附加=数字种类)、name、str、op、nl、comment_eof(注释一直到结尾,
    会吃掉模板补的 ']')。词法错误抛 _Py2SyntaxError。
    """
    toks = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c in ' \t\x0c':
            i += 1
        elif c == '\n':
            toks.append(('nl', c, None))
            i += 1
        elif c == '#':
            k = src.find('\n', i)
            if k < 0:
                toks.append(('comment_eof', src[i:], None))
                break
            i = k
        elif c == '\\':
            # 续行符后面必须紧跟换行,否则 E_LINECONT
            if _at(src, i + 1) != '\n':
                raise _Py2SyntaxError()
            i += 2
        elif c in _LETTERS or c == '_':
            # 先认 b"" r"" u"" br"" ur"" 前缀
            j = i
            if c in 'bBuU':
                j += 1
                if _at(src, j) in 'rR':
                    j += 1
            elif c in 'rR':
                j += 1
            if j > i and _at(src, j) in '"\'':
                end = _py2_lex_string(src, j)
                toks.append(('str', src[i:end], None))
                i = end
            else:
                j = i
                while _at(src, j) in _LETTERS or _at(src, j) in _DIGITS or \
                        _at(src, j) == '_':
                    j += 1
                toks.append(('name', src[i:j], None))
                i = j
        elif c in '"\'':
            end = _py2_lex_string(src, i)
            toks.append(('str', src[i:end], None))
            i = end
        elif c in _DIGITS or (c == '.' and _at(src, i + 1) in _DIGITS):
            end, kind = _py2_lex_number(src, i)
            toks.append(('num', src[i:end], kind))
            i = end
        elif src[i:i + 3] in _PY2_THREE_CHAR_OPS:
            toks.append(('op', src[i:i + 3], None))
            i += 3
        elif src[i:i + 2] in _PY2_TWO_CHAR_OPS:
            toks.append(('op', src[i:i + 2], None))
            i += 2
        elif c in _PY2_ONE_CHAR_OPS:
            toks.append(('op', c, None))
            i += 1
        else:
            raise _Py2SyntaxError()
    return toks


def _py2_number_value(tok, sval):
    """Py2 ast.c parsenumber 给出的数值。"""
    text, kind = tok[1], tok[2]
    if kind == 'imag':
        raise NotImplementedError(_DASH_NOT_EMULATED % (
            sval, '其中 %s 是复数字面量' % text))
    if kind == 'float':
        # PyOS_string_to_double 与 Py3 float() 同为正确舍入的 dtoa
        return float(text)
    digits = text.rstrip('lL')
    try:
        if kind == 'hex':
            return int(digits[2:], 16)
        if kind == 'oct':
            return int(digits[2:], 8)
        if kind == 'bin':
            return int(digits[2:], 2)
        if kind == 'oldoct':
            return int(digits, 8)
        return int(digits, 10)
    except ValueError:
        # Py3.10.7+ 限制十进制整数字符串位数(默认 4300),Py2 没有这个限制
        raise NotImplementedError(_DASH_NOT_EMULATED % (
            sval, '整数字面量位数超出本解释器的转换上限'))


class _Py2DashParser(object):
    """子集文法的递归下降解析器(文法见上方注释)。只建树不求值 ——
    Py2 是先 compile 整串、再 exec,语法错误优先于任何求值错误。"""

    MAX_DEPTH = 40
    MAX_CHAIN = 200

    def __init__(self, toks):
        # 模板的外层 '[' 里换行不算词(tok->level > 0)
        self.toks = [tok for tok in toks if tok[0] != 'nl']
        self.pos = 0
        self.depth = 0

    def peek(self):
        if self.pos < len(self.toks):
            return self.toks[self.pos]
        return None

    def at_op(self, *texts):
        tok = self.peek()
        return tok is not None and tok[0] == 'op' and tok[1] in texts

    def take(self):
        tok = self.toks[self.pos]
        self.pos += 1
        return tok

    def enter(self):
        self.depth += 1
        if self.depth > self.MAX_DEPTH:
            raise _Py2DashSubsetMismatch()

    def parse(self):
        items = []
        if self.peek() is not None:
            items.append(self.parse_arith())
            while self.at_op(','):
                self.take()
                if self.peek() is None:
                    break
                items.append(self.parse_arith())
        if self.peek() is not None:
            raise _Py2DashSubsetMismatch()
        return items

    def parse_arith(self):
        node = self.parse_term()
        count = 0
        while self.at_op('+', '-'):
            count += 1
            if count > self.MAX_CHAIN:
                raise _Py2DashSubsetMismatch()
            op = self.take()[1]
            node = ('bin', op, node, self.parse_term())
        return node

    def parse_term(self):
        node = self.parse_factor()
        count = 0
        while self.at_op('*', '/', '//', '%'):
            count += 1
            if count > self.MAX_CHAIN:
                raise _Py2DashSubsetMismatch()
            op = self.take()[1]
            node = ('bin', op, node, self.parse_factor())
        return node

    def parse_factor(self):
        if self.at_op('+', '-', '~'):
            op = self.take()[1]
            self.enter()
            node = ('unary', op, self.parse_factor())
            self.depth -= 1
            return node
        return self.parse_atom()

    def parse_atom(self):
        tok = self.peek()
        if tok is None:
            raise _Py2DashSubsetMismatch()
        if tok[0] == 'num':
            self.take()
            return ('num', tok)
        if tok[0] == 'name' and tok[1] not in _PY2_KEYWORDS:
            self.take()
            if not self.at_op('('):
                return ('name', tok[1])
            self.take()
            self.enter()
            args = []
            if not self.at_op(')'):
                args.append(self.parse_arith())
                while self.at_op(','):
                    self.take()
                    if self.at_op(')'):
                        break
                    args.append(self.parse_arith())
            if not self.at_op(')'):
                raise _Py2DashSubsetMismatch()
            self.take()
            self.depth -= 1
            return ('call', tok[1], args)
        if self.at_op('('):
            self.take()
            self.enter()
            node = self.parse_arith()
            if not self.at_op(')'):
                raise _Py2DashSubsetMismatch()
            self.take()
            self.depth -= 1
            return node
        raise _Py2DashSubsetMismatch()


def _py2_dash_eval(node, sval):
    """按 Py2 求值顺序与语义计算子集表达式。"""
    kind = node[0]
    if kind == 'num':
        return _py2_number_value(node[1], sval)
    if kind in ('name', 'call'):
        # 调用先 LOAD_NAME 被调者,名字不存在就在求实参之前 NameError
        if node[1] in _PY2_EXEC_NAMES:
            raise NotImplementedError(_DASH_NOT_EMULATED % (
                sval, '名字 %s 在原版 exec 命名空间里查得到' % node[1]))
        raise _Py2EvalError()  # NameError
    if kind == 'unary':
        val = _py2_dash_eval(node[2], sval)
        if node[1] == '-':
            return -val
        if node[1] == '+':
            return +val
        if isinstance(val, float):
            raise _Py2EvalError()  # TypeError: bad operand type for unary ~
        return ~val
    # 'bin':先左后右,再运算。
    # 审查修正:a+b+...+z 这类左结合链是左深树,逐层递归时 5 层括号 × 199 项
    # (约 2000 字符)就撞 Py3 递归上限,RecursionError 不是 _Py2EvalError,会被
    # translate_obj 的 except Exception 吞掉、悄悄丢掉整个对象;Py2 编译这种深度
    # 没问题,照常得到数值。沿左脊展开成循环,求值顺序(最左叶子 -> 逐层右子树
    # -> 运算)与递归版逐步相同。
    spine = []
    while node[0] == 'bin':
        spine.append(node)
        node = node[2]
    left = _py2_dash_eval(node, sval)
    for bin_node in reversed(spine):
        right = _py2_dash_eval(bin_node[3], sval)
        left = _py2_dash_binop(bin_node[1], left, right)
    return left


def _py2_dash_binop(op, left, right):
    """Py2 语义的二元运算(_py2_dash_eval 的 'bin' 节点)。"""
    try:
        if op == '+':
            return left + right
        if op == '-':
            return left - right
        if op == '*':
            return left * right
        if op == '/':
            if isinstance(left, int) and isinstance(right, int):
                # Py2 的 int / int(及 long)是地板除
                return left // right
            return left / right
        if op == '//':
            return left // right
        return left % right
    except ArithmeticError:
        # ZeroDivisionError / OverflowError(大整数转 float)
        raise _Py2EvalError()


_PY2_CLOSER_TO_OPENER = {')': '(', ']': '[', '}': '{'}

# 只能出现在两个操作数之间的运算符 / 关键字
_PY2_BINARY_ONLY = frozenset((
    '*', '/', '//', '%', '**', '<<', '>>', '&', '|', '^', '<', '>', '==', '!=',
    '<>', '<=', '>=', '=', 'and', 'or', 'in', 'is', 'if', 'else',
))
_PY2_UNARY = frozenset(('+', '-', '~', 'not'))
# 紧跟在开括号或逗号后面必错的词。去掉 '*' '**'(f(*a) f(a, **k))、
# 'in'(Py2 允许 [x for x, in y]);':' 与 '.' 本来就不在里面(x[:1]、x[...])。
_PY2_BAD_AFTER_SEPARATOR = (_PY2_BINARY_ONLY - frozenset(('*', '**', 'in'))) | \
    frozenset((',',))
# 在表达式括号里任何位置都必错的词(语句关键字、';'、'@'、增强赋值)。
# 'yield' 不算:[lambda: (yield)] 在 Py2 是合法的。
_PY2_BAD_INSIDE_BRACKETS = frozenset((
    'assert', 'break', 'class', 'continue', 'def', 'del', 'elif', 'except',
    'exec', 'finally', 'from', 'global', 'import', 'pass', 'print', 'raise',
    'return', 'try', 'while', 'with', 'as',
    ';', '@', '+=', '-=', '*=', '/=', '//=', '%=', '&=', '|=', '^=', '<<=',
    '>>=', '**=',
))


def _tok_is(tok, texts):
    return tok[0] in ('op', 'name') and tok[1] in texts


def _is_operand(tok):
    return tok[0] in ('num', 'str') or \
        (tok[0] == 'name' and tok[1] not in _PY2_KEYWORDS)


def _is_opener(tok):
    return tok[0] == 'op' and tok[1] in ('(', '[', '{')


def _is_closer(tok):
    return tok[0] == 'op' and tok[1] in (')', ']', '}')


def _py2_certain_syntax_error(toks):
    """'dash=[' + S + ']' 在 Py2 下是否**必定**编译失败(toks 是 S 的词)。

    只认下列规则,认不出的一律返回 False(调用方随即抛 NotImplementedError):
      - 括号类型不配对、多余的闭括号、到结尾仍未闭合(含注释吃掉模板的 ']');
    以下几条只在模板外层 '[' 尚未被 S 提前闭合时适用(一旦提前闭合,后面可能是
    任意语句,不再下结论):
      - 两个操作数相邻(数字 / 字符串 / 非关键字名字,或闭括号后接操作数),
        字符串接字符串除外:'4 2'、'4px'、'1_0';
      - 二元或一元运算符后面直接是逗号或闭括号:'50%'、'5%,3%'、'5-,3';
      - 开括号或逗号后面直接是二元运算符或逗号:',4'、'4,,2';
      - 括号里出现语句关键字、';'、'@'、增强赋值。
    """
    stack = ['[']  # 模板 'dash=[' 的外层括号
    closed_early = False
    prev = ('op', '[', None)
    seq = list(toks)
    if not (seq and seq[-1][0] == 'comment_eof'):
        seq.append(('op', ']', 'END'))  # 模板结尾补的 ']'
    for tok in seq:
        kind = tok[0]
        if kind == 'comment_eof':
            # 注释吃掉了模板的 ']':还有没闭合的括号就是 EOF 错误
            return bool(stack)
        if kind == 'nl':
            if closed_early:
                prev = None
            continue
        if not closed_early:
            if _tok_is(tok, _PY2_BAD_INSIDE_BRACKETS):
                return True
            if prev is not None:
                if _is_operand(tok) and \
                        (_is_operand(prev) or _is_closer(prev)) and \
                        not (prev[0] == 'str' and kind == 'str'):
                    return True
                if (_tok_is(prev, _PY2_BINARY_ONLY) or
                        _tok_is(prev, _PY2_UNARY)) and \
                        (_is_closer(tok) or _tok_is(tok, (',',))):
                    return True
                if (_is_opener(prev) or _tok_is(prev, (',',))) and \
                        _tok_is(tok, _PY2_BAD_AFTER_SEPARATOR):
                    return True
        if _is_opener(tok):
            stack.append(tok[1])
        elif _is_closer(tok):
            if not stack or stack[-1] != _PY2_CLOSER_TO_OPENER[tok[1]]:
                return True
            stack.pop()
            if not stack and tok[2] != 'END':
                closed_early = True
        prev = tok
    return bool(stack)


def _py2_exec_dasharray(sval):
    """原版 exec 之后局部变量 dash 的实际值。

    原版落进 except Exception 的情况返回 [];复现不了的抛 NotImplementedError。
    返回的列表元素是 int(含 Py2 long)或 float,与 Py2 exec 出来的逐值相同。
    """
    if '\0' in sval:
        # compile() expected string without null bytes(TypeError)
        return []
    # Py2.7 compile() 对字符串源码先做 translate_newlines:\r\n、\r -> \n
    src = sval.replace('\r\n', '\n').replace('\r', '\n')
    try:
        toks = _py2_tokenize(src)
    except _Py2SyntaxError:
        return []
    try:
        items = _Py2DashParser(toks).parse()
    except _Py2DashSubsetMismatch:
        if _py2_certain_syntax_error(toks):
            return []
        raise NotImplementedError(_DASH_NOT_EMULATED % (
            sval, '且它可能是合法的 Python 2 表达式'))
    dash = []
    try:
        for item in items:
            dash.append(_py2_dash_eval(item, sval))
    except _Py2EvalError:
        return []
    return dash
