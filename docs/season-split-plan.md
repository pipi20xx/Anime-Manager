# 番剧分季拆分（Season Splitter）落地方案 · v3

> v3 相对 v2：
> 1. 撤回两条错误判断（`includes=` 不是坑，是有意设计；TVDB 是官方共用 Key）；
> 2. **执行方式改为「纯渲染词」**，不再新增识别阶段 —— 侵入从 ~300 行降到 ~30 行；
> 3. 独立功能页、开关体系保留不变。

---

## 0. 结论（先看这个）

**执行器用现成的 `RenderEngine`，一行"分季专用代码"都不进识别管线。**
分季规则编译成渲染词文本，和用户自定义渲染词一起进 `all_render`，引擎自己会改 `begin_season/begin_episode` + `final_result`。

侵入只有 3 处、约 30 行：

| # | 文件 | 改动 | 行数 |
|---|---|---|---|
| 1 | `recognition/context.py:87` | `all_render` 合流时追加分季规则（按开关/黑名单过滤） | ~6 |
| 2 | `recognition/renderer.py:94-101` | 季集号变化打日志（原打算重算 `processed_name`，实测该方法从未生效，见 §3） | ~4 |
| 3 | `recognition/render/engine.py:101` | 规则先按 `tmdbid` 建索引，避免几千条规则逐条正则 | ~10 |

其余全是**新增文件**（生成器 + 页面 + 接口），不碰既有逻辑。

---

## 1. 先撤回两条我之前说错的话

### 1.1 `includes=` 不是坑，是有意设计

我原来说"`includes=2024` 拿文件名匹配会空转"。**是我理解反了**：正因为不能保证 `meta.year` 解析正确
（番剧文件名里年份经常缺失、或者写成放送年 vs 制作年），拿**原始文件名**做包含匹配反而更稳——
文件里有 `2024` 就一定匹配上，没有就不匹配、退回 SeasonStage 的判定，**不会用一个可能错的元数据去覆盖**。

`evaluate_includes` 还支持 `& |`，这比 Lens 的 Year 条件表达力更强。所以：

> 分季规则生成时，年份消歧用 `includes=2024`（照 Lens 原样），不要改成 `year=`。
> 唯一约束：引擎的条件判定是 `elif` 链（`engine.py:149-161`），`e=` 在 `includes=` 之前，
> 所以**一条规则里不能同时写 `e=` 和 `includes=`** —— 这也正是 Lens 的生成方式（年份规则单独成行、只改 `s=`），完全兼容。

### 1.2 TVDB 是官方共用 Key，不是必须自己申请

`d3158670-26f0-48bb-9267-2f63781dca6b` 是 TVDB v4 的官方共用 Key（Lens 直接内置）。
所以：**默认填这个，能跑；设置页留一个可选覆盖框**（自己有 key 的可以填，配额更宽松）。
这条从"必须配置才能用"降级为"可选"，P2 的依赖风险消失。

---

## 2. 三条路线对比，选侵入最少的

| | A. 纯渲染词（推荐） | B. 独立 Stage | C. 整理层注入（v1） |
|---|---|---|---|
| 识别管线改动 | **~30 行** | ~120 行 | 0 |
| 新增后端 | 生成器 ~300 行 | 生成器 + stage + cache ~450 行 | 同 A |
| 全链路一致（订阅/Emby/识别测试） | ✅ 天然一致 | ✅ | ❌ 只覆盖整理 |
| 单番开关 / 黑名单 | ✅ 靠规则过滤 | ✅ | ✅ |
| 排除集（总集篇） | ✅ 靠分段不规则 | ✅ 直白 | ✅ |
| 命中日志/调试 | ✅ 引擎已有 `🎯 命中专家规则` + `=> [Mod] 季数/集数` | 需自建 | 需自建 |
| 用户手写规则优先级 | ✅ 天然可编排（谁先谁后） | 需自己定 | — |
| 性能 | 需按 tmdbid 索引（10 行） | O(1) 字典 | — |

**A 不只是代码少，能力上也够用**——原因在下一节的分段算法。

唯一真正要盯的是 `processed_name`（第 3 节改动 2）——实测发现模板渲染那段是死代码，
所以不改它，只加日志。

---

## 3. A 路线落地：3 处改动

### 改动 1 · `recognition/context.py:87`（合流，~6 行）

```python
local_render  = self.config.get("custom_render_words", [])
remote_render = [f"[REMOTE]{r}" for r in cached_rules.get("render", [])]
split_render  = SeasonSplitRules.as_render_words(self.config)   # 开关关/黑名单内 → []
# 顺序：用户规则优先（按 TMDB 坐标书写），分季规则最后做归一化
self.all_render = kwargs.get("all_render") or (local_render + remote_render + split_render)
```

**为什么放最后**：用户规则是"对识别结果的显式修正"，他们写的时候脑子里是 TMDB 坐标；
分季是"自动归一化"，放最后才不会把用户已有规则的条件前提打乱。
（如果反过来，用户写的 `s=1;e=13` 规则会因为分季先跑而永远不命中。）

`SeasonSplitRules.as_render_words()`：读 `season_split_rules` 表 → 过滤 `status=active` + 不在黑名单
→ 返回已编译好的文本行（**不在这里编译**，保存时编译好存库，热路径零计算）。
进程内缓存 + 保存时 `reload()` + 30s 版本轮询兜底多 worker。

注入的每一行都带 `[SPLIT]` 前缀（只在内存里加，不落库），`RenderEngine` 见到它会把日志来源标成
`[分季]`，和用户自己的 `[私有]` / 社区 `[社区]` 区分开：

```
🎯 [Render][分季] 命中专家规则: @?{[tmdbid=65942;type=tv;e=67-85]} => {[s=4;e=EP-66]}
┃  => [Mod] 季数: S1 -> S4
┃  => [Mod] 集数: E85 -> E19
⏩ 跳过 1 条其他番的分季规则        ← tmdbid 预筛跳过的
🔀 季集号已变更: S1E85 → S4E19      ← renderer 的标注日志
```

**执行顺序与优先级**：用户规则 → 分季规则。因为分季在最后，它会覆盖前面规则对 `s=` 的修改；
两条都命中时以分季结果为准（分季是"结构归一化"，用户规则是"局部修正"）。
反过来的代价更大：用户按 TMDB 坐标写的 `s=1;e=13` 规则会永远不命中。
若要否决某番的分季结果，用**黑名单**或直接在页面里改分组，不要靠"再写一条规则盖回去"。

**一个前提**：分季规则的 `e=EP-xx` 偏移是相对 TMDB 原始集号算的，假定前面的规则没有改过集号。
如果某番同时挂了改集数的自定义规则（偏移定位 `A <> B >> Expr`），建议把该番加入黑名单，避免两者打架。

### 改动 2 · `recognition/renderer.py:94-101`（季集变更日志，~4 行）

**原计划是「重算 processed_name」，实测后改成只打日志**——原因见下。

`_prepare_data_packet` 里那段「用改名模板渲染 processed_name」（`:116-143`）调的是
`Renamer.render_name(...)`，而 `organizer_core/renamer.py` **根本没有这个方法**
（只有 `format_path` / `sanitize` / `get_default_rules`），且外面套着 `try: ... except: pass`。
也就是说这段模板渲染从来没生效过，`processed_name` 一直是**内核清洗后的原文件名**。

所以：
- 不存在「规则改了季集、processed_name 还是旧号」的错位（processed_name 里根本没有季集号）；
- 反而**不能**去改它：`{processed_name}` / `raw_processed_name` 模板的语义就是「渲染后的原名」，
  改成 `S02E01` 会污染既有改名结果。

最终只保留一行可观测日志：

```python
if after_se != before_se:
    ctx.log(f"🔀 季集号已变更: S{before_se[0]}E{before_se[1]} → S{after_se[0]}E{after_se[1]}")
```

> 若以后确实想让 processed_name 变成「模板渲染名」，正确的做法是给 `Renamer` 补一个
> `render_name(template, ctx_dict)`，并同时修 `_prepare_data_packet`（两处一起生效），
> 那是独立于分季的一次行为变更，需要单独评估对 `raw_processed_name` 模板的影响。

### 改动 3 · `recognition/render/engine.py:101`（tmdbid 索引，~10 行）

现在 `apply_rules` 对每个文件遍历全部规则，每条都跑一次 `re.search(r"\{\[(.*?)\]\}", ...)`。
2000 番 × 2 条 = 4000 条 → 每文件 4000 次正则，约 2-4ms，加上用户规则会更慢。

```python
# 循环前建一次索引
index = {}
for r in rules:
    m = _TMDBID_HINT.search(r)          # 预编译，只认 tmdbid=
    index.setdefault(m.group(1) if m else "*", []).append(r)
candidates = index.get("*", []) + index.get(current_tmdb_id, [])
```

4000 条压成 O(1)，对既有规则也一并加速。

---

## 4. 规则怎么生成：分段 + 偏移（Lens 的算法，正好能表达排除集）

映射表 `(orig_s, orig_e) → (virt_s, virt_e)` 编译成规则的算法：

1. 按原始季分组，按 `orig_e` 排序；
2. **切段**：只要 `orig_e` 连续、`virt_s` 相同、`(orig_e - virt_e)` 偏移相同，就在同一段内；
3. 每段出一条规则：`@?{[tmdbid=X;type=tv;e=a-b]} => {[s=VS;e=EP-off]}`（`off == 0` 时省略 `e=`）；
4. `virt_s == orig_s 且 off == 0` 的段 → **不出规则**（本来就对，省得污染规则表）；
5. 段与段之间**允许有洞** —— 洞里的集不被任何规则命中 → 保持原编号。

第 5 条就是"排除集"的实现：`S1E12.5`（总集篇）标排除后，`1-11` 和 `13-24` 成为两段，
`12.5` 落在洞里不动，后面各段各自带自己的偏移，不会串。

再叠一条年份规则（照 Lens）：`@?{[tmdbid=X;type=tv;includes=2024]} => {[s=2]}`，只改 `s=` 不改 `e=`。
同一年份对应多个虚拟季时无法消歧 → 跳过并注释说明（Lens 的做法）。

**能省规则数**：`off == 0 && virt_s == orig_s` 的段不出规则，大多数番只有 1-3 条规则。

---

## 5. 独立功能页（不变）

`/season-split`，导航「工具」组，图标 `mdi-call-split`。三 tab + 顶部常驻开关条。

### 5.1 顶部开关条

| 控件 | 语义 |
|---|---|
| `关闭 / 只预览 / 启用` | 关闭=不出规则；预览=页面生成但不入 `all_render`，只在调试器里看效果；启用=注入 |
| 生效范围 | ☑整理 ☑订阅匹配 ☐识别测试页 |
| 黑名单 | 番级 + 集级弹窗 |
| 规则计数 | 已编译 N 条规则 / 缓存版本 / 手动重载 |

> 注意：A 路线下"只预览"的实现要简单改一处——`as_render_words` 在 preview 模式返回 `[]`，
> 调试器走独立的 `compile→dry-run` 接口。不额外加运行时分支。

### 5.2 Tab 1 · 规则库

表格：番名 / TMDB / 来源 / 参照源 / 分组 `12+14` / 规则数 / 状态 / 更新时间 / 操作。

- 状态：`草稿 / 生效 / 停用 / ⚠结构已变`（`tmdb_hash`）
- 来源：`手动 / SYTMDB / 自动 / 历史`（见 5.2.1）
- **批量扫描候选**：扫库内已识别的 TMDB 剧集，比对 `TMDB 季结构 vs TVDB 定义`，列出疑似需分季的番，一键加入待办。
- 操作：编辑 / 启停 / 删除 / 写剧集组 / 复制规则文本

### 5.2.1 规则来源（手动 / SYTMDB 导入 / 自动生成）

规则库卡片上除了状态，还有一个「来源」标签，用来回答「这条规则是谁写进来的」。
落库字段是 `season_split_rules.origin`，**只在创建时写一次，之后不再改**（启停、工作台再编辑都保留原值）：

| 值 | 卡片显示 | 写入路径 |
|---|---|---|
| `manual` | 手动 | `PUT /api/season-split/rules`（分组工作台「保存」/「保存并启用」） |
| `sytmdb` | SYTMDB | `POST /api/season-split/sytmdb/import`（规则库「导入 SYTMDB」，由 `sytmdb_source.build_rule` 写入） |
| `auto` | 自动 | 识别链路 `service.auto_generate_rule()`（开关 `season_split_auto_generate` 打开时现场生成并启用） |
| `NULL` | 历史 | 升级前保存的老规则，当时没有这一列，无法追溯（不臆测成手动/自动） |

- 与 `reference`（依据：tvdb / bangumi / curetmdb / gap / year / finale / fixed / sytmdb）正交：
  `reference` 回答「按什么依据分的季」，`origin` 回答「谁写进来的」。自动生成与手动保存都可能用 `tvdb` 依据，
  所以只靠 `reference` 分不出来——这正是新增 `origin` 的原因。
- 列表接口支持过滤：`GET /api/season-split/rules?origin=manual|sytmdb|auto|legacy`（`legacy` = `origin IS NULL`）。
- 存量数据回填：启动迁移只把 `reference='sytmdb'` 的老数据标成 `sytmdb`（这是唯一可靠的信号），其余保持 `NULL`。

### 5.3 Tab 2 · 分组工作台

三栏：`原始季逐集`（带 air_date 间隔虚线）｜`分组编辑器`｜`自动生成`。

**自动生成 5 种依据**：

| 依据 | 说明 |
|---|---|
| 参照源集数 | TVDB / Bangumi / CureTMDb 表 —— **三套同时生成、并列可切换**（规则表默认关闭，地址需自己填）|
| **播出间隔** | `air_date` 间隔 > N 天（默认 45）处切 —— split cour 的天然特征，无参照源时最好用 |
| 播出年份 | 跨年处切 |
| finale 标记 | `episode_type == "finale"` 处切 |
| 固定集数 | 12 / 13 / 24 / 26 |

编辑器支持：拖拽改序、改起止集、改季名、**逐集覆盖**（任意一集指定目标或标排除）、
重新生成时保留人工修改（弹 diff 确认）。

底部输出三 tab：**映射表** / **剧集组 JSON**（写 SYTMDB）/ **渲染词文本**（可直接贴进「设置→自定义渲染词」，也可导出）。

### 5.3.1 参照源是「并列」而不是「按优先级取第一个」

生成方案时后端会把 **TVDB、Bangumi（以及启用时的 CureTMDb 规则表）各取一次**，
每个源各出一套候选分组，全部丢进右侧「自动生成」：

- 每套独立判断「是否需要拆分」（该源定义集数 < TMDB 实际集数）；
- 「参照优先级」降级为**默认选中哪个**，不再决定"只取哪一个"；
- 列表上方的 chip 会显示 `TVDB 12 + 14`、`BANGUMI 12 + 14` 这类摘要，需要拆分的源用 info 色标出；
- 代价：一次生成会多打几次接口（Bangumi 续集链最重），换来的是可以直接对比两套定义。

### 5.4 Tab 3 · 高级

raw JSON / 渲染词文本直编 · 默认参照优先级 · TVDB Key（留空=官方共用）·
CureTMDb 表地址（**默认留空，不启用**；填了才在「生成方案」时勾选使用）·
**映射调试器**：输文件名 → 跑一遍识别 → 显示 `解析 S/E → 映射后 S/E → 命中哪条规则`（直接复用引擎日志）。

---

## 6. 黑名单 / 开关（三层）

| 层级 | 位置 | 作用 |
|---|---|---|
| 全局 | `season_split_mode` = `off/preview/on` | 总闸 |
| 全局细分 | `season_split_scope` = `{organize, subscription, recognition_test}` | 哪些入口生效 |
| 单番 | `season_split_rules.status` | 该番规则是否进 `all_render` |
| 单集 | `excluded_eps` / 标题正则 | 该集不参与重排 |

`season_split_scope` 在 A 路线下靠 `ctx` 的入口标记实现（`context.kwargs` 里加个 `entry`），约 3 行。

---

## 7. 数据模型

```python
class SeasonSplitRule(SQLModel, table=True):
    __tablename__ = "season_split_rules"

    tmdb_id: int = Field(primary_key=True)
    title: str = ""
    status: str = "draft"            # draft / active / disabled
    reference: str = ""              # 依据：tvdb / bangumi / curetmdb / gap / year / finale / fixed
    origin: str | None = None        # 来源：manual / sytmdb / auto（老数据 NULL）

    groups_json: str = "[]"          # 人写的：[{order, name, start, end}]
    overrides_json: str = "{}"       # {"1-13": {"s":2,"e":1}} 逐集覆盖
    excluded_eps_json: str = "[]"    # ["1-12.5"]
    mapping_json: str = "{}"         # 编译产物（页面展示用）

    render_words: str = ""           # ★ 编译产物：多行规则文本，运行时直接 concat
    group_json: str = ""             # 剧集组 JSON
    tmdb_hash: str = ""
    created_at / updated_at
```

**编译在保存时发生**，运行时只 `splitlines()` 后合流。热路径零计算。

`config.json` 新增：`season_split_mode` / `season_split_scope` / `season_split_blacklist` /
`season_split_exclude_patterns` / `season_split_priority` / `season_split_source` / `tvdb_api_key`（默认官方 Key）。

---

## 8. 算法要点（移植 Lens `splitter.py`）

内核仍是 `去重 → 摊平 → 重灌`，但边界来源统一成 groups：

```
参照源(每季集数) ─┐
播出间隔 ────────┼→ groups → mapping → 分段编译成渲染词
年份/finale/固定 ─┤
人工编辑 ────────┘
```

硬要求：
1. `air_date` 缺失率 > 30% 不摊平，改按集号顺序切并告警；
2. 同日去重**只在跨季时**生效（同季连播不删）；
3. `S0` 不参与摊平，只进查找表；
4. Bangumi 链的 `剧场版/OVA` 先过滤（剧集组表达不了）；
5. 原始集数溢出定义总和 → **判失败**，不给默认季名硬跑；
6. 连载中 → `volatile`，禁止一键启用。

---

## 9. 排期（比 v2 轻）

| 阶段 | 内容 | 人日 |
|---|---|---|
| P0 | 决策确认 + 3 个真实番手工核对（重点验证"间隔切分"够不够） | 0.5 |
| P1 | 纯函数：`grouping.py`（5 种依据）+ `compiler.py`（分段/偏移/年份规则）+ 离线 fixture 测试 | 2 |
| P2 | `reference.py`：TVDB（共用 key）/ Bangumi 续集链 / CureTMDb 表 | 1.5 |
| P3 | 表 + `store.py` + 接口 + 编译缓存 | 1.5 |
| P4 | **3 处侵入改动**（合流 / processed_name / tmdbid 索引）+ 回归 | 0.5 |
| P5 | 前端：规则库 + 工作台 + 高级 | 4 |
| P6 | 剧集组写 SYTMDB（扫描候选已取消，见下） | 1.5 |
| P7 | ~~存量迁移 + 4 条链路回归~~ **已取消** | — |
| | **合计** | **11.5 人日** |

> **P6 的「批量扫描候选」与 P7「存量迁移」已按需求方判断取消**（无实际价值）。
> 因此最终交付范围为：算法内核 + 参照源 + PG 规则表 + 11 个接口 + 3 处侵入 + 独立页面 + 剧集组写入。

**里程碑**：P0–P1 完成（2.5 天）就能拿到"自动生成 + 编译出的渲染词"，**手工贴进现有自定义渲染词**立刻验证真伪，
一行生产代码都不用改。这是最省的一次押注。

---

## 10. 什么时候该升级到「独立 Stage」

A 路线够用的前提是：映射能表达成**分段线性的 (e 区间 → 偏移)**。以下情况会顶到天花板，那时再升 stage：

1. 需要**按标题/集名**决定归属（不只是集号区间），例如按 `episode_type` 把 SP 单独归季；
2. 需要**跨 tmdb_id**（一部番拆到两个 TMDB 条目）；
3. 需要运行时**读数据库的额外信息**（比如按文件哈希白名单）；
4. 规则数超过 ~2 万条，`all_render` 合流本身变成负担。

到那时把 `SeasonSplitRules.as_render_words()` 换成 `SeasonMapStage.apply()` 即可，
**数据模型和页面完全不用改**（这也是把它设计成"表里存 groups、编译成文本"的好处）。

---

## 11. 验收

1. 一条规则（TVDB 依据）→ 整理预览 `S01E13` 落到 `Season 2/S02E01`；
2. 关规则 → 回到 `Season 1/S01E13`；
3. `preview` 模式：页面能编译、能看调试器，文件不动；
4. 黑名单：日志无分季规则、文件不动；
5. 排除集 `S1E12.5`：该集保持原位，后续集号不串；
6. 无 TVDB 数据的番：用 `gap=45` 自动切 2 组且人工确认正确；
7. 剧集组写 SYTMDB，`routers/sytmdb.py:158` 能读回且一致；
8. 4000 条规则下识别 P99 增量 < 2ms；
9. 规则保存后 30s 内所有 worker 生效。

---

## 12. 实现状态（第一批已落地）

### 已完成

| 文件 | 说明 |
|---|---|
| `backend/season_split/models.py` | Lens `media_models` 移植（EpisodeMap / SeasonEntry / SeriesEntry / LogicSeries） |
| `backend/season_split/splitter.py` | Lens 主算法移植：同日去重 → 摊平 → 按定义重灌（同步 IO 换异步 fetcher，逻辑不变） |
| `backend/season_split/compiler.py` | 分段+偏移编译渲染词、`includes` 年份规则、（映射⇄分组）、轻量规则回放 |
| `backend/season_split/grouping.py` | 5 种自动生成依据 + `validate()` 自检 |
| `backend/season_split/reference.py` | TMDB 适配层 / TVDB v4 / Bangumi 续集链 / CureTMDb 表 |
| `backend/season_split/store.py` | **PostgreSQL** 规则表读写 + 进程内编译缓存 + 30s 版本轮询 |
| `backend/season_split/service.py` | 预览 / 编译 / 保存 / 写剧集组 / 调试器 |
| `backend/season_split/selftest.py` | 离线自测（58 项，零依赖，含「规则回放 == 映射表」） |
| `backend/season_split/integration_check.py` | 真实链路自检（24 项：表 DDL / 真引擎 / 开关 / 合流） |
| `backend/routers/season_split.py` | 11 个接口 |
| `backend/models.py` | `SeasonSplitRule` 表（PG，JSONB 列，`tmdb_id BIGINT` 天然主键不带序列） |
| `backend/config_manager.py` | 8 个配置项（含 `tvdb_api_key`，默认空=官方共用 Key） |
| `backend/recognition/context.py` | 分季规则合流进 `all_render`（放最后）+ `entry` 入口标记 |
| `backend/recognition/renderer.py` | 季集号变更日志（`processed_name` 语义不变，见 §3 改动 2） |
| `backend/recognition/render/engine.py` | `tmdbid` 索引跳过无关规则（性能） |
| `frontend/src/api/seasonSplit.ts` / `views/season/SeasonSplitView.vue` | 独立页面：规则库 / 工作台 / 高级（黑名单+调试器） |
| `frontend` 路由 + 导航 | `/season-split`，「工具 → 番剧分季」 |

### 验证

**离线自测（纯函数内核，零依赖）**

```
cd backend && python -m season_split.selftest     # 58/58 通过
```
覆盖：参照源 12+14 重灌、三季、间隔切分、跨年 includes、排除集、同日去重、finale、分组⇄映射往返、溢出。

**真实链路自检（需要项目依赖，不需要数据库）**

```
cd backend && python -m season_split.integration_check     # 24/24 通过
```
覆盖：`SeasonSplitRule` 在 PG 方言下的 DDL（`tmdb_id BIGINT` 主键、无 SERIAL、JSONB）；
真实 `RenderEngine.apply_rules` 执行分季规则（`S1E13 → S2E1`、`S1E5` 不动、
`includes=2024` 命中 → `S3`、其它番的规则被索引跳过、空规则表 no-op）；
**26 集逐集回放 == 映射表**；`processed_name` 不被污染；
开关 / scope / 黑名单；`RecognitionContext.all_render` 合流保持原有 `or` 语义。

**静态检查**：18 个改动文件 `py_compile` 通过；前端 `vue-tsc --noEmit` 通过。

### 范围收口

- **批量扫描候选**：不做（需求方判断无价值）。
- **存量迁移（已入库文件重排）**：不做（需求方判断无价值）；需要时按映射表手工处理即可。
- 设置页联动（把 `season_split_*` 搬进「系统设置 → 基础配置」）：可选，页面自带的开关条已够用。
- `subscription_matcher.py` 已补 `entry="subscription"`（该入口 scope 默认关，行为不变）。

### 上线步骤

1. 重启后端：`init_db()` 自动建表，启动时 `store.reload()` + 30s 轮询启动；
2. 打开「工具 → 番剧分季」，先用默认 `只预览` 建 1~2 条规则；
3. 在识别测试页跑一个第 13 集的文件，看日志出现 `🔀 季集号已变更: S1E13 → S2E1`；
4. 确认无误后把开关切到 `启用`，再跑整理预览看落盘路径 `Season 2/S02E01`；
5. Emby 显示需要额外点「写 SYTMDB」（写剧集组），二者配套才生效。

---

## SYTMDB 一键导入（规则库 → 直接用那边的剧集组）

规则库里多了一个「导入 SYTMDB」按钮：把 SYTMDB 上**已经画好**的剧集组直接搬成规则，
**不拿 TMDB ID 重新生成**——季号、集号、组名都按 SYTMDB 的数据来。

### 用到的 SYTMDB 接口

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/items/tmdb-tv?has_episode_group=yes&page=&limit=` | 列出所有条目；新版本原生支持 `has_episode_group` 筛选，老版本静默忽略该参数 |
| GET | `/api/tv/{tmdb_id}/episodegroup` | 读单部番的剧集组 JSON |

老版本 SYTMDB（`routers/items.py` 只认 `search_term` / `source` / `poster_status` /
`genre` / `year` / `month` / `sort_by` / `page` / `limit`）会忽略 `has_episode_group`，
所以 `sytmdb_source.fetch_tmdb_tv_items()` 翻完全部分页后再按响应里的
`has_episode_group` 字段兜底过滤一次——新老版本都能正确取到候选。

### Anime-Manager 侧新增端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/season-split/sytmdb/candidates` | 候选列表：组数 / 集数 / 改动集数 / 特别篇数 / 是否已有规则 |
| POST | `/api/season-split/sytmdb/import` | `{tmdb_ids?: [..], status: "active"\|"draft", overwrite: bool}`，`tmdb_ids` 留空 = 全部「会改动」的 |

### 转换规则（`backend/season_split/sytmdb_source.py`）

1. **剧集组 → 映射表**：组内 `episodes[].order` 就是组内最终集号，因此
   `(season_number, episode_number) → (group.order, order+1)`，与 SYTMDB 完全一致。
2. **S0 特别篇照搬**：源把特别篇放进第 N 组，就映射成 `S0Exx → SNExx`，**不丢弃**；
   只有同一 `(季, 集)` 在源里出现两次时会去重（保留第一次，重复集不占编号）。
3. **判定「有没有改动」**：`will_change = 存在 原坐标 ≠ 目标坐标 的集`。
   —— 所以「只有一个组、只是调了顺序」或「只加了一集特别篇」的 DIY 条目同样会判定为可导入；
   与 TMDB 原生季结构完全一致的条目才会显示「无改动」并且不默认勾选。
4. **映射表 → 渲染词**，四层递进，每层都用 `compiler.apply_rules_to_episode` 做逐集回放自检：
   - 紧凑区间：`@?{[tmdbid=..;type=tv;e=13-24]} => {[s=2;e=EP-12]}`
   - 带季号 + 季号倒序：源里跨季集号重叠时用（避免规则互相二次改写）
   - 混合：区间规则（S≥1）+ 逐集规则补 S0 / 乱序集
   - 全逐集：任意置换都能表达；**有环时用「临时季号」两阶段搬运**（`SnExx → S9xxx → SNExx`），
     所以像《桃子男孩渡海而来》那种环形自定义顺序也能 1:1 导入
5. **落库字段**：`groups_json` 是编辑器能改的区间分组，`mapping_json` 是逐集真值，
   `group_json` 保留 SYTMDB 原文（「写回 SYTMDB」直接可用）；区间表达不了源数据时
   （含特别篇/乱序/跳号）额外写 `overrides_json`（扁平 `"季-集"` 键），
   保证编辑器里再保存一次也不会改形。
6. 导入不依赖 TMDB（不需要 API Key），写完统一 `store.reload()` 一次。

### 已知边界

- **S0 特别篇的规则当前不会命中**：`recognition/render/engine.py` 里
  `curr_s = int(meta.get("begin_season") or 1)` 会把季 0 当成季 1，因此 `s=0` 的条件永远不成立。
  带特别篇的条目仍会**完整**写入规则、映射表与剧集组（Emby 显示按剧集组走，不受影响），
  只是"特别篇跟着改名进对应季"这一步暂时不生效。
- 有 2 条条目 `has_episode_group=true` 但剧集组文件为空（《恶魔高校D×D》《未来日记》），
  导入时会以「空分组」跳过；
- 与 TMDB 原始季结构完全一致的分组不会产生规则（`will_change=false`），列表里标「无改动」。

离线自测（不联网、不接库，42 项，覆盖 S0 / 自定义顺序 / 环形置换 / 重复集 / 无改动）：

```bash
cd backend && python -m season_split.sytmdb_selftest
```

---

## 连番号折算（TMDB 已分季 / 发布侧按 1..N 连续编号）

### 场景

分季判定「不需要拆」有两种含义，别混：

| 情况 | TMDB | 发布侧 | 项目怎么处理 |
|---|---|---|---|
| 需要拆（现有） | 一季 24 集（合并了） | 按 12+12 或 1..24 都行 | 用参照源拆成两季 + 写剧集组 |
| **需要折（本节）** | S1 12 集 + S2 12 集（本来就对） | 按 `第 1 话…第 24 话` 连续编号 | 文件名里的 13 在 TMDB 里不存在，其实是 `S2E1` |

第二种情况下 `need_split=false`，参照源帮不上忙——因为答案就在 TMDB 自己的季边界里：
「连番号 i」就是「摊平后第 i 集」。

### 开关

`season_split_use_absolute_rules`（高级 → 默认参数「无需分季时附带『连番号折算』」，默认关）。
开启后**只在编译渲染词时多追加一段规则**，关掉与以前完全一致：

```
# [自动分季] 番名 TMDB:12345 依据=tmdb 2026-11-07
@?{[tmdbid=12345;type=tv;e=13-24]} => {[s=2;e=EP-12]}
```

- 由 `compiler.absolute_rule_lines()` 生成：`(1, i) → flat[i-1]` 的 TMDB 坐标，
  再交给现成的 `generate_render_words()`（offset==0 的段落本来就不出规则）；
- `includes` 年份规则在这段里固定关闭，避免 `…(2024)… - 13` 被年份规则把季号按回去；
- 三季番 → 两条：`e=13-24 => S2`、`e=25-36 => S3`；单季番 → 空（连番号与 TMDB 坐标一致）。

### 两个入口

1. **分组工作台**（手动）：开关开着且 `need_split=false` 时，「自动生成」里多一个
   **「TMDB 季边界」** 候选并默认选中，分组就是 TMDB 自己的季边界（恒等），保存即可。
2. **识别时自动**：`auto_generate_rule()` 判定无需分季时先尝试 `_save_absolute_rule()`：
   开关开着 + TMDB ≥2 季 + 真能生成规则 → 建一条 `reference=tmdb`、`origin=auto` 的 active 规则
   并当场注入本次识别，**不写黑名单**；任一条件不满足才回到原来的「加入黑名单」。

### 为什么不写 SYTMDB

分组、`mapping_json`、`group_json` 全是 **TMDB 原生坐标的恒等映射**，追加的那一段只存在于
`render_words` 里。所以：

- 剧集组推上去等于 TMDB 原生结构，没有意义也不需要；
- 自动生成的路径根本不调用 `push_episode_group()`；
- 在工作台里重新保存也不会丢这段（开关还在，`compile_rule` 会重新追加）。

### 与黑名单的关系

开关只对「TMDB ≥ 2 季」的番生效，所以黑名单并没有消失，只是范围缩小了：

| 情况 | 结果 |
|---|---|
| TMDB ≥ 2 季 | 生成一条「只写渲染词」的规则，**不进黑名单**（下次 `auto_generate_rule()` 第一步就被 `get_rule` 短路） |
| TMDB 单季、集数 ≥ 15 | 拆不出两季、也没有跨季边界 → 进黑名单（原状态） |
| TMDB 单季、集数 < 15 | **快速拉黑**：`grouping.single_season_too_short()`，连 TVDB / Bangumi 都不拉（省一次网络往返） |
| 开关关着 | 完全维持旧行为 |

- 阈值在 `constants.SINGLE_SEASON_BLACKLIST_MAX = 15`，判定是 `episode_count < 15`（正好 15 集不拉黑）；
- 快速拉黑用的是识别链路已经拿到的 `ctx.tmdb_data["seasons"]`，零额外请求；
  那会儿没有季表（智能记忆只给了 id + type）时退回原来的 preview 流程；
- 历史上已经被拉黑的番不会自动补，要在「黑名单」页删掉才会重新触发。

### 规则库里的「只写渲染词」

这类规则 `reference = tmdb`，在规则库里是独立的一类：

- 卡片上有 **只写渲染词** 标签（悬停提示「不写 SYTMDB 剧集组」）；
- 「剧集组」按钮禁用；即使绕过 UI 直接调接口，`push_episode_group()` 也会拒绝写入；
- 顶部工具栏多了 **类型** 筛选：`全部类型 / 分季拆分 / 连番号折算`
  （接口 `GET /api/season-split/rules?kind=split|absolute`），需要单独查看或清理这一批时用它。

### 边界

- 文件名带季标（`S2E01`）→ 不命中 13-24，保持原值；带季标又问连号（`S2E13`）→ 命中，能救回来；
- 合集（`13-24` 打包）→ 渲染引擎会同时改起止集号，落成 `S2E1-12`；
- S0 特别篇不参与连番号（不占序号）；
- TMDB 少登记了几集时可能把 `S1E13` 误折成 `S2E1`——规则落库后卡片可见（依据=TMDB 季边界、
  来源=自动），停用/删除即可；
- 需要拆分的番（TMDB 合并季）不会走这里：`need_split=true` 时既不建 `tmdb` 候选，也不进折算分支。

离线自测已覆盖：
`case_absolute`（14 项）—— 规则文本、13→S2E1、24→S2E12、12 不变、S2E1 不被二次改写、
单季不生成、三季两条、恒等分组回编译仍是恒等映射；
`case_scope`（8 项）—— 单季 12/14 集拉黑、15/24 集不拉黑、两季不拉黑、S0 不计数、集数未知/无季表不拉黑。

