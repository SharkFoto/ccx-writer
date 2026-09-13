# 上游缺陷台账

> 文中提到的 `tests/`、`ops/ccx/` 是 SharkFoto 内部仓库里的验证工具(解码器、门禁、夹具、Py2 基线容器),未随本仓发布。

移植 Step 3 时清点出来的 UniConvertor 2.0 @973d5b6 缺陷。

**一条都没动。** Step 3 的验收判据是与 Py2 原版字节一致 —— 现在修,
就永远分不清哪些差异来自移植、哪些来自修复。修复统一放 Step 7 的独立 diff,
在字节一致的基线之上做,每一条都可单独审查、单独回滚。

移植前的方案只列了 6 条,实际清出 **29 条**。


## cmx_config.py

- **cmx_presenter.py:CMX_Presenter.new() → cmx_model.py:1041 CmxRoot.__init__ 的 `config.rifx = root_id == cmx_const.ROOTX_ID`**
  config 的 rifx 开关实际是死的:new() 不传 root_id,CmxRoot 构造时无条件把 config.rifx 覆写成 False。于是 cmx_saver(..., rifx=True) / cnf={'rifx': True} 被无声丢弃,永远写不出 RIFX(大端)文件。原样保留未动。

- **uc2/formats/generic_filters.py AbstractSaver.save(移植后在 cmx_presenter.py 的 CmxSaver.save)**
  调用方传入的 fileptr 也会被 saver 无条件 close():`cmx_saver(doc, fileptr=f)` 返回后 f 已关闭(我实测复现了)。而且 self.fileptr.close() 不在 finally 里,do_save 抛异常时句柄不释放。原样保留。

- **uc2/formats/generic.py ModelPresenter.save 的 except 分支**
  `msg = _('Error while saving') + ' ' + filename + ' %s'`:只传 fileptr(filename=None)时字符串拼 None 直接 TypeError,把真正的保存异常盖掉。移植版因为删 i18n 顺带写成了 LOG.error('...%s', filename),已在 changes 里声明。

- **cmx_presenter.py:__init__ 的 self.config.load(config_file) → uc2/utils/config.py XMLPrefReader.endElement**
  安全性质:偏好文件的加载是 `line = 'self.value=' + self.value; exec compile(line)` —— cmx_config.xml 里的任意内容会被当 Python 执行。移植版已整条删除(读取侧/偏好),这里只记录。


## cmx_const.py

- **cmx_from_sk2.py:116(不在本文件,仅记录;移植该文件时会再遇到)**
  查错映射表:cap = SK2_JOIN_MAP.get(outline[4], cmx_const.CMX_MITER_CAP) —— 线帽用 outline[4] 去查 SK2_JOIN_MAP(应为 SK2_CAP_MAP)。sk2 的 CAP_BUTT/ROUND/SQUARE=1/2/3,而 SK2_JOIN_MAP 的键是 JOIN_MITER/ROUND/BEVEL=0/1/2,于是 BUTT(1) 被当成 ROUND_JOIN(1)、ROUND(2) 被当成 BEVEL_JOIN(2)、SQUARE(3) 直接 miss 落默认值。按验收判据原样保留,未改。


## cmx_from_sk2.py

- **_add_line_style，原版第 116 行：`cap = SK2_JOIN_MAP.get(outline[4], cmx_const.CMX_MITER_CAP)`**
  查错映射表：cap 应该查 SK2_CAP_MAP，却查了 SK2_JOIN_MAP。后果：SK2_CAP_MAP 全文件无人使用（死代码），而 cap 值被 JOIN 表映射——CAP_BUTT(1)->CMX_ROUND_JOIN(1)、CAP_ROUND(2)->CMX_BEVEL_JOIN(2)、CAP_SQUARE(3) 未命中->默认 CMX_MITER_CAP(0)。即所有线帽写出来都是错的，且 square 帽退化成 butt。已原样保留。

- **_add_line_style，原版第 117 行：`joincap = join << 4 + cap`**
  运算符优先级写错：Python 里 `+` 比 `<<` 紧，实际算的是 `join << (4 + cap)`，而非本意的 `(join << 4) + cap`。后果：cap 不再占低 4 位，而是变成 join 的额外移位量，joincap 字节完全错（例如 join=1,cap=2 本应 0x12，实得 1<<6=0x40）；join=0 时结果恒为 0，cap 信息彻底丢失。已原样保留。

- **index_ixpg，原版第 419-425 行的 `for page in cmx_pages:` 循环**
  循环忘了自增：`index = 0` 在循环外，循环体内用 `ixlrs[index]` 却从不 `index += 1`。后果：多页文档里每一条 ixpg 记录的 ixl_offset 都指向第 1 页的 ixlr，第 2 页及以后的层索引表偏移全错（单页文档恰好正确，所以一直没被发现）。已原样保留。

- **make_v1_objects，原版第 268-270 行：`curve = obj.to_curve(); curve.update(); if not curve: return`**
  空值检查顺序倒了：先无条件调用 `curve.update()`，再判断 `if not curve`。如果 to_curve() 返回 None（原作者显然预期它可能返回 None，否则不会有这个判断），第 269 行就先抛 AttributeError 了，判断永远救不了场。已原样保留。

- **make_v1_objects，原版第 288-291 行：`if curve.stroke_trafo:` ... `libgeom.apply_trafo_to_points(points, obj.stroke_trafo)`**
  取错对象：条件判断的是 `curve.stroke_trafo`（to_curve 之后的新对象），实际拿去做变换的却是 `obj.stroke_trafo`（原对象）。两者不一致时会用错矩阵；若 curve 有 stroke_trafo 而 obj 的是 None/空，apply_trafo_to_points 直接炸。已原样保留。

- **make_v1_objects，原版第 306-307 行：`p = path[1][-1] if len(path[1][-1]) == 2 else path[1][-1][-1]`**
  取错下标：else 分支处理的是贝塞尔段 `[p0, p1, p2, flag]`，终点是 `[2]`，代码却取了 `[-1]` —— 拿到的是 flag（一个 int），不是坐标点。后果：随后 `if not path[0] == p` 把 list 和 int 比较，恒为 True，于是强制闭合路径时永远多插一个重复节点（起点被再写一遍），多出一个 NODE_LINE 节点和一对坐标。已原样保留。

- **_default_notes，原版第 349 行：`link = "(https://%s/)" % appdata.app_domain`**
  死变量：link 算出来了但 return 只用了 name 和 ver，域名链接从没进过 ICMT 注释文本。（看得出原意是要拼进去的。）已原样保留。

- **_add_color，原版第 92 行：`clr = (5, 5, (0, 0, 0))  # Fallback RGB black`**
  死赋值：紧接着的 if/elif/else 三个分支都会无条件重写 clr，这个「兜底黑色」永远不会被用到。无害，但说明作者以为 else 分支之外还有别的路径。已原样保留。

- **_int2word / _int2dword，原版第 83-87 行**
  死方法：两个转换方法在本文件和整个 cmx 包内都没有任何调用点（坐标最终是由 cmx_instr 自己打包的）。已原样保留。

- **make_v1_page，原版第 209 行的形参 `rlst`**
  未使用的形参：translate_doc 传进来 `rlsts`（切片得到的列表），make_v1_page 函数体内一次都没用到——rlist 记录其实是调用方自己在 translate_doc 里加的。已原样保留。

- **make_template，原版第 183-186 行**
  潜在 ZeroDivisionError：`max_value = max([abs(item) for item in bbox])` 若为 0（例如全部对象退化成一个点在原点），第 185 行 `frame / max_value` 直接除零崩溃，没有 max(1, ...) 之类的保护。已原样保留。


## cmx_instr.py

- **Inst16JumpAbsolute.update(原版 244-250)**
  三个问题堆在一起,已原样保留:(1) 头部 '\x08\x00\x6f\x00' 是硬编码小端,完全忽略 config.rifx —— RIFX(大端)文档下 size/code 两个字段字节序都是错的;(2) 不调用 CmxInstruction.update,所以 size 永远写死 8,即使 data = self.chunk[8:] 带了尾巴,长度字段也不会跟着变,也不做奇偶补位;(3) jump = len(self.chunk) + pos 用的是**重建之前**的 chunk 长度,首轮 update 时 self.chunk 还是类属性 b''(长度 0),jump 会比正确值少 8,只有靠 cmx_from_sk2 反复 do_update 才收敛。

- **CmxInstruction.update(原版 126-131),对 END_PAGE/END_LAYER/END_GROUP 这类走基类的指令**
  size = len(self.chunk) 是在把 4 字节头拼上去**之前**算的。基类实例的 chunk 初值为空,首轮 update 写出的 size 字段是 0(实际长度 4),要再跑一遍 update 才变成 4。写出结果依赖「update 被调用了几次」这一隐式前提(cmx_from_sk2 恰好调了多次)。

- **Inst16BeginLayer.update(原版 198)**
  长度字段用 len(self.data['layer_name']) 即字符数;Py2 下非 ASCII 图层名(unicode)会写错长度或在拼接时抛 UnicodeDecodeError。这是移植版唯一动过的地方(改成编码后字节数),已在 changes 里声明。

- **Inst16BeginPage.update / Inst16BeginGroup.update 的 struct.pack(sig, *self.data['bbox'])**
  bbox 由 cmx_from_sk2 写成 page_instr.get_bbox() / group_instr.get_bbox(),而 CmxInstruction.get_bbox 在没有任何带 bbox 的子节点时返回 None → struct.pack(*None) 直接 TypeError。空页 / 只有空组的页会炸。原样保留。

- **Inst16PolyCurve.update(原版 347-368)**
  不支持的填充类型走 else: skip = True 之后,直接跳到 self.chunk += self.data['tail'];写出侧 tail 恒为空,于是轮廓引用、点表、节点表、bbox 全被丢掉,指令只剩 style_flags + fill_type,结构不完整(读取侧对应分支是把剩余字节整块塞进 tail,两边不对称)。写出侧目前不产生这类填充,属潜伏问题。

- **CmxInstruction.resolve(原版 120-124)**
  sz = '%d' % len(self.chunk) 算完从未使用(返回的第三项是 offset,行尾留着 `# sz` 注释);同时形参 name 一进来就被 name = '[%s]' % self.get_name() 覆盖,传参无效。纯 UI 辅助,不影响字节。

- **Inst16PolyCurve 中的 `flags >= cmx_const.INSTR_LENS_FLAG`(原版 300/355/425)**
  写法看着像位判断写错,实际不是 bug:LENS(0x04)/CANVAS(0x08)/CONTAINER(0x10) 之上没有别的位,而 FILL|STROKE 最大只有 0x03,所以 `>= 0x04` 与 `& 0x1C` 等价。列在这里只是提示审查者别顺手「修」成 &。


## cmx_model.py

- **cmx_model.py L404-406 CdrxPack.set_defaults**
  identifier 默认写成了 cmx_const.PAGE_ID('page'),而这是 pack 块,应为 PACK_ID。现在没暴露是因为 make_cmx_chunk 永远把 identifier 塞进 kwargs,而 kwargs 在 __init__ 里是 set_defaults() 之后才 update 进 data 的,正好盖住了错误默认值。任何不经 make_cmx_chunk 直接 new CdrxPack 的路径都会写出以 'page' 开头的 pack 块。未改。

- **cmx_model.py L660-670 CmxIxpg.update(以及 L606-618 CmxIxtl.update)**
  {2:'H',4:'I',8:'Q'}.get(...) 没给默认值:rec_sz//4 不属于 {2,4,8} 时返回 None,随后 4 * None / '<' + None 抛 TypeError,而不是给出『记录尺寸非法』这种可读错误。rec_sz 又完全来自调用方 kwargs(cmx_from_sk2 硬编码 16 / 4),没有任何校验。未改。

- **cmx_model.py L640-642 CmxIxpg.set_defaults / L584-586 CmxIxtl.set_defaults / L535-537 CmxIxlr.set_defaults**
  set_defaults 只初始化 identifier 和 records/layers,但 update() 还要读 data['rec_sz']、data['table_id']、data['page'],这三个键没有默认值。构造时不传对应 kwargs,update() 直接 KeyError。未改。

- **cmx_model.py L743-745 CmxRclrV1.get_color(同型:CmxRdotV1.get_dashes L833、CmxRpenV1.get_pen L884、CmxRottV1.get_linestyle L946、CmxRotlV1.get_outline L993)**
  这些 getter 写成 list[index - 1] if index - 1 < len(list) else (),只卡了上界没卡下界。index=0(CMX 里 0 常表示『无』)会取到 index-1 = -1,即静默返回最后一个颜色/线型/画笔,而不是空元组。读取侧(cmx_to_sk2)会因此把『无填充』解析成最后一个颜色。未改。

- **cmx_model.py L76-81 CmxRiffElement.update**
  补位字节是在 sz 算完之后才 += 上去的,而下一次 update() 又用 self.chunk[8:](已含上次那个补位字节)重建 chunk,于是第二次 update 起,声明的 chunk data size 比真实数据大 1。所有写出侧子类的 update() 都会先把 chunk 整个重建一遍,所以实际不触发 —— 只有『不重建 chunk 的类』会踩到,而那正是原版 make_cmx_chunk 未命中时静默退回的 CmxRiffElement 基类。本次按要求把那个退回改成 raise,等于顺带堵住了这条路,但基类 update() 本身的这个 off-by-one 没动。

- **cmx_from_sk2.py index_ixpg(不是本次移植的文件,顺带发现)**
  for page in cmx_pages 循环里用 index 取 ixlrs[index],但循环体内从不 index += 1。多页文档的所有页在 ixpg 表里都会指向第一页的 layer table 偏移。未动。


---

## Step 7 修复清单(2026-09-13)

每条都按 `uc2_compat` 分流:`True` 逐位复现原版(CI 继续用它证明与 Py2 字节一致),
`False`(默认)是修复后的行为。标「不分流」的是对单页输出/合法输入无影响、兼容模式下
字节也不变的修复。代码里的注释编号与这里一一对应。

| # | 位置 | 原版怎么错 | 修复 | 验证 |
|---|---|---|---|---|
| 1 | cmx_from_sk2 make_template | `coef` 多乘 `pt_to_in`、`factor` 少乘,分辨率砍 72 倍,最大坐标恒 451 | 保持 `coef·factor == pt_to_in`,单位见 #28 | A3 量化 0.48mm → **0.0254mm** |
| 2 | 同上 | `max_value` 取 cache_bbox,而它是贝塞尔**紧**包围盒(探针实测),控制点可越界 | 取所有将写出的点(含控制点)与包围盒的最大绝对值 | G6 饱和 0 |
| — | 同上 | `frame = 32512.5` 让极值点恰落 .5 平局,舍入随浮点噪声摆动 | `frame = 32512` | G9 确定性 |
| 3 | 点 / 包围盒 | `int()` 朝零截断,系统偏置;包围盒可能比内容小 | 点四舍五入;包围盒向外取整 | G3 ≈ 0.5 量化步,G4 |
| 4 | `_add_pen` | `int()` 截断,细线 0 宽(f3a 5000 条全灭) | `max(1, round())`,**s16** 封顶(第二轮:libcdr 按 s16 读);笔宽计入量程 | G5 零宽 0 |
| 5 | 全链路 | 无 int16 越界检查,越界 `struct.error` | 可读的 ValueError | — |
| 6 | PolyCurve | 指令长度 u16,>13,100 点 `struct.error` 丢整个文件 | 单指令 <= 6540 点(<= 32767 字节,libcdr 按 **s16** 读长度)。只描边的按子路径/段边界拆;有填充的按包围盒包含关系分组,孔与岛跟随外轮廓同组拆,单组超限才抛可读错误 | f3b_longpath 写出,G8 |
| 7 | svg_translators :378 | 描边宽度多除一次 `dpi_coeff`,无单位描边一律细 0.8 倍 | 删掉那次除法 | f7/f7c 宽度正确 |
| 8 | `_add_line_style` | spec 恒 0x02,虚线位 0x04 从不置 | 有 dash 时置 0x04(依据读取侧 cmx_to_sk2:245) | f4 spec 0x06 |
| 9 | 同上 | cap 查 JOIN 表;`join << 4 + cap` 优先级错 | 查 CAP 表;`(join << 4) \| cap`(依据读取侧 :233-235) | — |
| 10 | `index_ixpg` | 循环不自增,多页都指第 1 页 | `index += 1`(不分流) | — |
| 11 | `make_v1_objects` | 先 `update()` 再判 None | 先判 None | — |
| 12 | 强制闭合 | 贝塞尔终点取 `[-1]`(flag),每条闭合曲线多一个重复点 | 取 `[2]` | ccxcompare 对齐 |
| 13 | 最外层 RIFF 长度 | 压缩版写的是未压缩总长 | 落盘时回填(不碰偏移计算,CorelDRAW 认的是现有偏移) | G7 结构自洽 |
| 14 | make_template | `max_value == 0` 除零 | 保持默认比例 | — |
| 15 | 空子路径 | `path[1][-1]` IndexError(上游 #56) | 跳过孤立 move_to | — |
| 16 | dasharray | 属性值拼成 Python 代码 exec,`"4 2"` 语法错 → 虚线全丢;写出侧 u16 喂浮点 | 按 SVG 规范解析;写出取整 | f4 虚线写出 |

### 第二轮(对抗式审查,2026-09-13)

对第一轮做了对抗式审查:5 个维度找问题,每条由怀疑者尝试证伪。30 条里 29 条被亲手复现为真,
其中写出器 12 项在这里修,门禁 14 项另行重写。上面 #4、#6 已按第二轮结论改写。

| # | 输入 | 第一轮的行为 | 修复 |
|---|---|---|---|
| 17 | 指令 32768–65535 字节 | libcdr 按 s16 读成负数、改读 S32,整页后续内容丢失 | 见 #6 |
| 18 | `stroke-width=""` | 修复模式整份崩溃 | 按 SVG 初始值 1 |
| 19 | `stroke-width="0"` / 负值 | 仍写出 0 宽实线描边 | 不写描边 |
| 20 | `stroke-dasharray="0 4"` | 0 段被抬成 1,圆头点线变短划线 | 保留 0;间隙全 0 视为实线;挡住 inf/nan |
| 21 | 兼容模式 `"4,2"` | Py3 崩,而 Py2 能写出 | 按 Py2 截断,仍与 Py2 字节一致 |
| 22 | 包围盒 | 取 cairo 1/256pt 的 cache_bbox,放大后实测越出实际点 4–46 单位 | 由实际写出的整数点求贝塞尔紧包围盒 |
| 23 | 空白文档、组内全是孤立 move_to | 崩溃 | 写出空页 / 丢弃空组 |
| 24 | 页面正中单点 | `max_value` 趋 0,`coef` 极端,笔宽溢出 | 量程下限 1pt |
| 25 | 远处的孤立 move_to | 不写出却撑大量程、压低分辨率 | 不计入量程 |
| 26 | 粗描边的细图标 | 笔宽不计入量程,截到 65535 或读成负数 | 量程计入 `w·32512/32767` |
| 27 | 渐变填充 | 写 `INSTR_FILL_EMPTY`,图形静默变空心 | 取渐变沿轴平均色写成均匀填充(CMX fountain 未经真机验证,暂不写) |
| 28 | 坐标单位 | 第一轮按「最远点 = 32512」定量程(A3 0.0064mm)。CorelDRAW 按 cont.factor 读,显示正确;但 libcdr 16 位**一律按 1/1000 英寸**读坐标与笔宽(`CommonParser::readCoordinate`:`readS16 / 1000.0`),factor 读了不用 —— Inkscape / LibreOffice、我们自己的 cdr→X 工具读回来尺寸差 1.4 倍(A0)到近 10 倍(小图标) | 装得下就用 1/1000 英寸(0.0254mm,原版给空文档的默认值也正是它);内容离页心超过 32.5 英寸才放大单位 | SCALE 按此判;G1 改成「量化 ≤ 1/1000 英寸,或装不下时利用率 ≥ 0.90」 |
| 29 | 页 / 组 / cont 包围盒 | `get_bbox` 用 sk2 的 `sum_bbox` 合并 CMX 顺序 (x0, 上, x1, 下) 的盒子,「上」取了最小、「下」取了最大 | 按 CMX 顺序取并集 | G7:容器包围盒 == 其中 PolyCurve 包围盒的并集 |
| 30 | BeginPage / BeginGroup 包围盒字段 | 按 UC2 读取侧的布局写 4 x s32;CMX 规范与 libcdr 16 位都是 4 x s16。dev 实测:我们产出的 .cdr 传回 cdr→svg,LibreOffice 读出的页面高 0.03mm,cdr→png 栅格化直接失败 | 写 4 x s16 再补 8 个零字节,指令总长不变(原版在那 8 个字节写的是 s32 高半字,CorelDRAW 照样打开) | G7 按 s16 读并要求后 8 字节为 0;变异 M26 |

复测:兼容模式端到端 20/20、对象树 8/8 仍与 Py2 逐字节一致;审查给的 16 个对抗性输入全部通过。

### 门禁重写与变异矩阵(2026-09-13)

第一轮门禁被审查证明太松(14 条漏洞),重写成严格模式:G3/G4 逐点、节点类型逐字节、PolyCurve 边界与包含关系、
样式引用链、量程、索引链、指令白名单与嵌套……每条检查都在 `ops/ccx/gate_selftest.py` 里有一个篡改产物证明它抓得到
(65 项)。之后又让一个挑战者专门造「错的产物却能过门禁」的文件,找到的 20 条逃逸补掉 17 条,余下 3 条见下。

**变异矩阵**(`tests/mutate.py`):把上面每个修复逐个改回错误行为,门禁必须 FAIL。第一次在常规夹具上跑,24 个变异
活下来 10 个 —— 不是判错,是夹具里根本没有触发那条修复的输入。补了 `tests/adversarial.py`(22 个对抗性夹具,
走同一套门禁,CI 里跑)之后 **杀掉 23 个**;加上 #30–#32 的变异共 **29 个杀掉 28 个**。剩下的 `_add_pen` 封顶
32767 改成 65535 是**等价变异**:量程已经把笔宽算进去,笔宽单位到不了 32512 以上,封顶那一支不可达。

门禁仍然看不见的(挑战轮报告,不是门禁判定逻辑能补的):
- 前端缺陷:录制「源几何」用的就是写出器自己的 SVG 解析,颜色解析错成 R/B 对调时,录下的源和产物错得一样。
  f7 笔宽、f4 虚线是写死的专项,能兜一部分;根治要一份独立的 SVG 期望来源
- BeginLayer 页号/层号/flags、rlst、ixmr master id 这类字段:libcdr 不读,手头没有 CorelDRAW 语义的独立来源
- libcdr 回读(页面尺寸、能否栅格化)不在 CI 里:容器里没有 LibreOffice。#30 就是 dev 端到端回读才发现的,
  发版前在 dev 上跑 `X -> cdr -> svg/png`

### CorelDRAW 真机验收(修复版,web.coreldraw.com,2026-09-13)

`1_渐变文字虚线.cdr`(dev 端 mixed.svg → text2path → ccx_writer v0.1.1):
- 渐变矩形:Curve,1.181″×0.788″(源 30×20mm,差 < 1 个量化步),填充 #82374F = 渐变平均色,黑边 1.44pt
  (源 0.5mm,笔宽取整到 20 单位 = 0.508mm)。中心位置与源一致
- 文字「CDR」:Curve,填充 #2A9D8F,无轮廓
- 虚线:外观、长度 72mm、宽 1.2mm、颜色都对,但对象是「Group of 1 Objects → Curve(填充 #457B9D,无轮廓)」

我们写的虚线是只描边的 PolyCurve(线型 spec 0x06、笔 47 单位、虚线 (3,1)、无组),转换发生在 CorelDRAW 导入时。
`7_描边对照_A到G.cdr` 同一文件 7 条开放直线分离两个假设:

| 线 | 编码 | CorelDRAW 导入结果 |
|---|---|---|
| A 虚线 | spec 0x06,arrows 1(现状) | 组 + 填充曲线,虚线节奏正确(80mm 上 18 段,3mm/1.5mm) |
| B 圆头虚线 | spec 0x06,cap 圆 | 组 + 填充曲线,圆头正确 |
| C 虚线 | spec 0x04(只置虚线位) | Curve,4.248pt 实线 —— **虚线丢失** |
| D 虚线 | spec 0x26(虚线 + 随图缩放) | 组 + 填充曲线 |
| E 实线 | spec 0x02,arrows 1 | Curve,4.248pt(源 1.5mm)可编辑轮廓 |
| F 实线 | arrows 0 | **整条不见** |
| G 虚线 | spec 0x06,arrows 0 | **整条不见** |

结论:与箭头无关(E 开放实线照样是轮廓);CorelDRAW 对 CMX 的虚线轮廓一律转成外观等效的填充对象。
现状 0x06 + arrows 1 就是能拿到的最好结果,不改;把 0x04 与 arrows 0 两条死路写进代码注释。

其余验收文件:
- `4_尺寸`:80×30mm → 79.98×30.00mm、50×50mm → 49.99×49.99mm,中心距 84.99 / 170.03mm(源 85 / 170)
- `6_描边宽度`:1/2/5/10/20mm → 0.991/2.007/5.004/10.008/19.990mm,全是可编辑实线轮廓(原版 0.8 倍的问题确认已修)
- `5_A3精度`:5740 条曲线正常打开,7pt 标签 800% 下笔画平滑可读,对象数与源 PDF 一致(600 色块 + 40 线 + 300 标签)
- `2_真实CDR中文转曲`:外观与原 CDR 的渲染一致、中文是可编辑曲线;**但每个组里多一个看不见的对象** → #31、#32

| # | 位置 | v0.1.1 的行为 | 修复 | 验证 |
|---|---|---|---|---|
| 31 | make_v1_objects / 量程 | LibreOffice 导出 SVG 给每个图形附一个 fill=none stroke=none 的包围盒矩形(class="BoundingBox"),照样写成 PolyCurve,CorelDRAW 里每组多一个看不见的对象 | 既无填充(实色 / 有色标的渐变)也无有效描边的曲线不写出、不计入量程 | 门禁同一约定;a_invisible / a_invisible_near;变异 M27 M28 |
| 32 | BeginGroup | 去掉 #31 后 LibreOffice 的每图形包装组只剩一个对象,CorelDRAW 里一串「Group of 1 Objects」 | 按**输出**判:组里恰好一条 PolyCurve 或一个子组就展开不写;一条曲线被拆成多条 PolyCurve 时保留组 | GROUPS 同一约定;a_groups;变异 M29 M30。前端 translate_g 本来就展开源里只有一个子元素的组,两者不冲突 |

### 仍未修、属能力边界(写进 README)

- 渐变 → 平均色的纯色(#27)、透明 → 不透明:CMX v1 写出器只写纯色
- 虚线长度取整到线宽的整数倍;CorelDRAW 导入时把虚线轮廓转成组 + 填充曲线(外观对,但不再是可编辑虚线)
- 页面尺寸不写(round-trip SVG 高度为 0)
- `<text>` 需上游转曲线;`<image>` 不支持
- 显式单位(mm/cm/in)的描边宽度按 UC2 的 90dpi 约定换算,浏览器按 96dpi,差 6.25%;
  生产链路(potrace / pdftocairo)只出无单位描边,不受影响
- `config.rifx` 是死的(大端输出写不出):我们只写小端,不修
