# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2016 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 移植说明:逐行照搬原版 uc2/formats/svg/svg_const.py,纯常量表,零改动。
# SVG_ATTRS 只服务于保存 SVG(svg_methods.create_new_svg),留着保持可 diff。
# SVG_STYLE 在 svg_translators.get_level_style 里被 .keys() 遍历:Py2 是
# 哈希序、Py3 是插入序,但循环体对每个键独立赋值,结果与遍历顺序无关。
# 注意由 deepcopy(SVG_STYLE) 派生出的 style dict 的键序同样 Py2/Py3 不同,
# 下游如有依赖 style 键序的输出,须在下游处理(本文件无需改动)。

SVG_ATTRS = {
    "xmlns": "http://www.w3.org/2000/svg",
    "xmlns:xlink": "http://www.w3.org/1999/xlink",
    "version": "1.1",
}

SVG_DPI = 72.0

in_to_pt = 72.0
pt_to_in = 1.0 / 72.0

pt_to_svg_px = pt_to_in * SVG_DPI
svg_px_to_pt = in_to_pt / SVG_DPI

SVG_PX = 'px'
SVG_PC = 'pc'
SVG_PT = 'pt'
SVG_MM = 'mm'
SVG_CM = 'cm'
SVG_IN = 'in'
SVG_FT = 'ft'
SVG_M = 'm'

SVG_UNITS = (SVG_PX, SVG_PC, SVG_PT, SVG_MM, SVG_CM, SVG_IN, SVG_FT, SVG_M)

SVG_STYLE = {
    'opacity': '1',
    'fill': 'black',
    'fill-rule': 'nonzero',
    'fill-opacity': '1',
    'stroke': 'none',
    'stroke-width': '1',
    'stroke-linecap': 'butt',
    'stroke-linejoin': 'miter',
    'stroke-miterlimit': '4',
    'stroke-dasharray': 'none',
    'stroke-dashoffset': '0',
    'stroke-opacity': '1',
    'font-family': 'Sans',
    'font-style': 'normal',
    'font-weight': 'normal',
    'font-size': '12',
    'text-align': 'start',
    'text-anchor': 'start',
}

IMG_SIGS = ('data:image/jpeg;base64,', 'data:image/png;base64,')
