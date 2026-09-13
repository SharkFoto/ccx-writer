# -*- coding: utf-8 -*-
#
#  ccx_writer —— SVG 输入规范化
#  Copyright (C) 2026 SharkFoto
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。
"""把 SVG 规范化成写出器吃得下的形状。纯标准库,py3.6+。

原版 UniConvertor 直接吃 pdftocairo 出的 SVG 会失败或丢东西,实测定位的根因:
  1. 空子路径(d 末尾孤立的 "M x y")—— 保存时 IndexError(上游 uniconvertor#56)
  2. 颜色写在 style 里且是 rgb(89.99%,...) 百分比 —— 整条路径在读入时被丢弃
  3. <use> / <symbol> / <clipPath> / <mask> —— 展开 use、去掉后三者链路才稳
这两步在调用方这侧做,不改写出器本身。

  python -m ccx_writer.svgprep in.svg out.svg
"""
import copy
import re
import sys
import xml.etree.ElementTree as ET

SVG = 'http://www.w3.org/2000/svg'
XL = 'http://www.w3.org/1999/xlink'
ET.register_namespace('', SVG)
ET.register_namespace('xlink', XL)

# ------------------------------------------------------------------ 展平


def q(t):
    return '{%s}%s' % (SVG, t)


def flatten(src, dst):
    tree = ET.parse(src)
    root = tree.getroot()
    ids = dict((e.get('id'), e) for e in root.iter() if e.get('id'))
    n_use = 0
    for _ in range(6):                       # <use> 可以套 <use>,逐层展开
        parent = dict((c, p) for p in root.iter() for c in p)
        uses = [e for e in root.iter(q('use'))]
        if not uses:
            break
        for u in uses:
            p = parent.get(u)
            if p is None:
                continue
            ref = (u.get('{%s}href' % XL) or u.get('href') or '').lstrip('#')
            t = ids.get(ref)
            i = list(p).index(u)
            p.remove(u)
            if t is None:
                continue
            g = ET.Element(q('g'))
            tf = [u.get('transform')] if u.get('transform') else []
            x = float(u.get('x') or 0)
            y = float(u.get('y') or 0)
            if x or y:
                tf.append('translate(%g %g)' % (x, y))
            if tf:
                g.set('transform', ' '.join(tf))
            for k in ('style', 'fill', 'stroke', 'fill-opacity', 'stroke-width'):
                if u.get(k) is not None:
                    g.set(k, u.get(k))
            for k in (list(t) if t.tag in (q('symbol'), q('g')) else [t]):
                g.append(copy.deepcopy(k))
            p.insert(i, g)
            n_use += 1
    parent = dict((c, p) for p in root.iter() for c in p)
    drop = [e for e in root.iter() if e.tag in (q('symbol'), q('clipPath'), q('mask'))]
    for e in drop:
        p = parent.get(e)
        if p is not None:
            p.remove(e)
    for e in root.iter():
        e.attrib.pop('clip-path', None)
        e.attrib.pop('mask', None)
        st = e.get('style')
        if st and ('clip-path' in st or 'mask' in st):
            e.set('style', re.sub(r'(clip-path|mask)\s*:[^;]*;?', '', st))
    tree.write(dst)
    return n_use, len(drop)


# ------------------------------------------------------------------ 规范化

RGB = re.compile(r'rgb\(\s*([^)]*)\)')
EMPTY = re.compile(r'[Mm]\s*[-+.\deE]+[\s,]+[-+.\deE]+\s*(?=[Mm]|$)')


def to_hex(m):
    out = []
    for v in [x.strip() for x in m.group(1).split(',')][:3]:
        n = float(v[:-1]) * 2.55 if v.endswith('%') else float(v)
        out.append(max(0, min(255, int(round(n)))))
    return '#%02x%02x%02x' % tuple(out)


def fix_d(d):
    d, prev = d.strip(), None
    while prev != d:
        prev, d = d, EMPTY.sub('', d).strip()
    return d


def normalize(src, dst):
    tree = ET.parse(src)
    root = tree.getroot()
    parent = dict((c, p) for p in root.iter() for c in p)
    n_style = n_d = n_rm = 0
    for e in list(root.iter()):
        st = e.attrib.pop('style', None)
        if st:
            n_style += 1
            for decl in st.split(';'):
                if ':' in decl:
                    k, v = [x.strip() for x in decl.split(':', 1)]
                    # style 声明的优先级高于同名的表现属性(SVG 规范),所以覆盖而不是跳过
                    if k and v:
                        e.set(k, v)
        for k in ('fill', 'stroke', 'stop-color'):
            if e.get(k) and 'rgb(' in e.get(k):
                e.set(k, RGB.sub(to_hex, e.get(k)))
        if e.tag == '{%s}path' % SVG and e.get('d') is not None:
            nd = fix_d(e.get('d'))
            if nd != e.get('d'):
                n_d += 1
            if not re.search(r'[LlCcQqAaHhVvSsTtZz]', nd):
                p = parent.get(e)
                if p is not None:
                    p.remove(e)
                    n_rm += 1
                continue
            e.set('d', nd)
    tree.write(dst)
    return n_style, n_d, n_rm


def prepare(src, dst):
    """展平 + 规范化,一步到位。返回 (展开的 use 数, 删掉的 symbol/clipPath/mask 数,
    style 转属性数, 修正的 d 数, 删掉的空路径数)。"""
    mid = dst + '.flat.svg'
    n_use, n_drop = flatten(src, mid)
    n_style, n_d, n_rm = normalize(mid, dst)
    try:
        import os
        os.remove(mid)
    except OSError:
        pass
    return n_use, n_drop, n_style, n_d, n_rm


if __name__ == '__main__':
    print('svgprep use=%d drop=%d style=%d d=%d empty=%d' % prepare(sys.argv[1], sys.argv[2]))
