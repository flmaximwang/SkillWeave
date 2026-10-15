# 09: 添加 CI 自动化测试（GitHub Actions）

**What to build:** 在仓库中添加 GitHub Actions 配置，每次 push 或 PR 时自动运行 `self-check` 和 `--self-test`，确保工具本身始终合规。CI 失败时阻止合并，保证主分支质量。

**Blocked by:** 05-implement-self-check-command（需要 self-check 命令可用）

**Status:** ready-for-agent

- [ ] 创建 `.github/workflows/test.yml` 文件：
  ```yaml
  name: SkillWeave Tests
  
  on:
    push:
      branches: [ main, develop ]
    pull_request:
      branches: [ main ]
  
  jobs:
    self-check:
      name: Self-check and fixtures
      runs-on: ubuntu-latest
      
      steps:
        - name: Checkout code
          uses: actions/checkout@v3
        
        - name: Set up Python
          uses: actions/setup-python@v4
          with:
            python-version: '3.10'
        
        - name: Run self-check
          run: |
            python3 scripts/weave.py self-check
        
        - name: Run fixture tests
          run: |
            python3 scripts/weave.py --self-test
        
        - name: Upload disclosure report on failure
          if: failure()
          uses: actions/upload-artifact@v3
          with:
            name: disclosure-report
            path: /tmp/skillweave-self-*/
  ```
- [ ] 在 `README.md` 中添加 CI 徽章：
  ```markdown
  ![Tests](https://github.com/<user>/SkillWeave/workflows/SkillWeave%20Tests/badge.svg)
  ```
  （替换 `<user>` 为实际的 GitHub 用户名或组织名）
- [ ] 添加 `.github/workflows/README.md` 说明 CI 流程：
  - self-check: 验证工具自身符合规范（SKILL.md 不超限、无孤儿文件）
  - --self-test: 运行所有 fixture 测试（caps 表、披露链、豁免规则等）
  - 失败时上传 disclosure 报告到 Artifacts，方便调试
- [ ] 本地测试 CI 逻辑：
  - 确保在干净的环境中（新 clone 的仓库）能通过
  - 故意破坏一个测试（比如修改 SKILL.md 超限），验证 CI 失败
  - 修复后验证 CI 通过
- [ ] （可选）添加定期运行（cron）：
  ```yaml
  on:
    schedule:
      - cron: '0 0 * * 0'  # 每周日运行
  ```
  确保依赖的外部规范（agentskills.io、Anthropic）变化时能及时发现不兼容
