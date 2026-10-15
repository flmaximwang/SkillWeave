# Changelog

SkillWeave 的对外变更记录。口径与 caps 的来源见 [`docs/contract.md`](docs/contract.md) §4。

## [Unreleased]

### Changed

- 统一 caps 表为 **agentskills.io + Anthropic 公开实践**，删除项目特定口径（Dream 常量、临时决策、
  `claude-skills-cli` 三档）；阈值唯一代码出处是 `weavelib/common.py` 的 `CAPS` / `CAP_*`。
- 重构 `skills/skillweave/SKILL.md` 为**两层披露架构**（精简入口 + 详细 `references/`），184 行 → 88 行。
- 披露深度警告改为**建议**：出现 L3+ 只警告、不退出（Anthropic 建议不超过 L2）。
- 文档口径同步：README 的「三级披露」改为「两层披露架构」；`docs/contract.md` §0/§4 重写 caps 表；
  `docs/flow.md` 顶部加指针指向 `skills/skillweave/references/workflow.md`。

### Added

- 执行者配置功能：`prepare` 阶段选择并持久化（`dispatch/executor.json`），`dispatch` 阶段在每个
  `batch-N.prompt.md` 末尾输出执行方式。
- `self-check` 命令：对工具自身跑 `disclosure`，未豁免待办为空即 PASS（用户与 CI 可随时验证）。
- 自动豁免 `templates/` · `examples/` · `tests/` 资源目录，无需写进 `waivers.txt`。
- 脚本类文档不做「悬空」检查（与「脚本不设字节上限」同源；markdown 里悬空照报）。
- 文档：`CHANGELOG.md`（本文件）。
- CI 自动化测试（GitHub Actions：`self-check` + `--self-test`）。

### Removed

- Dream 项目的 **20000 字节**资源上限。
- 「包主口径 2026-10-12」的临时决策（脚本字节口径的结论保留，改归本工具口径）。
- `claude-skills-cli` 的 **50 / 150 / 500** 行三档（收敛为单一建议值 500 行）。
- `MAX_FIRST_LAYER = 20` 硬闸（收敛为入口层参考线 `FIRST_LAYER_REFERENCE`）。
