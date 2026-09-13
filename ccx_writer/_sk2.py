# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(写出侧)
#  Copyright (C) 2019 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植与修复)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。
"""写出链路用到的 uc2const / sk2const 常量,按原版取值逐个抄过来。

原版这两个文件合计 744 行,绝大部分是页面尺寸表、调色板名、文件类型注册,
写出侧一个都用不到。这里只留 cmx_from_sk2 真正引用的十几个。
取值与 upstream @973d5b6 一致,`tests/test_constants.py` 有断言兜底。
"""

# --- uc2const ---
in_to_pt = 72.0
pt_to_in = 1.0 / 72.0

COLOR_GRAY = 'Grayscale'
COLOR_RGB = 'RGB'
COLOR_CMYK = 'CMYK'
COLOR_LAB = 'LAB'
COLOR_SPOT = 'SPOT'

# --- sk2const ---
CURVE_OPENED = 0
CURVE_CLOSED = 1

FILL_SOLID = 0
FILL_GRADIENT = 1
FILL_CLOSED_ONLY = 2          # 二进制 10

JOIN_MITER = 0
JOIN_ROUND = 1
JOIN_BEVEL = 2

CAP_BUTT = 1
CAP_ROUND = 2
CAP_SQUARE = 3
