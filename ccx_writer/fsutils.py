# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2003-2021 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/utils/fsutils.py,逐行对应移植。
# 运行时清单实际执行:upath / isfile / uopen / get_fileptr / exists / getsize /
# get_file_extension。
#
# 与原版的差异(全部是 Py2「路径 = utf-8 字节串」模型 -> Py3「路径 = str」模型):
#   - 导入:from uc2 import _, events, msgconst -> 下面的绝对导入(_ 来自 ccx_writer.translator)。
#   - from uc2.utils import system:只用来算 IS_MSW / IS_MAC。system 不在映射表里,
#     把 system.get_os_family() 的判定内联成 platform.system() 与 'Windows' / 'Darwin'
#     比较 —— get_os_family 返回 WINDOWS 当且仅当 platform.system() == 'Windows',结果一致。
#   - HOME:原版 expanduser('~') 后 decode(文件系统编码).encode('utf-8') 得到 utf-8 字节串;
#     Py3 直接用 str。
#   - get_sys_path / get_utf8_path:原版在 unicode 与字节串之间来回编码;Py3 的 os
#     接口吃 str,统一返回 str(传进 bytes 时按原版对应的编码解码)。
#   - upath:`not isinstance(path, unicode)` -> `isinstance(path, bytes)`。
#   - listdir:原版把每个名字 encode('utf8') 成字节串;Py3 保持 str。
#   - uopen 的默认 mode 'rb':Py3 读出来是 bytes,调用方自行处理(与原版 Py2 str 对应)。

import errno
import logging
import os
import platform
import shutil
import sys

from ccx_writer.translator import _
from ccx_writer import events, msgconst
# 原版:from uc2.utils import system(见文件头,内联为 platform.system())

LOG = logging.getLogger(__name__)

# Platform
IS_MSW = platform.system() == 'Windows'
IS_MAC = platform.system() == 'Darwin'

# 原版:os.path.expanduser('~').decode(sys.getfilesystemencoding()).encode('utf-8')
HOME = os.path.expanduser('~')


def expanduser(path=''):
    return HOME + path[1:] if path.startswith('~') else path


def normalize_path(path):
    return os.path.abspath(expanduser(path))


def get_sys_path(path):
    # 原版:非 unicode 先 decode('utf-8'),再 encode(文件系统编码) 成字节串。
    # Py3 的系统路径就是 str。
    if isinstance(path, bytes):
        path = path.decode('utf-8')
    return path


def get_utf8_path(path):
    # 原版:非 unicode 先 decode(文件系统编码),再 encode('utf-8') 成字节串。
    # Py3 统一用 str。
    if isinstance(path, bytes):
        path = path.decode(sys.getfilesystemencoding())
    return path


def upath(path):
    return path.decode('utf8') if isinstance(path, bytes) else path


def isfile(path):
    return os.path.isfile(upath(path))


def isdir(path):
    return os.path.isdir(upath(path))


def uopen(path, mode='rb'):
    return open(upath(path), mode)


def get_fileptr(path, writable=False):
    if not path:
        msg = _('There is no file path')
        raise IOError(errno.ENODATA, msg, '')
    try:
        return uopen(path, 'wb' if writable else 'rb')
    except Exception:
        msg = _('Cannot open %s file for writing') % path \
            if writable else _('Cannot open %s file for reading') % path
        events.emit(events.MESSAGES, msgconst.ERROR, msg)
        LOG.exception(msg)
        raise


def makedirs(path):
    os.makedirs(upath(path))


def lexists(path):
    return os.path.lexists(upath(path))


def exists(path):
    return os.path.exists(upath(path))


def remove(path):
    os.remove(upath(path))


def rename(oldpath, newpath):
    os.rename(upath(oldpath), upath(newpath))


def listdir(path):
    # 原版:[pth.encode('utf8') for pth in ...](utf-8 字节串);Py3 保持 str。
    return [pth for pth in os.listdir(upath(path))]


def copy(src, dest):
    shutil.copy(upath(src), upath(dest))


def getsize(path):
    return os.path.getsize(upath(path))


def rmtree(path):
    shutil.rmtree(upath(path))


def get_file_extension(path):
    """
    Returns file extension without comma.
    """
    ext = os.path.splitext(path)[1]
    ext = ext.lower().replace('.', '')
    return ext


def change_file_extension(path, ext):
    filename = os.path.splitext(path)[0]
    ext = ext.lower().replace('.', '')
    return filename + '.' + ext


def normalize_sys_argv():
    """Converts sys.argv to unicode and translate relative paths as
    absolute ones.
    """
    for item in range(1, len(sys.argv)):
        if not sys.argv[item] or sys.argv[item].startswith('-'):
            continue
        if sys.argv[item].startswith('~'):
            sys.argv[item] = os.path.expanduser(sys.argv[item])
        sys.argv[item] = os.path.abspath(sys.argv[item])
