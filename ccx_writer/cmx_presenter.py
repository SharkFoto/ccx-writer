# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(写出侧)
#  Copyright (C) 2019 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

import errno
import logging
import struct
from io import BytesIO

from ccx_writer import cmx_model, cmx_from_sk2
from ccx_writer.cmx_config import CMX_Config

LOG = logging.getLogger(__name__)

# 原 uc2const.CMX,取值照抄('cmx')。uc2const 整个文件 601 行,
# 写出链路只要这一个格式 id(cmx_saver 用它判断「已经是 CMX 就别再转」)。
CMX = 'cmx'


# --------------------------------------------------------- 原版基类的写出子集
#
# 原版这一层是三个文件:
#   uc2.formats.generic.ModelPresenter / BinaryModelPresenter  —— presenter
#   uc2.formats.generic_filters.AbstractSaver  —— 开文件、驱动 update + do_save
#   uc2.formats.cmx.cmx_filters.CmxSaver       —— do_save 一行:model.save(self)
# 合计 500 多行,里面读取侧(load / parse / readbyte…)、事件广播
# (events.emit)、i18n(`_()`)、doc_dir 缓存目录清理都不在写出链路上,
# 而 cmx_filters.py 按移植范围清单整个文件不移植 —— 所以把写出真正
# 走到的那点东西收在这里。方法名与语句顺序保持原样,便于和原版逐行对照。

class CmxSaver(object):
    name = 'CMX_Saver'

    presenter = None
    config = None

    fileptr = None

    model = None

    def save(self, presenter, path=None, fileptr=None):
        self.presenter = presenter
        self.config = self.presenter.config
        self.model = presenter.model
        if path:
            # 原版是 uc2.utils.fsutils.get_fileptr(path, True),
            # 内部就是 open(path, 'wb') 外加一层 py2 的路径编码处理。
            self.fileptr = open(path, 'wb')
        elif fileptr:
            self.fileptr = fileptr
        else:
            msg = 'There is no file for writting'  # 原版的拼写,照抄
            raise IOError(errno.ENODATA, msg, '')

        self.presenter.update()
        try:
            self.do_save()
        except Exception as e:
            LOG.error('Error saving file content %s', e)
            raise
        self.fileptr.close()
        self.fileptr = None

    def do_save(self):
        if self.config.uc2_compat:
            self.model.save(self)
            return
        # 修复 #13:压缩版(CDRX)最外层 RIFF 长度字段写的是**未压缩**总长 ——
        # CdrxPack.get_chunk_size 返回子块未压缩长度之和,根块据此填长度。
        # 不能直接改 get_chunk_size:它同时参与索引表偏移的计算,而 CorelDRAW
        # 真机认的正是现在这套偏移。所以只在最终落盘时回填最外层那 4 个字节。
        # 未压缩的 CMX1 本来就对,回填是空操作。
        real, buf = self.fileptr, BytesIO()
        self.fileptr = buf
        try:
            self.model.save(self)
        finally:
            self.fileptr = real
        data = bytearray(buf.getvalue())
        if data[:4] in (b'RIFF', b'RIFX'):
            struct.pack_into('>I' if data[:4] == b'RIFX' else '<I', data, 4, len(data) - 8)
        self.fileptr.write(bytes(data))

    def write(self, data):
        self.fileptr.write(data)


class BinaryModelPresenter(object):
    cid = 0
    config = None
    doc_file = ''
    model = None

    saver = None
    obj_num = 0

    def update(self, action=False):
        if self.model is not None:
            self.obj_num = self.model.count() + 1
            try:
                self.model.config = self.config
                self.model.do_update(self, action)
            except Exception as e:
                LOG.error('Error updating document model')
                LOG.exception(e)
                raise

    def save(self, filename=None, fileptr=None):
        if filename:
            self.doc_file = filename
        elif not fileptr:
            msg = 'Error while saving: No file object'
            raise IOError(msg)

        try:
            self.saver.save(self, filename, fileptr)
        except Exception as e:
            LOG.error('Error while saving %s', filename)
            LOG.exception(e)
            raise

    def close(self):
        self.doc_file = ''
        if self.model is not None:
            self.model.destroy()
        self.model = None
        # 原版后面还有两段,移植版不要:一段是 send_ok 的日志文案(要先把
        # filename 按 py2 的 unicode 转 utf-8),一段是 doc_dir 缓存目录清理
        # —— cmx 的 doc_dir 恒为 '',那段是死代码。

    # 读取侧,移植版不要:ModelPresenter.load


# ------------------------------------------------------------------ 本体

class CMX_Presenter(BinaryModelPresenter):
    cid = CMX

    config = None
    doc_file = ''
    model = None

    def __init__(self, appdata, cnf=None):
        cnf = cnf or {}
        self.config = CMX_Config()
        # 用户偏好文件,移植版不要(CMX_Config 已不是 XmlConfigParser):
        #   config_file = os.path.join(appdata.app_config_dir, 'cmx_config.xml')
        #   self.config.load(config_file)
        self.config.update(cnf)
        self.appdata = appdata
        # 读取侧,移植版不要:self.loader = cmx_filters.CmxLoader()
        self.saver = CmxSaver()
        self.new()

    def new(self):
        self.model = cmx_model.CmxRoot(self.config)

    def translate_from_sk2(self, sk2_doc):
        cmx_from_sk2.SK2_to_CMX_Translator().translate(sk2_doc, self)

    # 读取侧,移植版不要:translate_to_sk2(cmx_to_sk2.CMX_to_SK2_Translator)
