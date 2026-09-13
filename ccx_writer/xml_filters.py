# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2015-2016 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/formats/xml_/xml_filters.py,逐行对应移植。
#
# 与原版的差异:
#   - 导入:uc2.formats.generic_filters / uc2.formats.xml_.xml_model
#     -> ccx_writer.generic_filters / ccx_writer.xml_model
#   - XML_Loader.start_element 里属性值的 .strip():见 _PY2_STR_WHITESPACE。
#   - XML_Saver / Advanced_XML_Saver 只服务保存 SVG/XML:保留类(presenter 会
#     实例化它们当 saver),方法删掉,do_save 抛 NotImplementedError,免得
#     AbstractSaver.do_save 的 pass 悄悄写出空文件。
#
# 属性 dict 顺序:原版 attrs._attrs 在 AbstractXMLLoader.startElement 里被重建
# 成 Py2 dict(哈希序),这里再按它的 keys() 顺序填 obj.attrs;Py3 是文档序。
# 下游 svg_translators 对 obj.attrs 只做 `'x' in attrs` / `attrs['x']` / .get,
# 没有遍历,顺序差异不进 sk2 对象树。

from ccx_writer.generic_filters import AbstractXMLLoader, AbstractSaver
from ccx_writer.xml_model import XMLObject, XmlContentText

# Py2 原版对 utf-8 字节串调 str.strip(),只剥 ASCII 空白 ' \t\n\v\f\r'
# (字节串的 isspace;多字节 UTF-8 序列的每个字节都 >= 0x80,不会被剥)。
# Py3 的 str.strip() 还会剥 U+00A0、U+2000..U+200A、U+3000、U+0085、
# U+001C..U+001F 等 Unicode 空白 —— 属性值首尾若有 NBSP/全角空格会与 Py2 不同。
# 显式传字符集复现 Py2 行为。
_PY2_STR_WHITESPACE = ' \t\n\r\x0b\x0c'


class XML_Loader(AbstractXMLLoader):
    name = 'XML_Loader'
    stack = []

    def do_load(self):
        self.stack = []
        self.start_parsing()

    def start_element(self, name, attrs):
        obj = XMLObject()
        obj.tag = name
        if not self.stack:
            self.model = obj
            self.model.id_map = {}

        for item in attrs._attrs.keys():
            # 原版 .strip();Py2 字节串语义,见 _PY2_STR_WHITESPACE
            obj.attrs[item] = attrs._attrs[item].strip(_PY2_STR_WHITESPACE)

        if 'id' in obj.attrs:
            self.model.id_map[obj.attrs['id']] = obj

        if self.stack: self.stack[-1].childs.append(obj)
        self.stack.append(obj)

    def element_data(self, data):
        self.stack[-1].content += data

    def end_element(self, name):
        if self.stack and self.stack[-1].tag == name:
            self.stack = self.stack[:-1]


class Advanced_XML_Loader(XML_Loader):
    name = 'Advanced_XML_Loader'

    def start_element(self, name, attrs):
        name = name[4:] if name.startswith('svg:') else name
        XML_Loader.start_element(self, name, attrs)

    def end_element(self, name):
        name = name[4:] if name.startswith('svg:') else name
        XML_Loader.end_element(self, name)

    def element_data(self, data):
        obj = XmlContentText(data)
        if self.stack: self.stack[-1].childs.append(obj)


class XML_Saver(AbstractSaver):
    name = 'XML_Saver'
    indent = 0

    def do_save(self):
        # 移植版不要:do_save / write_obj / get_obj_attrs(保存 XML;原版往 'wb' 文件写 str,Py3 下需另定编码,不在范围)
        raise NotImplementedError('保存 SVG/XML 不在移植范围:ccx_writer 只把 SVG 读成 sk2')


class Advanced_XML_Saver(XML_Saver):
    name = 'Advanced_XML_Saver'

    # 移植版不要:write_obj(保存 SVG;do_save 已在 XML_Saver 里抛 NotImplementedError)
