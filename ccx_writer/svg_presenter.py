# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2016 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/formats/svg/svg_presenter.py,逐行对应移植。只保留载入与 translate_to_sk2。
#
# 与原版的差异:
#   - 导入改成 ccx_writer 下的绝对导入。
#   - translate_from_sk2(sk2 -> SVG,保存 SVG)删掉,连带 SK2_to_SVG_Translator 的导入。
#   - saver 照抄 Advanced_XML_Saver():移植版 xml_filters 保留了这个类,但 do_save
#     抛 NotImplementedError,不会悄悄写出空文件。
#
# cms:原版 self.cms = self.appdata.app.default_cms 照抄。移植版 appdata.app.default_cms
# 是 ccx_writer.cms.CmsStub(见 convert.AppData),色彩管理方法抛 NotImplementedError。
# config:SVG_Config.load 在移植版不读文件(见 ccx_writer.config),路径拼接照抄。

import os

from ccx_writer import uc2const
from ccx_writer.generic import TaggedModelPresenter
from ccx_writer.svg_config import SVG_Config
from ccx_writer.svg_methods import SVG_Methods, create_new_svg
# 移植版不要:from uc2.formats.svg.svg_translators import SK2_to_SVG_Translator(保存 SVG)
from ccx_writer.svg_translators import SVG_to_SK2_Translator
from ccx_writer.xml_filters import Advanced_XML_Loader, Advanced_XML_Saver


class SVG_Presenter(TaggedModelPresenter):
    cid = uc2const.SVG

    config = None
    doc_file = ''
    resources = None
    cms = None

    def __init__(self, appdata, cnf=None, filepath=None):
        cnf = cnf or {}
        self.config = SVG_Config()
        config_file = os.path.join(appdata.app_config_dir, self.config.filename)
        self.config.load(config_file)
        self.config.update(cnf)
        self.appdata = appdata
        self.cms = self.appdata.app.default_cms
        self.loader = Advanced_XML_Loader()
        self.saver = Advanced_XML_Saver()
        self.methods = SVG_Methods(self)
        if filepath is None:
            self.new()
        else:
            self.load(filepath)

    def new(self):
        self.model = create_new_svg(self.config)
        self.update()

    def update(self, action=False):
        TaggedModelPresenter.update(self, action)
        self.methods.update()

    # 移植版不要:translate_from_sk2(sk2 -> SVG,只服务保存 SVG)

    def translate_to_sk2(self, sk2_doc):
        translator = SVG_to_SK2_Translator()
        translator.translate(self, sk2_doc)
