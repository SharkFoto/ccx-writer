# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2015 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/formats/sk2/sk2_config.py,逐行照搬,全部默认值保留。
# 唯一改动是导入(原为 from uc2 import uc2const, sk2const /
# from uc2.utils.config import XmlConfigParser)。
# 类体内只有字面量、乘法和对前面类属性的直接引用(不在推导式里),Py3 作用域规则下
# 结果与 Py2 相同;default_stroke_color / default_text_fill 等与 sk2const.CMYK_BLACK
# 是同一个 list 对象(不拷贝),照搬。

from ccx_writer import uc2const, sk2const
from ccx_writer.config import XmlConfigParser


class SK2_Config(XmlConfigParser):
    system_encoding = 'utf-8'

    # --- DOCUMENT PREVIEW
    preview = True
    preview_size = (300.0, 300.0)
    preview_transparent = False

    # --- DOCUMENT PROPERTIES
    doc_origin = sk2const.DOC_ORIGIN_LL
    doc_units = uc2const.UNIT_MM
    doc_author = ''
    doc_license = ''
    doc_keywords = ''
    doc_notes = ''

    # --- PAGE PROPERTIES
    page_format = 'A4'
    page_orientation = uc2const.PORTRAIT

    # --- LAYER PROPERTIES
    layer_color = '#3252A2'
    layer_propeties = [1, 1, 1, 1]
    master_layer_color = '#000000'

    guide_layer_color = '#0051FF'
    guide_layer_propeties = [1, 1, 0, 0]

    grid_layer_color = [0.0, 0.0, 1.0, 0.15]
    grid_layer_geometry = [0.0, 0.0, uc2const.mm_to_pt, uc2const.mm_to_pt]
    grid_layer_propeties = [0, 0, 0, 1]

    # --- FILL STYLE
    default_fill = []
    default_fill_rule = sk2const.FILL_EVENODD

    # --- STROKE STYLE
    default_stroke_rule = sk2const.STROKE_MIDDLE
    default_stroke_width = 0.1 * uc2const.mm_to_pt
    default_stroke_color = sk2const.CMYK_BLACK
    default_stroke_dash = []
    default_stroke_cap = sk2const.CAP_BUTT
    default_stroke_join = sk2const.JOIN_MITER
    default_stroke_miter_limit = 10.433
    default_stroke_behind_flag = 0
    default_stroke_scalable_flag = 0
    default_stroke_markers = []

    default_stroke = [
        default_stroke_rule,
        default_stroke_width,
        default_stroke_color,
        default_stroke_dash,
        default_stroke_cap,
        default_stroke_join,
        default_stroke_miter_limit,
        default_stroke_behind_flag,
        default_stroke_scalable_flag,
        default_stroke_markers,
    ]

    # --- TEXT STYLE
    default_text = "TEXT text"
    default_font_family = 'Sans'
    default_font_face = 'Regular'
    default_font_size = 12.0
    default_text_alignment = sk2const.TEXT_ALIGN_LEFT
    default_text_spacing = []
    default_cluster_flag = True
    default_text_style = [default_font_family, default_font_face,
                          default_font_size, default_text_alignment,
                          default_text_spacing,
                          default_cluster_flag]

    default_text_fill = [sk2const.FILL_EVENODD, sk2const.FILL_SOLID,
                         sk2const.CMYK_BLACK]

    # --- PIXMAP STYLE
    default_cmyk_image_style = [sk2const.CMYK_BLACK, sk2const.CMYK_WHITE]
    default_rgb_image_style = [sk2const.RGB_BLACK, sk2const.RGB_WHITE]
    default_image_style = [[], [], [], default_cmyk_image_style]

    # --- POLYGON
    default_polygon_num = 5

    # ============== COLOR MANAGEMENT SECTION ===================
    default_rgb_profile = ''
    default_cmyk_profile = ''
    default_lab_profile = ''
    default_gray_profile = ''
