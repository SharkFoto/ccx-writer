# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(写出侧)
#  Copyright (C) 2019 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

import logging
import struct

from ccx_writer import _compat as utils
from ccx_writer import _geom as libgeom
from ccx_writer import cmx_const
# 原版:from uc2.formats.generic import BinaryModelObject
# generic.py 是整个 uc2 的模型基类集合(读写共用),写出侧只要 ModelObject /
# BinaryModelObject 的这几个成员,就地内联,不把整包搬过来。

LOG = logging.getLogger(__name__)


class BinaryModelObject(object):
    """原版 `uc2.formats.generic` 里 ModelObject + BinaryModelObject 的
    写出侧子集,成员名与原版一致。
    hex 查看器侧的 update_for_sword / cache_fields 不移植。"""
    cid = 0
    parent = None
    config = None
    childs = []
    chunk = b''  # 原版是 ''(Py2 的 str 就是字节)

    def destroy(self):
        for child in self.childs:
            child.destroy()
        for item in self.__dict__.keys():
            self.__dict__[item] = None

    def update(self):
        pass

    def do_update(self, presenter=None, action=False):
        for child in self.childs:
            child.parent = self
            child.config = self.config
            child.do_update(presenter, action)
        self.update()
        # hex 查看器侧,移植版不要:if action: self.update_for_sword()

    def add(self, child, before=False):
        if before:
            self.childs.insert(0, child)
        else:
            self.childs.append(child)
        child.parent = self
        child.config = self.config

    def add_childs(self, childs, before=False):
        if before:
            self.childs = childs + self.childs
        else:
            self.childs += childs
        for child in childs:
            child.parent = self
            child.config = self.config

    def remove(self, child):
        if child in self.childs:
            self.childs.remove(child)

    def count(self):
        val = len(self.childs)
        for child in self.childs:
            val += child.count()
        return val

    def save(self, saver):
        saver.write(self.chunk)
        for child in self.childs:
            child.save(saver)


class CmxObject(BinaryModelObject):
    toplevel = False
    data = None
    offset = 0

    def get_root(self):
        parent = self
        while not parent.toplevel:
            parent = parent.parent
        return parent

    def get(self, name, default=None):
        return self.data.get(name, default)

    def set(self, name, value):
        self.data[name] = value

    def is_padding(self):
        sz = len(self.chunk)
        return sz > (sz // 2) * 2

    def get_chunk_size(self, recursive=True):
        if recursive:
            return sum([len(self.chunk)] + [item.get_chunk_size()
                                            for item in self.childs])
        return len(self.chunk)

    def get_offset(self):
        offset = 0
        parent = self.parent
        obj = self
        while parent:
            index = parent.childs.index(obj)
            offset += sum([item.get_chunk_size()
                           for item in parent.childs[:index]])
            offset += parent.get_chunk_size(recursive=False)
            obj = parent
            parent = parent.parent if not parent.toplevel else None
        return offset

    def set_defaults(self):
        pass

    # 读取侧,移植版不要:update_from_chunk


class CmxInstruction(CmxObject):
    toplevel = False
    bbox = None
    is_layer = False
    is_page = False

    def __init__(self, config, chunk=None, offset=0, **kwargs):
        self.config = config
        self.offset = offset
        self.childs = []
        self.data = {}
        self.bbox = None

        # 读取侧,移植版不要:if chunk: self.chunk = chunk;
        #   self.data['code'] = self._get_code(chunk[2:4]);
        #   self.update_from_chunk()

        if kwargs:
            self.data.update(kwargs)

    # 读取侧,移植版不要:_get_code

    def _get_code_str(self):
        return utils.py_int2word(self.data['code'], self.config.rifx)

    def get_name(self):
        return cmx_const.INSTR_CODES.get(self.data['code'],
                                         str(self.data['code']))

    def get_bbox(self):
        def _sum_bbox(bbox0, bbox1):
            if bbox0 is None and bbox1 is None:
                return None
            if bbox0 is None:
                return [] + bbox1
            if bbox1 is None:
                return [] + bbox0
            return libgeom.sum_bbox(bbox0, bbox1)
        self.bbox = None
        for child in self.childs:
            self.bbox = _sum_bbox(self.bbox, child.get_bbox())
        return self.bbox

    def resolve(self, name=''):
        sz = '%d' % len(self.chunk)
        offset = hex(self.get_offset())
        name = '[%s]' % self.get_name()
        return len(self.childs) == 0, name, offset  # sz

    def update(self):
        if self.is_padding():
            self.chunk += b'\x00'
        size = len(self.chunk)
        sz = utils.py_int2word(size, self.config.rifx)
        self.chunk = sz + self._get_code_str() + self.chunk[4:]

    # hex 查看器侧,移植版不要:update_for_sword


def _bbox_bytes(config, bbox):
    """BeginPage / BeginGroup 的包围盒,16 字节。

    原版按 UC2 读取侧的布局写 4 x s32。修复 #30:CMX 规范与 libcdr(CMXParser::readBeginPage /
    readBeginGroup -> readBBox -> readCoordinate)在 16 位里都是 4 x s16,后面紧跟页/组的计数字段。
    libcdr 按 s16 读到的是 s32 的高低半字,页面尺寸成了乱值(dev 实测回读 SVG 高 0.03mm,
    栅格化直接失败)。修复版写 4 x s16 再补 8 个零字节,指令总长与原版相同 ——
    规范里这 8 个字节是计数/偏移,原版在那里写的是 s32 的高半字,CorelDRAW 照样打开,
    说明它不依赖这些值。"""
    rifx = config.rifx
    if config.uc2_compat:
        return utils.py2_pack('>iiii' if rifx else '<iiii', *bbox)
    return utils.py2_pack('>hhhh' if rifx else '<hhhh', *bbox) + b'\x00' * 8


class Inst16BeginPage(CmxInstruction):
    is_page = True

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        int2word = utils.py_int2word
        int2dword = utils.py_int2dword
        self.chunk = b'\x00\x00' + int2word(self.data['code'], rifx)
        self.chunk += int2word(self.data['page_number'], rifx)
        self.chunk += int2dword(self.data['flags'], rifx)
        self.chunk += _bbox_bytes(self.config, self.data['bbox'])
        self.chunk += self.data['tail']
        CmxInstruction.update(self)

    # hex 查看器侧,移植版不要:update_for_sword


class Inst16BeginLayer(CmxInstruction):
    is_layer = True

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        int2word = utils.py_int2word
        int2dword = utils.py_int2dword
        self.chunk = b'\x00\x00' + int2word(self.data['code'], rifx)
        self.chunk += int2word(self.data['page_number'], rifx)
        self.chunk += int2word(self.data['layer_number'], rifx)
        self.chunk += int2dword(self.data['flags'], rifx)
        self.chunk += int2dword(self.data['tally'], rifx)
        # 文本编码(移植版唯一的语义变更):原版把 layer_name 直接拼进 chunk、
        # 用 len(str) 当长度字段。Py3 下文本必须显式编码一次,长度用编码后的
        # 字节数;ASCII 图层名与原版逐字节一致,非 ASCII 是修了 Py2 跑不到的分支。
        layer_name = utils.as_bytes(self.data['layer_name'])
        self.chunk += int2word(len(layer_name), rifx)
        self.chunk += layer_name + self.data['tail']
        CmxInstruction.update(self)

    # hex 查看器侧,移植版不要:update_for_sword


class Inst16BeginGroup(CmxInstruction):
    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        int2word = utils.py_int2word
        self.chunk = b'\x00\x00' + int2word(self.data['code'], rifx)
        self.chunk += _bbox_bytes(self.config, self.data['bbox']) + self.data['tail']
        CmxInstruction.update(self)

    # hex 查看器侧,移植版不要:update_for_sword


class Inst16JumpAbsolute(CmxInstruction):
    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        pos = self.get_offset()
        jump = self.data['jump'] = len(self.chunk) + pos
        data = self.chunk[8:]
        self.chunk = b'\x08\x00\x6f\x00'
        self.chunk += utils.py_int2dword(jump, rifx) + data

    # hex 查看器侧,移植版不要:update_for_sword


class Inst16PolyCurve(CmxInstruction):
    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        int2word = utils.py_int2word
        self.chunk = b'\x00\x00' + int2word(self.data['code'], rifx)
        self.chunk += utils.py_int2byte(self.data['style_flags'])
        skip = False
        flags = self.data['style_flags']
        # FILL
        if flags & cmx_const.INSTR_FILL_FLAG:
            self.chunk += int2word(self.data['fill_type'], rifx)
            if self.data['fill_type'] == cmx_const.INSTR_FILL_EMPTY:
                pass
            elif self.data['fill_type'] == cmx_const.INSTR_FILL_UNIFORM:
                # (color, screen)
                sig = '>hh' if rifx else '<hh'
                self.chunk += struct.pack(sig, *self.data['fill'])
            elif self.data['fill_type'] == cmx_const.INSTR_FILL_FOUNTAIN:
                sig = '>hhhihhhh' if rifx else '<hhhihhhh'
                self.chunk += struct.pack(sig, *self.data['fill'])
                sig = '>hh' if rifx else '<hh'
                for item in self.data['steps']:
                    self.chunk += struct.pack(sig, *item)
            else:
                skip = True

        if not skip:
            # OUTLINE
            if flags & cmx_const.INSTR_STROKE_FLAG:
                self.chunk += int2word(self.data['outline'], rifx)

            if not flags >= cmx_const.INSTR_LENS_FLAG:
                # POINTS
                self.chunk += int2word(len(self.data['points']), rifx)
                for point in self.data['points']:
                    sig = '>hh' if rifx else '<hh'
                    self.chunk += struct.pack(sig, *point)
                # NODES
                self.chunk += struct.pack('B' * len(self.data['nodes']),
                                          *self.data['nodes'])
                # BBOX
                sig = '>hhhh' if rifx else '<hhhh'
                self.chunk += utils.py2_pack(sig, *self.data['bbox'])

        self.chunk += self.data['tail']
        CmxInstruction.update(self)

    # hex 查看器侧,移植版不要:update_for_sword

    def get_bbox(self):
        bbox = self.data.get('bbox')
        return list(bbox) if bbox else None

INSTR_16bit = {
    cmx_const.BEGIN_PAGE: Inst16BeginPage,
    cmx_const.BEGIN_LAYER: Inst16BeginLayer,
    cmx_const.BEGIN_GROUP: Inst16BeginGroup,
    cmx_const.POLYCURVE: Inst16PolyCurve,
    cmx_const.JUMP_ABSOLUTE: Inst16JumpAbsolute,
}

INSTR_32bit = {}


def make_instruction(config, chunk=None, offset=0, identifier=None, **kwargs):
    instructions = INSTR_16bit if config.v16bit else INSTR_32bit
    # 读取侧,移植版不要:if chunk is not None: identifier = 从 chunk[2:4] 解析
    # 注意:这里**保留**原版「未命中回退到 CmxInstruction」的行为,不 raise ——
    # 写出侧的 EndPage/EndLayer/EndGroup 本来就走基类(只写 4 字节的
    # size+code,没有 payload),raise 会直接打断写出链路。
    cls = instructions.get(identifier, CmxInstruction)
    kwargs['code'] = identifier
    return cls(config, chunk, offset, **kwargs)
