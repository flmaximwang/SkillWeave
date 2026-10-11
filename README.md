# SkillWeave

分析一个 **skill pack**（任意 agent 框架的 `SKILL.md` 目录树），构建可导航的**文档树**，并据此优化**分层披露**
结构 —— 让每一层在它自己的选择数下，Agent 仍能一次选对内容。

- **输入** = 一个 skill pack 目录，契约就是 [agentskills.io 规范](https://agentskills.io/specification)：
  `SKILL.md`（frontmatter `name` ≤64 / `description` ≤1024）+ 可选 `scripts/` `references/` `assets/`。
- **不依赖任何 agent 框架**：仓库里没有 profile、安装器、lock 文件、内置技能表这些概念。
  任何 agent（或人）拿到这批文件就能跑。
- **开发计划（唯一真相）**：`plans/skillweave/`（`plan.json` 机器模型 · `PLAN.md` 摘要 · `plan.html` 看板）。

## 要解决的问题

分层披露（progressive disclosure）的失败形态不是「文件太大」，而是**某一层摆出的选项太多**：
Agent 站在那一层选不对，就再也到不了正确的细节。本仓库把这件事变成**可量的量**再动手：

1. **构建文档树** —— 把 pack 解析成节点图（pack → 类目 → 技能 → 章节 → 引用文件），每个节点带自己的
   摘要与代价（字节/token），边 = 正文里的真实引用。
2. **量每一层** —— 每层的选择数（fanout）分布、每个节点的体积上限、孤儿文件（没有任何祖先点名它）、
   从入口到每个文件要跳几跳、以及**互相抢题的近重复节点**（同一层里两个长得太像的 description）。
3. **优化** —— 拆（大节点下沉到 `references/` 并留转指）、并（同级近重复合并）、分（同级选项归入类目
   压低 fanout）、改写（description 的触发词），每一步都给 diff 与判据，改完重跑第 2 步。
4. **路由可测** —— pack 级、框架无关的盲测：候选只有各节点的 description，判官只能读那一份文件，
   金标逐题给定；分数按**校正随机的口径**报，因为「这一层有 30 个选项」和「有 5 个」的成功率不可直接比。

## 与已有工具的关系

| 已有 | 它管什么 | 本仓库补什么 |
|---|---|---|
| `Dream` 的 `check-disclosure.py` | **一个** `SKILL.md` 自己的第一层：行数/字节/文档字节/被点名的同 pack 兄弟数 | **pack 层与层间**：每层的选项数、文档树形状、路由是否测得出来 |
| Hermes 的 `load-external-skill-index` / `skill-routing-blind-test` | Hermes 里的索引成本与路由盲测口径 | 去掉框架依赖，输入只认 pack 目录 |

## 形状（硬约束）

- 第一层（`SKILL.md`）只放：边界 · 方法 · 每步一行转指；细节下沉 `references/`，每份都被点名（无孤儿文档）。
- 长度上限是**可自检的常量**，超限即拆。
- 判据只求真命令与实测输出：改完必须能重跑出一份新的度量，不许写「应该好了」。

## 依据（读过的外部工作）

见 [`docs/prior-art.md`](docs/prior-art.md)：它列了每一项实测数字与本仓库据此做的决定。
