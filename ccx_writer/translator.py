# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2018 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/utils/translator.py,逐行对应移植;文件末尾补上原 uc2/__init__.py 里的
# `_ = translator.MsgTranslator()`,各模块统一 `from ccx_writer.translator import _`。
#
# 与原版的差异:
#   - set_locale:unicode -> str。原版条件写成 `not (msgs_path, unicode)`(漏了
#     isinstance,元组恒真,decode 分支永远走不到)—— 照搬成 `not (msgs_path, str)`,
#     行为不变(见返回的 found_bugs)。
#
# 运行时清单里只执行了 __call__ 与 dummy_translate(恒等),所有 _('...') 原样返回。

import gettext
import os


class MsgTranslator(object):
    translate = None

    def __init__(self):
        self.translate = self.dummy_translate

    def dummy_translate(self, msg):
        return msg

    def set_locale(self, textdomain, msgs_path, locale='system'):
        msgs_path = msgs_path.decode('utf8') \
            if not (msgs_path, str) else msgs_path
        if locale == 'en' or not os.path.exists(msgs_path):
            return
        if locale and not locale == 'system':
            os.environ['LANGUAGE'] = locale
        gettext.bindtextdomain(textdomain, msgs_path)
        gettext.textdomain(textdomain)
        self.translate = gettext.gettext

    def __call__(self, msg):
        return self.translate(msg)


# 原 uc2/__init__.py:`_ = translator.MsgTranslator()`
_ = MsgTranslator()
