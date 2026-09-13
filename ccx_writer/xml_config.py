# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2015 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/formats/xml_/xml_config.py,逐行照搬,全部默认值保留。
# 唯一改动是导入(原为 from uc2.utils.config import XmlConfigParser)。

from ccx_writer.config import XmlConfigParser

class XML_Config(XmlConfigParser):

    system_encoding = 'utf-8'
    encoding = 'utf-8'
    filename = 'xml_config.xml'
    indent = '\t'
