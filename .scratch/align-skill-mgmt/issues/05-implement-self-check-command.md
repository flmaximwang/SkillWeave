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


---

## 执行前必须知道的实测发现（2026-10-16，Phase 1 之后）

在 main 上跑 `python3 scripts/weave.py disclosure .` 的真实读数：

```
层 L1=1 → L2=4 → 未分层=14 · 文档 19 份 · 超限 1 · 到不了根 13 · 自动豁免 0 · 悬空 12 · external 13
```

**self-check 想通过，这 13 个「到不了根」和 12 条「悬空」必须先定性**，而它们分两类：

1. **`skills/skillweave/scripts/weavelib/*.py` 共 13 份「到不了根」** —— 全部是 Python 源码。
   工具的口径是「脚本不设字节上限、不拆」，但**仍要求被所属 SKILL.md 点名**，否则算孤儿。
   ticket 03 改 SKILL.md 时必须点名这些脚本（或写进 `.skillweave/waivers.txt`）。

2. **`selftest.py` / `graph.py` / `model.py` 里 12 条「悬空」** —— 这些是 **fixture 字符串**，
   不是真的打算指到某个文件：

   | 文件:行 | 命中的字面量 | 来源 |
   |---|---|---|
   | `selftest.py:36` | `references/gone.md` · `references/guide.md` | 悬空/到不了根的 fixture |
   | `selftest.py:37` | `templates/README.md` | 同上 |
   | `selftest.py:137` | `references/中文说明.md` | 非 ASCII 路径 fixture |
   | `selftest.py:143` | `references/x.md` | 同上 |
   | `selftest.py:147` | `references/leaf.md` | 嵌套 skill fixture |
   | `selftest.py:166` | `references/ref1.md` | **ticket 04 新加的深度 fixture**（本轮 11→12 的那一条） |
   | `selftest.py:328` | `references/moved2.md` | 拆分/搬移 fixture |
   | `selftest.py:377` | `references/p1.md` | 提案 fixture |
   | `selftest.py:432` | `references/nope.md` | apply 校验 fixture |
   | `graph.py:162` | `references/x.md` | 注释里的举例 |
   | `model.py:79` | `templates/README.md` | 注释里的举例 |

   **这是工具对自己测量的一个真实盲点**：它扫「脚本正文里像包内路径的字符串」，
   而 fixture 与注释里的示例路径天生就是「不存在的路径」。两条出路，ticket 05 二选一（或在 spec 里定）：

   - **A（工具改口径）**：脚本类文档**不做悬空检查**（与「脚本不设字节上限」同一条理由 ——
     Agent 不整份读脚本，脚本里的示例路径不是披露意图）。改动小、口径自洽。
   - **B（包内豁免）**：在 `<pack>/.skillweave/waivers.txt` 里列这三个文件。
     不改工具，但每次新增 fixture 都要维护清单，且把「工具自身缺陷」记成「包主的判断」。

   **建议 A**：理由与 §4 已确立的「脚本不计字节」完全同源；B 会让 waivers.txt 承担它不该承担的职责
   （契约 §0.6 写明 waivers 是「包主的判断」，而这里是工具口径问题）。

**验收口径提醒**：self-check 通过 ≠ 全文零发现。它要求 **`disclosure.json` 里 `waived` 之外的条目为空**。
所以 ticket 03 与 ticket 05 谁先合并会影响读数 —— 建议 03（点名脚本）先落地，05 再收口。
