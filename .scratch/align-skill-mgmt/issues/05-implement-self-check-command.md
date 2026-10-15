# 05: 实现自举测试命令（self-check）

**What to build:** 新增 `weave.py self-check` 子命令，对 SkillWeave 仓库自己运行 `disclosure`，要求待办清单为空（豁免除外）。这是工具自己符合规范的可验证证据，用户和 CI 可以随时运行确认工具本身合规。

**Blocked by:** 02-auto-waive-resource-dirs, 03-refactor-skillweave-skill（必须先修复工具自己的问题，self-check 才能通过）

**Status:** ready-for-agent

- [ ] 在 `skills/skillweave/scripts/weavelib/analysis.py` 中添加 `cmd_self_check()` 函数：
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
      
      # 读取 disclosure.json（TODO.md 的机器可读版本）
      todo_json = os.path.join(tmp, "disclosure.json")
      if not os.path.exists(todo_json):
          print(f"[self-check] FAIL 未找到 {todo_json}")
          return 1
          
      todo = json.load(open(todo_json, encoding="utf-8"))
      issues = [item for item in todo.get("issues", []) if not item.get("waived")]
      
      if issues:
          print(f"[self-check] FAIL 发现 {len(issues)} 个未解决问题：")
          for item in issues[:10]:  # 显示前 10 个
              print(f"  - {item.get('path', '?')}: {item.get('kind', '?')} - {item.get('detail', '')}")
          print(f"\n查看完整清单: {os.path.join(tmp, 'TODO.md')}")
          return 1
      
      print(f"[self-check] PASS 自举检查通过（{tmp}）")
      return 0
  ```
- [ ] 在 `skills/skillweave/scripts/weavelib/cli.py` 中添加 `self-check` 子命令：
  - 修改 `choices` 列表，加入 `"self-check"`
  - 添加处理分支：
    ```python
    if a.cmd == "self-check":
        from .analysis import cmd_self_check
        # 定位到 SkillWeave 仓库根（向上三级从 weavelib/cli.py）
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        return cmd_self_check(root)
    ```
- [ ] 修改 `disclosure.json` 的输出格式（如果尚未包含）：
  - 添加 `issues` 数组，每个元素包含：`path`, `kind`, `detail`, `waived`, `action`, `who`
  - 这样 `cmd_self_check()` 可以编程读取而不是解析 Markdown
- [ ] 测试：
  - 在 ticket 02 和 03 完成之前，运行 `python3 scripts/weave.py self-check` 应该 FAIL（显示当前的 13 个孤儿 + 1 个超限）
  - 在 ticket 02 和 03 完成之后，运行应该 PASS
- [ ] 更新 `README.md`，添加"验证工具自身合规"章节：
  ```bash
  # 验证 SkillWeave 自己符合规范
  python3 scripts/weave.py self-check
  ```
