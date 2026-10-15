# Tickets Overview: Align SkillWeave with New Skill Management Specification

## Dependency Graph

```
[01] Unify caps table
  └─→ [03] Refactor SKILL.md
       └─→ [05] Implement self-check
            └─→ [09] Add CI automation
  └─→ [10] Update README and docs

[02] Auto-waive resource dirs
  └─→ [05] Implement self-check

[04] Add depth warning
  (no dependencies)

[06] Executor config in prepare
  └─→ [07] Dispatch output executor instructions
  └─→ [10] Update README and docs

[08] Improve CLI error messages
  (no dependencies)

[05] Implement self-check
  └─→ [09] Add CI automation

[10] Update README and docs
  (depends on 01, 03, 06)
```

## Execution Order (by priority and dependencies)

### Phase 1: Foundation (P0 - Blocking)
可以并行执行：
- **[01] Unify caps table** - 统一口径，删除 Dream/临时决策引用
- **[02] Auto-waive resource dirs** - 豁免 templates/examples/tests
- **[04] Add depth warning** - 披露深度警告（L3+ 不退出）
- **[06] Executor config in prepare** - 执行者配置（prepare 阶段）
- **[08] Improve CLI error messages** - 命令行 UX 改进

预计工作量：1-2 天（并行）

### Phase 2: Core Refactoring (P1)
依赖 Phase 1 的部分 tickets：
- **[03] Refactor SKILL.md** - 重构 SkillWeave 自己的 SKILL.md（依赖 01）
- **[07] Dispatch output executor instructions** - dispatch 输出执行说明（依赖 06）

预计工作量：2-3 天

### Phase 3: Validation & CI (P1)
依赖 Phase 2 完成：
- **[05] Implement self-check** - 自举测试命令（依赖 02, 03）
- **[09] Add CI automation** - GitHub Actions CI（依赖 05）

预计工作量：1 天

### Phase 4: Documentation (P3)
依赖大部分功能完成：
- **[10] Update README and docs** - 更新文档（依赖 01, 03, 06）

预计工作量：1 天

## Total Estimated Time
- 并行执行（理想情况）：5-7 天
- 串行执行（单人）：8-10 天

## Acceptance Criteria (Overall)

运行以下命令全部通过，才算完成整个 spec：

```bash
# 1. 自举测试通过
python3 scripts/weave.py self-check
# 预期：PASS 自举检查通过

# 2. Fixture 测试通过
python3 scripts/weave.py --self-test
# 预期：所有测试通过

# 3. SKILL.md 符合规范
python3 scripts/weave.py disclosure . --out /tmp/check
# 预期：待办 0 条（豁免除外）

# 4. 完整流程可执行
python3 scripts/weave.py prepare . --dest /tmp/test-ws --executor=manual
python3 scripts/weave.py disclosure /tmp/test-ws
cat /tmp/test-ws/.skillweave/TODO.md
# 预期：流程顺利完成，executor 配置已保存

# 5. CI 通过
git push
# 预期：GitHub Actions 绿灯
```

## Verification Checklist

- [ ] SkillWeave 的 `skills/skillweave/SKILL.md` < 100 行
- [ ] `python3 scripts/weave.py disclosure .` 返回"待办 0 条"（豁免除外）
- [ ] `python3 scripts/weave.py self-check` 通过
- [ ] `docs/contract.md` §4 只引用 agentskills.io 和 Anthropic 文档
- [ ] `README.md` 的示例能一次跑通
- [ ] 所有 fixture 测试通过（`--self-test`）
- [ ] CI 流程运行并通过（`self-check` + `--self-test`）
- [ ] 执行者配置功能正常（prepare 询问 → dispatch 输出执行说明）
- [ ] 披露深度 L3+ 显示警告但不退出
- [ ] templates/examples/tests 自动豁免生效

## Notes for Implementers

### Using opencode + deepseek-v4.1-flash

按照你的要求，这些 tickets 应该交给 opencode + deepseek-v4.1-flash 执行。建议的执行方式：

```bash
# 对于每个 ticket（按依赖顺序）
opencode --model deepseek-v4.1-flash \
  --prompt .scratch/align-skill-mgmt/issues/01-unify-caps-table.md \
  --context "$(cat docs/SPEC-align-with-new-skill-management.md)"
```

或者使用 delegate_task：
```python
delegate_task(
    goal="完成 ticket 01: Unify caps table",
    context=f"""
    Spec: {read_file('docs/SPEC-align-with-new-skill-management.md')}
    Ticket: {read_file('.scratch/align-skill-mgmt/issues/01-unify-caps-table.md')}
    
    仓库根目录: /Users/maxim/Repositories/AgentNative/SkillWeave
    """
)
```

### Critical Path

最关键的依赖链（阻塞后续工作）：
```
01 → 03 → 05 → 09
```

如果资源有限，优先完成这条链，其他 tickets（02, 04, 06-08, 10）可以后续补充。

### Testing Strategy

- 每个 ticket 完成后立即运行 `python3 scripts/weave.py disclosure .`，确保不引入新问题
- Ticket 05 完成后，每个后续 ticket 都要确保 `self-check` 仍然通过
- Ticket 03 是最复杂的（重构 SKILL.md），建议分步骤：
  1. 先创建 4 个新的 references/ 文件
  2. 验证它们被 SKILL.md 引用（不是孤儿）
  3. 再精简 SKILL.md
  4. 最后验证 disclosure 通过

### Rollback Plan

如果某个 ticket 实现后导致工具不可用：
1. `git revert` 该 commit
2. 分析失败原因，更新 ticket 的 acceptance criteria
3. 重新实现

所有改动都应该在 feature branch 上进行，主分支保持可用。
