---
name: skillweave
description: "当要整理或优化一个 skill pack（含 1..N 个 skill 的仓库/目录）的分层披露时用：先构建文档树（节点 = 文档、边 = 披露、层 = 披露深度），再逐文档量超限与到不了根，然后按批次改、按批次复测。触发：「skill pack 太大」「Agent 选不对 skill」「一级菜单太长」「分层披露」「整理 skill 仓库」「技能互相抢题」。"
license: MIT
---

# SkillWeave · 把一个 skill pack 的文档树量出来，再收敛它的分层披露

**一句话**：分层披露的失败形态不是「文件太大」，而是**某一级摆出的选项太多** —— Agent 站在那一级选不对，
就再也到不了正确的细节。这个 skill 先**量**（可复现的数字），再**改**（四类动作），最后**重测**。

## 什么时候用

- 一个 skill pack 里技能变多，Agent 开始「选错」「该触发的不触发」「被兄弟抢走」。
- 要给一个包做体检：一级菜单多长、哪个技能正文超标、哪些文件没人点名、哪两个技能互相抢题。
- 改完结构要证明「没变差」。

**边界**：不装/不卸/不发布技能（那是安装器的事）；不替你判断「这个技能该不该存在」；
不改任何 pack 里的文件，除非你按 `references/` 的做法动手并**在副本上**验证。

## 输入是什么（先把定义说死）

- **一个 skill pack = 一个仓库或目录，含 1 个或多个 skill。**
- **输入 = 一整套含 `SKILL.md` 的文件夹树**（整个 pack 目录），不是单个 `SKILL.md`。
- 契约是 [agentskills.io 规范](https://agentskills.io/specification)：`<skill 名>/SKILL.md` + 可选
  `scripts/` `references/` `assets/`。工具**不依赖任何 agent 框架**：输入只有目录与文件，不认识任何
  agent 侧的目录约定、安装器或状态文件。
- pack 在 git 仓库里时只算 **git 跟踪**文件；目录里的未跟踪垃圾会被单列、不混进任何度量。
  刚新建还没提交的技能目录也会被算作未跟踪 —— 先提交再量。

## 文档树与「层」（本 skill 的核心概念）

- **节点 = 一份文档**（`SKILL.md`、`references/*.md`、`scripts/*.py`…），每份记它所属的 skill。
- **边 = 披露**：一份文档正文里真实写出的另一份文档路径。URL、代码块里的示例路径、不带目录的裸文件名都不算。
- **层 = 披露深度**：根为 L1（根 = 每个 skill 的 `SKILL.md`；单入口形状下只有 1 个根），根直接披露的为 L2，
  L2 披露的为 L3，依次递推。走不到的记「到不了根」。
- **每份文档的量**：字符数、估算 token、行数、披露了几项（fanout）、被几项披露。
- 解析基三处：该文件所在目录 → 该 skill 目录 → **最近的 `SKILL.md` 所在目录**（嵌套 skill 的相对引用按它自己的根写）→ pack 根。
- path 字符集含非 ASCII：包里的文件名可能是中文，只认 ASCII 会把它们误判成「到不了根」。

## 跑一轮的命令顺序

```
prepare   出工作副本 + 基线        → 原本在 git 仓库里就开 worktree；不是 git 才 copy + git init
disclosure 构建文档树 + 逐文档体检  → DISCLOSURE.md / disclosure.json / TODO.md（待办清单）
dispatch  事实补全 + 划批 + 落 prompt → dispatch/{plan.json,state.json,baseline.json}
（把 batch-N.prompt.md 交给执行者，只收提案，不让它写盘）
apply     校验并落盘提案            → 错就整条不动；每条记 patch，可单条回退
verify    集合级复测                → 该消的消了 / 无新增 / 外部集合不变 / 拆分守恒
judge+score  只在动了 description / 入口 SKILL.md / INDEX.md 时才跑
visualize 交付时收尾                  → TREE.md + TREE.html 落进 pack 根，README 指路（随包持久化，别只留在 /tmp）
```
失败不整批回滚：通过的条目保留，未通过的条目改输入后在已改动的树上继续修，只有无法修正的条目才回退它自己那一条。

## 命令（全部只读命令在下面）

```bash
SW=<本 skill 的 scripts/weave.py 绝对路径>     # 装好后：<skills 目录>/skillweave/scripts/weave.py
PACK=<要分析的 pack 目录>                      # 例：某个 skill 仓库的根

python3 "$SW" tree   "$PACK" --out /tmp/sw     # 文档树：pack → 类目 → skill → 章节/文件
python3 "$SW" layers "$PACK" --out /tmp/sw     # 老口径的层汇总（常驻成本 / 正文规模 / 孤儿与悬空）；新口径用 disclosure
python3 "$SW" audit  "$PACK" --out /tmp/sw     # 审计四段：体积 / 孤儿悬空 / 同层抢题 / 成本两组数
python3 "$SW" checks "$PACK" --out /tmp/sw     # 七条检查（含硬编码路径、内嵌密钥；命中退 1）
python3 "$SW" propose "$PACK" --out /tmp/sw    # 四类动作的提案：**默认 dry-run，不改盘**
python3 "$SW" visualize "$PACK"                 # 生成物落回 pack：TREE.md + TREE.html（文档树与互指图的文本版与可视化）
python3 "$SW" collapse  "$PACK" --out /tmp/sw   # 可选方案：塌成「L1 = 1 个 skill 入口」的账 + 伞体 + git mv 清单（dry-run）
python3 "$SW" disclosure "$PACK" --out /tmp/sw            # 第二步：披露链递归 + 逐文档体检 → DISCLOSURE.md
python3 "$SW" prepare "$PACK" --dest /tmp/pw/ws --out /tmp/pw   # 第一步：拿一份可回滚、可对账的工作副本（原目录只读）
python3 "$SW" collapse  "$PACK" --out /tmp/sw --apply --entry-dir using-hermes \
        --description "…"                       # 真塌：搬目录 + 写伞体与各岛 INDEX.md；**没 --description 直接拒绝**
python3 "$SW" propose "$PACK" --out /tmp/sw --apply --apply-group /tmp/map.json   # 只执行机械那部分
```

产物落在 `--out`：`tree.json` / `LAYERS.md` / `audit.json` / `checks.json` / `proposals.json` + `PROPOSALS.md`。
**先跑 `checks`**：它命中的硬编码路径/密钥是安全与可移植问题，先解决再谈结构。
`propose` 每条提案带 `文件:行` + diff 形状 + 是否 `auto_applyable`；`needs_model=True` 的那些**必须你来判断**。

`visualize` 默认把两份产物写在 pack 根（`--out` 可改）：`TREE.md`（L1 菜单 → L2 正文 → L3 按需，逐 skill 数字）
与 `TREE.html`（自包含、离线可开；互指图画成圆环 + 弦，节点带编号 + 框内图例）。两份都是**生成物，不要手改**。
互指图的边 = 「某个 skill 的任何文本文件里点到另一个 skill 的**目录名**」；岛 = 该图的连通分量。

**验收判据（issue #1 后立的规矩）**：`TREE.html` 里 `rect.node` 的个数 == 本 pack 的 `SKILL.md` 份数
（= 命令自报的 `skill N 个`）。单入口形状下入口层仍是 1 项，但岛内嵌套 skill（住在入口的
`references/<岛>/<skill>/`）各算一个 skill、各画一个框。**工具自报的数不等于事实时就是 bug**。
`visualize` 另有一道闸：工作区里存在**未被 git 跟踪**的 `SKILL.md` 时报错退出（退 1）并提示先 commit ——
collapse 刚改完还没 commit 时索引里是旧路径，新入口会被当 untracked 跳过，静默出一棵空树（退出码 0）。

`disclosure` 是**第二步**：层 = **披露深度**（L1 = 根文档 `SKILL.md`；L2 = L1 直接披露的；Lₙ₊₁ 由 Lₙ 披露），
不是「按文件类型分三级」那套。它把每个根文档的披露链递归展开（深度 / fanout / 体积），并**对每一份文档**跑它那类 cap
（正文 <5000 tok 与行数三档 · description ≤1024 字符 · 资源文件 ≤20000 B），跨文档查孤儿（没人披露）、悬空（披露了不存在的）、
根选择层近重复。产物三份：`DISCLOSURE.md`（体检表，自带术语表 + 根选择层单列）· `disclosure.json`（机器版）·
`TODO.md`（**照着做的待办清单**：每条 = 文档 · 问题 · 数字 · 建议动作 · 谁判；悬空按文件聚合成一行）。命令行自检「表行数 == 节点数」（每个文档恰好出现一次）。
**根的数量 = 形状**：多入口 = K 个根（每个 skill 的 `SKILL.md`）；单入口 = 1 个根。

**流程见仓库里的 `docs/flow.md`（唯一来源；按架构写）**：A 取景 → **B 机械构建文档树**（`disclosure` 建树，
体检是它的出口）→ C 读树（判断：切法/命名/待办）→ D 改树 → E 复测 → F 验收交付。本 skill 只写怎么做。

**只改副本（硬规矩）**：工作区一律是 `prepare` 出的副本，真包只读（副本内 git 化后可回滚）。
形状是**启动参数**（`--shape single|multi`），在准备之前就定 —— 不让用户等到中途拍板。

**派发**：`weave.py dispatch <pack>` 划批（单位 = skill 子树，≤10 个/批）+ 事实补全 + 落 `dispatch/*.prompt.md`；
**验收**：`weave.py verify <pack> --state dispatch/state.json --expect-fixed <id…>` —— 集合级对账 + 拆分守恒 +
回归拦截 + 梯子记账。失败不回滚整批：通过的条目保留，未通过的条目改输入后回 `apply` 继续修。

**落盘**：`weave.py apply <pack> --proposals <提案 json…>` —— 逐条校验并落盘：锚点在该行 ±3 内逐字相同、
改动只落在「本条目自己的文件 + 披露它的父文档 + 该 skill 的入口 SKILL.md」、拆分前后内容守恒、
豁免规则只命中本条目自己的文件；`obsolete` 不自动通过，落 `PARKED.md`。每落一条都写进 `dispatch/patches.json`，
所以回退粒度是单条：`weave.py apply <pack> --revert <条目 id>`。

**免检表放在包里**：`<pack>/.skillweave/waivers.txt`，一行一条 `<glob>` + 两个以上空格 + 理由。命中的不进待办、
只在 TODO.md 的「已豁免」栏记一行 —— 「哪张 png 是给人看的」「哪个 json 是测试留档」是**包主的判断**，不是通用真理，
所以规则写在包里，工具只匹配 + 单独计数。

`prepare` 是**第一步**（可以把它当成整条流程的入口）：`cp -Rc` 拷一份副本 → **在副本里确保由 git 管**
（拷贝的是仓库就摘掉所有 remote —— 误推当场失败 —— 再把当前状态提交成起点；输入没有 git 就 `git init` +
一行 `.gitignore` + 初始 commit）→ 量副本、推导 L1（互指岛的岛）→ 出 `BASELINE.md`：副本路径与 rev、
推导的 L1、**单入口/多入口两种形状同口径的账**、以及待用户选定的形状。**原目录只读、绝不碰**；
形状没定之前不动副本里任何文件。`--shape single|multi` 用来记下用户的选择。

`collapse` 是**可选**的第二种形状（默认不做）：**L1 = 1 个 skill 入口 → L2 = 13 个岛 → L3 = 39 篇正文**。
分工照旧：搬目录、生成伞体与各岛 `INDEX.md` 是机械动作，工具做；**那一条 `description` 必须你写**——
它是唯一的常驻触发词、是判断题，所以 `--apply` 不给 `--description` 会直接拒绝（不生成半成品）。
在 UsingHermes 上实测过的账：常驻 3,310 → **58** tok（description 写多长就是多少）· 伞体 556 tok（13 行）·
各岛 `INDEX.md` 合计 4,344 tok（均值 334）· **独立可装从 39 个降到 1 个**（其余变成 `references/`）。
注意一条**构造性假象**：塌完 `孤儿`/`悬空` 会归零——伞体按目录点名了每个 `references/<岛>/`，目录级点名把里面全盖住了，
不是问题被修好，是这条指标失去分辨力。
**岛数对口径敏感**（同一份数据：只看 SKILL.md 的 frontmatter `name` → 11 个；再加「引用落到别的 skill 目录」→ 10 个；
扫全部文本文件按目录名 → 13 个）——报岛数必须连口径一起报。

**塌完必须 commit 再跑 `visualize`**（issue #1 的坑）：`collapse --apply` 只改工作区，索引里还是旧路径。
这时 `visualize` 会把新入口当未跟踪跳过、静默出空树；现在它会**报错退出（退 1）**并让你先 commit。
入口 `SKILL.md` 的 frontmatter 由 `yaml_scalar()` 写（issue #2）：值里带 `: `、` #`、`>-` 一律加双引号转义，
落盘后回读校验「顶层技能数 == 1 · 入口层 == 1 · frontmatter 自检通过 · description 逐字一致」。
**注意**：工具自带的 `parse_frontmatter()` 是宽松子集，它吃得下 `description: a: b` 这种坏写法 ——
「工具自己读得通」不等于文件合法，判合法性看 `frontmatter_selfcheck()` 或真 YAML 解析器。

## 四类动作：谁做什么（**判断靠你，机械靠 CLI**）

| 动作 | 你（语言模型）判断 | CLI 给你什么 |
|---|---|---|
| **拆** split | 哪几段该下沉到 `references/`、第一层留什么 | 超限清单、每个标题的行号与体量 |
| **分** group | 哪些散技能该归入哪个类目、类目叫什么 | 入口层条目清单与 L1 条目数 |
| **并** merge | 这对是不是真重复、保留哪个、折进哪个 | 同层相似度排序的候选对 |
| **改写** rewrite | `description` 改成什么（触发词/排除条款） | 当前 `description`、长度、同层相似度 |

**每一步都必须能重测**：改完重跑 `layers`（+ `audit`）出前后对照 —— 没有对照表就等于没改。

## 细节（按需读，别一次全读）

| 文件 | 承担什么 |
|---|---|
| `references/split.md` | 拆：切分界线、该下沉的标准、留什么转指行、改完怎么验 |
| `references/group.md` | 分：两轴判据（软件/工具 vs 任务/学科）、类目命名、压 L1 的验收 |
| `references/merge.md` | 并：近重复取证、保留/折进规则、合并后怎么验路由不退化 |
| `references/rewrite.md` | 改写：`description` 前 57 字符窗口、触发词优先、排除条款位置、重测口径 |

## 这轮真跑撞出来的坑（都已在工具里修掉，写在这里免得重踩）

- **删行别按内容锚点找**：空行到处一样，按内容找会删错位置（实测把正文删串了）。删行要按行号 + 内容双严格，且同文件内按行号**降序**应用。
- **拆段落 = 一行指针 + 删掉整段**：`after: null` 删行；指针写一行（`## 坑 → 见 \`references/x.md\``）。整篇拆分才用 `parts` + 守恒校验；
  `parts` 拼起来等于原文就按拆分处理（删原件），不等于才当搬出（留原件）。
- **搬完还要再看一眼**：搬出去的 174 行清单自己就超了 20000 B，得再拆一次。拆完别忘让新文件**被披露**（指针行就是那条披露）。
- **回退顺序**：先删新文件 → 再恢复被拆掉的原件 → 最后回退行改动；被拆掉的原件不再回退行。
- **口径改了要重建基线**：工具修了路径解析之后，旧基线里的 external 集合会整体变，`verify` 会报「external 变了」——
  这是正常的，用 `dispatch --refresh-baseline` 重建基线再验。

## 判据（不许自己降级）

- 一切数字来自命令输出，不许凭印象；报告里每个数都要带产生它的命令。
- **改完必须重跑**：`layers` 的 L1 条目数、常驻 token、L2 超限数、L3 孤儿数四项前后对照。
- 在**副本**上改（`cp -R` 或 git worktree），验证通过再动原仓库；原仓库里只留能过 `checks` 的改动。
