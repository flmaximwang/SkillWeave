#!/usr/bin/env python3
"""仓库根的入口 —— 真正的实现只有一份：`skills/skillweave/scripts/weave.py`（skill 自包含）。

这里只做转发，不复制代码：同一份代码存两处，改一处忘一处是必然会发生的。
"""
import os
import runpy
import sys

REAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                    "skills", "skillweave", "scripts", "weave.py")
sys.argv[0] = REAL
runpy.run_path(REAL, run_name="__main__")
