# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(写出侧)
#  Copyright (C) 2019 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

import logging
import math
from copy import deepcopy

from ccx_writer import _compat as utils
from ccx_writer import _geom as libgeom
from ccx_writer import _sk2 as sk2const      # 同时提供 uc2const 的常量
from ccx_writer import cmx_const, cmx_model, cmx_instr
# 原版还从 uc2 取 libimg / cms 和 sk2.crenderer.CairoRenderer:
# cms.val_255 / val_100 由 _compat 提供(内部用 py2round,不是 Py3 的银行家舍入);
# libimg + CairoRenderer 只服务预览,移植版不要,见 make_template。

LOG = logging.getLogger(__name__)
mkinstr = cmx_instr.make_instruction

# ---------------------------------------------------------------- Step 7 修复
# 每个修复都按 cmx_cfg.uc2_compat 分流:
#   uc2_compat=True  -> 逐位复现原版(含缺陷),给「与 Py2 字节一致」的回归验证用
#   uc2_compat=False -> 修复后的行为(默认)
# 编号与 BUGS.md 末节「Step 7 修复清单」对应,每处都写明原版怎么错、为什么这么改。
#
# 单条 PolyCurve 指令的点数上限。
# ⚠️ 16 位 CMX 的指令长度字段是**有符号** s16:libcdr CMXParser::readCommands 用 readS16 读,
# 读到负数就改读一个 S32 当长度(对抗式审查在真 libcdr 上复现:32768–65535 字节的指令会让
# 整页后面的内容丢失)。UC2 自己的读取侧按 u16 读,所以只拿 UC2 对照看不出来。
# 字节数:4(长度+代码)+ 1(style)+ 最多 6(填充)+ 2(描边)+ 2(点数)+ 5n + 8(包围盒)
# + 奇数补 1 <= 32767 -> n <= 6548。留余量取 6540。
POLYCURVE_MAX_POINTS = 6540
# 32 位(修复 #33):4(长度+代码)+ 渲染标签最多 43 + 点表标签 5 + 9n + 包围盒标签 19 + 空标签 3
# + 结束 1 + 奇数补 1 <= 32767 -> n <= 3632。留余量取 3620。
POLYCURVE_MAX_POINTS_32 = 3620
# 修复 #34:上面两个是「单条指令 <= 32767 字节」的装箱上限,只描边的曲线与互不嵌套的子路径照它拆。
# 拆不开的一组(外框 + 它的孔)超过它时,单独写成一条扩展长度的指令(CmxInstruction.update),
# 真正的上限是格式字段:16 位点数字段 u16;32 位点表标签长度 u16 -> 3 + 2 + 9n <= 65535 -> n <= 7281。
# 点表拆成多个标签 libcdr 能读,但 CorelDRAW 只保留最后一个(真机实测 12000 点只剩后 5000 点),不能拆。
POLYCURVE_HARD_POINTS = 65535
POLYCURVE_HARD_POINTS_32 = 7281
INT16_MAX = 32767
INT32_MAX = 2147483647
# 笔宽、虚线元素在 libcdr 里同样按 s16 读(CommonParser::readCoordinate)。
S16_MAX = 32767
# 16 位 CMX 的原生坐标单位(英寸),见 make_template 修复 #28。
NATIVE_UNIT_IN = 0.001

SK2_CAP_MAP = {
    sk2const.CAP_BUTT: cmx_const.CMX_MITER_CAP,
    sk2const.CAP_ROUND: cmx_const.CMX_ROUND_CAP,
    sk2const.CAP_SQUARE: cmx_const.CMX_SQUARE_CAP,
}

SK2_JOIN_MAP = {
    sk2const.JOIN_MITER: cmx_const.CMX_MITER_JOIN,
    sk2const.JOIN_ROUND: cmx_const.CMX_ROUND_JOIN,
    sk2const.JOIN_BEVEL: cmx_const.CMX_BEVEL_JOIN,
}


def _gradient_mean_color(stops):
    """渐变沿轴 [0, 1] 的平均色(色标间线性插值,两端按 pad 延伸)。
    stops: [[offset, [colorspace, vals, alpha, name]], ...]。色彩空间不一致时取第一个色标。"""
    stops = sorted((s for s in stops if s and s[1]), key=lambda s: s[0])
    if not stops:
        return None
    first = stops[0][1]
    if len(stops) == 1 or any(s[1][0] != first[0] or len(s[1][1]) != len(first[1])
                              for s in stops):
        return deepcopy(first)
    pos = [min(1.0, max(0.0, float(s[0]))) for s in stops]
    vals = [s[1][1] for s in stops]
    acc = [pos[0] * v for v in vals[0]]
    for i in range(len(stops) - 1):
        w = (pos[i + 1] - pos[i]) / 2.0
        acc = [a + w * (u + v) for a, u, v in zip(acc, vals[i], vals[i + 1])]
    acc = [a + (1.0 - pos[-1]) * v for a, v in zip(acc, vals[-1])]
    color = deepcopy(first)
    color[1] = [min(1.0, max(0.0, a)) for a in acc]
    return color


class SK2_to_CMX_Translator(object):
    root = None
    cmx_doc = None
    cmx_model = None
    sk2_doc = None
    sk2_model = None
    sk2_mtds = None
    cmx_cfg = None
    coef = 1.0
    rifx = False

    def translate(self, sk2_doc, cmx_doc):
        self.cmx_doc = cmx_doc
        self.cmx_model = self.root = cmx_doc.model
        self.cmx_cfg = cmx_doc.config
        self.sk2_doc = sk2_doc
        self.sk2_model = sk2_doc.model
        self.sk2_mtds = sk2_doc.methods

        self._curves = {}
        self.make_template()
        self.translate_doc()
        self.cmx_doc.update()
        self.add_info()
        self.index_model()
        self.cmx_doc.update()

        self.cmx_doc = None
        self.cmx_model = None
        self.cmx_cfg = None
        self.sk2_doc = None
        self.sk2_model = None
        self.sk2_mtds = None

    # 预览侧(libimg + CairoRenderer/pycairo),移植版不要:_make_preview

    def make_el(self, cmx_id, **kwargs):
        kwargs['identifier'] = cmx_id
        return cmx_model.make_cmx_chunk(self.cmx_cfg, **kwargs)

    def _int2word(self, val):
        return utils.py_int2signed_word(int(val * self.coef), self.rifx)

    def _int2dword(self, val):
        return utils.py_int2signed_dword(int(val * self.coef), self.rifx)

    def _add_color(self, color):
        doc_cms = self.sk2_doc.cms
        rclr = self.cmx_model.chunk_map[b'rclr']
        clr = (5, 5, (0, 0, 0))  # Fallback RGB black
        if color[0] == sk2const.COLOR_RGB:
            model = cmx_const.COLOR_MODELS.index(cmx_const.CMX_RGB)
            palette = cmx_const.COLOR_PALETTES.index('User')
            vals = utils.val_255(color[1])
            clr = (model, palette, vals)
        elif color[0] == sk2const.COLOR_CMYK:
            model = cmx_const.COLOR_MODELS.index(cmx_const.CMX_CMYK)
            palette = cmx_const.COLOR_PALETTES.index('User')
            vals = utils.val_100(color[1])
            clr = (model, palette, vals)
        else:
            model = cmx_const.COLOR_MODELS.index(cmx_const.CMX_RGB)
            palette = cmx_const.COLOR_PALETTES.index('User')
            vals = doc_cms.get_rgb_color255(color)
            clr = (model, palette, vals)
        return rclr.add_color(clr)

    def _add_line_style(self, outline):
        rott = self.cmx_model.chunk_map[b'rott']
        linestyle = (0x01, 0x00)
        if outline:
            spec = 0x02
            join = SK2_JOIN_MAP.get(outline[5], cmx_const.CMX_MITER_JOIN)
            if self.cmx_cfg.uc2_compat:
                cap = SK2_JOIN_MAP.get(outline[4], cmx_const.CMX_MITER_CAP)
                joincap = join << 4 + cap
            else:
                # 修复 #9:原版 cap 查的是 JOIN 表(BUTT=1 被当成 ROUND_JOIN、SQUARE 落默认),
                # 且 join << 4 + cap 实为 join << (4 + cap)。依据是 UC2 自己的读取侧
                # cmx_to_sk2.py:233-235:join = 高 4 位,cap = 低 4 位。
                cap = SK2_CAP_MAP.get(outline[4], cmx_const.CMX_MITER_CAP)
                joincap = (join << 4) | cap
                # 修复 #8:原版 spec 恒为 0x02,从不置虚线位,虚线全部丢失。
                # 读取侧 cmx_to_sk2.py:245:dashes 只在 spec & 0x04 时生效。
                # 16 位:保留实线位(0x06)。CorelDRAW 真机实测只写 0x04 时虚线被忽略、画成实线;
                # 0x06 的虚线导入后转成「组 + 填充曲线」,外观对,但不再是可编辑的虚线轮廓。
                # 32 位(修复 #33):虚线只写 0x04。CorelDRAW 自己导出的 32 位 CMX 就是 0x04、导回可编辑;
                # 同一文件改成 0x06 轮廓变 None(BUGS.md #33 对照实验)。
                if outline[3]:
                    spec = spec | 0x04 if self.cmx_cfg.v16bit else 0x04
            linestyle = (spec, joincap)
        return rott.add_linestyle(linestyle)

    def _add_pen(self, outline):
        rpen = self.cmx_model.chunk_map[b'rpen']
        if self.cmx_cfg.uc2_compat:
            width = int(self.coef * outline[1])
        else:
            # 修复 #4:原版 int() 截断,细线直接变 0 宽(f3a_many 5000 条全灭、
            # f6_hairline 丢两档)。有宽度的描边至少 1 个单位;笔宽字段是 u16,封顶。
            # 审查确认:笔宽在 libcdr 里按 s16 读,u16 封顶会让 32768-65535 读成负数;
            # 量程也已经把笔宽算进去(_max_abs_coord),正常输入不会触顶。
            w = self.coef * outline[1]
            cap = S16_MAX if self.cmx_cfg.v16bit else INT32_MAX
            width = 0 if w <= 0 else min(cap, max(1, int(utils.py2round(w))))
        aspect = 100
        angle = 0
        matrix_flag = 1
        return rpen.add_pen((width, aspect, angle, matrix_flag))

    def _add_dash(self, outline):
        rdot = self.cmx_model.chunk_map[b'rdot']
        if self.cmx_cfg.uc2_compat:
            # Py2 原版的 struct.pack('<H', 2.67) 朝零截断成 2;Py3 直接报错。
            # 原版能写出 "4,2" 这类逗号分隔的虚线(exec 解析成功),兼容模式必须照样写出。
            return rdot.add_dashes([int(v) if isinstance(v, float) else v
                                    for v in outline[3]])
        # 修复 #16 的写出侧:CMX 虚线元素是 u16 整数、单位是线宽倍数(读取侧
        # cmx_to_sk2.py:245 原样取回)。sk2 里是浮点(长度 / 线宽),原版直接喂给
        # '<H' 在 Py2 靠隐式截断、在 Py3 直接报错;原版能跑只是因为前端从来解析不出虚线。
        # 审查确认:0 段不能抬成 1 —— "0 4" 配圆头是点线,抬了就成短划线。源为 0 的保留 0。
        return rdot.add_dashes([0 if v == 0 else max(1, min(S16_MAX, int(utils.py2round(v))))
                                for v in outline[3]])

    def _add_outline(self, outline):
        rotl = self.cmx_model.chunk_map[b'rotl']
        linestyle = self._add_line_style(outline)
        screen = 1
        color = self._add_color(outline[2])
        # 必须是 1(指向 rota 里的 (0,0) 无箭头条目)。CorelDRAW 真机实测(2026-09-13):
        # 改成 0 的开放路径整条被丢掉,实线虚线都一样。
        arrowheads = 1
        pen = self._add_pen(outline)
        dashes = self._add_dash(outline)
        return rotl.add_outline(
            (linestyle, screen, color, arrowheads, pen, dashes))

    def _make_bbox(self, bbox):
        x0, y0, x1, y1 = bbox
        if self.cmx_cfg.uc2_compat:
            return x0 * self.coef, y1 * self.coef, x1 * self.coef, y0 * self.coef
        # 修复 #3:原版交给 '<hhhh' 靠 Py2 的隐式截断(朝零),包围盒可能比内容小。
        # 包围盒只能大不能小:左/下取 floor,右/上取 ceil。
        return (int(math.floor(x0 * self.coef)), int(math.ceil(y1 * self.coef)),
                int(math.ceil(x1 * self.coef)), int(math.floor(y0 * self.coef)))

    def make_template(self):
        self.rifx = self.cmx_cfg.rifx
        cont_obj = self.make_el(cmx_const.CONT_ID)
        self.cmx_model.add(cont_obj)
        if self.cmx_cfg.v16bit:
            # 32 位不写 ccmm(色彩校正块):CorelDRAW 自己的 32 位导出没有它
            self.cmx_model.add(self.make_el(cmx_const.CCMM_ID))
        if self.cmx_cfg.save_preview:
            # 原版在这里塞 DISP 预览块(libimg.generate_preview + CairoRenderer)。
            # 移植版不带 pycairo,save_preview 恒 False;分支保留以便 diff 对齐。
            raise NotImplementedError(
                'DISP preview generation is not ported (needs pycairo)')
        if self.cmx_cfg.pack:
            self.root = self.make_el(cmx_const.PACK_ID)
            self.cmx_model.add(self.root)

        objs = []
        for page in self.sk2_mtds.get_pages():
            self.root.add(self.make_el(cmx_const.PAGE_ID))
            self.root.add(self.make_el(cmx_const.RLST_ID))
            if not self.cmx_cfg.v1 and self.cmx_cfg.v16bit:
                # 32 位只有一个 rlst(CorelDRAW 导出如此);这条原版分支属于从未跑通的 16 位 V2
                self.root.add(self.make_el(cmx_const.RLST_ID))
            for layer in page.childs:
                objs.extend(layer.childs)

        cmx_ids = [cmx_const.ROTL_ID, cmx_const.ROTT_ID, cmx_const.RPEN_ID,
                   cmx_const.RDOT_ID, cmx_const.ROTA_ID, cmx_const.RCLR_ID,
                   cmx_const.RSCR_ID, cmx_const.INDX_ID]
        for cmx_id in cmx_ids:
            self.root.add(self.make_el(cmx_id))
        self.cmx_model.update_map()

        if not self.cmx_cfg.v16bit:
            # 修复 #33:32 位 CMX 的坐标单位固定 1/254000 英寸(libcdr readCoordinate:readS32 / 254000),
            # s32 量程 +-8454 英寸,不需要按内容选单位。cont 头保留默认的 unit 0x23 + factor 1e-7,
            # 与 CorelDRAW 自己的 32 位导出一致。
            if self.cmx_cfg.uc2_compat:
                raise ValueError('兼容模式只有 16 位')
            self.coef = sk2const.pt_to_in * cmx_const.UNITS_PER_IN_32
            return

        self.coef = sk2const.pt_to_in * 1000.0
        factor = 0.001

        if objs and self.cmx_cfg.uc2_compat:
            bbox = [] + objs[0].cache_bbox
            for obj in objs[1:]:
                bbox = libgeom.sum_bbox(bbox, obj.cache_bbox)
            max_value = max([abs(item) for item in bbox])
            frame = 255 * 255 / 2.0
            self.coef = sk2const.pt_to_in * frame / max_value
            factor = max_value / frame
        elif objs:
            # 修复 #1:原版 coef 多乘了 pt_to_in(1/72)、factor 少乘同一个因子。
            # 两者乘积仍是 pt_to_in,所以物理尺寸对,但分辨率被砍 72 倍:
            # 最大坐标恒为 32512.5/72 = 451,A3 上一级坐标 0.48mm,7pt 字碎成色块。
            # 不变量 coef * factor == pt_to_in 必须保持(只改一边整图缩放 72 倍)。
            # 修复 #2:原版 max_value 取 cache_bbox,而 cache_bbox 是 cairo path_extents
            # 的贝塞尔**紧**包围盒(CI 探针实测),控制点可以落在它外面 —— 量程用满时
            # 控制点越出 int16 就会崩。改为取所有将要写出的点(含控制点、笔宽)。
            #
            # 修复 #28:单位装得下就用 1/1000 英寸,不再按「最远点 = 32512」定。
            # libcdr 在 16 位 CMX 里把坐标、笔宽一律按 1/1000 英寸解释
            # (CommonParser::readCoordinate:readS16 / 1000.0),cont.factor 读了但从来不用;
            # 原版自己在上面给空文档的默认值也正是 factor = 0.001 —— 这是 16 位 CMX 的原生单位。
            # 第一轮按最远点定量程,CorelDRAW 显示正确,但 Inkscape / LibreOffice(libcdr)读出来的
            # 尺寸按内容大小差 1.4 倍(A0)到近 10 倍(小图标),用户把 .cdr 传回我们自己的 cdr→X 工具也一样。
            # 1/1000 英寸 = 0.0254mm(约 1000dpi),仍比原版 A3 上的 0.48mm 细 19 倍。
            # 内容离页心超过 32.5 英寸时装不下,才按「最远点 = 32512」放大单位,那时只有 CorelDRAW 读得对。
            # frame 取整数 32512 而不是原版的 32512.5:按最远点定量程时极值点**按构造**落在 .5 平局上,
            # 舍入方向取决于一个 ulp 的浮点噪声。
            # 这样也顺带解决了 #14(max_value 为 0 时除零)和审查 #13(页心单点 coef 极端):
            # 量程小于原生单位能表达的范围时,一律用原生单位。
            frame = 32512.0
            unit_in = max(NATIVE_UNIT_IN, self._max_abs_coord(objs) * sk2const.pt_to_in / frame)
            self.coef = sk2const.pt_to_in / unit_in
            factor = unit_in

        cont_obj.set('factor', utils.py_float2double(factor, self.rifx))
        cont_obj.set('unit', cmx_const.CONT_UNIT_IN)

    def translate_doc(self):
        index = 0
        cont_obj = self.cmx_model.chunk_map[b'cont']
        cmx_pages = self.cmx_model.chunk_map['pages']
        for page in self.sk2_mtds.get_pages():
            cmx_page = cmx_pages[index][0]
            rlsts = cmx_pages[index][1:]
            if self.cmx_cfg.v1 or not self.cmx_cfg.v16bit:
                # 32 位与 16 位的对象树相同,指令类按 v16bit 选(cmx_instr.make_instruction)
                self.make_v1_page(page, index + 1, cmx_page, rlsts)
                rlst = rlsts[0]
                layers_num = len(cmx_page.childs[0].childs) - 1
                for i in range(layers_num):
                    rlst.add_rlist((2, 9, i + 1))
                cont_obj.data['tally'] += cmx_page.count()
            index += 1
        pg = cmx_pages[0][0].childs[0]
        if self.cmx_cfg.uc2_compat:
            cont_obj.data['bbox'] = tuple(pg.get_bbox())
        else:
            # 审查确认:一条 PolyCurve 都没写出(空白文档、全是孤立 move_to)时 get_bbox 返回 None,
            # tuple(None) 直接 TypeError。空内容给零包围盒。
            cont_obj.data['bbox'] = tuple(self._union_bbox(pg) or (0, 0, 0, 0))

    @staticmethod
    def _union_bbox(instr):
        """修复 #29:子孙 PolyCurve 包围盒的并集,CMX 顺序 (x0, 上, x1, 下);没有曲线返回 None。
        原版 get_bbox 用 libgeom.sum_bbox,它按 sk2 的 (x0, y0, x1, y1) 取 min/max,
        套在 CMX 顺序上就成了「上取最小、下取最大」—— 页面、组、cont 的包围盒上下颠倒。"""
        boxes = []
        stack = [instr]
        while stack:
            it = stack.pop()
            if it.data.get('code') == cmx_const.POLYCURVE:
                if it.data.get('bbox'):
                    boxes.append(it.data['bbox'])
                continue
            stack.extend(it.childs)
        if not boxes:
            return None
        return (min(b[0] for b in boxes), max(b[1] for b in boxes),
                max(b[2] for b in boxes), min(b[3] for b in boxes))

    def make_v1_page(self, page, page_num, cmx_page, rlst):
        kwargs = {
            'page_number': page_num,
            'flags': 0,
            'bbox': (0, 0, 0, 0),
            'tail': b'\x00\x00\x01\x00\x00\x00',
        }
        page_instr = mkinstr(self.cmx_cfg,
                             identifier=cmx_const.BEGIN_PAGE, **kwargs)
        cmx_page.add(page_instr)

        layer_count = 1
        for layer in page.childs:
            if self.cmx_cfg.skip_empty and not layer.childs:
                continue
            kwargs = {
                'page_number': page_num,
                'layer_number': layer_count,
                'flags': 0,
                'tally': 0,
                # 文本编码:原版把 str 直接拼进 chunk、长度字段用 len(str)。
                # 移植版显式 utf-8 编码一次,长度字段随之变成编码后的字节数。
                # ASCII 层名与原版字节一致(夹具都是 ASCII)。
                'layer_name': layer.name.encode('utf-8'),
                'tail': b'\x01\x00\x00',
            }
            layer_instr = mkinstr(self.cmx_cfg,
                                  identifier=cmx_const.BEGIN_LAYER, **kwargs)
            page_instr.add(layer_instr)

            for obj in layer.childs:
                self.make_v1_objects(layer_instr, obj)

            layer_count += 1

            layer_instr.add(
                mkinstr(self.cmx_cfg, identifier=cmx_const.END_LAYER))
            layer_instr.data['tally'] = layer_instr.count() + 1

        page_instr.add(
            mkinstr(self.cmx_cfg, identifier=cmx_const.END_PAGE))
        if self.cmx_cfg.uc2_compat:
            page_instr.data['bbox'] = page_instr.get_bbox()
        else:
            page_instr.data['bbox'] = self._union_bbox(page_instr) or (0, 0, 0, 0)

    def make_v1_objects(self, parent_instr, obj):
        if obj.is_group and obj.childs:
            kwargs = {
                'bbox': (0, 0, 0, 0),
                'tail': b'\x00\x00',
            }
            group_instr = mkinstr(self.cmx_cfg,
                                  identifier=cmx_const.BEGIN_GROUP, **kwargs)
            parent_instr.add(group_instr)

            for item in obj.childs:
                self.make_v1_objects(group_instr, item)

            group_instr.add(
                mkinstr(self.cmx_cfg, identifier=cmx_const.END_GROUP))

            if self.cmx_cfg.uc2_compat:
                group_bbox = group_instr.get_bbox()
            else:
                group_bbox = self._union_bbox(group_instr)
            if not self.cmx_cfg.uc2_compat and group_bbox is None:
                # 审查确认:组里的曲线全被跳过(只有孤立 move_to)时,原版 bbox=None 在打包时崩。
                # 空组不写出。
                parent_instr.childs.remove(group_instr)
                return
            content = group_instr.childs[:-1]           # 去掉 EndGroup
            if not self.cmx_cfg.uc2_compat and len(content) == 1:
                # 修复 #32:只装一个对象的组没有意义,原样写出后 CorelDRAW 里全是「Group of 1 Objects」。
                # LibreOffice 导出 SVG 给每个图形各包一层 <g>(去掉 #31 的包围盒矩形后就只剩一个对象)。
                # 按**输出**判:组里恰好一条 PolyCurve 或一个子组才展开;一条曲线被拆成多条 PolyCurve
                # 时保留组,拆开的几段仍在一起。
                idx = parent_instr.childs.index(group_instr)
                parent_instr.childs[idx] = content[0]
                content[0].parent = parent_instr
                return
            group_instr.data['bbox'] = group_bbox

        elif obj.is_primitive:
            if self.cmx_cfg.uc2_compat:
                curve = obj.to_curve()
                curve.update()
            else:
                # 修复 #11:原版先 update() 再判 None,判断永远救不了场。
                # 顺带复用 _max_abs_coord 已经转好的曲线,保证量程与写出的是同一批点。
                curve = self._curve_of(obj)
            if not curve:
                return
            elif curve.is_group:
                self.make_v1_objects(parent_instr, curve)
            elif curve.paths:
                if not self.cmx_cfg.uc2_compat and not self._visible(curve):
                    return                          # 修复 #31:看不见的曲线不写出
                close_flag = False
                style = curve.style
                attrs = {
                    'style_flags': 1 if style[0] else 0,
                    'fill_type': cmx_const.INSTR_FILL_EMPTY,
                }
                stroke_w = None
                if not self.cmx_cfg.uc2_compat and style[1]:
                    stroke_w = self._stroke_width_pt(curve)
                    if not stroke_w or stroke_w <= 0:
                        # 审查确认:stroke-width="0" / 负值在 SVG 里是不画描边,
                        # 原版照样写出一条 0 宽的实线描边。
                        style = [style[0], []] + list(style[2:])
                attrs['style_flags'] += 2 if style[1] else 0
                if style[0] and style[0][1] == sk2const.FILL_SOLID:
                    attrs['fill_type'] = cmx_const.INSTR_FILL_UNIFORM
                    attrs['fill'] = (self._add_color(style[0][2]), 1)
                    close_flag = not style[0][0] & sk2const.FILL_CLOSED_ONLY
                elif not self.cmx_cfg.uc2_compat and style[0] and \
                        style[0][1] == sk2const.FILL_GRADIENT:
                    # 原版对渐变写 INSTR_FILL_EMPTY:图形静默变空心。CMX 的 fountain 填充
                    # 没有真机验证过,先取渐变沿轴的平均色写成均匀填充 —— 颜色近似,形状不丢。
                    clr = _gradient_mean_color(style[0][2][2])
                    if clr:
                        attrs['fill_type'] = cmx_const.INSTR_FILL_UNIFORM
                        attrs['fill'] = (self._add_color(clr), 1)
                        close_flag = not style[0][0] & sk2const.FILL_CLOSED_ONLY
                if style[1] and stroke_w is not None:
                    outline = deepcopy(style[1])
                    outline[1] = stroke_w
                    attrs['outline'] = self._add_outline(outline)
                elif style[1]:
                    outline = style[1]
                    if curve.stroke_trafo:
                        points = [[0.0, 0.0], [1.0, 0.0]]
                        # 原版判断 curve.stroke_trafo、取值却用 obj.stroke_trafo。
                        # to_curve 会原样复制 stroke_trafo,两者平时相等;修复版统一用 curve。
                        if self.cmx_cfg.uc2_compat:
                            stroke_trafo = obj.stroke_trafo
                        else:
                            stroke_trafo = curve.stroke_trafo
                        points = libgeom.apply_trafo_to_points(points, stroke_trafo)
                        coef = libgeom.distance(*points)
                        outline = deepcopy(outline)
                        outline[1] *= coef
                    attrs['outline'] = self._add_outline(outline)
                trafo = libgeom.multiply_trafo(
                    curve.trafo, [self.coef, 0.0, 0.0, self.coef, 0.0, 0.0])
                paths = libgeom.apply_trafo_to_paths(curve.paths, trafo)
                if not self.cmx_cfg.uc2_compat:
                    self._emit_polycurves(parent_instr, attrs, paths, close_flag, curve)
                    return
                attrs['points'] = []
                attrs['nodes'] = []
                for path in paths:
                    # Force path closing
                    if close_flag and not path[2] == sk2const.CURVE_CLOSED:
                        path = deepcopy(path)
                        path[2] = sk2const.CURVE_CLOSED
                        p = path[1][-1] if len(path[1][-1]) == 2 \
                            else path[1][-1][-1]
                        if not path[0] == p:
                            path[1].append([] + path[0])
                    x, y = path[0]
                    attrs['points'].append((int(x), int(y)))
                    node = cmx_const.NODE_MOVE + cmx_const.NODE_USER
                    if path[2] == sk2const.CURVE_CLOSED:
                        node += cmx_const.NODE_CLOSED
                    attrs['nodes'].append(node)

                    for point in path[1]:
                        if len(point) == 2:
                            x, y = point
                            attrs['points'].append((int(x), int(y)))
                            node = cmx_const.NODE_LINE + cmx_const.NODE_USER
                            attrs['nodes'].append(node)
                        else:
                            p0, p1, p2, flag = point
                            for item in (p0, p1, p2):
                                x, y = item
                                attrs['points'].append((int(x), int(y)))
                            node = cmx_const.NODE_ARC
                            attrs['nodes'].append(node)
                            attrs['nodes'].append(node)
                            node = cmx_const.NODE_CURVE + cmx_const.NODE_USER
                            attrs['nodes'].append(node)

                    if path[2] == sk2const.CURVE_CLOSED:
                        attrs['nodes'][-1] += cmx_const.NODE_CLOSED

                attrs['bbox'] = self._make_bbox(curve.cache_bbox)

                attrs['tail'] = b''

                curve_instr = mkinstr(self.cmx_cfg,
                                      identifier=cmx_const.POLYCURVE, **attrs)
                parent_instr.add(curve_instr)

    # ------------------------------------------------------ Step 7 新增方法

    def _max_points(self):
        return POLYCURVE_MAX_POINTS if self.cmx_cfg.v16bit else POLYCURVE_MAX_POINTS_32

    def _hard_points(self):
        return POLYCURVE_HARD_POINTS if self.cmx_cfg.v16bit else POLYCURVE_HARD_POINTS_32

    def _curve_of(self, obj):
        """obj.to_curve() 的缓存。修复 #11:先判 None 再 update。"""
        key = id(obj)
        if key not in self._curves:
            curve = obj.to_curve()
            if curve:
                curve.update()
            self._curves[key] = curve
        return self._curves[key]

    def _visible(self, curve):
        """修复 #31:既没有填充、也没有可见描边的曲线看不见,不写出、不计入量程。
        LibreOffice 导出 SVG 时给每个图形附一个 fill="none" stroke="none" 的包围盒矩形
        (class="BoundingBox");原样写出后 CorelDRAW 每个组里都多一个看不见的对象(真机实测)。
        判定与写出一致:实色、有色标的渐变算填充(#27);描边有效宽度 > 0 才算描边(#19)。"""
        style = curve.style
        if not style:
            return False
        fill = style[0]
        if fill and (fill[1] == sk2const.FILL_SOLID or
                     (fill[1] == sk2const.FILL_GRADIENT and
                      _gradient_mean_color(fill[2][2]) is not None)):
            return True
        if style[1]:
            w = self._stroke_width_pt(curve)
            return bool(w and w > 0)
        return False

    def _max_abs_coord(self, objs):
        """修复 #2:所有将要写出的点(含贝塞尔控制点)与包围盒的最大绝对值,单位 pt。
        遍历与 make_v1_objects 同构。"""
        m = 0.0
        stack = list(objs)
        while stack:
            obj = stack.pop()
            if obj.is_group and obj.childs:
                stack.extend(obj.childs)
                continue
            if not obj.is_primitive:
                continue
            curve = self._curve_of(obj)
            if not curve:
                continue
            if curve.is_group:
                stack.extend(curve.childs)
                continue
            if not curve.paths or not self._visible(curve):
                continue
            for path in libgeom.apply_trafo_to_paths(curve.paths, curve.trafo):
                if not path[1]:
                    # 审查确认:孤立 move_to 不写出(#15),也不该撑大量程 —— 否则远处一个空子路径
                    # 就能把整图分辨率压下去。
                    continue
                m = max(m, abs(path[0][0]), abs(path[0][1]))
                for p in path[1]:
                    for x, y in ((p,) if len(p) == 2 else p[:3]):
                        m = max(m, abs(x), abs(y))
            if curve.style and curve.style[1]:
                # 审查确认:笔宽与坐标共用 coef。笔宽单位 = coef * w <= s16 要求 m >= w * 32512 / 32767。
                w = self._stroke_width_pt(curve)
                if w and w > 0:
                    m = max(m, w * 32512.0 / S16_MAX)
        return m

    def _stroke_width_pt(self, curve):
        """描边有效宽度(pt)= 样式宽度 × stroke_trafo 的缩放。与 make_v1_objects 同一口径。"""
        outline = curve.style[1]
        w = outline[1]
        if w is None:
            return None
        if curve.stroke_trafo:
            points = libgeom.apply_trafo_to_points([[0.0, 0.0], [1.0, 0.0]],
                                                   curve.stroke_trafo)
            w = w * libgeom.distance(*points)
        return w

    def _subpath_segments(self, path, close_flag):
        """一条子路径 -> (起点, [(节点列表, 点列表), ...], 是否闭合),坐标已取整。"""
        rnd = utils.py2round
        if close_flag and not path[2] == sk2const.CURVE_CLOSED and path[1]:
            path = deepcopy(path)
            path[2] = sk2const.CURVE_CLOSED
            last = path[1][-1]
            # 修复 #12:原版取贝塞尔段终点用 [-1],拿到的是 flag(int)不是坐标,
            # 于是「终点 != 起点」恒成立,每条被强制闭合的曲线都多插一个重复点。
            p = last if len(last) == 2 else last[2]
            if not path[0] == p:
                path[1].append([] + path[0])
        x, y = path[0]
        start = (int(rnd(x)), int(rnd(y)))
        segs = []
        for point in path[1]:
            if len(point) == 2:
                x, y = point
                segs.append(([cmx_const.NODE_LINE + cmx_const.NODE_USER],
                             [(int(rnd(x)), int(rnd(y)))]))
            else:
                p0, p1, p2, _flag = point
                segs.append(([cmx_const.NODE_ARC, cmx_const.NODE_ARC,
                              cmx_const.NODE_CURVE + cmx_const.NODE_USER],
                             [(int(rnd(q[0])), int(rnd(q[1]))) for q in (p0, p1, p2)]))
        return start, segs, path[2] == sk2const.CURVE_CLOSED

    def _emit_polycurves(self, parent_instr, attrs, paths, close_flag, curve):
        """修复 #3 #5 #6 #12 #15 的 PolyCurve 发射。

        #3  坐标 int() 截断 -> 四舍五入(朝零截断是系统偏置,G4 抓得到)
        #5  全链路原本没有 int16 越界检查,越界直接 struct.error;这里给出可读错误
        #6  单条指令超 65535 字节时原版 struct.error 丢整个文件(f3b_longpath)。
            只描边的曲线按子路径/段边界拆成多条指令;**有填充的不拆** —— 同一条路径里的
            子路径可能构成镂空,拆开就填实了 —— 改为抛可读错误,由上层回落到其他格式
        #15 空子路径(只有 move_to):原版 path[1][-1] 直接 IndexError(上游 #56),
            这里跳过 —— 一个孤立的 move_to 本来就不画任何东西
        """
        subs = []
        for path in paths:
            if not path[1]:
                continue
            subs.append(self._subpath_segments(path, close_flag))
        if not subs:
            return

        lim = INT16_MAX if self.cmx_cfg.v16bit else INT32_MAX
        for start, segs, _closed in subs:
            for q in [start] + [q for _nodes, pts in segs for q in pts]:
                if abs(q[0]) > lim or abs(q[1]) > lim:
                    if self.cmx_cfg.v16bit:
                        raise ValueError('坐标越界 int16:%r(量程计算有误)' % (q,))
                    raise ValueError('坐标超出 32 位 CMX 的量程(约 +-8454 英寸):%r' % (q,))

        total = sum(1 + sum(len(p) for _n, p in segs) for _s, segs, _c in subs)
        filled = bool(attrs.get('style_flags', 0) & cmx_const.INSTR_FILL_FLAG) and \
            attrs.get('fill_type') != cmx_const.INSTR_FILL_EMPTY
        if total <= self._max_points():
            chunks = [subs]
        elif filled:
            # 审查确认:上限按 s16 降到 6540 点之后,「有填充就不拆」会误伤 potrace 描摹 ——
            # potrace 把整张图写成**一条**带大量子路径的填充 path。按包围盒包含关系分组:
            # 被包含的子路径(孔、孔里的岛)与包含它的外轮廓同组,组内不拆,组与组之间装箱。
            chunks = self._split_filled(subs)
        else:
            chunks = self._split_for_limit(subs)

        for chunk in chunks:
            pts, nodes = [], []
            for start, segs, closed in chunk:
                pts.append(start)
                node = cmx_const.NODE_MOVE + cmx_const.NODE_USER
                if closed:
                    node += cmx_const.NODE_CLOSED
                nodes.append(node)
                for seg_nodes, seg_pts in segs:
                    pts.extend(seg_pts)
                    nodes.extend(seg_nodes)
                if closed:
                    nodes[-1] += cmx_const.NODE_CLOSED
            instr_attrs = dict(attrs)
            instr_attrs['points'] = pts
            instr_attrs['nodes'] = nodes
            # 审查确认:cache_bbox 来自 cairo 的 1/256pt 定点,放大到新分辨率后可能比实际写出的点小
            # (实测越出 4-46 个单位)。包围盒改由**实际写出的整数点**求贝塞尔紧包围盒。
            instr_attrs['bbox'] = self._tight_bbox(pts, nodes)
            instr_attrs['tail'] = b''
            parent_instr.add(mkinstr(self.cmx_cfg,
                                     identifier=cmx_const.POLYCURVE, **instr_attrs))

    @staticmethod
    def _tight_bbox(pts, nodes):
        """由写出的整数点求紧包围盒,返回 CMX 顺序 (x0, 上, x1, 下),向外取整。"""
        xs, ys = [], []
        i, n = 0, len(pts)
        prev = None
        while i < n:
            node = nodes[i] & 0xC0
            if node == cmx_const.NODE_ARC and i + 2 < n:
                p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2]
                p0 = prev if prev is not None else p1
                xs += [p0[0], p3[0]]
                ys += [p0[1], p3[1]]
                for axis, acc in ((0, xs), (1, ys)):
                    a0, a1, a2, a3 = p0[axis], p1[axis], p2[axis], p3[axis]
                    # 三次贝塞尔导数 = 3[(a1-a0)(1-t)^2 + 2(a2-a1)t(1-t) + (a3-a2)t^2]
                    qa = (a1 - a0) - 2.0 * (a2 - a1) + (a3 - a2)
                    qb = 2.0 * ((a2 - a1) - (a1 - a0))
                    qc = float(a1 - a0)
                    roots = []
                    if abs(qa) < 1e-12:
                        if abs(qb) > 1e-12:
                            roots.append(-qc / qb)
                    else:
                        disc = qb * qb - 4.0 * qa * qc
                        if disc >= 0:
                            sq = math.sqrt(disc)
                            roots += [(-qb + sq) / (2.0 * qa), (-qb - sq) / (2.0 * qa)]
                    for t in roots:
                        if 0.0 < t < 1.0:
                            u = 1.0 - t
                            acc.append(u * u * u * a0 + 3 * u * u * t * a1
                                       + 3 * u * t * t * a2 + t * t * t * a3)
                prev = p3
                i += 3
            else:
                xs.append(pts[i][0])
                ys.append(pts[i][1])
                prev = pts[i]
                i += 1
        return (int(math.floor(min(xs))), int(math.ceil(max(ys))),
                int(math.ceil(max(xs))), int(math.floor(min(ys))))

    def _split_filled(self, subs):
        """有填充的复合路径:按包围盒包含关系把子路径并成组,组内不拆,组间装箱。

        包含关系用包围盒判(比真正的点在多边形内更保守:包围盒包含但几何上不包含的也并一组,
        只会让组变大,不会拆散真正的孔)。用粗网格索引候选,避免子路径多时 O(n^2)。
        单组超过上限 -> ValueError(拆开就会把孔填实)。
        """
        limit = self._max_points()
        n = len(subs)
        boxes = []
        for start, segs, _closed in subs:
            xs = [start[0]] + [q[0] for _nd, ps in segs for q in ps]
            ys = [start[1]] + [q[1] for _nd, ps in segs for q in ps]
            boxes.append((min(xs), min(ys), max(xs), max(ys)))
        parent = list(range(n))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        gx0 = min(b[0] for b in boxes)
        gy0 = min(b[1] for b in boxes)
        gw = max(1, max(b[2] for b in boxes) - gx0)
        gh = max(1, max(b[3] for b in boxes) - gy0)
        cells = 64
        grid = {}

        def cell(x, y):
            return (min(cells - 1, int((x - gx0) * cells / gw)),
                    min(cells - 1, int((y - gy0) * cells / gh)))

        for idx, b in enumerate(boxes):
            cx0, cy0 = cell(b[0], b[1])
            cx1, cy1 = cell(b[2], b[3])
            for cx in range(cx0, cx1 + 1):
                for cy in range(cy0, cy1 + 1):
                    grid.setdefault((cx, cy), []).append(idx)
        for idx, b in enumerate(boxes):
            for other in grid.get(cell((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0), ()):
                if other == idx:
                    continue
                o = boxes[other]
                if o[0] <= b[0] and o[1] <= b[1] and o[2] >= b[2] and o[3] >= b[3]:
                    ra, rb = find(idx), find(other)
                    if ra != rb:
                        parent[ra] = rb

        groups = {}
        for idx in range(n):
            groups.setdefault(find(idx), []).append(idx)
        chunks, cur, cur_n = [], [], 0
        for root in sorted(groups, key=lambda r: min(groups[r])):
            members = sorted(groups[root])
            size = sum(1 + sum(len(p) for _nd, p in subs[i][1]) for i in members)
            if size > limit:
                hard = self._hard_points()
                if size > hard:
                    raise ValueError('填充复合路径里一组相互嵌套的子路径共 %d 个点,超过 %d 位 CMX 单条曲线上限 %d;'
                                     '拆开会把孔填实,不拆' % (size, 16 if self.cmx_cfg.v16bit else 32, hard))
                # 修复 #34:原来这里直接报错(单条指令 <= 32767 字节是我们自己加的限制,不是格式限制)。
                # 这一组单独成一条扩展长度的指令,前后的组照常装箱
                if cur:
                    chunks.append(cur)
                    cur, cur_n = [], 0
                chunks.append([subs[i] for i in members])
                continue
            if cur and cur_n + size > limit:
                chunks.append(cur)
                cur, cur_n = [], 0
            cur += [subs[i] for i in members]
            cur_n += size
        if cur:
            chunks.append(cur)
        return chunks

    def _split_for_limit(self, subs):
        """只描边曲线的拆分:先按子路径装箱;单条子路径本身超限时,按段边界切成
        首尾相接的开放片段(闭合的先补一段回到起点,再当开放的切)。"""
        limit = self._max_points()
        pieces = []
        for start, segs, closed in subs:
            n = 1 + sum(len(p) for _n, p in segs)
            if n <= limit:
                pieces.append((start, segs, closed))
                continue
            if closed:
                segs = segs + [([cmx_const.NODE_LINE + cmx_const.NODE_USER], [start])]
            cur_start, cur, cur_n = start, [], 1
            for seg in segs:
                if cur and cur_n + len(seg[1]) > limit:
                    pieces.append((cur_start, cur, False))
                    cur_start = cur[-1][1][-1]
                    cur, cur_n = [], 1
                cur.append(seg)
                cur_n += len(seg[1])
            if cur:
                pieces.append((cur_start, cur, False))
        chunks, cur, cur_n = [], [], 0
        for piece in pieces:
            n = 1 + sum(len(p) for _n, p in piece[1])
            if cur and cur_n + n > limit:
                chunks.append(cur)
                cur, cur_n = [], 0
            cur.append(piece)
            cur_n += n
        if cur:
            chunks.append(cur)
        return chunks

    def _default_notes(self):
        appdata = self.sk2_doc.appdata
        name = "Created by %s" % appdata.app_name
        ver = "%s%s" % (appdata.version, appdata.revision)
        link = "(https://%s/)" % appdata.app_domain
        return "%s %s" % (name, ver)

    def add_info(self):
        info = self.make_el(cmx_const.INFO_ID)
        self.cmx_model.add(info)

        metainfo = self.sk2_model.metainfo
        keys = metainfo[2] or ''
        notes = metainfo[3] or self._default_notes()

        # 文本编码:同 layer_name,显式 utf-8 编码一次;长度/补零按编码后的字节数。
        info.add(self.make_el(cmx_const.IKEY_ID, text=keys.encode('utf-8')))
        info.add(self.make_el(cmx_const.ICMT_ID, text=notes.encode('utf-8')))

    def index_model(self):
        indx = self.cmx_model.chunk_map[b'indx']
        ixlrs = self.index_ixlr()
        indx.do_update()
        ixtl = self.index_ixtl(ixlrs)
        indx.do_update()
        ixpg = self.index_ixpg(ixlrs)
        indx.do_update()
        self.index_ixmr(ixpg, ixtl)

    def index_ixlr(self):
        index = 1
        ixlrs = []
        cmx_pages = self.cmx_model.chunk_map['pages']
        indx = self.cmx_model.chunk_map[b'indx']
        for item in cmx_pages:
            kwargs = {
                'page': index,
                'layers': []
            }
            recs = kwargs['layers']
            page = item[0]
            for layer in page.childs[0].childs:
                if not layer.is_layer:
                    continue
                recs.append((layer.get_offset(), layer.data['layer_name']))
            ixlr = cmx_model.make_cmx_chunk(
                self.cmx_cfg, identifier=cmx_const.IXLR_ID, **kwargs)
            ixlrs.append(ixlr)
            indx.add(ixlr)
            index += 1
        return ixlrs

    def index_ixtl(self, ixlrs):
        kwargs = {
            'table_id': 3,
            'rec_sz': 4,
            'records': []
        }
        ixlrs = [] + ixlrs
        ixlrs.reverse()
        for item in ixlrs:
            kwargs['records'].append(item.get_offset())
        indx = self.cmx_model.chunk_map[b'indx']
        ixtl = cmx_model.make_cmx_chunk(
            self.cmx_cfg, identifier=cmx_const.IXTL_ID, **kwargs)
        indx.add(ixtl)
        return ixtl

    def index_ixpg(self, ixlrs):
        kwargs = {
            'rec_sz': 16,
            'records': []
        }
        cmx_pages = self.cmx_model.chunk_map['pages']
        index = 0
        for page in cmx_pages:
            page_offset = page[0].get_offset()
            ixl_offset = ixlrs[index].get_offset()
            thmb_offset = 0xffffffff
            ref_offset = page[1].get_offset()
            kwargs['records'].append(
                (page_offset, ixl_offset, thmb_offset, ref_offset))
            # 修复 #10:原版循环里 index 从不自增,多页文档每一页都指向第 1 页的层索引。
            # 单页文档不受影响(我们的输出恒为单页),所以不分流。
            index += 1
        indx = self.cmx_model.chunk_map[b'indx']
        ixpg = cmx_model.make_cmx_chunk(
            self.cmx_cfg, identifier=cmx_const.IXPG_ID, **kwargs)
        indx.add(ixpg)
        return ixpg

    def index_ixmr(self, ixpg, ixtl):
        kwargs = {
            'records': []
        }
        recs = kwargs['records']

        # Master Index Table
        offset = ixpg.get_offset() + ixpg.get_chunk_size()
        recs.append((cmx_const.MASTER_INDEX_TABLE, offset))

        # Page Index Table
        offset = ixpg.get_offset()
        recs.append((cmx_const.PAGE_INDEX_TABLE, offset))

        # Master Layer Table
        offset = ixtl.get_offset()
        recs.append((cmx_const.MASTER_LAYER_TABLE, offset))

        # Outline Description Section
        if b'rotl' in self.cmx_model.chunk_map:
            offset = self.cmx_model.chunk_map[b'rotl'].get_offset()
            recs.append((cmx_const.OUTLINE_DESCRIPTION_SECTION, offset))

        # Line Style Description Section
        if b'rott' in self.cmx_model.chunk_map:
            offset = self.cmx_model.chunk_map[b'rott'].get_offset()
            recs.append((cmx_const.LINE_STYLE_DESCRIPTION_SECTION, offset))

        # Arrowheads Description Section
        if b'rota' in self.cmx_model.chunk_map:
            offset = self.cmx_model.chunk_map[b'rota'].get_offset()
            recs.append((cmx_const.ARROWHEADS_DESCRIPTION_SECTION, offset))

        # Screen Description Section
        if b'rscr' in self.cmx_model.chunk_map:
            offset = self.cmx_model.chunk_map[b'rscr'].get_offset()
            recs.append((cmx_const.SCREEN_DESCRIPTION_SECTION, offset))

        # Pen Description Section
        if b'rpen' in self.cmx_model.chunk_map:
            offset = self.cmx_model.chunk_map[b'rpen'].get_offset()
            recs.append((cmx_const.PEN_DESCRIPTION_SECTION, offset))

        # Dot-Dash Description Section
        if b'rdot' in self.cmx_model.chunk_map:
            offset = self.cmx_model.chunk_map[b'rdot'].get_offset()
            recs.append((cmx_const.DOTDASH_DESCRIPTION_SECTION, offset))

        # Color Description Section
        if b'rclr' in self.cmx_model.chunk_map:
            offset = self.cmx_model.chunk_map[b'rclr'].get_offset()
            recs.append((cmx_const.COLOR_DESCRIPTION_SECTION, offset))

        # Color Correction Section
        if b'ccmm' in self.cmx_model.chunk_map:
            offset = self.cmx_model.chunk_map[b'ccmm'].get_offset()
            recs.append((cmx_const.COLOR_CORRECTION_SECTION, offset))

        indx = self.cmx_model.chunk_map[b'indx']
        ixmr = cmx_model.make_cmx_chunk(
            self.cmx_cfg, identifier=cmx_const.IXMR_ID, **kwargs)
        indx.add(ixmr)
        self.cmx_model.do_update()

        cont = self.cmx_model.chunk_map[b'cont']
        offset = ixpg.get_offset() + ixpg.get_chunk_size()
        cont.data['IndexSection'] = offset
        cont.data['InfoSection'] = offset + ixmr.get_chunk_size()

        if b'DISP' in self.cmx_model.chunk_map:
            offset = self.cmx_model.chunk_map[b'DISP'].get_offset()
            cont.data['Thumbnail'] = offset
