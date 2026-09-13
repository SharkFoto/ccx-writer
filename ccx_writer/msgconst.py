# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2012 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/msgconst.py,逐行照搬,纯常量表。
# 模块映射表里没有它,但 generic / generic_filters / fsutils 都
# from uc2 import msgconst(只取 OK/INFO/WARNING/ERROR 当事件参数),
# 所以按同样的平铺规则补成 ccx_writer.msgconst。无 Py2/Py3 差异。


JOB = 0
OK = 1
INFO = 2
WARNING = 3
ERROR = 4
STOP = 5

MESSAGES = {
    JOB: 'JOB',
    OK: 'OK',
    INFO: 'INFO',
    WARNING: 'WARNING',
    ERROR: 'ERROR',
    STOP: 'STOP',
}

MAX_LEN = max(*[len(val) for val in MESSAGES.values()])
