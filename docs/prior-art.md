# 先例与外证（2026-10-11 检索）

本文件是 SkillWeave 的立论依据：外部已经量过的结论 → 本仓库据此做的决定。**数字都来自下面的来源**，
引用时要连口径一起说（哪个榜单、多少候选、什么指标），别把不同口径的数字混着用。

## 1. 规范：Agent Skills 的开放格式（无厂商依赖）

来源：<https://agentskills.io/specification>（同一份内容也见于 Microsoft Learn / LangChain 文档）

- 一个技能 = 一个目录，至少含 `SKILL.md`；惯例子目录 `scripts/`（可执行）、`references/`（文档）、
  `assets/`（模板资源）。
- frontmatter：`name` 必填、≤64 字符、小写字母数字连字符；`description` 必填、**≤1024 字符**、非空；
  可选 `license` / `compatibility` / `metadata` / `allowed-tools`。
- 披露分三段：**元数据**（约 100 token，启动时给全部技能）→ **`SKILL.md` 正文**（**建议 < 5000 token**，
  激活时载入）→ **打包文件**（按需读）。

**决定**：契约就取这一份。SkillWeave 读的是目录 + frontmatter，不读任何 agent 的私有状态
（无 profile、无 lock、无内置技能表）——这是「不依赖 Hermes」的落地方式。

## 2. 厂商文档：`SKILL.md` 的上限与「什么时候拆文件」

来源：<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>

- 「接近这个上限时把内容拆进独立文件」（上限即第 1 条的 ~5000 token / 常用 500 行经验值）。
- `description` 同时承担 **发现**（discovery）与**何时使用**：必须写「做什么」+「什么时候用」+ 可识别的关键词。
- 正文里已给上下文的不重复讲；每个 token 都在跟对话历史抢窗口。

**决定**：审计的节点上限用**两条**口径并列报（字节 + 估算 token），阈值取规范建议值而不是自创数字；
`description` 的检查项就是「做什么 + 何时用 + 触发词」。

## 3. 反面证据：只看 description 会在近重复的大库上崩掉

来源：SkillRouter，Alibaba，arXiv:2603.22455（SkillsBench 派生榜单，约 **80K** 候选技能）

- 「隐藏技能正文」（只留名字 + description 做路由）会让路由准确率掉 **31–44 个百分点** —— 在候选量大、
  互相重叠的库里，**正文是关键路由信号**，不是可省的元数据。
- 他们必须专门做的两个适配：**近重复技能的假阴性过滤**、**listwise 重排**（说明同质技能池里的混淆是主因）。
- 榜单分档：Easy = 大池检索；**Hard = 功能接近的错误选项之间的混淆**。
- 其 1.2B 全文本 retrieve-and-rerank 管线 Hit@1 **74.0%**，胜过 16B 基线（68.0%）。

**决定**：审计必须能查**近重复 / 互相抢题**的节点（同层两个 description 或两份正文高度相似）；
路由评测要按「大池检索」与「近邻混淆」两类分开报，不能只给一个总分。

## 4. 「一层摆几个」是可评的，不是拍脑袋的常量

来源：How Many Tools Should an LLM Agent See? A Chance-Corrected Answer，Meta，arXiv:2605.24660

- 把**短名单深度 K**当作评估对象，用 **Bits-over-Random（BoR）** 校正随机基线：
  「在这个深度上比随机选得好吗」。
- 覆盖注册表 **20 → 3,251** 个工具；学到按查询调深度的策略在 BFCL（370 工具）上以平均 **K≈7.4** 达到
  K=50 的覆盖率（**90.3% vs 90.8%**）；ToolBench（3,251 工具）上固定 **K=5** 的总分更高；
  自适应深度下 **93.1% vs 87.1%**（永远给 5 个），在更难的档位拉开到 **76.8% vs 60.9%**。
- 成本口径：**约 200 token / 个工具描述**，短名单 100 个 ≈ 2 万 token。

**决定**：不写死「每层最多 20 个」当成真理；SkillWeave 报的是 **fanout 分布 + 该层的校正随机成功率**，
把「这一层该摆几个」变成在**这个 pack 上**测出来的数。

## 5. 分层披露本身值多少

来源：Report: Progressive Disclosure of Agent Skills，Workday AI Research，arXiv:2609.35692

- 在真实部署环境（2026-08 有 5,500+ 客户在用其 AI agent）实测：**分层披露（懒加载）提升技能检索质量，
  但轻微增加整体延迟**（多一次 LLM 调用换更少的上下文 token）。
- 随技能库规模 N 增长，**eager（一次全载）** 的检索质量掉得更快，且在 **N=100** 时开始**溢出上下文上限**。

**决定**：SkillWeave 报两组代价 —— **常驻成本**（元数据/索引 token）与**每次多出的调用数**；
验收里必须出现「同一 pack 改前/改后」的对照数字，而不是「更清晰了」这类形容词。

## 6. 「先建一棵树，再沿树导航」是成熟的检索形状

来源：RAPTOR，arXiv:2401.18059（递归摘要建树，用于树组织检索）；LLM-guided Hierarchical Retrieval /
LATTICE，arXiv:2510.13217（LLM 沿层次导航大语料）

- 树节点的**摘要**是导航信号：上层摘要让检索/路由不必下探就能判断该往哪走；导航复杂度随树高呈对数。
- 树是**构建出来的产物**（可重建、可 diff），不是人手维护的目录。

**决定**：`tree` 是 SkillWeave 的第一等产物（JSON + 人读视图），且必须**可重建、可 diff**；
每个节点都要带摘要，摘要由该节点自身内容产生（frontmatter description 或首段），不手写。

## 7. 改写 description 是有效手段（不是玄学）

来源：Learning to Rewrite Tool Descriptions for Reliable LLM-Agent Tool Use / Trace-Free+，arXiv:2602.20426

- 在候选扩到 **150+** 的规模上，改写工具描述能**减少准确率退化**，即「同一件事换个说法」是可优化的。

**决定**：优化动作里的「改写」按**可测**做：改完必须重跑路由评测（第 4 条口径）并给出前后分组分数。

## 没找到 / 不再找的

- 没有找到任何工具**直接**做这件事：输入一个 pack 目录 → 输出文档树 → 按层量化选择数 → 给出重构方案。
  已有的都是**库侧**（retrieval / rerank / 训练小模型）或**单文件侧**（作者规范），中间这层是空的。
- 检索词已覆盖：progressive disclosure、skill routing/selection benchmark、hierarchical/tree retrieval、
  tool-shortlist depth、tool description rewriting、skill pack 目录规范。
