# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2015-2019 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 移植说明:逐行照搬原版 uc2/sk2const.py,纯常量表。
# 唯一改动是下面这行导入(原为 from uc2 import uc2const)。
# SK2DOC_ID / SK2XML_* / SK2SVG_START / SK2IMG_TAG* / SK2DOC_START 只服务于
# sk2 文件读写与 SVG 保存,移植版用不到;它们是纯字面量,留着不影响语义、
# 也保持与原版可 diff,所以不删,保持 str(不改 bytes)。
# NORMAL_TRAFO / CMYK_BLACK 等是模块级可变 list,原版调用方靠 [] + X 或
# deepcopy 取副本;FALLBACK_OUTLINE 内嵌的是 CMYK_BLACK 同一个对象 —— 照搬。
from ccx_writer import uc2const

SK2DOC_ID = '##sK1 2 '
SK2XML_ID = '<!-- sK1 2 '
SK2VER = '1'
SK2XML_START = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
SK2SVG_START = '<svg xmlns:svg="http://www.w3.org/2000/svg" ' + \
               'xmlns="http://www.w3.org/2000/svg" ' + \
               'xmlns:xlink="http://www.w3.org/1999/xlink" ' + \
               'version="1.0" width="%d" height="%d">'
SK2IMG_TAG = '<image y="0.0"  x="0.0" xlink:href="data:image/png;base64,'
SK2IMG_TAG_END = '"  height="%d" width="%d" />'
SK2DOC_START = '<!-- Encapsulated SK2'

DOC_ORIGIN_CENTER = 0
DOC_ORIGIN_LL = 1
DOC_ORIGIN_LU = 2
ORIGINS = [DOC_ORIGIN_CENTER, DOC_ORIGIN_LL, DOC_ORIGIN_LU]

# Bezier curve constants
NORMAL_TRAFO = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
# [scale_x, scale_y, shear_x, shear_y, rotate]
PATTERN_TRANSFORMS = [1.0, 1.0, 0.0, 0.0, 0.0]
CORNERS = [0.0, 0.0, 0.0, 0.0]
EMPTY_STYLE = [[], [], [], []]
EMPTY_IMAGE_STYLE = [[], []]

CURVE_CLOSED = 1
CURVE_OPENED = 0

NODE_CUSP = 0  # 0000
NODE_SMOOTH = 1  # 0001
NODE_SMOOTH_OPP = 2  # 0010
NODE_SMOOTH_BOTH = 3  # 0011
NODE_SYMMETRICAL = 4  # 0100
NODE_NOT_SMOOTH_OPP = 5  # 0101
NODE_SYMM_SMOOTH = 6  # 0110

ARC_ARC = 0
ARC_CHORD = 1
ARC_PIE_SLICE = 2

CIRCLE_CTRL = 0.552191307086614
CIRCLE_CTRL_SHIFT = 0.447808692913386

STUB_RECT = [0.0, 0.0, 1.0, 1.0]
STUB_PATHS = [[[0.0, 0.0], [[10.0, 10.0], ], CURVE_OPENED], ]
STUB_CIRCLE = [[[1.0, 0.5], [
    [[1.0, 0.776095653543307], [0.776095653543307, 1.0], [0.5, 1.0],
        NODE_SYMMETRICAL],
    [[0.223904346456693, 1.0], [0.0, 0.776095653543307], [0.0, 0.5],
        NODE_SYMMETRICAL],
    [[0.0, 0.223904346456693], [0.223904346456693, 0.0], [0.5, 0.0],
        NODE_SYMMETRICAL],
    [[0.776095653543307, 0.0], [1.0, 0.223904346456693], [1.0, 0.5],
        NODE_SYMMETRICAL],
], CURVE_CLOSED]]

STUB_ARCS = [
    [[1.0, 0.776095653543307], [0.776095653543307, 1.0], [0.5, 1.0],
        NODE_SYMMETRICAL],
    [[0.223904346456693, 1.0], [0.0, 0.776095653543307], [0.0, 0.5],
        NODE_SYMMETRICAL],
    [[0.0, 0.223904346456693], [0.223904346456693, 0.0], [0.5, 0.0],
        NODE_SYMMETRICAL],
    [[0.776095653543307, 0.0], [1.0, 0.223904346456693], [1.0, 0.5],
        NODE_SYMMETRICAL],
]

# Fill and stroke constants

FILL_EVENODD = 1  # 01
FILL_NONZERO = 0  # 00
FILL_NONZERO_CLOSED_ONLY = 2  # 10
FILL_EVENODD_CLOSED_ONLY = 3  # 11

FILL_ANY = 0  # 00
FILL_CLOSED_ONLY = 2  # 10

FILL_SOLID = 0
FILL_GRADIENT = 1
FILL_PATTERN = 2

GRADIENT_LINEAR = 0
GRADIENT_RADIAL = 1
GRADIENT_CONICAL = 2

GRADIENT_EXTEND_NONE = 0
GRADIENT_EXTEND_PAD = 1
GRADIENT_EXTEND_REPEAT = 2
GRADIENT_EXTEND_REFLECT = 3

PATTERN_IMG = 0
PATTERN_TRUECOLOR = 1
PATTERN_EPS = 2

STROKE_MIDDLE = 0
STROKE_OTSIDE = 1
STROKE_INSIDE = 2

JOIN_MITER = 0
JOIN_ROUND = 1
JOIN_BEVEL = 2

CAP_BUTT = 1
CAP_ROUND = 2
CAP_SQUARE = 3

CMYK_BLACK = [uc2const.COLOR_CMYK, [0.0, 0.0, 0.0, 1.0], 1.0, 'Black']
CMYK_WHITE = [uc2const.COLOR_CMYK, [0.0, 0.0, 0.0, 0.0], 1.0, 'White']
RGB_BLACK = [uc2const.COLOR_RGB, [0.0, 0.0, 0.0], 1.0, 'Black']
RGB_WHITE = [uc2const.COLOR_RGB, [1.0, 1.0, 1.0], 1.0, 'White']

FALLBACK_OUTLINE = [STROKE_MIDDLE, 1.0, CMYK_BLACK, [], CAP_BUTT, JOIN_MITER,
                    10.433, 0, 0, []]

TEXTBLOCK_WIDTH = -1

TEXT_ALIGN_LEFT = 0
TEXT_ALIGN_CENTER = 1
TEXT_ALIGN_RIGHT = 2
TEXT_ALIGN_JUSTIFY = 3

TEXT_VALIGN_TOP = 0
TEXT_VALIGN_BASELINE = 1
TEXT_VALIGN_BOTTOM = 2
