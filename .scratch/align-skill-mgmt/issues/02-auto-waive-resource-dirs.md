# 02: 扩展豁免规则支持 templates/examples/tests 自动豁免

**What to build:** `templates/`、`examples/`、`tests/` 三个目录下的文件不再被标记为"到不了根"（孤儿）。这些资源目录的文件不要求被 SKILL.md 显式引用，但如果确实被引用，则验证路径正确性。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 在 `skills/skillweave/scripts/weavelib/disclosure.py` 中添加常量：
  ```python
  AUTO_WAIVED_DIRS = ["templates", "examples", "tests"]
  ```
- [ ] 修改 `build_disclosure_tree()` 或负责检测"到不了根"的函数：
  - 检查文档路径是否匹配 `*/templates/*`、`*/examples/*`、`*/tests/*`
  - 匹配的文档自动标记 `waived=True`，原因为 "auto-waived resource directory"
- [ ] 在 `TODO.md` 生成逻辑中：
  - 这些文档不进入"待办"表
  - 在"已豁免"表中单独列出，注明 "(自动豁免：资源目录)"
  - 保留统计数字：`已豁免 N 条（自动 X · 手动 Y）`
- [ ] 更新 `docs/contract.md` §0.6（免检表）章节：
  - 说明 templates/examples/tests 自动豁免，无需写入 waivers.txt
  - 给出示例：waivers.txt 只需写其他特殊情况
- [ ] 添加 fixture 测试到 `selftest.py`：
  - 创建临时 pack：1 个 SKILL.md + templates/schema.json（未被引用）
  - 跑 disclosure，验证 schema.json 在"已豁免"表中，不在"待办"表中
- [ ] 跑 `python3 scripts/weave.py disclosure .` 验证 SkillWeave 自己的孤儿数减少
