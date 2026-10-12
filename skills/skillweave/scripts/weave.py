#!/usr/bin/env python3
"""SkillWeave 入口（薄壳）—— 实现已拆进同目录的 `weavelib/` 包。

用法（不变）:
  python3 scripts/weave.py tree <pack 目录> [--out DIR]
  python3 scripts/weave.py --self-test

不依赖任何 agent 框架、不依赖第三方包（纯 stdlib）。模块划分与依赖见
docs/architecture-review-2026-10-12.md。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from weavelib.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
