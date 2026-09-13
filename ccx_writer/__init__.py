# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(写出侧)
#  Copyright (C) 2019 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。


from ccx_writer.cmx_presenter import CMX_Presenter, CMX

# 读取侧,移植版不要的导入:cmx_const(check_cmx 的签名常量)、
# SK2_Presenter(cmx_loader 的产物)、fsutils.get_fileptr(check_cmx 读文件)。


def merge_cnf(cnf=None, kw=None):
    # 原 uc2.utils.mixutils.merge_cnf,四行照搬。mixutils 剩下的是日志配置
    # 和终端彩色输出,跟写出链路无关,不移植。
    cnf = cnf or {}
    if kw:
        cnf.update(kw)
    return cnf


# 读取侧,移植版不要:cmx_loader


def cmx_saver(sk2_doc, filename=None, fileptr=None,
              translate=True, cnf=None, **kw):
    cnf = merge_cnf(cnf, kw)
    if sk2_doc.cid == CMX:
        translate = False
    if translate:
        cmx_doc = CMX_Presenter(sk2_doc.appdata, cnf)
        cmx_doc.translate_from_sk2(sk2_doc)
        cmx_doc.save(filename, fileptr)
        cmx_doc.close()
    else:
        sk2_doc.save(filename, fileptr)


# 读取侧,移植版不要:check_cmx(RIFF/CMX 签名嗅探,只在 load 时用)
