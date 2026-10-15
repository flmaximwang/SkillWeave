# Spec: Align SkillWeave with New Skill Management Specification

## Problem Statement

SkillWeave 当前架构与更新后的 skill 管理规范（`0-manage-skills-by-maxim`）存在五类冲突：

1. **深度失控**：支持任意递归披露（L1→L2→...→Ln），但新规范要求浅层渐进披露（推荐 L2，最多 L3）
2. **口径混乱**：混合了 agentskills.io 规范、Anthropic 实践、Dream 项目常量和临时决策，缺乏明确的权威来源
3. **结构臃肿**：184 行的 SKILL.md 混合了概念、命令、流程、判据，违反"level-1 必须精简"的原则
4. **执行者缺位**：流程需要外部执行者（opencode/subagent）但没有地方配置和记录选择
5. **自举失败**：工具自己的 skill 不符合它定义的规范（SKILL.md 超限 5164 > 5000 token，13 个孤儿文档）

验证证据（2026-10-16）：
```bash
$ python3 scripts/weave.py disclosure . --out /tmp/skillweave-self-check
[disclosure] 根 1 个 · 层 L1=1 → L2=4 → 未分层=14 · 文档 19 份 · 超限 1 · 到不了根 13 · 悬空 11
```

## Solution

将 SkillWeave 重构为**严格两层披露架构**：
- **L1（SKILL.md）**：触发条件、核心概念、流程概览、命令速查、验收标准（目标 ~80 行）
- **L2（references/）**：详细的命令参考、四类动作指南、架构文档、排错手册

同时：
- 统一口径为 **agentskills.io + Anthropic 实践**
- 在 `prepare` 阶段记录执行者选择
- 工具自身先过自己的检查

## User Stories

1. 作为 skill pack 维护者，我希望快速检查我的 pack 是否符合两层披露规范，这样我可以在分发前发现问题
2. 作为 Agent 开发者，我希望工具只依赖 agentskills.io 和 Anthropic 的公开规范，这样我不必理解项目特定的口径
3. 作为自动化流程维护者，我希望在流程开始时配置执行者（opencode/claude-code/subagent），这样后续步骤可以按配置自动执行
4. 作为新用户，我希望阅读 SKILL.md 就能理解"何时用、怎么做、如何验收"，这样我不必先读完整个 references/ 树
5. 作为 SkillWeave 的贡献者，我希望工具自己符合它定义的规范，这样我可以相信它的判据
6. 作为披露优化的执行者，我希望看到"L3 超限警告"而不是"报错退出"，这样我可以量出完整的问题清单再决定如何修复
7. 作为 skill 作者，我希望知道 `templates/`、`examples/`、`tests/` 目录是否需要被显式引用，这样我可以正确组织资源
8. 作为 pack 分析者，我希望看到"这个文档在 L4"而不是"这个 pack 违规"，这样我可以追溯具体的引用链
9. 作为命令行用户，我希望 `weave.py --help` 能告诉我每个子命令的必需参数，这样我不必试错
10. 作为持续集成维护者，我希望 `disclosure` 命令输出 JSON 格式的待办清单，这样我可以编程处理结果

## Implementation Decisions

### 1. 口径统一：agentskills.io + Anthropic 实践

**caps 表重建**（替换 `docs/contract.md` §4）：

| 检查项 | 上限 | 来源 | 违规时行为 |
|---|---|---|---|
| `name` | ≤ 64 字符 | agentskills.io 规范 | 错误 |
| `description` | ≤ 1024 字符 | agentskills.io 规范（硬约束） | 错误 |
| SKILL.md 正文 | 建议 < 5000 token | Anthropic 实践 | 警告 |
| SKILL.md 行数 | 建议 < 500 行 | Anthropic 实践 | 警告 |
| `references/` 单文件 | 建议 < 300 行 | Anthropic 实践 | 警告 |
| 允许的目录 | `scripts/`, `references/`, `assets/`, `templates/`, `examples/`, `tests/` | agentskills.io + 扩展 | 警告未知目录 |
| 披露深度 | 建议 L2，警告 L3+ | Anthropic 实践 | 警告 |

**删除**：
- Dream 的 20000 字节上限
- "包主口径 2026-10-12"
- 50/150/500 行三档（简化为单一 500 行建议值）

**豁免资源**：
- `templates/`、`examples/`、`tests/` 下的文件**不要求**被 SKILL.md 显式引用
- 这三个目录自动加入"已豁免"（waivers.txt 不必手写）
- 但如果 SKILL.md 或 references/ 确实引用了它们，则验证路径正确性

实现位置：
- `skills/skillweave/scripts/weavelib/common.py`：更新 `CAPS` 常量和检查函数
- `skills/skillweave/scripts/weavelib/disclosure.py`：添加 `AUTO_WAIVED_DIRS = ["templates", "examples", "tests"]`
- `docs/contract.md` §4：重写 caps 表，删除 Dream 相关引用

### 2. SKILL.md 重构

**切分方案**（SkillWeave 的 `skills/skillweave/SKILL.md`）：

**保留在 SKILL.md**（目标 ~80 行）：
- §"什么时候用"（触发条件）
- §"核心概念"（文档树、层、披露、形状——不超过 10 行）
- §"快速开始"（最常用的 3 个命令：`disclosure`、`visualize`、`deliver`）
- §"完整流程"（A→B→C→D→E→F 六阶段概览，每阶段 1 行）
- §"验收标准"（改完必须重跑、TODO 清空、自举通过）
- §"详细文档"（指向 references/ 的路由表）

**下沉到 references/**：
- `references/commands.md`：所有子命令的详细用法（从 SKILL.md §"命令" 搬出）
- `references/concepts.md`：文档树、披露链、形状、caps 表的完整定义（从 `docs/contract.md` 搬过来，成为 skill 的一部分）
- `references/workflow.md`：A→B→C→D→E→F 的详细流程（从 `docs/flow.md` 搬过来）
- `references/pitfalls.md`：经验教训（从 SKILL.md §"这轮真跑撞出来的坑" 搬出）
- 保留现有的 `split.md`、`group.md`、`merge.md`、`rewrite.md`

**docs/ 树的处理**：
- `docs/flow.md`、`docs/contract.md` 的核心内容合并进 `references/`，原文件可删除或保留为指向 references/ 的指针
- `docs/prior-art.md`、`docs/similar-work.md`、`docs/architecture-review-2026-10-12.md` 保留（作为开发文档，不属于 skill 的披露链）

实现位置：
- `skills/skillweave/SKILL.md`：重写为精简版本
- `skills/skillweave/references/commands.md`：新建
- `skills/skillweave/references/concepts.md`：新建，从 `docs/contract.md` 迁移内容
- `skills/skillweave/references/workflow.md`：新建，从 `docs/flow.md` 迁移内容
- `skills/skillweave/references/pitfalls.md`：新建

### 3. 执行者配置

**在 `cmd_prepare()` 中添加交互式询问**：

```python
def cmd_prepare(root, out, dest, shape, description):
    # ... 现有的副本创建逻辑 ...
    
    # 询问执行者选择（只在首次 prepare 时）
    executor_config_path = os.path.join(dest, "dispatch", "executor.json")
    if not os.path.exists(executor_config_path):
        print("\n选择执行者（用于 dispatch 阶段的批次执行）：")
        print("  1) opencode + deepseek-v4.1-flash")
        print("  2) claude-code")
        print("  3) 子代理（delegate_task）")
        print("  4) 手动执行")
        choice = input("输入编号 [1-4, 默认 4]: ").strip() or "4"
        
        executors = {
            "1": {"type": "opencode", "model": "deepseek-v4.1-flash", 
                  "command": "opencode --model deepseek-v4.1-flash --prompt {input} --output {output}"},
            "2": {"type": "claude-code", "command": "claude-code --file {input}"},
            "3": {"type": "subagent", "command": "delegate_task(goal='...', context='{input}')"},
            "4": {"type": "manual", "command": "请手动执行 {input} 并将提案写入 {output}"}
        }
        
        executor = executors.get(choice, executors["4"])
        os.makedirs(os.path.dirname(executor_config_path), exist_ok=True)
        with open(executor_config_path, "w") as f:
            json.dump(executor, f, indent=2)
        print(f"[prepare] 执行者配置已保存到 {executor_config_path}")
```

**在 `cmd_dispatch()` 中读取并追加执行说明**：

```python
def cmd_dispatch(root, out, batch_size, refresh_baseline):
    # ... 现有的划批逻辑 ...
    
    # 读取执行者配置
    executor_config = os.path.join(root, "dispatch", "executor.json")
    if os.path.exists(executor_config):
        executor = json.load(open(executor_config))
        # 在每个 batch-N.prompt.md 末尾追加
        with open(prompt_path, "a") as f:
            f.write(f"\n\n## 执行方式\n\n")
            f.write(f"类型：{executor['type']}\n")
            f.write(f"命令：{executor['command']}\n")
            f.write(f"  - {{input}}：本文件路径\n")
            f.write(f"  - {{output}}：batch-{n}.proposal.json\n")
```

实现位置：
- `skills/skillweave/scripts/weavelib/transform.py`：修改 `cmd_prepare()`
- `skills/skillweave/scripts/weavelib/disclosure.py`：修改 `cmd_dispatch()`

### 4. 披露深度处理

**在 `cmd_disclosure()` 中计算并报告深度**（不退出）：

```python
def cmd_disclosure(root, out):
    # ... 现有的构建树逻辑 ...
    
    # 计算每个文档的披露深度
    max_depth = max((doc.get("depth", 0) for doc in all_docs), default=1)
    depth_histogram = {d: len([doc for doc in all_docs if doc.get("depth") == d]) 
                       for d in range(1, max_depth + 1)}
    
    # 报告深度分布
    print(f"[disclosure] 披露深度：L1={depth_histogram.get(1, 0)} → " +
          " → ".join(f"L{d}={depth_histogram.get(d, 0)}" for d in range(2, max_depth + 1)))
    
    if max_depth >= 3:
        print(f"  ⚠️ 检测到 L{max_depth} 层（Anthropic 建议不超过 L2）")
        # 列出所有 L3+ 的文档
        deep_docs = [doc for doc in all_docs if doc.get("depth", 0) >= 3]
        print(f"  深层文档 {len(deep_docs)} 份：")
        for doc in deep_docs[:5]:  # 只显示前 5 个
            print(f"    L{doc['depth']} {doc['path']}")
    
    # 不退出，继续生成 TODO.md
```

**在 TODO.md 中添加"披露过深"类别**：

待办清单新增一列用于标记披露深度问题：

```markdown
| # | 文档 | 问题 | 数字 | 建议动作 | 谁判 |
|---|---|---|---|---|---|
| X | `path/to/file.md` | 披露过深 | L4（被 L3 的 `other.md` 引用） | 考虑：上提到 L2（让 SKILL.md 直接引用）· 合并到父文档 · 或接受当前深度 | 待模型 |
```

实现位置：
- `skills/skillweave/scripts/weavelib/disclosure.py`：修改 `cmd_disclosure()` 和 TODO.md 生成逻辑
- 深度计算逻辑可能已存在于 `build_disclosure_tree()` 函数中，需要确认并扩展

### 5. 自举测试

**添加 `--self-check` 命令**：

```python
def cmd_self_check(root):
    """对 SkillWeave 自己跑 disclosure，要求 TODO 清单为空（豁免除外）"""
    import tempfile
    print("[self-check] 对 SkillWeave 自己运行 disclosure...")
    
    tmp = tempfile.mkdtemp(prefix="skillweave-self-")
    ret = cmd_disclosure(root, tmp)
    if ret != 0:
        print(f"[self-check] FAIL disclosure 返回 {ret}")
        return 1
    
    todo_json = os.path.join(tmp, "disclosure.json")
    if not os.path.exists(todo_json):
        print(f"[self-check] FAIL 未找到 {todo_json}")
        return 1
        
    todo = json.load(open(todo_json))
    issues = [item for item in todo.get("issues", []) if not item.get("waived")]
    
    if issues:
        print(f"[self-check] FAIL 发现 {len(issues)} 个未解决问题：")
        for item in issues[:5]:
            print(f"  - {item.get('path', '?')}: {item.get('kind', '?')}")
        return 1
    
    print(f"[self-check] PASS 自举检查通过")
    return 0
```

**修改 CLI 入口**：

```python
# 在 cli.py main() 函数中
if a.self_test:
    from .selftest import self_test
    return self_test()

if a.cmd == "self-check":
    from .analysis import cmd_self_check
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))  # 定位到 SkillWeave 仓库根
    return cmd_self_check(root)
```

加入 CI 流程（新建 `.github/workflows/test.yml`）：

```yaml
name: Test SkillWeave
on: [push, pull_request]
jobs:
  self-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Run self-check
        run: python3 scripts/weave.py self-check
      - name: Run existing self-test
        run: python3 scripts/weave.py --self-test
```

实现位置：
- `skills/skillweave/scripts/weavelib/analysis.py`：新增 `cmd_self_check()`
- `skills/skillweave/scripts/weavelib/cli.py`：添加 `self-check` 子命令
- `.github/workflows/test.yml`：新建 CI 配置

### 6. 命令行 UX 改进

**改进错误消息**（已有基础，需统一格式）：

```python
if a.cmd == "judge":
    if not a.prompts:
        print("[judge] 错误：缺少 --prompts 参数")
        print("用法：weave.py judge <pack> --prompts <题面.json> [--out DIR]")
        print("说明：生成判官输入文件（judge-input.txt）和金标文件（judge-key.json）")
        return 2
```

**添加 `help` 子命令**（可选，优先级低）：

```python
if a.cmd == "help":
    # 显示详细帮助
    help_texts = {
        "disclosure": """...""",
        "visualize": """...""",
        # ...
    }
    print(help_texts.get(a.pack, "使用 --help 查看所有命令"))
    return 0
```

实现位置：
- `skills/skillweave/scripts/weavelib/cli.py`：统一所有子命令的错误消息格式

## Testing Decisions

### 测试什么

1. **单元测试**（扩展现有 `selftest.py`）：
   - caps 表的每个闸（超 1024 字符的 description、超 5000 token 的 SKILL.md）
   - 披露深度计算（L1→L2→L3 的链）
   - 豁免规则匹配（templates/examples/tests 自动豁免）
   
2. **集成测试**（新增 fixture）：
   - 完整流程（prepare → disclosure → dispatch → verify → deliver）
   - 执行者配置的持久化和读取
   - 自举测试（SkillWeave 自己通过 disclosure）

3. **回归测试**（fixture）：
   - 现有的 `--self-test` fixture 保留
   - 新增"两层披露"fixture（SKILL.md → 2 个 references/ → 结束）
   - 新增"过深披露"fixture（SKILL.md → ref1.md → ref2.md → ref3.md，验证 L4 警告）

### 现有测试的借鉴

- 保留 `skills/skillweave/scripts/weavelib/selftest.py` 的框架
- 测试用 fixture 继续用临时目录（不污染仓库）
- 断言策略：精确匹配（JSON 字段）+ 模糊匹配（输出文本包含关键词）

### 测试先行原则

- 每个新功能必须有对应的 fixture 测试
- 修改现有功能时，先确保现有测试通过，再添加新测试覆盖新行为
- `--self-test` 必须在 CI 中运行

## Out of Scope

1. **不改变工具的定位**：SkillWeave 仍然是"量出问题"而不是"自动修复"——`propose` 给建议，人或 Agent 决定是否采纳
2. **不添加 GUI**：保持纯 CLI，可视化输出为 HTML 文件（`TREE.html`）
3. **不集成特定 Agent 框架**：工具仍然不依赖 Hermes/Claude/任何特定平台
4. **不处理非 skill 仓库**：输入必须含至少一个 `SKILL.md`，否则拒绝
5. **不实现在线服务**：工具是本地 CLI，不做 API server 或 web service
6. **不重写整个 weavelib**：只修改必要的模块，保持现有架构（模块划分见 `docs/architecture-review-2026-10-12.md`）

## Further Notes

### 迁移路径

优先级顺序（从高到低）：

1. **P0（阻塞）**：caps 表统一、豁免规则扩展（templates/examples/tests）
2. **P1（核心）**：SKILL.md 重构、披露深度警告、自举测试
3. **P2（增强）**：执行者配置、命令行 UX 改进
4. **P3（完善）**：CI 集成、文档更新

每个 ticket 完成后必须：
- 跑 `weave.py disclosure .` 确认不引入新问题
- 更新相关文档（如果有）

### 验收标准

整个 spec 的完成标准：

- [ ] SkillWeave 的 `skills/skillweave/SKILL.md` < 100 行
- [ ] `weave.py disclosure .` 返回"待办 0 条"（豁免除外）
- [ ] `weave.py self-check` 通过
- [ ] `docs/contract.md` §4 只引用 agentskills.io 和 Anthropic 文档
- [ ] `README.md` 的示例能一次跑通
- [ ] 所有 fixture 测试通过（`--self-test`）
- [ ] CI 流程运行并通过（`self-check` + `--self-test`）

### 相关文档

- [agentskills.io 规范](https://agentskills.io/specification)
- [Anthropic Skills 最佳实践](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prompt-library#skills)
- 新 skill 管理规范：`/Users/maxim/Documents/Habit/SkillManagement/skills/0-manage-skills-by-maxim/SKILL.md`
- 当前架构文档：`docs/architecture-review-2026-10-12.md`
