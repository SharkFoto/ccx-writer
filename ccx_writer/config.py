# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2012 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/utils/config.py 的 XmlConfigParser 替身,逐行对应移植。
# 运行时清单实际执行:update(30 次)、load(30 次;fixture 环境下偏好文件都不存在,
# 所以只执行了 `self.filename = filename` 和一次 exists 判断,XMLPrefReader 一次没跑)。
#
# 与原版的差异:
#   - load:保留 `self.filename = filename`,不读偏好 XML 文件。原版在文件存在时用
#     xml.sax + XMLPrefReader(Py2 `exec` 语句,把文件里的字符串当 Python 执行)覆盖
#     默认值 —— 移植版一律用代码里的默认值,转换结果不随运行目录下有没有
#     svg_config.xml / sk2_config.xml 而变(原版 app_config_dir 为空时会去读 cwd 下的同名文件)。
#   - save:不写文件(转换链路从不调用)。
#   - get / update / encode_quotes / decode_quotes / escape_quote:照搬。
#
# update 遍历 cnf.keys() 逐个 setattr,键之间互不依赖,Py2 哈希序与 Py3 插入序无差别。

import logging
# 移植版不要:import xml.sax / from xml.sax import handler / XMLGenerator / InputSource(只服务 load/save 读写偏好文件)

# 移植版不要:from uc2.utils import fsutils(只服务 load/save 读写偏好文件)

LOG = logging.getLogger(__name__)

IDENT = '\t'


def encode_quotes(line):
    result = line.replace('"', '&quot;')
    result = result.replace("'", "&#039;")
    return result


def decode_quotes(line):
    result = line.replace('&quot;', '"')
    result = result.replace("&#039;", "'")
    return result


def escape_quote(line):
    ret = line.replace("\\", "\\\\")
    return ret.replace("'", "\\'")


class XmlConfigParser(object):
    """
    Represents parent class for application config.
    """
    filename = ''

    def get(self, name, subst=None):
        return self.__dict__[name] if name in self.__dict__ else subst

    def update(self, cnf=None):
        cnf = cnf or {}
        for key in cnf.keys():
            setattr(self, key, cnf[key])

    def load(self, filename=None):
        self.filename = filename
        # 移植版不要:`if fsutils.exists(filename):` 之后用 xml.sax + XMLPrefReader 读偏好文件
        # 覆盖默认值的整段(见文件头)。

    def save(self, filename=None):
        # 移植版不要:save 的主体(把非默认偏好用 XMLGenerator 写回 XML 文件;转换链路从不调用)
        return


# 移植版不要:XMLPrefReader(读偏好文件的 SAX 处理器;endElement 里是 Py2 `exec code`)


# 移植版不要:ErrorHandler(读偏好文件的 SAX 空处理器)


# 移植版不要:EntityResolver(读偏好文件的 SAX 空处理器)


# 移植版不要:DTDHandler(读偏好文件的 SAX 空处理器)
