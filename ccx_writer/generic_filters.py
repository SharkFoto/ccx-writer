# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2013-2017 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/formats/generic_filters.py,逐行对应移植。
#
# 与原版的差异:
#   - 导入:from uc2 import _, events, msgconst, utils /
#     from uc2.utils.fsutils import get_fileptr, getsize -> 下面的绝对导入。
#     utils 只给 AbstractBinaryLoader 用,随它一起不要。
#   - AbstractBinaryLoader 删除(二进制格式读取侧,SVG 前端不走)。
#   - AbstractXMLLoader.startElement / endElement / characters:Py2 的 expat 回调
#     给 unicode,原版在这里编码成 utf-8 字节串(str)再往下传;Py3 的 expat 给
#     str,移植版整条前端统一用 str,所以不编码(见各方法注释)。
#   - AbstractSaver.field_to_str 删除(只给 sk2 文件保存用)。
#
# 文件对象的模式:xml.sax 的 InputSource.setByteStream 要的是二进制流。
# 走路径时 fsutils.get_fileptr(path) 以 'rb' 打开,与之一致;走 fileptr 时
# 调用方也必须传二进制文件对象(Py3 文本模式不支持 seek(-1, 1);而且文本流
# read() 出的 str 会被 pyexpat 一律当 UTF-8,XML 声明里的 encoding 被忽略)。

import errno
import logging
import xml.sax
from xml.sax import handler
from xml.sax.xmlreader import InputSource

from ccx_writer.translator import _
from ccx_writer import events, msgconst
from ccx_writer.fsutils import get_fileptr, getsize

LOG = logging.getLogger(__name__)


class AbstractLoader(object):
    name = 'Abstract Loader'

    presenter = None
    config = None
    model = None

    filepath = ''
    fileptr = None
    position = 0
    file_size = 0

    def __init__(self):
        pass

    def load(self, presenter, path=None, fileptr=None):
        self.presenter = presenter
        self.model = presenter.model
        self.config = self.presenter.config
        if path:
            self.filepath = path
            self.file_size = getsize(path)
            self.fileptr = get_fileptr(path)
        elif fileptr:
            self.fileptr = fileptr
            self.fileptr.seek(-1, 1)
            self.file_size = self.fileptr.tell()
            self.fileptr.seek(0)
        else:
            msg = _('There is no file for reading')
            raise IOError(errno.ENODATA, msg, '')

        try:
            self.init_load()
        except Exception:
            LOG.error('Error loading file content')
            raise

        self.fileptr.close()
        self.position = 0
        return self.model

    def init_load(self):
        self.do_load()

    def do_load(self):
        pass

    def readln(self, strip=True):
        line = self.fileptr.readline()
        if strip:
            line = line.strip()
        return line

    def check_loading(self):
        if self.file_size:
            position = float(self.fileptr.tell()) / float(self.file_size) * 0.95
            if position - self.position > 0.05:
                self.position = position
                self.parsing_msg(position)

    def send_progress_message(self, msg, val):
        events.emit(events.FILTER_INFO, msg, val)

    def parsing_msg(self, val):
        msg = _('Parsing in progress...')
        self.send_progress_message(msg, val)

    def send_ok(self, msg):
        events.emit(events.MESSAGES, msgconst.OK, msg)

    def send_info(self, msg):
        events.emit(events.MESSAGES, msgconst.INFO, msg)

    def send_warning(self, msg):
        events.emit(events.MESSAGES, msgconst.WARNING, msg)

    def send_error(self, msg):
        events.emit(events.MESSAGES, msgconst.ERROR, msg)


# 移植版不要:AbstractBinaryLoader(二进制格式读取侧 readbytes/readbyte/readword…,依赖 uc2.utils;SVG 前端不走)


class AbstractXMLLoader(AbstractLoader, handler.ContentHandler):
    xml_reader = None
    input_source = None

    def init_load(self):
        self.input_source = InputSource()
        self.input_source.setByteStream(self.fileptr)
        self.xml_reader = xml.sax.make_parser()
        self.xml_reader.setContentHandler(self)
        self.xml_reader.setErrorHandler(handler.ErrorHandler())
        self.xml_reader.setEntityResolver(handler.EntityResolver())
        self.xml_reader.setDTDHandler(handler.DTDHandler())
        self.xml_reader.setFeature(handler.feature_external_ges, False)
        self.do_load()

    def start_parsing(self):
        self.xml_reader.parse(self.input_source)

    def startElement(self, name, attrs):
        # Py2 原版:
        #     if isinstance(name, unicode):
        #         name = name.encode('utf-8')
        #         ret = {}
        #         for key,value in attrs._attrs.items():
        #             ret[key.encode('utf-8')] = attrs[key].encode('utf-8')
        #         attrs._attrs = ret
        # Py2 的 expat 回调总是给 unicode,所以这段总会执行:tag 名和属性键值
        # 全变成 utf-8 字节串。Py3 的 expat 给 str,移植版前端统一用 str,
        # 不编码、也不必重建 attrs._attrs(键值内容相同)。
        # 唯一可观察差别:原版重建出的 dict 是 Py2 哈希序,Py3 保持文档序;
        # 下游(XML_Loader.start_element -> obj.attrs)只按键取值,不依赖顺序。
        self.start_element(name, attrs)

    def endElement(self, name):
        # Py2 原版:if isinstance(name, unicode): name = name.encode('utf-8')
        # Py3 的 name 已是 str,不编码
        self.end_element(name)

    def characters(self, data):
        # Py2 原版:if isinstance(data, unicode): data = data.encode('utf-8')
        # Py3 的 data 已是 str,不编码
        self.element_data(data)

    def start_element(self, name, attrs): pass

    def end_element(self, name): pass

    def element_data(self, data): pass


class AbstractSaver(object):
    name = 'Abstract Saver'

    presenter = None
    config = None

    filepath = ''
    fileptr = None
    position = 0
    file_size = 0

    model = None

    def __init__(self):
        pass

    def save(self, presenter, path=None, fileptr=None):
        self.presenter = presenter
        self.config = self.presenter.config
        self.model = presenter.model
        if path:
            self.fileptr = get_fileptr(path, True)
        elif fileptr:
            self.fileptr = fileptr
        else:
            msg = _('There is no file for writting')
            raise IOError(errno.ENODATA, msg, '')

        self.presenter.update()
        self.saving_msg(.01)
        try:
            self.do_save()
        except Exception as e:
            LOG.error('Error saving file content %s', e)
            raise
        self.saving_msg(.99)
        self.fileptr.close()
        self.fileptr = None

    def do_save(self):
        pass

    def writeln(self, line=''):
        self.fileptr.write(line + '\n')

    def write(self, data):
        self.fileptr.write(data)

    # 移植版不要:field_to_str(只给 sk2 文件保存用;另注:其中 val.__str__() 在 Py2 对 float 只留 12 位有效数字)

    def send_progress_message(self, msg, val):
        events.emit(events.FILTER_INFO, msg, val)

    def saving_msg(self, val):
        msg = _('Saving in progress...')
        self.send_progress_message(msg, val)

    def send_ok(self, msg):
        events.emit(events.MESSAGES, msgconst.OK, msg)

    def send_info(self, msg):
        events.emit(events.MESSAGES, msgconst.INFO, msg)

    def send_warning(self, msg):
        events.emit(events.MESSAGES, msgconst.WARNING, msg)

    def send_error(self, msg):
        events.emit(events.MESSAGES, msgconst.ERROR, msg)
