# SkillWeave

分析一个 **skill pack**，构建它的**文档树**，并据此优化**分层披露**结构 —— 让每一级摆出的选项数，
都还在「能一次选对」的范围内。

## 输入是什么（先把定义说死）

- **一个 skill pack = 一个仓库/目录，里面含 1 个或多个 skill。** 不是单个 `SKILL.md`。
- **输入 = 一整套含 `SKILL.md` 的文件夹树**（整个 pack 目录）。工具自己走这棵树，认出哪些目录是 skill、
  哪些是类目、哪些是资源；一个 pack 里可以有任意多个 skill，也可以有类目层（`skills/<类目>/<skill>/`）。
- 契约就是 [agentskills.io 规范](https://agentskills.io/specification)：
  `<skill 名>/SKILL.md`（frontmatter `name` ≤64 字符 / `description` ≤1024 字符）+ 可选
  `scripts/` `references/` `assets/`。工具**不依赖任何 agent 框架**：没有 profile、没有安装器、
  没有 lock 文件、没有内置技能表这些概念。
- pack 在 git 仓库里时，只算 **git 跟踪**的文件为成员；目录里躺着的未跟踪垃圾（例如别人跑批留下的 `~/`
  树）单列出来，**不混进任何度量**。

## 三级披露（要处理的核心问题）

| 级 | 是什么 | 谁在付代价 | 本仓库量的东西 |
|---|---|---|---|
| **L1 · 第一级** | **整个 pack 里所有 skill 的 `name` + `description`** —— Agent 第一次做选择时看到的菜单 | 常驻上下文（每会话都付） | **入口层摆出几项**（散技能 + 类目）、常驻字符/估算 token、是否超过第一层上限、有没有 `description` 超 1024 字符 |
| **L2 · 第二级** | 某个 skill 被选中后载入的 **`SKILL.md` 正文** | 触发时载入 | 正文估算 token / 行数（对照 <5000 token、50/150/500 行三档）、它点名了多少个同 pack 兄弟 |
| **L3 · 第三级** | 该 skill 的 `references/` `scripts/` `assets/` | 按需读 | 文件数与体积、最大文件、**孤儿文件**、**悬空引用** |

> **第一级披露的问题就是这个仓库存在的理由**：pack 一大，第一级菜单就长 —— 本机实测
> `AgentSkill-UsingHermes` 的入口层摆出 **69 项**（散技能 52 + 类目 17），Agent 在这一级选错就再也到不了
> 正确的细节。工具要能**量**它，并给出**收敛**方案：把散技能归入类目（一级选择拆成两级）、合并近重复项、
> 改写 `description` 的触发词。

## 现在能跑的东西

```bash
# 文档树：pack → 类目 → skill → 章节/文件；出 tree.json（机器读）+ TREE.md（人读）
python3 scripts/weave.py tree   <pack 目录> [--out DIR]

# 三级披露：L1 菜单与常驻成本 + L2 正文规模 + L3 孤儿与悬空；出 layers.json + LAYERS.md
python3 scripts/weave.py layers <pack 目录> [--out DIR]

# 审计四段：体积 / 孤儿悬空 / 同层抢题 / 成本两组数；出 audit.json
python3 scripts/weave.py audit  <pack 目录> [--out DIR]

# 安全与可移植检查（引用/预算/BOM/二进制/name/硬编码路径/内嵌密钥），命中即 exit 1
python3 scripts/weave.py checks <pack 目录> [--out DIR]

# 四类动作的提案（拆/分/并/改写）：默认 dry-run 只出提案，--apply 才落盘
python3 scripts/weave.py propose <pack 目录> [--out DIR]
python3 scripts/weave.py propose <pack 目录> --out DIR --apply                 # 只执行「可机械」的那几条
python3 scripts/weave.py propose <pack 目录> --out DIR --apply-group map.json  # 执行你给的归位映射（git mv）

python3 scripts/weave.py visualize <pack 目录> [--out DIR]      # 生成 TREE.md + TREE.html（默认落回 pack 根）
                                                                # 三级披露文本版 + 自包含可视化；互指岛的圆环 + 弦图
python3 scripts/weave.py disclosure <pack 目录> [--out DIR]     # 第二步：披露链递归 + 逐文档体检 → DISCLOSURE.md
python3 scripts/weave.py prepare   <pack 目录> --dest WORK/ws --out DIR   # 第一步：拷一份由 git 管的工作副本（原目录只读）
                                                          # 出 BASELINE.md：推导的 L1 + 两种形状同口径的账 + 待选形状
python3 scripts/weave.py collapse  <pack 目录> --out DIR        # 可选形状：L1=1 入口 / L2=岛 / L3=正文 的账 + 伞体草稿（dry-run）
python3 scripts/weave.py collapse  <pack 目录> --out DIR --apply --entry-dir <名字> --description "…"   # 真塌

# 自检（自带 fixture，不碰真实数据）
python3 scripts/weave.py --self-test
```

实测（2026-10-11 · UsingHermes 基准 `b8298f4`，详见 `reports/2026-10-11-usinghermes/report-usinghermes.md`）：

```
AgentSkill-UsingHermes  L1 技能=125 入口层摆出 68 项（散 51 + 类目 17）常驻 20864 字符 ≈ 6443 token ❌超上限20
                        L2 超限 16（token 单口径 14；最大 21427 tok / 747 行）  L3 468 文件 / 6.86 MB · 孤儿 104 · 悬空 46
Dream                   L1 技能=2   入口层 2 项 · 常驻 ≈268 token ✅              L3 悬空 15
AgentSkill-SoftwareDev  L1 技能=30  入口层 30 项（无类目）· ≈900 token ❌超上限20  L2 超限 9 个
```

## 与已有工具的关系

| 已有 | 它管什么 | 本仓库补什么 |
|---|---|---|
| `Dream` 的 `check-disclosure.py` | **入口层条目数**与**单个** `SKILL.md` 的规模（行/字节/文档字节/被点名的兄弟数） | 整棵**文档树**、**披露链递归**（层=披露深度，L1..Ln）与逐文档体检、同层抢题、路由可测、按度量重构并重测 |
| `agent-skill-analysis`（MIT·npm） | 单个 skill 目录 → 结构化 JSON（frontmatter/outline/files/refs/orphans/digest） | **pack 层**：多 skill 的母树、L1 菜单、跨 skill 抢题 |
| `skill-tools`（Apache-2.0·npm） | per-skill 校验/lint/打分 + BM25 检索式路由 | **判官式**路由评测（逐题金标 + 校正随机分）、重测闭环 |
| Hermes 的 `load-external-skill-index` / `skill-routing-blind-test` | Hermes 里的索引成本与盲测口径 | 去掉框架依赖，输入只认 pack 目录 |

## 形状（硬约束）

- 第一层只放：定义 · 方法 · 每步一行转指；细节下沉 `docs/`，每份都被点名（无孤儿文档）。
- 上限是**可自检的常量**，超限即报（`--self-test` 与 `layers` 都会判）。
- 判据只求真命令与实测输出：改完必须能重跑出一份新的度量，不许写「应该好了」。

## 依据与契约

- [`docs/flow.md`](docs/flow.md) — **流程（按架构写）**：A 取景 → **B 机械构建文档树** → C 读树 → D 改树 → E 复测 → F 验收交付（唯一流程来源）
- [`docs/contract.md`](docs/contract.md) —— 节点 schema、三级披露定义、每层要量的量、caps 表（每条带出处）。
- [`docs/prior-art.md`](docs/prior-art.md) —— 外部实测结论（分层披露值多少、只看 description 会掉多少分、
  层深该怎么评）。
- [`docs/similar-work.md`](docs/similar-work.md) —— **同类公开项目实勘**：已有的做到哪一步、本仓库还剩什么。
- `reports/` —— 在真实 pack 上跑出来的度量留档。

## 开发计划（唯一真相，随仓库提交）

`plans/skillweave/`：`plan.json`（机器模型）· `PLAN.md`（摘要）· `plan.html`（看板，`file://` 直接打开）。
计划由 [loomerto](https://github.com/flmaximwang/Loomerto) 管理，**只经 CLI 改**：

```bash
loomerto --plans-root plans current skillweave     # 现在该谁动
loomerto --plans-root plans check   skillweave     # 图质量
```
