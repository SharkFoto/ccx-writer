# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(写出侧)
#  Copyright (C) 2019 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原版基类 uc2.utils.config.XmlConfigParser,移植版不要:
# 它只为「从 ~/.config 下的 cmx_config.xml 读用户偏好」而存在(load/save
# 两个方法各自一坨 xml.sax),而且读取实现是 py2 的 `exec code` —— py3
# 连语法都过不了。写出侧只用到下面这几个默认值,加一个 update()。


class CMX_Config(object):
    system_encoding = 'utf16'
    fallback_encoding = 'cp1250'
    rifx = False
    pack = False
    v16bit = True
    v1 = True
    save_preview = True
    preview_size = (96, 96)
    skip_empty = True
    # Step 7:True = 逐位复现 UniConvertor 2.0 原版(含已知缺陷),
    # 只给「与 Py2 原版字节一致」的回归验证用;False(默认)= 修复后的行为。
    uc2_compat = False

    def update(self, cnf=None):
        # 原 XmlConfigParser.update,三行照搬 —— cmx_saver 收到的 cnf/kw
        # (pack / v1 / v16bit 这些)就是靠它落到配置对象上的,不能省。
        cnf = cnf or {}
        for key in cnf.keys():
            setattr(self, key, cnf[key])

    # 读取侧 / 用户偏好文件,移植版不要:XmlConfigParser 的 get / load / save
