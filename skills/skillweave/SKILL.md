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

**边界**：不装/不卸/不发布技能；不替你判断「这个技能该不该存在」；改动一律在 `prepare` 的副本上做，
流程走完默认由 `deliver` 合回真包 —— 真包在交付前保持原样。

## 核心概念

- **文档树**：节点 = 一份文档（`SKILL.md`、`references/*.md`、`scripts/*.py` 各算一份）；
  边 = 披露（正文里真实点到的另一份文档路径）。
- **层 = 披露深度**：根为 L1（根 = 每个 skill 的 `SKILL.md`），根直接披露的为 L2，依次递推；
  走不到的记「到不了根」。
- **披露**：只认正文里真实写出的路径 —— URL、代码围栏里的示例路径、没有目录的裸文件名都不算。
- **形状 = 根的数量**：多入口 = K 个根（默认）；单入口 = 1 个根（`collapse`，可选）。
- **caps**：`name` ≤64 字符 · `description` ≤1024 字符（agentskills.io，错误）；正文建议 <5000 token /
  <500 行 · `references/` 单文件建议 <300 行（Anthropic，警告）。脚本不设字节上限。

完整定义、caps 表、术语表、免检规则见 [`references/concepts.md`](references/concepts.md)。

## 快速开始

实现脚本是本 skill 自包含的 `scripts/weave.py`（仓库根的同名脚本只做转发）。

```bash
SW=<weave.py 绝对路径>     # <skills 目录>/skillweave/scripts/weave.py
PACK=<要分析的 pack 目录>

python3 "$SW" disclosure "$PACK"   # 建文档树 + 逐文档体检 → DISCLOSURE.md / disclosure.json / TODO.md
python3 "$SW" visualize  "$PACK"   # 收尾：TREE.md + TREE.html 落 pack 根（随包持久化）
python3 "$SW" deliver    "$PACK"   # 默认动作：合回真包 main + push + 回读 + 重跑 visualize + 清 worktree/分支
```

全部子命令的用法、参数、产物见 [`references/commands.md`](references/commands.md)。

## 完整流程（A→B→C→D→E→F）

| 阶段 | 职责 | 命令 |
|---|---|---|
| A 定形状 | 定根的数量（单入口 / 多入口），只做一次 | `--shape` |
| B 构建文档树 | **计算**：枚举文档、解析披露、算层与体积 | `prepare` · `disclosure` · `tree` · `visualize` |
| C 在树上判断 | **判断**：分组、命名、该改哪些文档 → `TODO.md` | `disclosure` 的 `TODO.md` · `propose` |
| D 改动文档树 | **判断出内容、计算落盘**：搬目录 / 改文档，逐条记 patch | `collapse` · `propose --apply-group` · `apply` |
| E 复测 | **计算**：该消的消了 / 无新增 / external 不变 / 拆分守恒 | `verify` |
| F 验收与交付 | **判官判断 + 计算**：盲判通过则合回真包 | `judge` · `score` · `deliver` |

失败不回滚整批：通过的条目保留，未通过的条目改输入后继续修，只有无法修正的条目才回退它自己那一条。
详细流程、循环控制参数、回退策略、终止条件见 [`references/workflow.md`](references/workflow.md)。

## 四类动作（判断靠你，机械靠 CLI）

**拆** `split` · **分** `group` · **并** `merge` · **改写** `rewrite` —— 各自的判据与落盘步骤见文末路由表。
每一步都必须能重测：改完重跑 `layers`（+ `audit`）出前后对照，没有对照表就等于没改。

## 验收标准

1. **改完必须重跑**：`layers` 的 L1 条目数、常驻 token、L2 超限数、L3 孤儿数四项前后对照。
2. **TODO 清空**：`disclosure` 的 `TODO.md` 里除已豁免与 `PARKED.md` 外没有剩余条目。
3. **自举通过**：工具自己也要过自己的检查（`checks` 无安全/可移植命中、`--self-test` 全过）。

一切数字来自命令输出，不许凭印象；报告里每个数都要带产生它的命令。改动在副本上做，验证通过后
**默认 `deliver` 合回真包 main 并 push**。

## 详细文档（按需读，别一次全读）

| 文件 | 承担什么 |
|---|---|
| [`references/concepts.md`](references/concepts.md) | 文档树 / 层 / 披露 / 形状定义 · caps 表 · 术语表 · 免检规则 |
| [`references/commands.md`](references/commands.md) | 全部子命令的用法、参数、产物、示例 |
| [`references/workflow.md`](references/workflow.md) | A→B→C→D→E→F 六阶段详细流程 · 循环控制参数 · 回退与终止 |
| [`references/pitfalls.md`](references/pitfalls.md) | 真跑撞出来的坑（问题 → 根因 → 解决 → 避免） |
| [`references/split.md`](references/split.md) | 拆：切分界线、下沉标准、留什么转指行、改完怎么验 |
| [`references/group.md`](references/group.md) | 分：两轴判据、类目命名、压 L1 的验收 |
| [`references/merge.md`](references/merge.md) | 并：近重复取证、保留 / 折进规则、合并后怎么验路由 |
| [`references/rewrite.md`](references/rewrite.md) | 改写：`description` 前 57 字符窗口、触发词优先、重测口径 |
