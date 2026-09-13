# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2015-2016 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/formats/xml_/xml_presenter.py,逐行对应移植。
#
# 与原版的差异只有导入(uc2 / uc2.formats.* -> ccx_writer.*)。
# SVG 前端不经过 XML_Presenter(svg_presenter 直接用 xml_filters 的
# Advanced_XML_Loader);原版里它只是 xml_ 包导入时被定义,照搬保留。
# cnf={} 可变默认参数照抄原版(config.update 只读 cnf,不会改它)。

import os

from ccx_writer import uc2const
from ccx_writer.generic import TaggedModelPresenter
from ccx_writer.xml_config import XML_Config
from ccx_writer.xml_filters import XML_Loader, XML_Saver
from ccx_writer.xml_model import XMLObject


class XML_Presenter(TaggedModelPresenter):

    cid = uc2const.XML

    config = None
    doc_file = ''
    resources = None
    cms = None

    def __init__(self, appdata, cnf={}, filepath=None):
        self.doc_file = ''
        self.resources = None
        self.config = XML_Config()
        config_file = os.path.join(appdata.app_config_dir, self.config.filename)
        self.config.load(config_file)
        self.config.update(cnf)
        self.appdata = appdata
        self.cms = self.appdata.app.default_cms
        self.loader = XML_Loader()
        self.saver = XML_Saver()
        if filepath is None:
            self.new()
        else:
            self.load(filepath)

    def new(self):
        self.model = XMLObject('root')

