# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(写出侧)
#  Copyright (C) 2019 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植与修复)
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License
#  as published by the Free Software Foundation, either version 3
#  of the License, or (at your option) any later version.
#
#  发行时应附带 AGPLv3 副本,见本目录的 LICENSE。
"""字节打包助手 —— 原 `uc2/utils/__init__.py` 里 cmx 用到的那一小撮。

原版整个文件 228 行,cmx 只用了这里的十来个函数,其余(base64 id、
时间戳 guid、bmp_to_dib)全是别处的需求,不移植。

Py3 差异:这些函数本来就返回 `struct.pack` 的结果,在 Py2 里是 str、
在 Py3 里是 bytes —— **函数体一个字都不用改**,变的是调用方:
凡是把它们的返回值和字面量拼在一起的地方,字面量必须是 b''。
`byte2py_int` 是唯一例外,见下。
"""
import math
import struct

__all__ = [
    'byte2py_int', 'py_int2byte',
    'word2py_int', 'signed_word2py_int', 'py_int2word', 'py_int2signed_word',
    'dword2py_int', 'signed_dword2py_int', 'py_int2dword',
    'py_int2signed_dword',
    'double2py_float', 'py_float2double',
    'py2round', 'val_255', 'val_100', 'py2_pack', 'as_bytes',
]


def py2round(val):
    """Py2 的 `round()`:四舍五入(half away from zero)。

    ⚠️ **这是会静默改字节的那一类差异。** Py3 的内置 `round()` 用的是
    banker's rounding(half to even):`round(0.5)` 在 Py2 得 1.0、
    在 Py3 得 0。原版 `cms.val_255` 是 `int(round(255 * x))` ——
    只要有颜色分量正好落在 .5 上,移植版就会比原版差 1,而颜色差 1
    不会有任何报错,只会在某天被用户发现。

    所以凡是原版写 `round()` 的地方,移植版一律改调这个函数。

    ⚠️ 不能写成 floor(val + 0.5):val = 0.49999999999999994 时 val + 0.5 在
    double 里舍入成 1.0,得 1;而 Py2 的 round 走 C 的 round(),精确远离零,得 0。
    (100 * 0.004999999999999999 就正好是这个值 —— CMYK 分量会差 1。复核 agent 抓到的。)
    这里先取整数部分再比较小数部分:|val| >= 1 时 val - floor(val) 按 Sterbenz 引理精确,
    |val| < 1 时小数部分就是 val 本身,也精确。
    """
    if val >= 0:
        r = math.floor(val)
        return r + 1 if val - r >= 0.5 else r
    r = math.ceil(val)
    return r - 1 if r - val >= 0.5 else r


def val_255(vals):
    """原版 `uc2.cms.val_255`。用 py2round 而不是内置 round,理由见上。"""
    return [int(py2round(255 * x)) for x in vals]


def val_100(vals):
    """原版 `uc2.cms.val_100`。"""
    return [int(py2round(100 * x)) for x in vals]


def byte2py_int(data):
    """字节 -> int。

    ⚠️ Py2/Py3 的唯一实质差异点。Py2 里 `chunk[i]` 得到长度 1 的 str,
    要 `struct.unpack('B', ...)`;Py3 里 `chunk[i]` **已经是 int**,
    再 unpack 会抛 TypeError。这里两种都吃,以便逐行移植时调用点不必改写。
    """
    if isinstance(data, int):
        return data
    return struct.unpack('B', data)[0]


def py2_pack(sig, *vals):
    """整数格式的 struct.pack,喂 float 时按 Py2 的方式处理。

    ⚠️ Py2 的 `struct.pack('<i', 1.9)` 只发一条 DeprecationWarning,然后
    **朝零截断**成 1;Py3 直接 `struct.error: required argument is not an
    integer`。原版到处把包围盒(浮点)直接丢给 '<iiii',靠的就是这个隐式转换。

    移植版必须显式复现它,否则:要么崩,要么(如果改用 round)与原版差一个
    最低位。朝零截断 == int(),与原版一致。

    CI 里有探针(`py2 struct 探针` 那一步)在真 Py2 上验证这个语义,
    不是靠记忆。
    """
    return struct.pack(sig, *[int(v) if isinstance(v, float) else v
                              for v in vals])


def as_bytes(text):
    """文本 -> bytes,幂等。

    移植版唯一的语义变更就在这里:原版把文本直接拼进 chunk、用 len(str)
    当长度字段,Py2 下非 ASCII 会崩或写错。这里显式编码一次,长度取
    编码后的字节数 —— 对 ASCII 与原版字节一致,对非 ASCII 是修复一个
    Py2 根本跑不到的分支。

    幂等很重要:图层名会经过两个块(BEGIN_LAYER 指令和 IXLR 索引),
    第二次拿到的已经是 bytes,再 .encode() 会 AttributeError。
    """
    return text if isinstance(text, bytes) else text.encode('utf-8')


def py_int2byte(val):
    return struct.pack('B', val)


def word2py_int(data, be=False):
    return struct.unpack('>H' if be else '<H', data)[0]


def signed_word2py_int(data, be=False):
    return struct.unpack('>h' if be else '<h', data)[0]


def py_int2word(val, be=False):
    return struct.pack('>H' if be else '<H', val)


def py_int2signed_word(val, be=False):
    return struct.pack('>h' if be else '<h', val)


def dword2py_int(data, be=False):
    return struct.unpack('>I' if be else '<I', data)[0]


def signed_dword2py_int(data, be=False):
    return struct.unpack('>i' if be else '<i', data)[0]


def py_int2dword(val, be=False):
    return struct.pack('>I' if be else '<I', val)


def py_int2signed_dword(val, be=False):
    return struct.pack('>i' if be else '<i', val)


def double2py_float(data, be=False):
    return struct.unpack('>d' if be else '<d', data)[0]


def py_float2double(val, be=False):
    return struct.pack('>d' if be else '<d', val)
