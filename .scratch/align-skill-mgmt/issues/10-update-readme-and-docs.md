# 10: 更新 README 和文档反映新规范

**What to build:** 更新 `README.md`、`docs/contract.md` 和相关文档，反映新的 caps 表、两层披露架构、执行者配置流程。新用户阅读 README 就能理解工具的设计原则和使用方式，不会遇到过时的口径引用。

**Blocked by:** 01-unify-caps-table, 03-refactor-skillweave-skill, 06-executor-config-in-prepare（需要这些功能完成才能更新文档）

**Status:** ready-for-agent

- [ ] 更新 `README.md`：
  - 在"三级披露"章节更新为"两层披露架构"：
    - L1: SKILL.md 精简入口（触发条件、核心概念、流程概览）
    - L2: references/ 详细资料（命令参考、工作流、概念定义）
  - 删除对 Dream 项目和"包主口径"的引用
  - 更新示例，体现执行者配置流程：
    ```bash
    # 完整流程示例
    python3 scripts/weave.py prepare my-skills --dest /tmp/ws
    # 选择执行者（交互式）
    python3 scripts/weave.py disclosure /tmp/ws
    # 查看 TODO.md，按建议修改
    python3 scripts/weave.py dispatch /tmp/ws
    # 按 batch-N.prompt.md 末尾的"执行方式"执行
    python3 scripts/weave.py verify /tmp/ws --state dispatch/state.json --expect-fixed <ids>
    python3 scripts/weave.py deliver /tmp/ws
    ```
  - 添加"验证工具自身"章节：
    ```bash
    # 验证 SkillWeave 符合自己的规范
    python3 scripts/weave.py self-check
    
    # 运行所有 fixture 测试
    python3 scripts/weave.py --self-test
    ```
  - 更新"依据与契约"章节，引用：
    - agentskills.io/specification
    - Anthropic Skills 文档
    - 新的 skill 管理规范（提供路径或 URL）
- [ ] 更新 `docs/contract.md`：
  - §4（caps 表）：应用 ticket 01 的更改，删除所有非公开规范的引用
  - §0（层的定义）：更新为"建议 L2，警告 L3+"
  - §0.5（术语表）：确保与 TODO.md 的术语表一致
  - §7（两种形状）：明确单入口和多入口都支持，不强制单入口
- [ ] 更新 `docs/flow.md`（或删除，因为内容已搬到 references/workflow.md）：
  - 如果保留，在文件顶部添加指针：
    ```markdown
    > **注意**：本文件的内容已迁移到 `skills/skillweave/references/workflow.md`。
    > 此文件保留作为开发参考，但 skill 的权威流程文档在 references/ 中。
    ```
- [ ] 检查其他文档文件：
  - `docs/prior-art.md`：确保引用的实测结论仍然有效（如果引用了 Dream 口径，更新或删除）
  - `docs/similar-work.md`：确保对比表格中 SkillWeave 的描述准确反映当前功能
  - `docs/architecture-review-2026-10-12.md`：如果提到口径或流程，更新相关部分
- [ ] 验证所有文档链接：
  - 确保文档内部链接（`docs/flow.md` → `docs/contract.md`）有效
  - 确保指向外部规范的链接可访问（agentskills.io、Anthropic docs）
- [ ] 在 `CHANGELOG.md`（如果没有则创建）中记录本次重构：
  ```markdown
  ## [Unreleased]
  
  ### Changed
  - 统一 caps 表为 agentskills.io + Anthropic 实践，删除项目特定口径
  - 重构 SKILL.md 为两层披露架构（精简入口 + 详细 references/）
  - 披露深度警告改为建议（L3+ 警告但不退出）
  
  ### Added
  - 执行者配置功能（prepare 阶段选择，dispatch 阶段输出执行说明）
  - self-check 命令（验证工具自身合规）
  - 自动豁免 templates/examples/tests 目录
  - CI 自动化测试（GitHub Actions）
  
  ### Removed
  - Dream 项目的 20000 字节上限
  - "包主口径 2026-10-12" 临时决策
  ```
