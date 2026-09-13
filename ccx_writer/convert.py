# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植
#  Copyright (C) 2026 SharkFoto
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。
"""SVG -> CorelDRAW CCX(.cdr)/ CMX(.cmx)的对外入口。

替代原版 1,802 行的 UCApplication + cmds 脚手架。原版一次转换真正用到的只有:
  svg_loader(appdata, 路径) -> sk2 文档 -> cmx_saver(sk2 文档, 路径, cnf)
外加 appdata 上的几个字段。这里把它们直接写出来。

⚠️ appdata 的 app_name / version / revision / app_domain 会被 cmx_from_sk2
的 _default_notes 写进 ICMT 块("Created by UniConvertor 2.0rc5")。
Step 3-6 的判据是与 Py2 原版字节一致,所以这里取原版的值,**不要改**。
想换成自己的署名,放到 Step 7 之后作为一次单独的、可审查的改动。
"""
import os

APP_NAME = 'UniConvertor'
APP_VERSION = '2.0'
APP_REVISION = 'rc5'
APP_DOMAIN = 'sk1project.net'


class _App(object):
    """原版 UCApplication 在前端里只被读 default_cms 一个属性。"""

    def __init__(self):
        from ccx_writer.cms import CmsStub
        self.default_cms = CmsStub()


class AppData(object):
    """原版 UCData 的替身,只保留写出链路读到的字段。"""
    app_name = APP_NAME
    version = APP_VERSION
    revision = APP_REVISION
    app_domain = APP_DOMAIN

    def __init__(self, config_dir=''):
        # 前端的 presenter 会 os.path.join(app_config_dir, 'xxx_config.xml')
        # 再交给 config.load —— 移植版的 load 不读文件,这里给什么都行。
        self.app_config_dir = config_dir
        self.app = _App()


# 与原版 uniconvertor 的扩展名分派一致:
#   .cdr -> formats/cdr/__init__.py:cdr_saver,强制 kw['pack'] = True -> CDRX(zlib 压缩)
#   .cmx -> formats/cmx/__init__.py:cmx_saver,pack 默认 False     -> CMX1(未压缩)
PACK_BY_EXT = {'.cdr': True, '.cmx': False}


def convert(svg_path, out_path, pack=None, appdata=None, uc2_compat=False):
    """把一个 SVG 转成 .cdr / .cmx。

    pack=None 时按扩展名走原版的默认;显式传 True/False 覆盖。
    注意:CorelDRAW 按内容识别格式,不看扩展名(真机实测)。所以
    「文件叫 .cdr、内容是未压缩 CMX1」是合法的,而且那样 libcdr 才读得回来 ——
    这是 Step 9 接入 office 时要做的选择,入口先把开关留好。

    uc2_compat=True 逐位复现 UniConvertor 原版(含精度缺陷),只给回归验证用。
    """
    from ccx_writer.svg_loader import svg_loader
    from ccx_writer import cmx_saver

    ext = os.path.splitext(out_path)[1].lower()
    if pack is None:
        if ext not in PACK_BY_EXT:
            raise ValueError('输出扩展名只能是 .cdr 或 .cmx,收到 %r' % ext)
        pack = PACK_BY_EXT[ext]
    appdata = appdata or AppData()
    sk2_doc = svg_loader(appdata, svg_path, cnf={'uc2_compat': uc2_compat})
    try:
        cmx_saver(sk2_doc, out_path, cnf={'pack': pack, 'save_preview': False,
                                          'uc2_compat': uc2_compat})
    finally:
        close = getattr(sk2_doc, 'close', None)
        if close:
            close()
    return out_path
