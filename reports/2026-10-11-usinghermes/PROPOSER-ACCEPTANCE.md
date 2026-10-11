# T-004#B-001 验收：提案器（默认只出提案，`--apply` 才落盘）

**跑在哪**：`/tmp/pack-fix3` = `AgentSkill-UsingHermes` 当前 HEAD 的临时副本（原 pack 全程未动）。
**命令**：`python3 scripts/weave.py propose /tmp/pack-fix3 --out /tmp/sw-fix3 [--apply] [--apply-group /tmp/group-map.json]`

## ① dry-run：27 条提案，每条带 `文件:行` + diff 形状

```
[propose] merge    skills/research/tushare/SKILL.md:1 · skills/research/tushare-data/SKILL.md:1 auto=True  | 保留 skills/research/tushare/（身份），正文取 skills/research/tushare-data（version 1.1.16）
[propose] group    skills/（入口层）                                        auto=False | 入口层摆出 68 项 > 上限 20：把散技能按用途归入类目（类目名要人拍板）
[propose] split    skills/accountancy-workflow/SKILL.md:572                 auto=False | 21427 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
…
[propose] dry-run：盘上未改任何文件（加 --apply / --apply-group 才落盘）
```

分类计数：**split 14 · rewrite 11 · merge 1 · group 1 = 27**；其中 `auto_applyable` **1 条**（那条 1.00 相似对），
其余 26 条标 `needs_model=True` —— CLI 不假装能做「哪段该下沉 / 进哪个类目 / 触发词怎么改」。
`PROPOSALS.md` 里每条都带证据 JSON（sim、引用次数、version、按体积排序的小节行号区间）。

## ② `--apply` + `--apply-group`：真落盘 + 逐条对账

```
[propose] 跳过（不存在）: skills/dream
[propose] --apply：执行 52 条机械动作 → 声明 106 个目录 · git 报出 411 个路径
[propose] 逐条自检 ✓ 全部落地；集合对账 ✓ 无未声明变更、无声明未发生
[propose] git diff --stat（原始输出）：
 209 files changed, 4 insertions(+), 1251 deletions(-)
```

> 口径说明：原验收句写「`git diff --stat` 与提案条数一致」。条数与路径数不是同一个量（一次 `git mv` 落在几十个文件上），
> 所以对账做成**路径集合级**：`git status --porcelain -z` 报出的每个路径都必须落在我声明过的目录里，且我声明的目录都必须真有变更。
> 中文文件名在 macOS 上是 NFD、git 索引里是 NFC，两边归一化后再比（否则全是假差异 —— 这是本块实测踩到的坑）。

## ③ 合并方向与版本（机械规则可复算）

```
$ ls /tmp/pack-fix3/skills/research | grep tushare
tushare
tushare-api-access
tushare-kline-pipeline
$ grep -m1 '^version:' /tmp/pack-fix3/skills/research/tushare/SKILL.md
version: 1.1.16
```

规则写进提案证据里：**身份取被全 pack 引用更多的一方（并列取更短名字）**、**同名文件取 `version` 更高的一方**、`version` 跟胜方走。
（第一版按 id 排序取身份，尾斜杠让 `tushare-data/` 排在 `tushare/` 前 —— 方向反了，已改。）

## ④ 改后四数（前 → 后）

两侧**同一 HEAD `b8298f4`**（`git -C /tmp/pack-fix3 rev-parse --short HEAD` = `b8298f4` = 原 pack HEAD），可直接比：

| 指标 | 改前（`b8298f4` 基线） | 改后 |
|---|---|---|
| L1 入口层条目 | 68（散 51 + 类目 17） | **24（散 0 + 类目 24）** |
| 常驻成本 | 20,864 字符 ≈ 6,443 token | 20,699 字符 ≈ **6,298 token** |
| L2 超限（两闸口径） | 16 | 15 |
| `dup` >0.5 对数 | 12 | **13**（合并 −1、归位 +2，净 +1） |
| 孤儿文件 | 104 | 101 |
| 悬空引用 | 46 | **46（新增 0）** |
| 技能数 | 125 | 124（合并 1 对） |

> 本表原先写的是「改前 6,311 token / 孤儿 101」—— 那是**更早快照**的数（当时 `/tmp/pack-fix3` 取自更早的提交），
> 被独立复核子代理指出与审计报告（6,443/104）对不上。现在两侧都取 `b8298f4`，跨文档引用不再互相打脸。

## ⑤ 诚实备注：基准快照与上游推进

- 三轮盲判（`round3/COMPARISON-3ROUNDS.md`）跑在**旧快照** `432c1f1` 系上；本块与审计报告的数字统一取 **`b8298f4`**（复核实测确认 `/tmp/pack-fix3` = `b8298f4`）。
- 15:46 取的那份快照在我做归位期间被别的 agent 推进过（`a2d79b6` 给 `maintain-hermes-memory` 加了 archify 图）。
  我一度把 `maintain-hermes-memory → assets/template.html` 记成「归位导致的新增悬空」，重取基线后确认：**它在当前 HEAD 的未改动副本里就已经悬空**，
  归位+合并新增悬空 **0 条**。这类假归因只能靠「对同一 HEAD 取 before/after」才能排掉。
