# UsingHermes 审计报告（SkillWeave 首个 subject）

**被测**：`~/Documents/AgentSkill/AgentSkill-UsingHermes` · 报告基准 commit **`b8298f4`**
（`git -C ~/Documents/AgentSkill/AgentSkill-UsingHermes rev-parse HEAD`）
**工具**：`scripts/weave.py`（纯 stdlib，无第三方依赖）· **产物目录**：`reports/2026-10-11-usinghermes/baseline-current/`

> 报告里每个数字后面都跟着产生它的命令；命令全部可在别的机器上重跑（见 §11 复现清单）。
> **约定**：所有测量都在**临时副本**上做，原 pack 从不被改。
> `est_tokens` 口径 = CJK 字符 ×1 + 其它字符 ×0.25（四舍五入，**估算**，不是分词器计数）。

---

## 0. 三句话结论

1. 这个 pack 的**第一级披露严重超载**：入口层 `skills/` 一次摆出 **68 项**（51 个散技能 + 17 个类目），
   而 Agent 第一次只能看到这一层 —— 这是「单层选择太多」的实锤，不是感觉。
2. **同层真有抢题**：1621 对同层比较里 **12 对相似度 > 0.5**，其中 1 对 `description` **逐字相同**（相似度 1.00）。
3. 已在临时副本上做了两刀（合并那对重复 + 51 个散技能归入类目），**第一级从 68 项压到 24 项**，
   而同一批题面的独立盲判**分数没掉**（详见 §8）。

---

## 1. 复现准备

```bash
# 取当前 HEAD 到临时副本（原 pack 不动）
rm -rf /tmp/base-now && cp -R ~/Documents/AgentSkill/AgentSkill-UsingHermes /tmp/base-now
OUT=reports/2026-10-11-usinghermes/baseline-current && mkdir -p $OUT
```

---

## 2. 文档树

**命令**：`python3 scripts/weave.py tree /tmp/base-now --out $OUT`
**产物**：`tree.json`（机器读）· `TREE.md`（人读）

- 节点与体积：`skills=125 · bytes=… · est_tokens=…`（`tree.json` → `pack`）
- **每层选择数（fanout）**：`tree.json` → `fanout` 数组，`fanout = 该目录直接子项数`
- 最大 fanout = **68**（入口层 `skills/`）

判据：**入口层** = 从 pack 根往下、只要唯一的选择项还是类目就继续下钻，遇到 ≥2 个选择项就停。
所以 `skills/` 是入口层（哪怕它下面全是类目），不是第一个类目。

---

## 3. 三级披露度量

**命令**：`python3 scripts/weave.py layers /tmp/base-now --out $OUT` → `layers.json`

| 层 | 是什么 | 实测 |
|---|---|---|
| **L1** 常驻菜单 | 全 pack 的 `name` + `description` | **入口层 68 项**（散技能 51 + 类目 17）❌ 超上限 20 · 常驻 **20,864 字符 ≈ 6,443 token** · `description` 超 1024 字符的 **0** 个 |
| **L2** 触发后载入 | 单个 `SKILL.md` 正文 | 全体 **385,991 token**（中位 **2,282**）· 超限 **16** 个（口径见下） |
| **L3** 按需 | `references/ scripts/ assets/` | **468 文件 / 6,862,852 B** |

- L2 的两个闸口径不同，报告里分开写：**`over_limit`=16**（`token>5000` **或** `行数>500`，任一超），
  **`over_token`=14**（只看 token）。`layers.json:L2.over_token` 与 `audit.json` 的 token 口径**必须相等**，自检里钉了这条。
- L2 最大的三个：`accountancy-workflow` 21,427 tok / 747 行 · `research/research-paper-writing` 17,832 tok / 1,611 行 · `maintain-hermes-profile` 17,134 tok / 874 行

---

## 4. 孤儿 / 悬空

**命令**：`python3 scripts/weave.py tree /tmp/base-now --out $OUT`（同一份 `tree.json`）
**或**：`python3 scripts/weave.py audit /tmp/base-now --out $OUT` → `audit.json:orphan`

- **孤儿文件 104**（没有任何正文点名它）· **悬空引用 46**
- 引用分类（全 pack）：`resolved` 241 · `external` 206 · `example` 267 · `broken` 46
- 判据细节（都是被实测逼出来的）：代码围栏里的路径、无目录部分的裸文件名算 **example 不算 broken**；
  正文点名 `templates/README.md` ⇒ `templates/` **整目录**算被点名（否则 templates 全成孤儿）；URL 不当路径。

---

## 5. 近重复 top-N（抢题主因）

**命令**：`python3 scripts/weave.py audit /tmp/base-now --out $OUT` → `audit.json:dup`

- 同层两两比较 **1,621 对**，相似度 **>0.5 的 12 对**
- top：

| 相似度 | 对 | 判断 |
|---|---|---|
| **1.00** | `research/tushare` ↔ `research/tushare-data` | **真重复**：`description` 逐字相同、`references/数据接口.md` 逐字节相同、两个脚本同名微差、正文只差 `slug` 与 `version`（1.1.12 vs 1.1.16） |
| 0.81 | `boc-statement` ↔ `ccb-statement` | 同族不同卡种，靠 description 里的「信用卡/借记卡/活期」区分 —— **靠描述词兜住，不是结构上消失** |
| 0.72 | `autonomous-ai-agents/hermes-profile-authoring` ↔ `…/hermes-projects` | 同族 |
| 0.52–0.65 | `autonomous-ai-agents/*` 其余 6 对 | 同族 |

`est_tokens`：正文用「CJK×1 + 其它×0.25」估；相似度用 `difflib.SequenceMatcher`（纯 stdlib）。
**ponytail**：同层 O(n²)，最大层 68 项 ≈ 2.3k 次比较；单层上千项时再换 shingle + 倒排。

---

## 6. 成本两组数

**命令**：同 §5（`audit.json:cost`）

| 组 | 数 |
|---|---|
| 常驻（每次对话都在） | 20,864 字符 ≈ **6,443 token** |
| 激活一次（L2 全量之和） | **385,991 token**（中位 2,282） |
| 按需（L3） | 468 文件 / 6.86 MB |

---

## 7. 七条检查（命中即 exit 1）

**命令**：`python3 scripts/weave.py checks /tmp/base-now --out $OUT` → `checks.json`

本次命中：**116**（全部是 `hardcoded_path`）。检查项：`broken_refs` · `token_budget` · `bom` · `binary` ·
`name_mismatch` · `hardcoded_path` · `embedded_secret`。
`hardcoded_path` 分布：`maintain-hermes-skills` 32 · `autonomous-ai-agents` 17 · `maintain-hermes-node` 12（其余若干）。

---

## 8. 优化提案与已实测的两刀

**命令**：`python3 scripts/weave.py propose /tmp/base-now --out $OUT`（默认 dry-run，不改盘）

提案 **27 条**：`split 14 · rewrite 11 · merge 1 · group 1`；其中**只有 1 条可机械执行**，其余 26 条标
`needs_model=True`（哪段该下沉 / 进哪个类目 / 触发词怎么改 —— 这些是语言模型的判断，CLI 不假装能做）。

在临时副本上真跑过的两刀（副本已删，命令与产物见 `PROPOSER-ACCEPTANCE.md`）：

| 指标 | 改前 | 改后 |
|---|---|---|
| L1 入口层条目 | 68（散 51 + 类目 17） | **24（散 0 + 类目 24）** |
| 常驻成本 | 6,443 token | **6,298 token** |
| `dup` >0.5 对数 | 12 | 11（那对 1.00 消失） |
| 技能数 | 125 | 124 |
| 悬空 / 孤儿 | 46 / 104 | 46 / 101（新增悬空 0） |

**路由评测（这是「改完没变差」的证据，不是感觉）**：同一批 14 道题面、2 个独立判官、金标统一：

| 轮次 | 结构 | should_trigger | should_not_trigger | near_confusion |
|---|---|---|---|---|
| r1 | 原结构（L1=69 项的旧快照） | 0.938 | 1.0 | **0.75** |
| r2 | 合并真重复对 | **1.0** | 1.0 | **1.0** |
| r3 | 再归入类目（L1=24 项） | 1.0 | 1.0 | 1.0 |

明细：`round3/COMPARISON-3ROUNDS.md`、`round1/`、`round2/`、`round3/`（判官输出原件一字未改）。

---

## 9. 已知问题 / 待决（都在计划里，不藏着）

1. **L1 仍有 24 项 > 上限 20**：再压需要合并现有类目或改二级命名 —— 属分类学决策（计划块 `T-004#B-004` 等你拍板）。
2. `boc` / `ccb` / `boc-credit` 三条同族目前判官都选对，但**靠 description 里的卡种词区分**，结构上没解决。
3. `hardcoded_path` 116 处未处理（本次只报不改）。
4. L2 超限 14–16 个 skill 的正文下沉尚未执行（提案给了按体积排序的小节行号区间，执行需要模型判断）。
5. 三轮盲判跑在旧快照 `432c1f1`；第 4 轮在 `b8298f4` 上重跑以对齐基准。

---

## 10. 这份报告自己怎么被验

计划块 `T-006#B-002` 要求**另一个**子代理只读本报告 + pack，按 §11 的命令重跑并逐项核对数字，
不一致就逐条列出、回到对应块整改（**不许改判据**）。复核输出落 `reports/2026-10-11-usinghermes/round4/verify-report.md`。

---

## 11. 复现清单（命令 → 该看到什么）

| # | 命令 | 该看到 |
|---|---|---|
| 1 | `git -C ~/Documents/AgentSkill/AgentSkill-UsingHermes rev-parse HEAD` | `b8298f4…`（若 pack 已被别人推进，数字会变 —— 以当时的 HEAD 为准） |
| 2 | `python3 scripts/weave.py tree /tmp/base-now --out $OUT` | `skills=125` · 最大 fanout `68` |
| 3 | `python3 scripts/weave.py layers /tmp/base-now --out $OUT` | 入口层 68 项（散 51 + 类目 17）· 常驻 ≈6443 token · L2 超限 16 |
| 4 | `python3 scripts/weave.py audit /tmp/base-now --out $OUT` | 孤儿 104 · 悬空 46 · >0.5 对 12 · top 1.00 是 tushare 那对 |
| 5 | `python3 scripts/weave.py checks /tmp/base-now --out $OUT` | `❌ 命中 116`（exit 1）· `checks.json` 里 7 类键 |
| 6 | `python3 scripts/weave.py propose /tmp/base-now --out $OUT` | 27 条提案 · `dry-run：盘上未改任何文件` |
| 7 | `python3 scripts/weave.py --self-test` | 全过（含 `layers↔audit 口径对拍`） |
| 8 | `python3 -c "import json;l=json.load(open('$OUT/layers.json'));a=json.load(open('$OUT/audit.json'));print(len(l['L2']['over_token']), sum(1 for r in a['size'] if r['over_token']))"` | 两个数相等（14 14） |
