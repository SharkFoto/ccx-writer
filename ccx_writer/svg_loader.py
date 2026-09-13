# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2016 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/formats/svg/__init__.py,逐行对应移植(包 __init__ 平铺成模块 svg_loader)。
#
# 与原版的差异:
#   - from xml.etree import cElementTree -> from xml.etree import ElementTree
#     (cElementTree 3.9 已删;Py3 的 ElementTree 自动用 C 加速器,底层同是 expat)。
#     check_svg 只取第一个 'start' 事件:两边的 iterparse 都是 16KB 一块喂 expat、
#     先把出错前已产生的事件吐完再抛 ParseError,所以「根元素之后才有语法错」的文件
#     两边都能拿到根标签。
#   - 其余导入改成 ccx_writer 下的绝对导入。
#   - svg_saver(sk2 -> SVG 保存)删掉,连带只被它用到的 uc2const 导入。

from xml.etree import ElementTree

# 移植版不要:from uc2 import uc2const(只被 svg_saver 使用)
from ccx_writer.sk2_presenter import SK2_Presenter
from ccx_writer.svg_presenter import SVG_Presenter
from ccx_writer.mixutils import merge_cnf
from ccx_writer.fsutils import get_fileptr


def svg_loader(appdata, filename=None, fileptr=None,
               translate=True, cnf=None, **kw):
    cnf = merge_cnf(cnf, kw)
    svg_doc = SVG_Presenter(appdata, cnf)
    svg_doc.load(filename, fileptr)
    if translate:
        sk2_doc = SK2_Presenter(appdata, cnf)
        if filename:
            sk2_doc.doc_file = filename
        svg_doc.translate_to_sk2(sk2_doc)
        svg_doc.close()
        return sk2_doc
    return svg_doc


# 移植版不要:svg_saver(sk2 -> SVG 保存)


def check_svg(path):
    tag = None
    fileptr = get_fileptr(path)
    try:
        for event, el in ElementTree.iterparse(fileptr, ('start',)):
            tag = el.tag
            break
    except ElementTree.ParseError:
        pass
    finally:
        fileptr.close()
    return tag == '{http://www.w3.org/2000/svg}svg' or tag == 'svg'
