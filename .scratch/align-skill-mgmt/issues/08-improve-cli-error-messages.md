# 08: 改进命令行错误消息（统一格式）

**What to build:** 所有子命令的错误消息遵循统一格式：[命令名] 错误描述 + 用法示例 + 简短说明。用户遇到参数错误时，不必查文档或试错，直接看到正确用法。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 在 `skills/skillweave/scripts/weavelib/cli.py` 中统一错误消息格式：
  - 定义格式模板：
    ```python
    def print_usage_error(cmd, error, usage, description):
        print(f"[{cmd}] 错误: {error}")
        print(f"用法: weave.py {usage}")
        print(f"说明: {description}")
    ```
- [ ] 逐个检查每个子命令的参数验证：
  - `judge`: 需要 `--prompts`
    ```python
    if not a.prompts:
        print_usage_error("judge", "缺少 --prompts 参数",
                         "judge <pack> --prompts <题面.json> [--out DIR]",
                         "生成判官输入文件（judge-input.txt）和金标文件（judge-key.json）")
        return 2
    ```
  - `score`: 需要 `--key` 和 `--judge`
  - `verify`: 需要 `--state` 和 `--expect-fixed`
  - `apply`: 需要 `--proposals` 或 `--revert`
  - `collapse --apply`: 需要 `--description`
  - 其他子命令类似检查
- [ ] 为没有必需参数的命令添加帮助提示：
  - 如果用户只输入 `weave.py` 不带参数，显示：
    ```
    用法: weave.py <command> <pack> [options]
    
    常用命令:
      disclosure  构建文档树并生成待办清单（TODO.md）
      visualize   生成可视化文件（TREE.md + TREE.html）
      prepare     创建工作副本并初始化流程
      deliver     合并改动回真包并推送
    
    运行 'weave.py <command> --help' 查看具体命令的选项
    运行 'weave.py --self-test' 验证工具自身
    运行 'weave.py self-check' 检查工具合规性
    ```
- [ ] 测试每个命令的错误路径：
  - `python3 scripts/weave.py judge .` → 显示缺少 --prompts 的错误
  - `python3 scripts/weave.py score` → 显示缺少 --key 和 --judge 的错误
  - `python3 scripts/weave.py` → 显示简要帮助
- [ ] （可选）添加 `--help` 对每个子命令的支持：
  - `python3 scripts/weave.py disclosure --help` → 显示 disclosure 的详细帮助
  - 实现方式：检查 `a.pack == "--help"` 时显示该命令的详细说明
