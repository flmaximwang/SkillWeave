#!/usr/bin/env python3
"""SkillWeave 开发计划的生成器（loomerto CLI 的唯一入口，不手改 plan.json）。

用法: python3 plans/build-plan.py
只在计划还没被别人动过时整份重建；重建 = 把 plans/skillweave 删掉再跑本脚本。
"""
import os
import shutil
import subprocess
import sys
import json

REPO = os.path.expanduser("~/Repositories/Repo/SkillWeave")
PLANS_ROOT = os.path.join(REPO, "plans")
SLUG = "skillweave"
LT = ["loomerto", "--plans-root", PLANS_ROOT]

FAILS = []
IDS = {}          # (task, index) -> real block id


def run(args):
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        FAILS.append((args, p.returncode, p.stdout.strip(), p.stderr.strip()))
        print("FAIL", " ".join(args[:6]), "rc=", p.returncode, p.stdout.strip()[:200], p.stderr.strip()[:200])
    return p.stdout.strip()


def task(title, deps=None, owner="default"):
    out = run(LT + ["task", "add", SLUG, "--title", title, "--owner", owner]
              + (["--deps"] + list(deps) if deps else []))
    tid = None
    for tok in out.replace("✓", " ").split():
        if tok.startswith("T-") and "#" not in tok:
            tid = tok.strip(":")
    if not tid:
        FAILS.append((["task", title], 0, out, "解析不出 task id"))
    print("task", tid, title)
    return tid


def block(tid, i, title, kind, doc, done_when, deps=None, status="pending", owner="default",
          review_of=None):
    out = run(LT + ["--no-render", "block", "add", SLUG, "--task", tid, "--title", title,
                    "--kind", kind, "--doc", doc, "--done-when", done_when,
                    "--owner", owner, "--status", status]
              + (["--deps"] + list(deps) if deps else [])
              + (["--review-of", review_of] if review_of else []))
    bid = None
    for tok in out.split():
        if tok.startswith("T-") and "#B-" in tok:
            bid = tok.strip(":")
    if not bid:
        FAILS.append((["block", title], 0, out, "解析不出 block id"))
    IDS[(tid, i)] = bid
    print("  block", bid, "|", title)
    return bid


def main():
    d = os.path.join(PLANS_ROOT, SLUG)
    if os.path.isdir(d):
        shutil.rmtree(d)
    run(LT + ["plan", "new", SLUG, "--title", "SkillWeave · skill pack 文档树与分层披露",
              "--goal",
              "并不依赖 Hermes：直接基于 skill pack 目录分析。提供构建 skill 文档树的方法，"
              "基于构建的文档树优化分层披露的结构（把「某一层摆出的选项太多、Agent 选不对」变成可量的量并修掉）。"
              "开发计划存在本仓库 plans/skillweave/，随仓库提交。"])

    # ---------------- T-001 契约与形状 ----------------
    t1 = task("契约与形状：先把「文档树」与「层」定义死")
    b = block(t1, 1, "决策：本仓库的落点与远端", "decision",
              """【问题】本仓库已在本地建成：`~/Repositories/Repo/SkillWeave`（`git init` 完成，**没有任何远端**，
工作区只有 README.md / docs/prior-art.md / plans/）。要不要建 GitHub 远端，建的话叫什么、公开还是私有。

1. 远端怎么定？
   - A：`flmaximwang/SkillWeave`（公开）—— 与 Dream / Loomerto 同级，别的 agent 可直接 `git clone` 用。
   - B：同名但私有 —— 先自己用，等形状稳了再公开。
   - C：不建远端，只在本地跑（那就没有备份，也没有跨机可用性）。
2. 本仓库要不要同时做成「可被任意 agent 安装的 skill」（`skills/skillweave/SKILL.md`），
   还是纯 CLI 工具仓库？（见 T-007#B-003，两问可一起答。）

【解锁】答 1 → 解锁 T-007#B-001（README/提交/推送）；答 2 → 解锁 T-007#B-003。

【已实测的事实】本地仓库存在、`git init` 完成、尚无 commit；本机已有 `git@github.com:flmaximwang/*` 的 SSH 凭据
（Dream / Loomerto 都在用）。""",
              "答案以原话落进本块的 run；解锁的块被改成对应状态（推送 / 不推送）。",
              status="blocked", owner="you")

    b = block(t1, 2, "docs/contract.md：文档树节点 schema 与「层」的定义", "impl",
              """【做什么】写死两件事，之后所有脚本与报告都按它读：

① 节点 schema：每个节点带 `path` / `kind`（`pack|category|skill|section|reference|script|asset`）/
`bytes` / `est_tokens` / `summary` / `summary_source`（frontmatter description | 首段首句 | 空）/
`refs`（该节点正文里真实出现的引用目标）。
② 「层」的定义：从 pack 入口到某个需求，**路上遇到的每个 fanout>1 的节点就是一层**；
层的度量 = 该节点的选项数（fanout）+ 该层被选中后的成功率（T-005 给）。

【命令】`python3 scripts/weave.py tree <pack 目录> --out <dir>` 产出的 `tree.json` 就是本 schema 的实例。

【口径】summary 只允许来自文件自身内容，禁止手写；refs 只记正文里真实出现的路径/技能名（记行号）。""",
              """`docs/contract.md` 存在，含：schema 每个字段的来源（frontmatter / 正文 / 文件系统）、
一份 tree.json 的最小示例（≥3 个节点、含一条引用边）、以及「层」的定义原文；
用 `python3 -c` 读示例 JSON 能过 `json.loads`。""",
              deps=None)

    block(t1, 3, "caps 表：上限常量与它们的出处", "impl",
          """【做什么】把上限写成**一张常量表**（供 T-003 逐条判），每条都必须引 prior-art 的出处与口径：
- 节点体积：`SKILL.md` 建议 < 5000 token（另报字节）；`description` ≤ 1024 字符（规范硬约束）。
- fanout：**不设死值**；报分布 + 该层的校正随机成功率（Meta BoR 口径），阈值只在报告里给「实测最优点」。
- 孤儿：任何文件必须被至少一个祖先点名（0 容忍）。
- depth-to-needle：从入口到最深处文件的跳数，超 N 需给转指链。
每条常量落到 `docs/contract.md` 的一张表里，附来源 URL 与口径（榜单规模 / 指标名）。""",
          """`docs/contract.md` 里出现该表；每一行的「来源」列都能点到 `docs/prior-art.md` 的对应小节；
表中不含没有任何出处的自创数字。""",
          deps=["T-001#B-002"])

    # ---------------- T-002 构建文档树 ----------------
    t2 = task("构建 skill 文档树")
    block(t2, 1, "scripts/weave.py tree：把 pack 解析成节点图", "impl",
          """【做什么】纯 stdlib（无第三方依赖）的 `tree` 子命令：走一个 pack 目录 → 出 `tree.json` + `TREE.md`。
- 解析 frontmatter：`name` / `description`（要为 `description: >-` 这类折叠块兜底，不能只用正则抓首行）。
- 节点：pack → 类目目录 → 技能目录（有 SKILL.md）→ 正文标题 → 被点名的文件。
- 边：`parent` / `ref`（正文里出现的相对路径）/ `mention`（正文里出现的同 pack 技能名）。
- 跳数：从 pack 入口算每个节点的最短跳数（BFS，供 T-003 用）。

【命令】
```
python3 scripts/weave.py tree ~/Documents/AgentSkill/AgentSkill-UsingHermes --out /tmp/sw-usinghermes
```""",
          """在 AgentSkill-UsingHermes 上跑出 `tree.json`：`json.loads` 能读；节点数 ≥ 该 pack 的 SKILL.md 数；
随机抽 5 条 `ref` 边，逐条能在正文里找到那一行（行号对得上）；命令与输出贴进本块的 run。""")

    block(t2, 2, "可重建、可 diff", "impl",
          """【做什么】同一 pack 连跑两次，产物逐字节相同（排序稳定、无时间戳）；
改动 pack 里一个文件后，diff 只出现在相关节点及其祖先的 `bytes`/`est_tokens` 上。""",
          """① 两次运行的 `sha256` 相同（贴两条 sha）。② 改一个文件的 description 后重跑，`diff tree.json`
只出现预期字段（贴 diff 原文）。""",
          deps=["T-002#B-001"])

    block(t2, 3, "节点摘要的来源可追溯", "impl",
          """【做什么】每个节点的 `summary` 必须带 `summary_source`（如 `SKILL.md:3 frontmatter.description`），
空的要显式写 `null`（不许编）。""",
          """抽 3 个节点（1 个有 frontmatter、1 个只有正文、1 个空文件）打印 `path / summary / summary_source`，
三条都能在源文件里定位到那一行。""",
          deps=["T-002#B-001"])

    # ---------------- T-003 审计 ----------------
    t3 = task("分层披露审计：把每一层量出来")
    block(t3, 1, "每层的选择数（fanout 分布 + 选项清单）", "impl",
          """【做什么】对每个 fanout>1 的节点：报该层的选项数与选项清单；全局给 fanout 分布直方图，
并标出超出该层实测最优点的层（最优点来自 T-005，未跑时留空不猜）。

【命令】`python3 scripts/weave.py audit <pack> --section fanout`""",
          """在 AgentSkill-UsingHermes 上，`skills/` 这一层报到实测的条目数与分类目录数、以及每个类目下的
技能数（贴命令输出）；直方图数据落 `<out>/fanout.json`。""",
          deps=["T-002#B-002"])

    block(t3, 2, "节点体积与规范建议值对照", "impl",
          """【做什么】逐节点报 `bytes` / `est_tokens`，对照 `SKILL.md` < 5000 token 与 `description` ≤ 1024 字符；
超限的按超出比例排序输出清单。""",
          """贴出超限清单（至少「0 条」也要有一行实测：扫了 N 个 SKILL.md，超限 0 条）。""",
          deps=["T-002#B-002"])

    block(t3, 3, "孤儿文件与悬空引用", "impl",
          """【做什么】两个方向都查：
① 孤儿：没有任何祖先节点点名过的文件（含 `references/` 里没被 SKILL.md 提到的、`assets/` 里没人用的）；
② 悬空：正文点名了但路径不存在的引用（相对路径解析 + 同 pack 技能名解析）。""",
          """两类各给一份清单文件（可为空，但要有文件）；在 AgentSkill-UsingHermes 上给出真实条数。""",
          deps=["T-002#B-002"])

    block(t3, 4, "近重复 / 互相抢题的节点", "impl",
          """【做什么】同层节点两两比 description 与正文首段（纯 stdlib：difflib / token-shingle Jaccard），
输出 top-N 相似对 + 相似度，标出「同层且相似度高」的对 —— 这是路由最容易错的形态
（SkillRouter 在 80K 候选上实测：正文是必需信号，近重复是主因）。

【命令】`python3 scripts/weave.py audit <pack> --section dup --top 20`""",
          """在 AgentSkill-UsingHermes 上给出 top-20 相似对清单（含相似度与两侧路径）；
至少一对要人工抽验：把两侧 description 原文贴进 run，说明为什么算相似。""",
          deps=["T-002#B-002"])

    block(t3, 5, "成本报告：常驻成本 + 多出的调用数", "impl",
          """【做什么】报两组数（Workday 报告的口径：分层披露提升检索质量、轻微增加延迟）：
① 常驻成本 = 全部 `description` 的字节/估算 token（每个 agent 每次会话都要付的那份）；
② 索引/激活成本 = `SKILL.md` 总量与「按需读一个文件」多出的一次调用数估算。""",
          """在 AgentSkill-UsingHermes 上给出两组实测数字与算法说明（估算 token 的规则要写出来）。""",
          deps=["T-002#B-002"])

    # ---------------- T-004 优化 ----------------
    t4 = task("优化：按度量的结果改结构")
    block(t4, 1, "四类动作的提案器（默认只出提案）", "impl",
          """【做什么】读 T-003 的报告，出**可执行的提案**（默认 `--dry-run`，只打印 diff 与影响面，不落盘）：
- 拆：超过体积上限的节点 → 下沉到 `references/`，原位留一行转指；
- 分：fanout 超最优点的一层 → 归入类目目录（并给出新路径清单）；
- 并：同层近重复 → 合并方案（保留哪个、折进哪个、正文哪几段是重复的）；
- 改写：description 缺「何时用」或缺触发词 → 给出改写稿（改完必须能重跑 T-005 证明更好）。
`--apply` 才落盘，且落盘前对每个被改文件留 `.orig` 备份。""",
          """在 AgentSkill-UsingHermes 上跑 `--dry-run`：输出的每条提案带 `文件:行` 与 diff 形状；
`--apply` 在一个**临时复制的 pack**上真跑一次，`git diff --stat` 与提案条数一致（贴输出）。""")

    block(t4, 2, "改完自动重跑审计并出前后对照", "impl",
          """【做什么】`--apply` 之后自动重跑 T-003 全套，输出「前 → 后」对照表（fanout 分布、超限条数、
孤儿数、近重复对数、常驻成本）。没有对照表 = 这次优化没有证据。""",
          """贴一份真实的前后对照表（在临时 pack 上做），每个数字都来自命令输出。""",
          deps=["T-004#B-001"])

    # ---------------- T-005 路由评测 ----------------
    t5 = task("路由评测：框架无关、可校正随机")
    block(t5, 1, "判官输入生成器（候选只有 description）", "impl",
          """【做什么】输入 pack + 一份冻结的题面集 → 输出**一个纯文本文件** `judge-input.txt`：
候选表（每行 `路径 | description 截断窗口`）+ 题面（编号）。任何 agent / 人都能拿它跑判官。
同时输出 `judge-key.json`（每题的金标：归属节点 + 题型），**不进判官输入**。
三类题：① 大池检索（该选谁）② 近邻混淆（两个相似节点里选对的）③ 诱饵（不该选任何一个）。""",
          """生成器在 AgentSkill-UsingHermes 上跑出两个文件；`judge-input.txt` 里不含金标字段
（`grep` 验证）；候选条数 == 该 pack 节点数（实测数字）。""")

    block(t5, 2, "打分器：逐题矩阵 + 分组 + 校正随机分", "impl",
          """【做什么】吃「判官输出 + 金标」出逐题矩阵，按三类题分组给分；并给**校正随机**分
（Meta 的 BoR 口径：在该层 fanout 下，比随机选好多少），因为 fanout=30 的一层和 fanout=5 的一层
的裸成功率不可直接比。""",
          """用 T-005#B-003 的真实判官输出打一遍分：逐题矩阵 + 三组分数 + 校正随机分都在报告里；
口径（随机基线怎么算）写清。""",
          deps=["T-005#B-001"])

    block(t5, 3, "在真实 pack 上跑一轮并留档", "impl",
          """【做什么】用 `delegate_task` 发独立判官（不共享上下文），跑 AgentSkill-UsingHermes 一轮；
判官输出落文件（批次摘要会截断长输出，必须落盘）。判官输出是**原件**，事后一个字都不改。""",
          """`<批次目录>/judge-*.txt` 存在且行数 == 题面数；打分结果落 `round-1-score.txt`；三处路径贴进 run。""",
          deps=["T-005#B-001"])

    # ---------------- T-006 验收 ----------------
    t6 = task("在真实 pack 上验收")
    block(t6, 1, "首个 subject：AgentSkill-UsingHermes 完整审计报告", "impl",
          """【做什么】对该 pack 出完整报告：文档树 + 每层 fanout + 体积超限 + 孤儿/悬空 + 近重复 top-N +
成本两组数 + 优化提案。基线（2026-10-11 实测）：`skills/` 第一层 69 个条目（52 个直接是技能 + 17 个类目）、
全 pack 126 份 `SKILL.md`。""",
          """报告文件落 `<批次目录>/report-usinghermes.md`，每个数字带产生它的命令；报告里的命令能被别人重跑复现。""",
          deps=["T-003#B-005", "T-004#B-002"])

    block(t6, 2, "独立子代理复核（不许自己验自己）", "review",
          """【做什么】派一个与执行者不同的子代理，只读报告与 pack，按报告里的命令重跑，逐项核对数字；
不一致的逐条列出。子代理**只用前台命令**（不许起后台进程）。""",
          """复核输出落文件，含「逐项 ✓/✗ 表 + 不一致明细」；有 ✗ 就回到对应块整改，不许改判据。""",
          review_of="T-006#B-001")

    block(t6, 3, "第二个 pack 交叉验证（防过拟合）", "impl",
          """【做什么】换一个形状不同的 pack（类目层级更深 / 技能更少 / 有大量 `references/`）跑一遍，
证明报告不是只对 UsingHermes 成立。候选：`AgentSkill-DoingSAXS`、`Dream`、`AgentSkill-LabProject`。""",
          """同一套命令在第二个 pack 上跑通，报告落 `<批次目录>/report-<pack>.md`；
两 pack 的 fanout 分布形状差异写进结论。""",
          deps=["T-003#B-001"])

    # ---------------- T-007 仓库与交付 ----------------
    t7 = task("仓库与交付")
    block(t7, 1, "提交本仓库：README / docs / plans 一起进版本", "impl",
          """【做什么】按决策块 T-001#B-001 的答案建远端（或不建）并提交推送。
本仓库自身守同一套规矩：`plans/skillweave/` 随仓库提交（`git add plans/`），README 给一行
`file:///Users/maxim/Repositories/Repo/SkillWeave/plans/skillweave/plan.html` 与几条只读命令。""",
          """`git show --stat` 里能看到 `plans/skillweave/plan.json` 与 `plan.html`；若已建远端，
`git log origin/main -1` 的 sha 与本地 HEAD 相同。""",
          deps=["T-001#B-001"])

    block(t7, 2, "本仓库自己的分层披露自检", "impl",
          """【做什么】本仓库也是 skill pack 的一种形态，给自己留一条自检：
`SKILL.md` 薄入口 + `references/` 下沉 + 无孤儿文档 + 体积极限，超限 exit 1。""",
          """`python3 scripts/selfcheck.py`（或等价命令）在仓库根跑出 exit 0，并把输出贴进 run。""",
          deps=["T-002#B-001"])

    block(t7, 3, "交付形态：纯 CLI 仓库，还是同时可安装的 skill", "impl",
          """【做什么】按 T-001#B-001 第 2 问的答案落地：
- 只做 CLI：README 写清 `python3 scripts/weave.py ...` 的用法即可；
- 同时做 skill：加 `skills/skillweave/SKILL.md`（第一层薄、细节下沉、`name` + `description` 合规），
  任何 agent 拿到本仓库都能按 agentskills.io 规范识别它。""",
          """按答案落地后，`ls` 与 `head -20` 的输出贴进 run；若做了 skill，`SKILL.md` 的 description ≤1024 字符
且含「做什么 + 何时用」。""",
          deps=["T-001#B-001"], status="blocked")

    run(["loomerto", "--plans-root", PLANS_ROOT, "render", SLUG])
    out = run(["loomerto", "--plans-root", PLANS_ROOT, "check", SLUG])

    print("\n=== 读回断言 ===")
    pj = json.load(open(os.path.join(PLANS_ROOT, SLUG, "plan.json")))
    total = 0
    for t in pj["tasks"]:
        n = len(t["blocks"])
        total += n
        print(f"  {t['id']} {t['title'][:40]:42s} blocks={n} deps={t.get('deps') or []}")
    print("  总块数 =", total)
    empty = [(t["id"], b["id"]) for t in pj["tasks"] for b in t["blocks"]
             if not b.get("done_when") or not b.get("doc")]
    print("  缺 doc/done_when 的块:", empty or "无")
    allids = {x["id"] for tt in pj["tasks"] for x in tt["blocks"]}
    broken = [(b["id"], d) for t in pj["tasks"] for b in t["blocks"]
              for d in (b.get("deps") or []) if "#" in d and d not in allids]
    print("  悬空依赖:", broken or "无")
    norev = [x["id"] for tt in pj["tasks"] for x in tt["blocks"]
             if x.get("kind") == "review" and not x.get("review_of")]
    print("  review 块缺 review_of:", norev or "无")
    print("\nFAILS =", len(FAILS))
    for f in FAILS:
        print("  ", f)
    return 1 if (FAILS or empty) else 0


if __name__ == "__main__":
    sys.exit(main())
