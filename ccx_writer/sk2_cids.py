# -*- coding: utf-8 -*-
#
#  ccx_writer —— UniConvertor 2.0 @973d5b6 的 Python 3 移植(SVG 前端)
#  Copyright (C) 2011-2015 by Ihor E. Novikov(原版)
#  Copyright (C) 2026 SharkFoto(Python 3 移植)
#
#  GNU Affero General Public License v3 或更高版本,见本目录的 LICENSE。

# 移植说明:逐行照搬原版 uc2/formats/sk2/sk2_cids.py,纯常量表。
# 唯一改动是下面这行导入(原为 from uc2 import _)。
# sk2_model 用 from ... import * 把这些 cid 拉进自己的命名空间;
# _ 以下划线开头,星号导入本来就不导出它,Py2/Py3 行为一致。
# CID_TO_TAGNAME / TAGNAME_TO_CID 原版只被 sk2_filters(sk2 文件读写)
# 使用,移植版用不到,但为保持可 diff 照样保留。
from ccx_writer.translator import _

# Document object enumeration
DOCUMENT = 1

METAINFO = 10
STYLES = 11
STYLE = 12
PROFILES = 13
PROFILE = 14
FONTS = 15
FONT = 16
IMAGES = 17
IMAGE = 18

STRUCTURAL_CLASS = 50
PAGES = 51
PAGE = 52
LAYER_GROUP = 53
MASTER_LAYERS = 54
LAYER = 55
GRID_LAYER = 57
GUIDE_LAYER = 58
DESKTOP_LAYERS = 59
GUIDE = 60

SELECTABLE_CLASS = 100
COMPOUND_CLASS = 101
GROUP = 102
CONTAINER = 103
TP_GROUP = 104

PRIMITIVE_CLASS = 200
RECTANGLE = 201
CIRCLE = 202
POLYGON = 203
CURVE = 204
TEXT_BLOCK = 205
TEXT_COLUMN = 206

BITMAP_CLASS = 250
PIXMAP = 251

CID_TO_NAME = {
    DOCUMENT: _('Document'),

    METAINFO: _('Metainfo'), STYLES: _('Styles'), STYLE: _('Style'),
    PROFILES: _('Profiles'), PROFILE: _('Profile'), FONTS: _('Fonts'),
    FONT: _('Font'), IMAGES: _('Images'), IMAGE: _('Image'),

    PAGES: _('Pages'), PAGE: _('Page'), LAYER_GROUP: _('Layer group'),
    MASTER_LAYERS: _('Master layers'), LAYER: _('Layer'),
    GRID_LAYER: _('Grid layer'), GUIDE_LAYER: _('Guide layer'),
    DESKTOP_LAYERS: _('Desktop layers'), GUIDE: _('Guide'),

    GROUP: _('Group'), CONTAINER: _('Container'),
    TP_GROUP: _('Text on Path Group'),

    RECTANGLE: _('Rectangle'), CIRCLE: _('Ellipse'),
    POLYGON: _('Polygon'), CURVE: _('Curve'),
    TEXT_BLOCK: _('Text block'), TEXT_COLUMN: _('Text column'),
    PIXMAP: _('Bitmap'),
}

CID_TO_TAGNAME = {
    DOCUMENT: 'Document',

    METAINFO: 'Metainfo', STYLES: 'Styles', STYLE: 'Style',
    PROFILES: 'Profiles', PROFILE: 'Profile', FONTS: 'Fonts',
    FONT: 'Font', IMAGES: 'Images', IMAGE: 'Image',

    PAGES: 'Pages', PAGE: 'Page', LAYER_GROUP: 'LayerGroup',
    MASTER_LAYERS: 'MasterLayers', LAYER: 'Layer',
    GRID_LAYER: 'GridLayer', GUIDE_LAYER: 'GuideLayer',
    DESKTOP_LAYERS: 'DesktopLayers', GUIDE: 'Guide',

    GROUP: 'Group', CONTAINER: 'Container',
    TP_GROUP: 'TP_Group',

    RECTANGLE: 'Rectangle', CIRCLE: 'Ellipse',
    POLYGON: 'Polygon', CURVE: 'Curve',
    TEXT_BLOCK: 'TextBlock', TEXT_COLUMN: 'TextColumn',
    PIXMAP: 'Pixmap',
}

TAGNAME_TO_CID = {
    'Document': DOCUMENT,

    'Metainfo': METAINFO, 'Styles': STYLES, 'Style': STYLE,
    'Profiles': PROFILES, 'Profile': PROFILE, 'Fonts': FONTS,
    'Font': FONT, 'Images': IMAGES, 'Image': IMAGE,

    'Pages': PAGES, 'Page': PAGE, 'LayerGroup': LAYER_GROUP,
    'MasterLayers': MASTER_LAYERS, 'Layer': LAYER,
    'GridLayer': GRID_LAYER, 'GuideLayer': GUIDE_LAYER,
    'DesktopLayers': DESKTOP_LAYERS, 'Guide': GUIDE,

    'Group': GROUP, 'Container': CONTAINER,
    'TP_Group': TP_GROUP,

    'Rectangle': RECTANGLE, 'Ellipse': CIRCLE,
    'Polygon': POLYGON, 'Curve': CURVE,
    'TextBlock': TEXT_BLOCK, 'TextColumn': TEXT_COLUMN,
    'Pixmap': PIXMAP,
}
