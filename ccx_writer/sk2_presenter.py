# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2013-2015 by Ihor E. Novikov
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/formats/sk2/sk2_presenter.py,逐行对应移植。只保留 new / update ——
# svg_loader 建 sk2 文档时走的就是 SK2_Presenter(appdata, cnf) -> new() -> update()。
#
# cms:原版 self.cms = self.appdata.app.default_cms 照抄。移植版里 appdata.app
# 的 default_cms 是 ccx_writer.cms.CmsStub(见 convert.AppData),其
# get_rgb_color255 等色彩管理方法抛 NotImplementedError —— 前端真正执行到的
# 只有 cms 模块级的 hexcolor_to_rgb / hexcolor_to_rgba / val_255 / val_100。

import os

from ccx_writer import uc2const
from ccx_writer.generic import TextModelPresenter
from ccx_writer.sk2_config import SK2_Config
from ccx_writer.sk2_methods import create_new_doc, SK2_Methods
# 移植版不要:from uc2.formats.sk2.sk2_filters import SK2_Loader, SK2_Saver(读写 sk2 文件)


class SK2_Presenter(TextModelPresenter):
    cid = uc2const.SK2

    config = None
    doc_file = ''
    resources = None
    cms = None
    app = None
    active_page = None
    doc_name = ''

    def __init__(self, appdata, cnf=None, filepath=None):
        cnf = cnf or {}
        self.config = SK2_Config()
        # 移植版的 config.load 不读文件(ccx_writer.config),这两行照抄只为可 diff
        config_file = os.path.join(appdata.app_config_dir, 'sk2_config.xml')
        self.config.load(config_file)
        self.config.update(cnf)
        self.appdata = appdata
        self.app = self.appdata.app
        self.cms = self.appdata.app.default_cms
        # 移植版不要:self.loader = SK2_Loader()(读 sk2 文件)
        # 移植版不要:self.saver = SK2_Saver()(写 sk2 文件)
        self.methods = SK2_Methods(self)
        self.resources = {}
        if filepath is None:
            self.new()
        else:
            # 移植版不要:self.load(filepath)(读 sk2 文件;SK2_Loader 未移植)
            raise NotImplementedError(
                '读 sk2 文件不在移植范围:ccx_writer 只从 SVG 建 sk2 文档')

    def new(self):
        self.model = create_new_doc(self.config)
        self.update()

    def update(self, action=False):
        TextModelPresenter.update(self, action)
        if self.model is not None:
            self.methods.update()
