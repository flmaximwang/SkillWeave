# 04: 添加披露深度警告（L3+ 时警告但不退出）

**What to build:** `disclosure` 命令计算每个文档的披露深度，报告深度分布直方图。检测到 L3 及以上层级时输出警告（列出具体文档），但继续执行并生成完整的 TODO.md。用户看到"这个文档在 L4"而不是"pack 违规，拒绝分析"。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 在 `skills/skillweave/scripts/weavelib/disclosure.py` 中修改 `cmd_disclosure()`：
  - 确保每个文档节点有 `depth` 字段（从根算起的披露距离，根=1）
  - 如果 depth 计算尚未实现，添加 BFS 遍历逻辑：从所有根开始，层次遍历披露边
- [ ] 在 `cmd_disclosure()` 输出中添加深度报告：
  ```python
  max_depth = max((doc.get("depth", 0) for doc in all_docs), default=1)
  depth_histogram = {d: sum(1 for doc in all_docs if doc.get("depth") == d) 
                     for d in range(1, max_depth + 1)}
  print(f"[disclosure] 披露深度：" + 
        " → ".join(f"L{d}={depth_histogram[d]}" for d in range(1, max_depth + 1)))
  
  if max_depth >= 3:
      deep_docs = [doc for doc in all_docs if doc.get("depth", 0) >= 3]
      print(f"  ⚠️ 检测到 L{max_depth} 层（Anthropic 建议不超过 L2）")
      print(f"  深层文档 {len(deep_docs)} 份（显示前 5 个）：")
      for doc in sorted(deep_docs, key=lambda d: d.get("depth", 0), reverse=True)[:5]:
          print(f"    L{doc['depth']} {doc['path']}")
  ```
- [ ] 在 TODO.md 生成逻辑中添加"披露过深"问题类型：
  - 对于 depth >= 3 的文档，生成一条待办
  - 问题类型："披露过深"
  - 数字：`L{depth}（被 L{depth-1} 的 {parent_path} 引用）`
  - 建议动作："考虑：上提到 L2（让 SKILL.md 直接引用）· 合并到父文档 · 或接受当前深度"
  - 谁判："待模型"
- [ ] 在 `disclosure.json` 中添加 `depth_histogram` 字段（供编程处理）
- [ ] 添加 fixture 测试到 `selftest.py`：
  - 创建临时 pack：SKILL.md → ref1.md → ref2.md → ref3.md（四层链）
  - 跑 disclosure，验证：
    - 不退出（返回 0）
    - 输出包含 "⚠️ 检测到 L4 层"
    - TODO.md 包含 ref3.md 的"披露过深"条目
- [ ] 确保 `--self-test` 中没有断言"disclosure 必须 < L3"（如果有，删除或放宽）
