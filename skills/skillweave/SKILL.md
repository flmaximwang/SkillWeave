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

## 命令（五条：四条只读 + 一条生成产物）

```bash
SW=<本 skill 的 scripts/weave.py 绝对路径>     # 装好后：<skills 目录>/skillweave/scripts/weave.py
PACK=<要分析的 pack 目录>                      # 例：某个 skill 仓库的根

python3 "$SW" tree   "$PACK" --out /tmp/sw     # 文档树：pack → 类目 → skill → 章节/文件
python3 "$SW" layers "$PACK" --out /tmp/sw     # 三级披露：L1 菜单与常驻成本 + L2 规模 + L3 孤儿/悬空
python3 "$SW" audit  "$PACK" --out /tmp/sw     # 审计四段：体积 / 孤儿悬空 / 同层抢题 / 成本两组数
python3 "$SW" checks "$PACK" --out /tmp/sw     # 七条检查（含硬编码路径、内嵌密钥；命中退 1）
python3 "$SW" propose "$PACK" --out /tmp/sw    # 四类动作的提案：**默认 dry-run，不改盘**
python3 "$SW" visualize "$PACK"                 # 生成物落回 pack：TREE.md + TREE.html（三级披露的文本版与可视化）
python3 "$SW" propose "$PACK" --out /tmp/sw --apply --apply-group /tmp/map.json   # 只执行机械那部分
```

产物落在 `--out`：`tree.json` / `LAYERS.md` / `audit.json` / `checks.json` / `proposals.json` + `PROPOSALS.md`。
**先跑 `checks`**：它命中的硬编码路径/密钥是安全与可移植问题，先解决再谈结构。
`propose` 每条提案带 `文件:行` + diff 形状 + 是否 `auto_applyable`；`needs_model=True` 的那些**必须你来判断**。

`visualize` 默认把两份产物写在 pack 根（`--out` 可改）：`TREE.md`（L1 菜单 → L2 正文 → L3 按需，逐 skill 数字）
与 `TREE.html`（自包含、离线可开；互指图画成圆环 + 弦，节点带编号 + 框内图例）。两份都是**生成物，不要手改**。
互指图的边 = 「某个 skill 的任何文本文件里点到另一个 skill 的**目录名**」；岛 = 该图的连通分量。
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
