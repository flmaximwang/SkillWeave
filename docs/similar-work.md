# 同类先例实勘（2026-10-11 检索 + 逐个核 capability）

**结论**：文档树这件事**不是新需求，也已经有人做了**。用户直觉正确。逐项核过之后，SkillWeave 的范围必须收窄到
「**pack 层**」——即一次看很多个 skill 时的那一层：每层的选择数、同层互相抢题的节点、以及改完能不能证明变好。

## A. 直接做 skill 结构化分析的（要用的/要让开路的）

### A1. `tanker327/agent-skill-analysis`（MIT · npm · Node ≥ 20 · 42 commits · 2026-06 创建）

- 一个 skill 目录（`SKILL.md` + 资源）→ **一份自描述 `SkillAnalysis` JSON**；同样的输入逐字节同样的输出
  （确定性），且有公开 JSON Schema。
- 产出覆盖：frontmatter 解析/归一化/按规范校验（未知键保留在 `frontmatter.extra`，不当错）；
  body（全文、行数、**heading outline，代码围栏内不计**、token 估计）；**files manifest**（`path` / `size` /
  `sha256` / `kind` = `instructions|reference|script|asset|readme|license|other` / `isText`）；
  **references：`declared` / `resolved` / `broken` / `external` / `orphans`**；按 kind 的体积分解；内容 digest。
- CLI 是 `asa`（`npx -p agent-skill-analysis asa ./my-skill`），零 harness 假设（"no registry concepts"）。

**意义**：**SkillWeave 原计划 T-002（树构建器）与 T-003 的「孤儿/悬空/体积/kind 分解」大部分已被它覆盖。**
它没做的是：**只有在单个 skill 之内**——没有 pack/类目层、没有 fanout（每层几个选项）、没有同层近重复、
没有路由评测、没有重构。

### A2. `skill-tools/skill-tools`（Apache-2.0 · npm）

- 自称 "the ESLint + Lighthouse for that format"：**20 条 spec 检查 + 10 条 lint 规则 + 0–100 质量分**
  （5 个维度，其中一维就叫 **Progressive Disclosure 15/15**）、**BM25 路由**（零依赖）、watch /
  pre-commit hook / GitHub Action / SARIF、还能从 OpenAPI/MCP **生成** SKILL.md。
- 默认分支是 `pre-release`（不是稳定 release）。

**意义**：per-skill 的披露打分与**检索式**路由它有了；它没有的是「判官式路由归属评测」与「按度量重构」。

### A3. `spences10/claude-skills-cli`（CLI · 130 commits）

- 用**硬上限**强制分层披露：L1 元数据 **<200 字符**、L2 正文 **≈50 行**、L3 `references/` 不限；
  `validate` 三档（默认 50 行 / `--lenient` 150 / `--loose` 500 = Anthropic 官方上限）；`init` 生成骨架。

**意义**：它的 per-skill 披露打分启发了 SkillWeave 的 caps 表。**SkillWeave 不再沿用它那套硬上限与
三档口径** —— 已收敛到 agentskills.io（`name` / `description`）+ Anthropic 实践（< 5000 token /
< 500 行 / `references/` < 300 行）的建议值，见 `docs/contract.md` §4。

### A4. 其它同类（同类形状，未逐个深挖）

`Resinder/claude-skill-forge`（Pydantic 校验 + 披露模式）、`KEINOS/skillmd-frontmatter-validator`、
`severith-ai/skill-md-validator`（frontmatter 校验器）、`antfu/skills-cli` / `Karanjot786/agent-skills-cli`
（生态安装/管理 CLI）、`VoltAgent/awesome-agent-skills` / `scienceaix/agentskills`（索引）。

## B. 「先建一棵树，再沿树导航」的成熟族谱（说明这不是新需求）

- **文档树的老祖宗**：Sphinx 的 `toctree` / doctree（1990s 就有）、DOM、Docling（PDF/DOCX → 层级化
  JSON 文档树，MIT）、`llms.txt`（AnswerDotAI 的索引约定）。
- **向量库之外的路由式检索**：PageIndex（VectifyAI，MIT，486 commits）「为文档生成**树索引**，让 LLM
  reasoning 着走树」；同族的 ReasonTree、Psi-RAG（ICML'26，跨文档层级抽象树）、`unstablebrainiac/Hierarchical-RAG`；
  学术侧 RAPTOR（arXiv:2401.18059）、LATTICE（arXiv:2510.13217）。
- **代码库的对应物**：aider 的 **repo map**（tree-sitter 抽符号 + PageRank 排序送进上下文）——「把整个仓库变成
  一张可读的图/树，再决定给模型看哪一块」，与 SkillWeave 想做的事同构（本机 Hermes 也有一个受它启发的
  issue #535）。

## C. 所以 SkillWeave 还剩什么（收窄后的范围）

没有被任何先例覆盖的四件，全部是 **pack 层 / 跨 skill** 的：

1. **pack 文档树**：`pack → 类目 → skill → 章节/文件` 的**父层**与每层的 fanout（每层几个选项）。
   A1 只给单个 skill 的树，没有母树。
2. **同层近重复 / 互相抢题**：一个 pack 里两个 skill（或一份 `references/` 与另一份）语义高度重叠时的清单。
   依据：SkillRouter 在 ~80K 候选上实测正文是关键路由信号、近重复是主要混淆源（arXiv:2603.22455）。
3. **判官式路由评测 + 校正随机分**：A2 只有 BM25 检索，没有「逐题判官 + 金标 + 该层 fanout 下比随机好多少」
   （Meta BoR 口径，arXiv:2605.24660）。
4. **按度量重构并重测**：拆/分/并/改写四类动作，加改完自动重跑出前后对照。先例全是**检查器**，没有**重构器**。

## D. 要用户拍板的一件事（决定用不用 A1）

A1 是 JS/TS（Node ≥ 20），SkillWeave 现在打算是纯 stdlib Python。两条路：
- **依赖 A1**：per-skill 的节点数据直接吃 `asa --json`，SkillWeave 只做 pack 层与评测层 → 少写代码，
  但引入 Node 依赖，且要跟它的 schema 版本走（它还在 0.x 阶段，42 commits）。
- **自带最小解析器**：stdlib 约 200 行覆盖 frontmatter / heading outline / files / refs / orphans / token 估计，
  **字段名与 kind 分类沿用 A1 的口径**（保持互操作），零依赖。
  → 代价：与 A1 有重叠实现；收益：任何机器（不必有 Node）都能跑，且能被完全验证。

**本仓库的取舍**：先按「自带最小解析器 + 字段对齐 A1」做（见 `docs/contract.md`），
替换点是**一个函数** `analyze_skill()`；要改成依赖 A1 只需换这一个函数的实现。等用户拍板后再定。
