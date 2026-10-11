---
name: skillweave
description: "当要整理或优化一个 skill pack（含 1..N 个 skill 的仓库/目录）的分层披露时用：先构建文档树，再量各级摆出的选项数（L1 菜单 / L2 正文 / L3 按需），最后按度量收敛。触发：「skill pack 太大」「Agent 选不对 skill」「一级菜单太长」「分层披露」「整理 skill 仓库」「技能互相抢题」。"
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

## 三级披露（本 skill 的核心概念）

| 级 | 是什么 | 谁付代价 | 要看住
|---|---|---|---|
| **L1 第一级** | pack 里**所有 skill 的 `name` + `description`**（Agent 第一次选择的菜单） | 常驻上下文 | 入口层摆出**几项**、常驻 token、是否超上限 |
| **L2 第二级** | 被选中那个 skill 的 **`SKILL.md` 正文** | 触发时载入 | 正文 token/行数、它转指出去多少个兄弟 |
| **L3 第三级** | 该 skill 的 `references/` `scripts/` `assets/` | 按需读 | 孤儿文件、悬空引用、最大文件 |

## 命令（七条：四条只读 + 三条生成/改结构）

```bash
SW=<本 skill 的 scripts/weave.py 绝对路径>     # 装好后：<skills 目录>/skillweave/scripts/weave.py
PACK=<要分析的 pack 目录>                      # 例：某个 skill 仓库的根

python3 "$SW" tree   "$PACK" --out /tmp/sw     # 文档树：pack → 类目 → skill → 章节/文件
python3 "$SW" layers "$PACK" --out /tmp/sw     # 三级披露：L1 菜单与常驻成本 + L2 规模 + L3 孤儿/悬空
python3 "$SW" audit  "$PACK" --out /tmp/sw     # 审计四段：体积 / 孤儿悬空 / 同层抢题 / 成本两组数
python3 "$SW" checks "$PACK" --out /tmp/sw     # 七条检查（含硬编码路径、内嵌密钥；命中退 1）
python3 "$SW" propose "$PACK" --out /tmp/sw    # 四类动作的提案：**默认 dry-run，不改盘**
python3 "$SW" visualize "$PACK"                 # 生成物落回 pack：TREE.md + TREE.html（三级披露的文本版与可视化）
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

`disclosure` 是**第二步**：层 = **披露深度**（L1 = 根文档 `SKILL.md`；L2 = L1 直接披露的；Lₙ₊₁ 由 Lₙ 披露），
不是「按文件类型分三级」那套。它把每个根文档的披露链递归展开（深度 / fanout / 体积），并**对每一份文档**跑它那类 cap
（正文 <5000 tok 与行数三档 · description ≤1024 字符 · 资源文件 ≤20000 B），跨文档查孤儿（没人披露）、悬空（披露了不存在的）、
根选择层近重复。产物三份：`DISCLOSURE.md`（体检表，自带术语表 + 根选择层单列）· `disclosure.json`（机器版）·
`TODO.md`（**照着做的待办清单**：每条 = 文档 · 问题 · 数字 · 建议动作 · 谁判；悬空按文件聚合成一行）。命令行自检「表行数 == 节点数」（每个文档恰好出现一次）。
**根的数量 = 形状**：多入口 = K 个根（每个 skill 的 `SKILL.md`）；单入口 = 1 个根。

**流程见仓库里的 `docs/flow.md`（9 步，唯一来源）**，本 skill 只写怎么做。

**只改副本（硬规矩）**：工作区一律是 `prepare` 出的副本，真包只读（副本内 git 化后可回滚）。
开发/试跑只在副本上做；**真跑 SkillWeave 本身就是 production 模式，不需要额外批准**。
形状是**启动参数**（`--shape single|multi`），在准备之前就定 —— 不让用户等到中途拍板。

**派发**：`weave.py dispatch <pack>` 划批（单位 = skill 子树，≤10 个/批）+ 事实补全 + 落 `dispatch/*.prompt.md`；
**验收**：`weave.py verify <pack> --state dispatch/state.json --expect-fixed <id…>` —— 集合级对账 + 拆分守恒 +
回归拦截 + 梯子记账，失败就整批回滚重派（不许用相同 prompt 重派）。

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

## 判据（不许自己降级）

- 一切数字来自命令输出，不许凭印象；报告里每个数都要带产生它的命令。
- **改完必须重跑**：`layers` 的 L1 条目数、常驻 token、L2 超限数、L3 孤儿数四项前后对照。
- 在**副本**上改（`cp -R` 或 git worktree），验证通过再动原仓库；原仓库里只留能过 `checks` 的改动。
