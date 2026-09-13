# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(写出侧)
#  Copyright (C) 2019 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

import logging
import struct
import zlib
from io import BytesIO  # Py2 原版:from cStringIO import StringIO

from ccx_writer import _compat as utils
from ccx_writer import cmx_const, cmx_instr

LOG = logging.getLogger(__name__)


class CmxRiffElement(cmx_instr.CmxObject):
    def __init__(self, config, chunk=None, offset=0, **kwargs):
        self.config = config
        self.offset = offset
        self.childs = []
        self.data = {}

        if chunk:
            self.chunk = chunk
            self.data['identifier'] = chunk[:4]
            if not self.is_leaf():
                self.data['name'] = chunk[8:12]
            # 读取侧,移植版不要:self.update_from_chunk()
        else:
            self.data['identifier'] = cmx_const.LIST_ID
            self.set_defaults()

        if kwargs:
            self.data.update(kwargs)

    def update_from_kwargs(self, **kwargs):
        self.data.update(kwargs)
        self.update()

    def is_leaf(self):
        return self.data['identifier'] not in cmx_const.LIST_IDS

    def get_name(self):
        return self.data.get('name', self.data['identifier'])

    def get_child_by_name(self, name):
        for item in self.childs:
            if item.get_name() == name:
                return item
        return None

    def get_chunk_offset(self):
        chunk = self
        offset = 0
        while not chunk.toplevel:
            childs = chunk.parent.childs
            index = childs.index(chunk)
            offset += sum([item.get_chunk_size() for item in childs[:index]])
            offset += len(chunk.parent.chunk)
            chunk = chunk.parent
        return offset

    def update(self):
        size = self.get_chunk_size() - 8
        sz = utils.py_int2dword(size, self.config.rifx)
        self.chunk = self.data['identifier'] + sz + self.chunk[8:]
        if self.is_leaf() and self.is_padding():
            self.chunk += b'\x00'

    def _get_icon(self):
        icon_map = {
            b'ccmm': 'gtk-select-color',
            b'DISP': 'gtk-missing-image',
            b'page': 'gtk-page-setup',
            b'pack': 'gtk-paste',
        }
        if self.is_leaf():
            return icon_map.get(self.data['identifier'], 'gtk-dnd')
        return False

    def resolve(self, name=''):
        sz = '%d' % self.get_chunk_size()
        offset = hex(self.get_offset())
        name = '<%s>' % self.get_name()
        return self._get_icon(), name, offset, sz

    # hex 查看器,移植版不要:update_for_sword / cache_fields


class CmxList(CmxRiffElement):
    chunk_map = None

    def __init__(self, config, chunk=None, offset=0, **kwargs):
        CmxRiffElement.__init__(self, config, chunk, offset, **kwargs)

    def update_map(self):
        self.chunk_map = {}
        for child in self.childs:
            self.chunk_map[child.get_name()] = child

    def update(self):
        self.chunk = cmx_const.LIST_ID + b'\x00' * 4
        self.chunk += self.data['name']
        CmxRiffElement.update(self)
        self.update_map()


class CmxInfoElement(CmxRiffElement):
    def __init__(self, config, chunk=None, offset=0, **kwargs):
        CmxRiffElement.__init__(self, config, chunk, offset, **kwargs)

    def set_defaults(self):
        self.data['identifier'] = cmx_const.IKEY_ID
        self.data['text'] = ''

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        self.chunk = self.data['identifier'] + b'\x00' * 4
        # 移植版唯一的语义变更:文本显式编码一次,长度字段用编码后的字节数
        text = utils.as_bytes(self.data['text'])
        self.chunk += text
        text_sz = len(text)
        padding = (text_sz // 32 + 1) * 32 - text_sz
        self.chunk += b'\x00' * padding
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxCont(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.CONT_ID
        self.data['file_id'] = cmx_const.CONT_FILE_ID
        self.data['os_type'] = cmx_const.CONT_OS_ID_WIN
        self.data['byte_order'] = cmx_const.CONT_BYTE_ORDER_LE
        self.data['coord_size'] = cmx_const.CONT_COORDSIZE_16BIT \
            if self.config.v16bit else cmx_const.CONT_COORDSIZE_32BIT
        self.data['major'] = cmx_const.CONT_MAJOR_V1 \
            if self.config.v1 else cmx_const.CONT_MAJOR_V2
        self.data['minor'] = cmx_const.CONT_MINOR
        self.data['unit'] = cmx_const.CONT_UNIT_MM
        self.data['factor'] = cmx_const.CONT_FACTOR_MM

        self.data['IndexSection'] = 0
        self.data['InfoSection'] = 0
        self.data['Thumbnail'] = utils.dword2py_int(b'\xff' * 4,
                                                    self.config.rifx)

        self.data['bbox'] = (0, 0, 0, 0)
        self.data['tally'] = 0

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        self.chunk = self.data['identifier'] + b'\x00' * 4
        padding_sz = 32 - len(self.data['file_id'])
        self.chunk += self.data['file_id'] + b'\x00' * padding_sz
        padding_sz = 16 - len(self.data['os_type'])
        self.chunk += self.data['os_type'] + b'\x00' * padding_sz
        self.chunk += self.data['byte_order']
        self.chunk += self.data['coord_size']
        self.chunk += self.data['major']
        self.chunk += self.data['minor']
        self.chunk += self.data['unit']
        self.chunk += self.data['factor']
        self.chunk += b'\x00' * 12
        self.chunk += utils.py_int2dword(self.data['IndexSection'], rifx)
        self.chunk += utils.py_int2dword(self.data['InfoSection'], rifx)
        self.chunk += utils.py_int2dword(self.data['Thumbnail'], rifx)

        sig = '>iiii' if rifx else '<iiii'
        self.chunk += utils.py2_pack(sig, *self.data['bbox'])
        self.chunk += utils.py_int2dword(self.data['tally'], rifx)
        self.chunk += b'\x00' * 64
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxCcmm(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.CCMM_ID
        self.data['dump'] = cmx_const.CCMM_DUMP

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        self.chunk = self.data['identifier'] + b'\x00' * 4
        self.chunk += self.data['dump']
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxDisp(CmxRiffElement):
    def __init__(self, config, chunk=None, offset=0, **kwargs):
        if 'bmp' in kwargs:
            chunk = self.make_chunk_from_bitmap(kwargs.pop('bmp'))
        CmxRiffElement.__init__(self, config, chunk, offset, **kwargs)

    @staticmethod
    def make_chunk_from_bitmap(bitmap_str):
        chunk = cmx_const.DISP_ID + b'\x00' * 4 + b'\x08' + b'\x00' * 3
        chunk += utils.bmp_to_dib(bitmap_str)
        return chunk

    # hex 查看器,移植版不要:update_for_sword


class CmxPage(CmxRiffElement):
    def get_chunk_size(self, recursive=True):
        def _get_recursive_size(el):
            return sum([len(el.chunk)] +
                       [_get_recursive_size(item) for item in el.childs])

        return _get_recursive_size(self) if recursive else 8

    # 读取侧,移植版不要:update_from_chunk

    def set_defaults(self):
        self.data['identifier'] = cmx_const.PAGE_ID

    def update(self):
        self.chunk = self.data['identifier'] + b'\x00' * 4
        CmxRiffElement.update(self)


class CdrxPack(CmxRiffElement):
    # 读取侧,移植版不要:update_from_chunk(内含 zlib.decompress 与子块重建)

    def set_defaults(self):
        self.data['identifier'] = cmx_const.PAGE_ID
        self.data['cpng_flags'] = cmx_const.CPNG_FLAGS

    # hex 查看器,移植版不要:update_for_sword

    def get_chunk_size(self, recursive=True):
        if recursive:
            return sum([item.get_chunk_size() for item in self.childs])
        return 0

    def get_childs_size(self):
        return sum([item.get_chunk_size() for item in self.childs])

    def update_cpng(self):
        stream = BytesIO()
        for child in self.childs:
            child.save(stream)
        self.data['cpng'] = zlib.compress(stream.getvalue())

    def update(self):
        size = self.get_childs_size()
        sz = utils.py_int2dword(size, self.config.rifx)
        self.update_cpng()
        compr_sz = len(self.data['cpng'])
        compr_sz += 1 if compr_sz > (compr_sz // 2) * 2 else 0
        compr_sz = utils.py_int2dword(compr_sz + 12, self.config.rifx)
        self.chunk = self.data['identifier'] + compr_sz + sz + \
                     cmx_const.CPNG_ID + self.data['cpng_flags']
        self.chunk += self.data['cpng']
        self.chunk += b'\x00' if self.is_padding() else b''

    def save(self, saver):
        saver.write(self.chunk)


class CmxRlst(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.RLST_ID
        self.data['rlists'] = []

    def get_rlist(self, index):
        return self.data['rlists'][index] \
            if index < len(self.data['rlists']) else ()

    def add_rlist(self, rlist):
        self.data['rlists'].append(rlist)
        return len(self.data['rlists']) - 1

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        int2word = utils.py_int2word
        self.chunk = self.data['identifier'] + b'\x00' * 4
        self.chunk += int2word(len(self.data['rlists']), rifx)
        sig = '>hhh' if rifx else '<hhh'
        for item in self.data['rlists']:
            self.chunk += struct.pack(sig, *item)
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxRota(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.ROTA_ID
        self.data['arrows'] = [(0, 0)]

    def get_arrows(self, index):
        return self.data['arrows'][index] \
            if index < len(self.data['arrows']) else ()

    def add_arrows(self, arrows):
        if arrows in self.data['arrows']:
            return self.data['arrows'].index(arrows)
        else:
            self.data['arrows'].append(arrows)
            return len(self.data['arrows']) - 1

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        int2word = utils.py_int2word
        self.chunk = self.data['identifier'] + b'\x00' * 4
        self.chunk += int2word(len(self.data['arrows']), rifx)
        sig = '>hh' if rifx else '<hh'
        for item in self.data['arrows']:
            self.chunk += struct.pack(sig, *item)
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxIxlr(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.IXLR_ID
        self.data['layers'] = []

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        self.chunk = self.data['identifier'] + b'\x00' * 4
        sz = len(self.data['layers'])
        self.chunk += utils.py_int2word(sz, rifx)
        self.chunk += utils.py_int2word(self.data['page'], rifx)
        for offset, name in self.data['layers']:
            self.chunk += utils.py_int2dword(offset, rifx)
            # 移植版唯一的语义变更:图层名显式编码一次,长度用编码后的字节数。
            # 幂等 —— 这里拿到的通常已经是 BEGIN_LAYER 编码过的 bytes。
            name = utils.as_bytes(name)
            self.chunk += utils.py_int2word(len(name), rifx)
            self.chunk += name + b'\xff' * 4
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxIxtl(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.IXTL_ID
        self.data['records'] = []

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        self.chunk = self.data['identifier'] + b'\x00' * 4
        rec_sz = self.data['rec_sz']
        rec_sig = {2: 'H', 4: 'I', 8: 'Q'}.get(rec_sz)
        sig = '>' + rec_sig if rifx else '<' + rec_sig
        self.chunk += utils.py_int2word(len(self.data['records']), rifx)
        if not self.config.v1:
            self.chunk += utils.py_int2word(rec_sz, rifx)
        self.chunk += utils.py_int2word(self.data['table_id'], rifx)
        for rec in self.data['records']:
            self.chunk += struct.pack(sig, rec)
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxIxpg(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.IXPG_ID
        self.data['records'] = []

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        self.chunk = self.data['identifier'] + b'\x00' * 4
        rec_sz = self.data['rec_sz']
        # Py2 的 int/int 是地板除,这里的商拿去当 dict 键,必须写 //
        rec_sig = 4 * {2: 'H', 4: 'I', 8: 'Q'}.get(rec_sz // 4)
        sig = '>' + rec_sig if rifx else '<' + rec_sig
        self.chunk += utils.py_int2word(len(self.data['records']), rifx)
        if not self.config.v1:
            self.chunk += utils.py_int2word(rec_sz, rifx)
        for rec in self.data['records']:
            self.chunk += struct.pack(sig, *rec)
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxIxmr(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.IXMR_ID
        self.data['records'] = []

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        self.chunk = self.data['identifier'] + b'\x00' * 4
        sz = len(self.data['records'])
        self.chunk += b'\x01\x00\x18\x00'
        self.chunk += utils.py_int2word(sz, rifx)
        for rec_id, offset in self.data['records']:
            self.chunk += utils.py_int2word(rec_id, rifx)
            self.chunk += utils.py_int2dword(offset, rifx)
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxRclrV1(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.RCLR_ID
        self.data['colors'] = []

    def get_color(self, index):
        return self.data['colors'][index - 1] \
            if index - 1 < len(self.data['colors']) else ()

    def add_color(self, color):
        if color in self.data['colors']:
            return self.data['colors'].index(color) + 1
        else:
            self.data['colors'].append(color)
            return len(self.data['colors'])

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        self.chunk = self.data['identifier'] + b'\x00' * 4
        sz = len(self.data['colors'])
        self.chunk += utils.py_int2word(sz, rifx)
        for model, palette, vals in self.data['colors']:
            self.chunk += utils.py_int2byte(model)
            self.chunk += utils.py_int2byte(palette)
            for val in vals:
                self.chunk += utils.py_int2byte(val)
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxRscrV1(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.RSCR_ID
        # 原版就写作 '\x01\00':后半是八进制转义,等于 \x00,原样保留
        self.data['rec_num'] = b'\x01\00'
        self.data['records'] = cmx_const.RSCR_RECORD

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        self.chunk = self.data['identifier'] + b'\x00' * 4
        self.chunk += self.data['rec_num'] + self.data['records']
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxRdotV1(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.RDOT_ID
        self.data['dashes'] = []

    def get_dashes(self, index):
        return self.data['dashes'][index - 1] \
            if index - 1 < len(self.data['dashes']) else ()

    def add_dashes(self, dashes):
        if dashes in self.data['dashes']:
            return self.data['dashes'].index(dashes) + 1
        else:
            self.data['dashes'].append(dashes)
            return len(self.data['dashes'])

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        int2word = utils.py_int2word
        self.chunk = self.data['identifier'] + b'\x00' * 4
        self.chunk += int2word(len(self.data['dashes']), rifx)
        for item in self.data['dashes']:
            self.chunk += int2word(len(item), rifx)
            self.chunk += b''.join([int2word(val, rifx) for val in item])
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxRpenV1(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.RPEN_ID
        self.data['pens'] = []

    def get_pen(self, index):
        return self.data['pens'][index - 1] \
            if index - 1 < len(self.data['pens']) else ()

    def add_pen(self, pen):
        if pen in self.data['pens']:
            return self.data['pens'].index(pen) + 1
        else:
            self.data['pens'].append(pen)
            return len(self.data['pens'])

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        int2word = utils.py_int2word
        self.chunk = self.data['identifier'] + b'\x00' * 4
        self.chunk += int2word(len(self.data['pens']), rifx)
        for item in self.data['pens']:
            sig = '>Hhih' if rifx else '<Hhih'
            self.chunk += struct.pack(sig, *item[:4])
            if len(item) > 4:
                sig = '>dddddd' if rifx else '<dddddd'
                self.chunk += struct.pack(sig, *item[4])
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxRottV1(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.ROTT_ID
        self.data['linestyles'] = []

    def get_linestyle(self, index):
        return self.data['linestyles'][index - 1] \
            if index - 1 < len(self.data['linestyles']) else ()

    def add_linestyle(self, linestyle):
        if linestyle in self.data['linestyles']:
            return self.data['linestyles'].index(linestyle) + 1
        else:
            self.data['linestyles'].append(linestyle)
            return len(self.data['linestyles'])

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        int2word = utils.py_int2word
        self.chunk = self.data['identifier'] + b'\x00' * 4
        self.chunk += int2word(len(self.data['linestyles']), rifx)
        sig = '>BB' if rifx else '<BB'
        for item in self.data['linestyles']:
            self.chunk += struct.pack(sig, *item)
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxRotlV1(CmxRiffElement):
    def set_defaults(self):
        self.data['identifier'] = cmx_const.ROTL_ID
        self.data['outlines'] = []

    def get_outline(self, index):
        return self.data['outlines'][index - 1] \
            if index - 1 < len(self.data['outlines']) else ()

    def add_outline(self, outline):
        if outline in self.data['outlines']:
            return self.data['outlines'].index(outline) + 1
        else:
            self.data['outlines'].append(outline)
            return len(self.data['outlines'])

    # 读取侧,移植版不要:update_from_chunk

    def update(self):
        rifx = self.config.rifx
        int2word = utils.py_int2word
        self.chunk = self.data['identifier'] + b'\x00' * 4
        self.chunk += int2word(len(self.data['outlines']), rifx)
        sig = '>HHHHHH' if rifx else '<HHHHHH'
        for item in self.data['outlines']:
            self.chunk += struct.pack(sig, *item)
        CmxRiffElement.update(self)

    # hex 查看器,移植版不要:update_for_sword


class CmxRoot(CmxList):
    toplevel = True
    chunk_map = None

    def __init__(self, config, chunk=None, offset=0, root_id=cmx_const.ROOT_ID):
        config.rifx = root_id == cmx_const.ROOTX_ID
        chunk = chunk or self.make_new_doc(config, root_id)
        CmxList.__init__(self, config, chunk, offset)

    def make_new_doc(self, config, root_id):
        chunk = root_id + b'\x00' * 4
        chunk += cmx_const.CDRX_ID if config.pack else cmx_const.CMX_ID
        return chunk

    def update_map(self):
        def _add_chunk(self, chunk):
            if chunk.get_name() == cmx_const.PAGE_ID:
                self.chunk_map['pages'].append([chunk, ])
            elif chunk.get_name() == cmx_const.RLST_ID:
                self.chunk_map['pages'][-1].append(chunk)
            else:
                self.chunk_map[chunk.get_name()] = chunk

        self.chunk_map = {'pages': []}
        for child in self.childs:
            if child.get_name() not in (cmx_const.PACK_ID, cmx_const.INFO_ID):
                _add_chunk(self, child)
            else:
                for item in child.childs:
                    _add_chunk(self, item)

    def update(self):
        CmxList.update(self)
        self.update_map()


GENERIC_CHUNK_MAP = {
    cmx_const.LIST_ID: CmxList,
    cmx_const.CONT_ID: CmxCont,
    cmx_const.CCMM_ID: CmxCcmm,
    cmx_const.DISP_ID: CmxDisp,
    cmx_const.PACK_ID: CdrxPack,
    cmx_const.PAGE_ID: CmxPage,
    cmx_const.RLST_ID: CmxRlst,

    cmx_const.ROTA_ID: CmxRota,

    cmx_const.INDX_ID: CmxList,
    cmx_const.IXLR_ID: CmxIxlr,
    cmx_const.IXTL_ID: CmxIxtl,
    cmx_const.IXPG_ID: CmxIxpg,
    cmx_const.IXMR_ID: CmxIxmr,

    cmx_const.INFO_ID: CmxList,
    cmx_const.IKEY_ID: CmxInfoElement,
    cmx_const.ICMT_ID: CmxInfoElement,
}

V1_CHUNK_MAP = {
    cmx_const.RCLR_ID: CmxRclrV1,
    cmx_const.RSCR_ID: CmxRscrV1,
    cmx_const.RDOT_ID: CmxRdotV1,
    cmx_const.RPEN_ID: CmxRpenV1,
    cmx_const.ROTT_ID: CmxRottV1,
    cmx_const.ROTL_ID: CmxRotlV1,
}

V2_CHUNK_MAP = {
}


def make_cmx_chunk(config, chunk=None, identifier=None, offset=0, **kwargs):
    identifier = chunk[:4] if chunk else identifier

    if identifier in GENERIC_CHUNK_MAP:
        mapping = GENERIC_CHUNK_MAP
    elif config.v1:
        mapping = V1_CHUNK_MAP
    else:
        mapping = V2_CHUNK_MAP
    # 原版这里是 mapping.get(identifier, CmxRiffElement) —— 未命中就静默退回
    # 基类,写出的块结构为空。移植版直接报错,不许写出半成品。
    if identifier not in mapping:
        raise ValueError('Unknown CMX chunk identifier: %r' % (identifier,))
    cls = mapping[identifier]

    if cls == CmxList and chunk is None:
        kwargs['name'] = identifier
    else:
        kwargs['identifier'] = identifier

    return cls(config, chunk, offset, **kwargs)
