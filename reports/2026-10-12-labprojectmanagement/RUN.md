# RUN · LabProjectManagement（2026-10-12 一轮：单入口伞包 → 8 个 L1）

输入 = 一整套含 `SKILL.md` 的目录树；形状由用户在 A 阶段定。流程见 `docs/flow.md`。

## 0 · 形状（用户定）

**B 多入口 · 8 个 L1**。用户给的分组要求：① Log 相关入口（创建、审查）② Ledger 相关入口
③ 常用流程（含已有的「记录一个 protein sample」）④ 其余由互指岛发现的入口。明确要求**不塌成单入口**。

## 1 · 输入与基线

| | 源包 `AgentSkill-LabProject` | 目标包 `LabProjectManagement`（改造前） |
|---|---|---|
| 形状 | 单入口（根 1） | 多入口（根 8，本次新建） |
| skill | 30（1 伞 + 13 岛内 29） | 30（8 L1 + 22 嵌套） |
| 常驻 | 伞 description 1529 tok | 8 条 L1 description 合计 ≈ 869 tok（`layers` 自报 2081 tok 是把 38 份 SKILL.md 都算进去） |
| L2 正文超限 | 3 | 0 |
| 孤儿 / 悬空 | 22 / 2 | 0 / 0 |

基线（D 前，`8bc91c3`，同版本工具重算）：文档 141 · L1 8 → L2 30 → L3 75 → L4 5 ·
**超限 3 · 到不了根 23 · 悬空 2 · external 69**。见 `DISCLOSURE-before.md` / `TODO-before.md`。

## 2 · 改了什么（D 批次）

**批次 1 · 三个正文超限（拆）** —— 判据、逐行守恒断言都记在提交信息里：

| 文件 | 前 | 后 | 下沉成 |
|---|---|---|---|
| `manage-logs/SKILL.md` | 7582 tok / 134 行 | **3294 tok** | vault-anatomy · heavy-data-locations · pitfalls |
| `manage-inventory-for-protein-engineering/SKILL.md` | 9024 tok / 244 行 | **4871 tok** | 14 节 → 既有 references（探针命中就删重复，没命中就追加） |
| `pymol-structural-visualization/SKILL.md` | 14104 tok / 1018 行 | **3077 tok / 223 行** | 10 份 references（histidine 摘要留正文：它的深度文件自称是「SKILL.md 摘要的 depth」） |

逐行守恒（脚本自断言）：`原非空行 = 剩余 + 搬走 − 转指` —— manage-logs `104 = 67 + 41 − 4`、
manage-inventory `178 = 111 + 81 − 14`、pymol `786 = 167 + 629 − 10`。

**批次 2 · 16 条「到不了根」+ 2 条「悬空」**：
补路径合格的引用 14 处（含两类解析不到的真 bug：`[path]` 不是合法 markdown 链接、裸文件名不带目录）；
1 处其实是「别的 pack 的文件」→ 改写成本包外说明；1 处是作者自己标 `(todo)` 指向不存在的文件 → 删那一行、补上真实存在的那份。

**脚本不拆**：`scripts/` 下的文件不设字节上限（口径已写进 SkillWeave：`docs/contract.md` §4 + `weavelib/disclosure.py` 的 `cap_of`）。
退掉的 5 条「拆脚本」待办不在这里，在 SkillWeave 侧的实测里。

## 3 · 复测（E）

| 判据 | 前 → 后 |
|---|---|
| 该消的消了 | 超限 **3 → 0**（消失的正是那三个文件）；到不了根 **23 → 11** |
| 无新增（按路径集合） | **新孤儿 0**、新悬空 0 ✅ |
| external 集合 | 提到的包外文件集合**未变**（差集空；总数 69→70 只是行跟着搬了） |
| 拆分守恒 | 三个文件逐行守恒 ✅（数字见上） |

剩余 11 条全部记为**豁免**（`.skillweave/waivers.txt`，5 行）：
7 条 `test-prompts.json`（行为测试留档）+ `*/templates/*.sql`×2 + 根级 `config.yaml` / `pyproject.toml`。
后四条的诚实理由：**工具口径够不到** —— `PATH_RE` 的扩展名表不含 `.sql`；解析器不把裸文件名当披露（root 级支持文件因此永远算孤儿）。
`PARKED.md`：无。

## 4 · 路由盲判（F · 19 道题面，判官只读 `judge-input.txt`）

题面：13 should_trigger + 4 near_confusion + 2 should_not_trigger，两侧候选列表不同
（新 38 个 vs 旧 30 个），描述都截断到 57 字符；金标不进判官输入，判官是两个独立子代理。

| 题型 | 新结构（8 L1） | 旧结构（单入口伞包） |
|---|---|---|
| should_trigger | **13/13**（BoR 1.0） | 12/13（0.92） |
| near_confusion | **4/4**（1.0） | 3/4（0.741） |
| should_not_trigger | **2/2**（1.0） | 2/2（1.0） |

- 判据「新不低于旧、且没有题从 1.0 掉到 0.5 以下」→ **过**。
- 旧结构掉的两题：P2「看 zsqlab11 里 OmcZ 纯化记录怎么写的」被引到 `lab-vault-experiment-records`
  （假阴性来自它自己的伞 description 前 57 字符是「same-field repeats need averaging…」，触发句在第 57 字符之外）；
  P15「为什么和论文产率不一样」被引到 `audit-log-protein-purification`。
- **同层抢题**（真问题，两结构都有）：`manage-logs` ↔ `lab-vault-experiment-records`（P2）、
  `manage-logs` ↔ `audit-log-protein-log`（P15）语义重叠，靠 description 划界还没拉开。
- 判官输出与金标：`judge-new-out.txt` / `judge-old-out.txt` / `judge-{new,old}-key.json`。

## 5 · 交付（F）

`deliver` 四道闸全过 → 合回真包 `main`（`--ff-only`）→ push 各 remote 并回读 → 重跑 `visualize` → 删 worktree/分支。
真包 `main` = **7aadb61**（tailscale 回读一致；`lab` 那条是 LAN 地址，当前不在那个网络所以推不上）。
交付后自查：38 份 `SKILL.md`、`TREE.html` 节点框 38 个、正文超限 0、悬空 0、与 openai life-science-research 插件 skill 集零重名。

## 6 · 下一批（没做的）

1. **同层抢题**：`manage-logs` / `lab-vault-experiment-records` / `audit-log-protein-purification` 三条的 description 边界（P2、P15 各错一次）。
2. 旧包 `AgentSkill-LabProject` 内容与 LabProjectManagement 现在是两处重复 —— 退掉或改成只留指针，待定。
3. 8 个 L1 尚未装进 skill 库（`README.md` 里给了 adopt/update/deploy + preset 的循环；`register-a-protein-sample` 路径变了，旧安装记录要重 adopt）。
