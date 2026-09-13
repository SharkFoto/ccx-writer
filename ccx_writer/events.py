# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2011-2017 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/events.py,逐行照搬,代码零改动。
# Py2 -> Py3 逐项核过:callable() 在 3.2+ 仍是内置;`except Exception as e` 两边同语法;
# 频道是模块级 list,emit 遍历 channel[1:](切片副本),接收方在回调里增删不影响本轮。
# 转换链路里没人 connect,emit 只是空转(运行时清单 emit 295 次,无接收方)。

import logging

LOG = logging.getLogger(__name__)

"""
This module provides Qt-like signal-slot functionality
for internal events processing.

Signal arguments:
CONFIG_MODIFIED   attr, value - modified config field
FILTER_INFO       msg, position - info message and progress in range 0.0-1.0
MESSAGES          msg_type, msg - message type and message text

"""

# Signal flags

CANCEL_OPERATION = False

# Signal channels

CONFIG_MODIFIED = ['CONFIG_MODIFIED']
FILTER_INFO = ['FILTER_INFO']
MESSAGES = ['MESSAGES']


def connect(channel, receiver):
    """
    Connects signal receive method
    to provided channel.
    """
    if callable(receiver):
        try:
            channel.append(receiver)
        except Exception as e:
            msg = 'Cannot connect <%s> receiver to <%s> channel. %s'
            LOG.error(msg, receiver, channel, e)


def disconnect(channel, receiver):
    """
    Disconnects signal receive method
    from provided channel.
    """
    if callable(receiver):
        try:
            channel.remove(receiver)
        except Exception as e:
            msg = 'Cannot disconnect <%s> receiver from <%s> channel. %s'
            LOG.error(msg, receiver, channel, e)


def emit(channel, *args):
    """
    Sends signal to all receivers in channel.
    """
    for receiver in channel[1:]:
        try:
            if callable(receiver):
                receiver(*args)
        except Exception as e:
            msg = 'Error calling <%s> receiver with %s %s'
            LOG.error(msg, receiver, args, e)
            continue


def clean_channel(channel):
    """
    Cleans channel queue.
    """
    name = channel[0]
    channel[:] = []
    channel.append(name)


def clean_all_channels():
    """
    Cleans all channels.
    """
    for item in (CONFIG_MODIFIED, MESSAGES, FILTER_INFO):
        clean_channel(item)
