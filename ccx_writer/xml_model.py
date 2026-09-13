# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2015-2016 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/formats/xml_/xml_model.py,逐行对应移植。
#
# 与原版的差异只有导入:
#   from uc2.formats.generic import TaggedModelObject -> from ccx_writer.generic import ...
#
# Py2 -> Py3:tag / attrs 键值 / content / text 在 Py2 是 utf-8 字节串(str),
# 移植版是 str(见 generic_filters.AbstractXMLLoader 的注释)。本文件只存取、
# 不做字符串运算;'%d' % len(...) 两边产出相同。


from ccx_writer.generic import TaggedModelObject


class XMLObject(TaggedModelObject):
    """
    Represents generic XML tree object.
    Object tag is stored in 'tag' field.
    Object attributes are in 'attrs' dict.
    'content' field contains object data.
    """
    comments = ''
    attrs = {}
    content = ''

    def __init__(self, tag=''):
        self.childs = []
        self.attrs = {}
        self.comments = ''
        self.content = ''
        self.tag = ''
        if tag: self.tag = tag

    def is_content(self):
        return False

    def resolve(self):
        is_node = len(self.childs)
        info = ''
        if is_node: info = '%d' % (len(self.childs))
        return (not is_node, self.tag, info)


class XmlContentText(XMLObject):
    text = ''

    def __init__(self, text=''):
        self.text = text
        XMLObject.__init__(self, 'spacer')

    def is_content(self): return True
