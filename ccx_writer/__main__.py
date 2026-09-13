# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植
#  Copyright (C) 2026 SharkFoto
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。
"""命令行:python -m ccx_writer IN.svg OUT.cdr|OUT.cmx [--pack | --no-pack]

退出码:0 成功;1 转换失败(原因打到 stderr);2 用法错误;
3 输入含本移植明确不支持的内容(<text> 需先转曲线、<image>)。
服务端应以子进程调用它(进程隔离),而不是 import 进闭源代码。
"""
import argparse
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='ccx_writer',
        description='SVG -> CorelDRAW CCX(.cdr)/ CMX(.cmx)。派生自 UniConvertor 2.0,AGPLv3。')
    ap.add_argument('src', help='输入 SVG')
    ap.add_argument('dst', help='输出 .cdr 或 .cmx')
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument('--pack', dest='pack', action='store_true', default=None,
                     help='zlib 压缩(CDRX)。.cdr 的默认')
    grp.add_argument('--no-pack', dest='pack', action='store_false',
                     help='不压缩(CMX1)。.cmx 的默认;libcdr 只读得回这种')
    args = ap.parse_args(argv)

    from ccx_writer.convert import convert
    try:
        convert(args.src, args.dst, pack=args.pack)
    except NotImplementedError as exc:
        sys.stderr.write('不支持:%s\n' % exc)
        return 3
    except ValueError as exc:
        sys.stderr.write('%s\n' % exc)
        return 2
    except Exception as exc:                            # noqa: BLE001
        sys.stderr.write('转换失败:%s: %s\n' % (type(exc).__name__, exc))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
