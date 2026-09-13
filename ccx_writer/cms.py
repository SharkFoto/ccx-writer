# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2011-2017 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 原 uc2/cms/__init__.py,只移植运行时清单里真正执行到的四个纯函数:
#   hexcolor_to_rgb(svg_utils.parse_svg_color)、hexcolor_to_rgba(sk2_model 图层色)、
#   val_255 / val_100(cmx_from_sk2._add_color)。它们没有调用本模块的其他函数。
# 其余全是基于 lcms(C 扩展 libcms)的色彩管理,移植版不带 lcms:
#   文档对象上的 cms(appdata.app.default_cms)换成下面的 CmsStub,方法一律抛 NotImplementedError。
#
# 与原版的差异:
#   - round() -> _compat.py2round():Py3 内置 round 是银行家舍入(round(0.5) == 0),
#     Py2 是四舍五入远离零;val_255 / val_100 的 int(round(...)) 必须用 Py2 语义。
#   - int(x, 0x10) -> _py2_int(x, 0x10):Py3 的 int() 比 Py2 宽松两处(见该函数),
#     hexcolor_to_rgb 的最后一段 hexcolor[5:] 不定长,畸形颜色串会走到差异上;
#     parse_svg_color 靠 except 把解析失败回落成黑色,宽松一点就会变成别的颜色。
#   - 审查修正:hexcolor_to_rgb / hexcolor_to_rgba 先把 str 编成 utf-8 字节再 len / 切片 / int,
#     复现 Py2 字节串语义(见 _py2_bytes)。原移植按 unicode 语义做,非 ASCII 的
#     Unicode 空白 / 十进制数字会被 Py3 int(str) 吃掉,与 Py2 结果不同。
#   - 除法 `/ 255.0` 本来就是浮点除法,保持不变。

# 移植版不要:import copy / from copy import deepcopy(只被下面删掉的函数使用)

# 移植版不要:import libcms(lcms C 扩展,色彩管理不移植)

from ccx_writer import uc2const
from ccx_writer.uc2const import COLOR_RGB, COLOR_CMYK, COLOR_LAB, COLOR_GRAY, \
    COLOR_SPOT, COLOR_DISPLAY, COLOR_REG
# 移植版不要:from uc2.uc2const import IMAGE_MONO, ... IMAGE_TO_COLOR(只服务位图色彩变换)
# 移植版不要:from uc2.utils import fsutils(只服务 get_profile_name / get_profile_info / get_profile_descr)
from ccx_writer._compat import py2round

CS = [COLOR_RGB, COLOR_CMYK, COLOR_LAB, COLOR_GRAY]


# Py2 字节串的 C isspace(C locale):int() / strtol 只认这 6 个空白
_PY2_C_SPACE = b' \t\n\r\x0b\x0c'


def _py2_bytes(hexcolor):
    """审查修正:Py2 里传进来的颜色串是 utf-8 **字节串**,不是 unicode。

    generic_filters.AbstractXMLLoader.startElement / characters 把 expat 给的
    unicode 属性值和文本全部 encode('utf-8') 过(svg_utils / xml_filters 的移植
    也按字节串语义处理);layer_color 等是 Py2 的 str 字面量。所以 len()、切片、
    int() 都必须在 utf-8 字节上做 —— 否则 '#ff0000\\u00a0'(尾随 NBSP)、
    '#\\u0661\\u0662\\u0663'(阿拉伯数字)、全角数字、U+3000 在 Py3 的 int(str) 里
    被当成空白 / 十进制数字解析成功,而 Py2 字节串必然 ValueError、
    parse_svg_color 回落成黑色。
    """
    return hexcolor.encode('utf-8') if isinstance(hexcolor, str) else hexcolor


def _py2_int(x, base):
    """Py2 的 int(str, base)(x 是字节串;移植新增)。

    Py2:int_new 查内嵌 NUL -> PyInt_FromString -> PyOS_strtol(C isspace)。
    Py3 的 int(bytes, base) 与之只有两处不同:
      1. 下划线:Py3.6+(PEP 515)接受数字之间 / 0x 之后的单个 '_'(b'0f_0' -> 240),
         Py2 一律 ValueError。
      2. 符号后的空白:Py2 的 PyOS_strtoul(以及溢出时的 PyLong_FromString)在符号之后
         还会再跳一次空白(b'-\\tf' -> -15),Py3 不跳,ValueError。
    其余(首尾 ASCII 空白、正负号、0x 前缀、大小写、超长数字、内嵌 NUL、>= 0x80 的字节)
    两边一致。
    """
    if b'_' in x:
        raise ValueError('invalid literal for int() with base %d: %r' % (base, x))
    s = x.lstrip(_PY2_C_SPACE)
    if s[:1] in (b'+', b'-'):
        return int(s[:1] + s[1:].lstrip(_PY2_C_SPACE), base)
    return int(x, base)


# 移植版不要:get_registration_black(色彩管理 / SPOT 色,前端不执行)


# 移植版不要:color_to_spot(色彩管理 / SPOT 色,前端不执行)


def val_100(vals):
    return [int(py2round(100 * x)) for x in vals]


def val_255(vals):
    return [int(py2round(255 * x)) for x in vals]


# 移植版不要:val_255_to_dec(只服务读取侧 / 其他格式)


# 移植版不要:val_100_to_dec(只服务读取侧 / 其他格式)


# 移植版不要:mix_vals(ColorManager.mix_colors 用,前端不执行)


# 移植版不要:mix_lists(ColorManager.mix_colors 用,前端不执行)


# 移植版不要:rgb_to_hexcolor(只服务 SK2 -> SVG 保存)


# 移植版不要:rgba_to_hexcolor(只服务保存 / GUI)


# 移植版不要:cmyk_to_hexcolor(只服务保存 / GUI)


def hexcolor_to_rgb(hexcolor):
    """Converts hex color string as a list of float values.
    For example: #ff00ff => [1.0, 0.0, 1.0]
    """
    # 审查修正:按 Py2 字节串做 len / 切片(bytes 取下标得 int,故用 [i:i + 1])
    hexcolor = _py2_bytes(hexcolor)
    if len(hexcolor) == 4:
        vals = (hexcolor[1:2] * 2, hexcolor[2:3] * 2, hexcolor[3:4] * 2)
    else:
        vals = (hexcolor[1:3], hexcolor[3:5], hexcolor[5:])
    return [_py2_int(x, 0x10) / 255.0 for x in vals]


def hexcolor_to_rgba(hexcolor):
    """Converts hex color string as a list of float values.
    For example: #ff00ffff => [1.0, 0.0, 1.0, 1.0]
    """
    hexcolor = _py2_bytes(hexcolor)  # 审查修正:Py2 字节串语义,见 _py2_bytes
    vals = (b'00', b'00', b'00', b'ff')
    if len(hexcolor) == 7:
        vals = (hexcolor[1:3], hexcolor[3:5], hexcolor[5:], b'ff')
    elif len(hexcolor) == 9:
        vals = (hexcolor[1:3], hexcolor[3:5], hexcolor[5:7], hexcolor[7:])
    return [_py2_int(x, 0x10) / 255.0 for x in vals]


# 移植版不要:hexcolor_to_cmyk(前端不执行)


# 移植版不要:gdk_hexcolor_to_rgb(GTK GUI)


# 移植版不要:rgb_to_gdk_hexcolor(GTK GUI)


# 移植版不要:cmyk_to_rgb(无 lcms 时的简易色彩变换,前端不执行)


# 移植版不要:rgb_to_cmyk(无 lcms 时的简易色彩变换,前端不执行)


# 移植版不要:gray_to_cmyk(简易色彩变换 / color_to_spot 用,前端不执行)


# 移植版不要:gray_to_rgb(简易色彩变换,前端不执行)


# 移植版不要:rgb_to_gray(简易色彩变换,前端不执行)


# 移植版不要:linear_to_rgb(Lab 变换,前端不执行)


# 移植版不要:lab_to_rgb(Lab 变换,前端不执行)


# 移植版不要:xyz_to_lab(Lab 变换,前端不执行)


# 移植版不要:rgb_to_linear(Lab 变换,前端不执行)


# 移植版不要:rgb_to_lab(Lab 变换,前端不执行)


# 移植版不要:do_simple_transform(无 lcms 时的简易色彩变换,前端不执行)


# 移植版不要:colorb(python-lcms COLORB 模拟,只服务 lcms 变换)


# 移植版不要:decode_colorb(只服务 lcms 变换)


# 移植版不要:verbose_color(GUI 显示用)


# 移植版不要:get_profile_name(读 ICC 配置文件,依赖 libcms)


# 移植版不要:get_profile_info(读 ICC 配置文件,依赖 libcms)


# 移植版不要:get_profile_descr(读 ICC 配置文件,依赖 libcms)


# 移植版不要:ColorManager(lcms 色彩管理器;文档上的 cms 由下面的 CmsStub 顶替)


class CmsStub(object):
    """移植新增:顶替 appdata.app.default_cms(原版 AppColorManager -> ColorManager)。

    SVG -> sk2 前端与 CMX 写出在运行时清单里一次都没调用文档 cms 的方法:SVG 颜色
    只会解析成 RGB / CMYK,cmx_from_sk2._add_color 走 val_255 / val_100 两个分支。
    只有 SPOT / Lab / Gray 颜色才会落到 get_rgb_color255 —— 那需要 lcms,移植版不带,
    明确抛错而不是悄悄给出与原版不同的颜色。方法名与 ColorManager 的公开接口一一对应。
    """

    def _unsupported(self, name):
        raise NotImplementedError(
            '色彩管理不支持:ccx_writer 不带 lcms,文档 cms 只是桩(调用了 %s)' % name)

    def update(self):
        self._unsupported('update')

    def clear_transforms(self):
        self._unsupported('clear_transforms')

    def get_transform(self, cs_in, cs_out):
        self._unsupported('get_transform')

    def get_proof_transform(self, cs_in):
        self._unsupported('get_proof_transform')

    def do_transform(self, color, cs_in, cs_out):
        self._unsupported('do_transform')

    def do_bitmap_transform(self, img, mode, cs_out=None):
        self._unsupported('do_bitmap_transform')

    def do_proof_transform(self, color, cs_in):
        self._unsupported('do_proof_transform')

    def do_proof_bitmap_transform(self, img):
        self._unsupported('do_proof_bitmap_transform')

    # Color management API
    def get_rgb_color(self, color):
        self._unsupported('get_rgb_color')

    def get_rgb_color255(self, color):
        self._unsupported('get_rgb_color255')

    def get_rgba_color255(self, color):
        self._unsupported('get_rgba_color255')

    def get_cmyk_color(self, color):
        self._unsupported('get_cmyk_color')

    def get_cmyk_color255(self, color):
        self._unsupported('get_cmyk_color255')

    def get_lab_color(self, color):
        self._unsupported('get_lab_color')

    def get_grayscale_color(self, color):
        self._unsupported('get_grayscale_color')

    def get_color(self, color, cs=COLOR_RGB):
        self._unsupported('get_color')

    def mix_colors(self, color0, color1, coef=.5):
        self._unsupported('mix_colors')

    def get_display_color(self, color):
        self._unsupported('get_display_color')

    def get_display_color255(self, color):
        self._unsupported('get_display_color255')

    def convert_image(self, img, outmode, cs_out=None):
        self._unsupported('convert_image')

    def adjust_image(self, img, profilestr):
        self._unsupported('adjust_image')

    def get_display_image(self, img):
        self._unsupported('get_display_image')
