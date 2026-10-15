# 01: 统一 caps 表为 agentskills.io + Anthropic 实践

**What to build:** 将 SkillWeave 的检查上限统一为仅依赖 agentskills.io 规范和 Anthropic 公开实践，删除所有 Dream 项目和临时决策的口径引用。用户运行 `disclosure` 时，所有警告和错误都基于可追溯的公开标准。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 更新 `skills/skillweave/scripts/weavelib/common.py` 中的 `CAPS` 常量：
  - `name`: ≤ 64 字符（agentskills.io）
  - `description`: ≤ 1024 字符（agentskills.io，硬约束）
  - SKILL.md 正文: 建议 < 5000 token（Anthropic，警告）
  - SKILL.md 行数: 建议 < 500 行（Anthropic，警告）
  - `references/` 单文件: 建议 < 300 行（Anthropic，警告）
  - 删除 20000 字节上限（Dream 口径）
  - 删除 50/150/500 行三档（简化为 500 行单一建议值）
- [ ] 更新 `skills/skillweave/scripts/weavelib/analysis.py` 中的 `cmd_layers()` 函数：
  - 删除对 `MAX_FIRST_LAYER = 20` 的引用（Dream 口径）
  - 或保留为"参考线"但明确标注来源和非强制性
- [ ] 更新 `docs/contract.md` §4（caps 表章节）：
  - 重写表格，每行包含：检查项、上限、来源（agentskills.io 或 Anthropic URL）、违规时行为（错误/警告）
  - 删除所有 "Dream 的 check-disclosure.py" 和 "包主口径 2026-10-12" 引用
  - 在表格下方添加"参考文档"链接：agentskills.io/specification 和 Anthropic docs
- [ ] 跑 `python3 scripts/weave.py disclosure .` 验证新 caps 不会拒绝工具自己
- [ ] 检查 `--self-test` 中的断言是否依赖旧 caps，更新相关 fixture
