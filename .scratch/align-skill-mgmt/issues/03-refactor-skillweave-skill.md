# 03: 重构 SkillWeave SKILL.md 为精简两层架构

**What to build:** 将当前 184 行的 `skills/skillweave/SKILL.md` 拆分为精简入口（~80 行）+ 详细 references/。用户阅读 SKILL.md 就能理解"何时用、怎么做、如何验收"，需要详细命令参考时再读 references/。

**Blocked by:** 01-unify-caps-table（caps 表需要先统一，才能在 references/concepts.md 中引用）

**Status:** ready-for-agent

- [ ] 创建 `skills/skillweave/references/commands.md`：
  - 从 SKILL.md §"命令" 章节搬出所有子命令的详细用法
  - 格式：每个命令一个 §，包含用法、参数说明、输出文件、示例
  - 包含：tree, layers, checks, audit, propose, judge, score, visualize, collapse, prepare, disclosure, dispatch, verify, apply, deliver
- [ ] 创建 `skills/skillweave/references/concepts.md`：
  - 从 `docs/contract.md` 搬入：文档树定义、披露定义、层的定义、形状的定义
  - 包含完整的 caps 表（引用 ticket 01 更新后的版本）
  - 包含术语表（从 DISCLOSURE.md 的术语表扩展）
- [ ] 创建 `skills/skillweave/references/workflow.md`：
  - 从 `docs/flow.md` 搬入 A→B→C→D→E→F 六阶段详细流程
  - 每个阶段：目标、输入、输出、谁判断（计算 vs 模型）、产物
  - 包含循环控制参数、回退策略、终止条件
- [ ] 创建 `skills/skillweave/references/pitfalls.md`：
  - 从 SKILL.md §"这轮真跑撞出来的坑" 搬出所有经验教训
  - 格式：问题描述 → 根因 → 解决方案 → 如何避免
- [ ] 重写 `skills/skillweave/SKILL.md`（目标 80 行）：
  - §"什么时候用"：触发条件（保留现有，精简到 5 行）
  - §"核心概念"：文档树、层、披露、形状（各 1-2 行定义，指向 concepts.md）
  - §"快速开始"：3 个最常用命令（disclosure、visualize、deliver），每个 2 行
  - §"完整流程"：6 阶段概览（每阶段 1 行：名称 + 一句话职责），指向 workflow.md
  - §"验收标准"：3 条（改完重跑、TODO 清空、自举通过）
  - §"详细文档"：路由表，指向 references/ 的 4 个文件 + 现有的 split/group/merge/rewrite
- [ ] 更新现有 references/ 中对 SKILL.md 章节的引用：
  - split.md, group.md, merge.md, rewrite.md 如果引用了 SKILL.md 的章节锚点，更新为指向新位置
- [ ] 在 SKILL.md 中显式引用所有新建的 references/ 文件（满足披露要求）
- [ ] 跑 `python3 scripts/weave.py disclosure .` 验证：
  - SKILL.md 不再超限（< 5000 token, < 500 行）
  - 新建的 4 个 references/ 文件都在 L2 层，不是"到不了根"
  - 没有新增悬空引用
