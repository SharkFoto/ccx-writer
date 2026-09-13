# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2017 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/utils/mixutils.py,逐行对应移植。转换链路只执行 merge_cnf(运行时清单)。
#
# 与原版的差异:
#   - config_logging:Py2 的 logging.basicConfig 在 filename 为真时直接忽略 stream;
#     Py3(3.3+)只要 kwargs 里同时出现 filename 与 stream 这两个键就抛 ValueError
#     (哪怕 filename=None)。这里按 Py2 语义二选一传参,效果与原版一致。
#
# merge_cnf 与原版一样会原地改调用方传入的 cnf(cnf.update(kw)),照搬。

import logging
import sys


def merge_cnf(cnf=None, kw=None):
    cnf = cnf or {}
    if kw:
        cnf.update(kw)
    return cnf


LOGGING_MAP = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARN': logging.WARN,
    'WARNING': logging.WARN,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}


def config_logging(filepath, level='INFO'):
    level = LOGGING_MAP.get(level.upper(), logging.INFO)
    # Py2:filename 为真 -> FileHandler(filename, filemode),stream 被忽略;
    # 否则 -> StreamHandler(stream)。Py3 不许两个键同时出现,所以拆开传。
    if filepath:
        logging.basicConfig(
            format=' %(levelname)-8s | %(asctime)s | %(name)s --> %(message)s',
            datefmt='%I:%M:%S %p',
            level=level,
            filename=filepath,
            filemode='w',
        )
    else:
        logging.basicConfig(
            format=' %(levelname)-8s | %(asctime)s | %(name)s --> %(message)s',
            datefmt='%I:%M:%S %p',
            level=level,
            stream=sys.stderr,
        )


MAGENTA = '\033[95m'
BLUE = '\033[94m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'


def echo(msg='', newline=True, flush=True, code=''):
    msg = '%s\n' % msg if newline else msg
    msg = '%s%s%s' % (code, msg, ENDC) if code else msg
    sys.stdout.write(msg)
    if flush:
        sys.stdout.flush()
