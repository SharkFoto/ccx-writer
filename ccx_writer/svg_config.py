# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2016 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/formats/svg/svg_config.py,逐行照搬,全部默认值保留。
# 唯一改动是导入(原为 from uc2.utils.config import XmlConfigParser)。
# 注意 svg_dpi = 0.0 表示「未指定」:svg_translators.define_units 在根元素 width 的单位
# 不是 px/pc 时把实例属性改成 90.0(写在实例上,不污染类默认值)。

from ccx_writer.config import XmlConfigParser


class SVG_Config(XmlConfigParser):
    system_encoding = 'utf-8'
    encoding = 'utf-8'
    indent = '\t'
    filename = 'svg_config.xml'
    svg_dpi = 0.0
    # Step 7:True = 逐位复现 UniConvertor 2.0 原版(含已知缺陷),
    # 只给「与 Py2 原版字节一致」的回归验证用;False(默认)= 修复后的行为。
    uc2_compat = False
