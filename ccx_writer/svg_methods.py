# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2016 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/formats/svg/svg_methods.py,逐行对应移植。
#
# 与原版的差异只有导入:
#   from uc2.formats.svg import svg_const            -> from ccx_writer import svg_const
#   from uc2.formats.svg.svg_utils import ...         -> from ccx_writer.svg_utils import ...
#
# Py2 -> Py3:get_units 的 len(value) 在 Py2 是 utf-8 字节数、Py3 是字符数。
# 只有「单个非 ASCII 字符」这种值两边会走不同分支,而两个分支都返回 SVG_PX
# (单位后缀全是 ASCII,匹配不上),结果相同,不需要改。

from copy import deepcopy

from ccx_writer import svg_const
from ccx_writer.svg_utils import create_xmlobj, create_nl


def create_new_svg(config):
    doc = create_xmlobj('svg', deepcopy(svg_const.SVG_ATTRS))
    defs = create_xmlobj('defs', {'id': 'defs1'})
    doc.childs.append(create_nl())
    doc.childs.append(defs)
    return doc


class SVG_Methods:
    presenter = None
    model = None
    config = None

    def __init__(self, presenter):
        self.presenter = presenter

    def update(self):
        self.model = self.presenter.model
        self.config = self.presenter.config

    def get_units(self, value):
        if len(value) > 1:
            for item in svg_const.SVG_UNITS:
                if value.endswith(item):
                    return item
        return svg_const.SVG_PX

    def doc_units(self):
        for item in self.model.childs:
            if item.tag == 'sodipodi:namedview':
                return item.attrs.get('inkscape:document-units',
                                      svg_const.SVG_PX)
        return self.get_units(self.model.attrs.get('width', ''))
