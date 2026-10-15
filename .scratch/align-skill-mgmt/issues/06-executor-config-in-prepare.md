# 06: 在 prepare 阶段添加执行者配置

**What to build:** 用户运行 `prepare` 创建工作副本时，工具交互式询问执行者选择（opencode/claude-code/subagent/手动），并将配置保存到副本的 `dispatch/executor.json`。这样后续 `dispatch` 阶段可以读取配置并生成对应的执行说明，避免流程中途询问用户导致任务阻塞。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 在 `skills/skillweave/scripts/weavelib/transform.py` 中修改 `cmd_prepare()` 函数：
  - 在创建副本并初始化 git 之后，检查 `<dest>/dispatch/executor.json` 是否存在
  - 如果不存在（首次 prepare），显示交互式菜单：
    ```python
    print("\n选择执行者（用于 dispatch 阶段的批次执行）：")
    print("  1) opencode + deepseek-v4.1-flash")
    print("  2) claude-code")
    print("  3) 子代理（delegate_task）")
    print("  4) 手动执行")
    choice = input("输入编号 [1-4, 默认 4]: ").strip() or "4"
    ```
  - 根据选择创建配置对象：
    ```python
    executors = {
        "1": {
            "type": "opencode", 
            "model": "deepseek-v4.1-flash",
            "command_template": "opencode --model {model} --prompt {input} --output {output}"
        },
        "2": {
            "type": "claude-code",
            "command_template": "claude-code --file {input}"
        },
        "3": {
            "type": "subagent",
            "command_template": "delegate_task(goal='执行批次提案', context='{input}')"
        },
        "4": {
            "type": "manual",
            "command_template": "请手动执行 {input} 并将提案写入 {output}"
        }
    }
    ```
  - 保存到 `<dest>/dispatch/executor.json`：
    ```python
    executor_path = os.path.join(dest, "dispatch", "executor.json")
    os.makedirs(os.path.dirname(executor_path), exist_ok=True)
    with open(executor_path, "w", encoding="utf-8") as f:
        json.dump(executors[choice], f, indent=2, ensure_ascii=False)
    print(f"[prepare] 执行者配置已保存: {executor_path}")
    ```
- [ ] 添加 `--executor` 命令行参数（可选，用于非交互式场景）：
  - 在 `cli.py` 中添加 `--executor` 参数：choices=["opencode", "claude-code", "subagent", "manual"]
  - 如果提供了 `--executor`，跳过交互式询问，直接使用指定值
- [ ] 在 `BASELINE.md` 中记录执行者选择：
  - 添加一行：`执行者：{type} ({model if exists})`
- [ ] 测试：
  - 运行 `python3 scripts/weave.py prepare <pack> --dest /tmp/ws`
  - 验证交互式菜单出现
  - 选择 "1"，验证 `/tmp/ws/dispatch/executor.json` 内容正确
  - 再次运行 prepare（同一 dest），验证不再询问（配置已存在）
