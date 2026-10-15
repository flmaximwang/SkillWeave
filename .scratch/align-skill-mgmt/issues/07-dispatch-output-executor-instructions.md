# 07: 在 dispatch 阶段读取并输出执行说明

**What to build:** `dispatch` 命令生成批次 prompt 文件（`batch-N.prompt.md`）时，读取 `dispatch/executor.json`，在每个 prompt 文件末尾追加"## 执行方式"章节，包含具体的命令行示例。用户或 CI 脚本看到 prompt 文件就知道如何执行，无需回忆或查文档。

**Blocked by:** 06-executor-config-in-prepare（需要先有配置才能读取）

**Status:** ready-for-agent

- [ ] 在 `skills/skillweave/scripts/weavelib/disclosure.py` 中修改 `cmd_dispatch()` 函数：
  - 在生成每个 `batch-N.prompt.md` 文件之后，检查 `<root>/dispatch/executor.json` 是否存在
  - 如果存在，读取配置并在文件末尾追加执行说明：
    ```python
    executor_config_path = os.path.join(root, "dispatch", "executor.json")
    if os.path.exists(executor_config_path):
        executor = json.load(open(executor_config_path, encoding="utf-8"))
        
        with open(prompt_path, "a", encoding="utf-8") as f:
            f.write("\n\n---\n\n")
            f.write("## 执行方式\n\n")
            f.write(f"**类型**: {executor['type']}\n\n")
            
            # 生成具体命令示例
            cmd = executor['command_template']
            cmd = cmd.replace("{model}", executor.get("model", ""))
            cmd = cmd.replace("{input}", os.path.basename(prompt_path))
            cmd = cmd.replace("{output}", f"batch-{batch_num}.proposal.json")
            
            f.write(f"**命令**:\n```bash\n{cmd}\n```\n\n")
            f.write("**说明**:\n")
            f.write(f"- `{{input}}`: 本文件路径（{os.path.basename(prompt_path)}）\n")
            f.write(f"- `{{output}}`: 提案输出文件（batch-{batch_num}.proposal.json）\n")
            
            if executor['type'] == "manual":
                f.write("\n请手动执行上述 prompt，将提案以 JSON 格式写入输出文件。\n")
    ```
- [ ] 在 `plan.json` 中记录执行者信息（供后续阶段使用）：
  - 在 dispatch 生成的 `plan.json` 中添加 `executor` 字段（副本整个配置）
- [ ] 如果 `executor.json` 不存在，输出警告但不阻塞：
  ```python
  print("[dispatch] 警告：未找到执行者配置（dispatch/executor.json）")
  print("           提示：运行 prepare 时选择执行者，或手动创建配置文件")
  ```
- [ ] 测试：
  - 完成 ticket 06 后，运行完整流程：
    ```bash
    python3 scripts/weave.py prepare <pack> --dest /tmp/ws
    # 选择 "1) opencode"
    python3 scripts/weave.py dispatch /tmp/ws
    ```
  - 打开 `/tmp/ws/dispatch/batch-1.prompt.md`，验证末尾包含：
    - "## 执行方式" 标题
    - 类型：opencode
    - 具体命令：`opencode --model deepseek-v4.1-flash --prompt batch-1.prompt.md --output batch-1.proposal.json`
    - 参数说明
- [ ] 更新 `references/workflow.md`（ticket 03 创建的文件），在 D 阶段说明：
  - dispatch 会自动读取执行者配置并生成执行说明
  - 用户按照 prompt 文件末尾的命令执行即可
