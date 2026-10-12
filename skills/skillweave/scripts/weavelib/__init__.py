"""SkillWeave 实现包 —— 原单文件 weave.py 按关注点拆成 12 个模块（2026-10-12）。

入口仍是 `scripts/weave.py`（薄壳，转调 `weavelib.cli.main`）。
模块依赖是一条 DAG（无环）；`cli` 对 `selftest` 用延迟导入。

SkillWeave · 把一个 skill pack 解析成文档树（契约见 docs/contract.md）。

用法:
  python3 scripts/weave.py tree <pack 目录> [--out DIR]     # 产 tree.json + TREE.md
  python3 scripts/weave.py --self-test                      # 自带 fixture 自检

不依赖任何 agent 框架、不依赖第三方包（纯 stdlib）。字段名与 kind 分类沿用
agent-skill-analysis 的口径（见 docs/similar-work.md A1），便于将来把 per-skill 段
换成 `asa --json`；替换点是 analyze_skill() 一个函数。

ponytail: 只做「树 + 每层 fanout」，不做语义索引/向量；规模上按 pack 目录线性扫一遍，
          pack 数到几千个 skill 时仍是秒级。
"""
