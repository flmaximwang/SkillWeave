"""CLI 入口与子命令派发。

从 weave.py 拆出，逻辑未改。issue #08 起：所有参数错误走**同一套格式**
（`print_usage_error`），错误消息 = [命令名] 错误描述 + 用法示例 + 一句话说明；
不带命令时给出简要帮助，而不是长篇 argparse usage。"""
import argparse, json, os
from .analysis import cmd_audit, cmd_checks, cmd_judge, cmd_layers, cmd_score
from .common import count, strip_private
from .deliver import cmd_deliver
from .disclosure import cmd_disclosure, cmd_dispatch, cmd_verify
from .graph import add_headings, fanout_report
from .model import add_mentions
from .pack import Pack
from .render import cmd_visualize, render_md
from .transform import cmd_apply, cmd_collapse, cmd_prepare, cmd_propose


# 每个子命令的 (用法, 一句话说明) —— 帮助与错误消息的**唯一来源**（issue #08）。
# `usage` 不含 "weave.py " 前缀：print_usage_error / --help 会自己拼。
COMMANDS = {
    "tree":       ("tree <pack> [--out DIR]",
                   "构建文档树 → tree.json + TREE.md"),
    "layers":     ("layers <pack> [--out DIR]",
                   "三级披露分层账（L1/L2/L3 体积与超限）"),
    "checks":     ("checks <pack> [--out DIR]",
                   "安全与可移植检查（引用/预算/name/硬编码路径/内嵌密钥），命中即 exit 1"),
    "audit":      ("audit <pack> [--out DIR]",
                   "审计四段：体积 / 孤儿悬空 / 同层抢题 / 成本两组数"),
    "propose":    ("propose <pack> [--out DIR] [--apply] [--apply-group MAP]",
                   "四类动作的提案（拆/分/并/改写）：默认 dry-run 只出提案"),
    "judge":      ("judge <pack> --prompts <题面.json> [--out DIR]",
                   "生成判官输入文件（judge-input.txt）和金标文件（judge-key.json）"),
    "score":      ("score --key <金标.json> --judge <判官输出文件…> [--out DIR]",
                   "对判官输出打分（含校正随机分）"),
    "visualize":  ("visualize <pack> [--out DIR]",
                   "生成可视化文件（TREE.md + TREE.html）"),
    "collapse":   ("collapse <pack> [--out DIR] [--entry-dir NAME] [--apply --description \"…\"]",
                   "把 pack 塌成单入口（L1=1）：默认 dry-run"),
    "prepare":    ("prepare <pack> --dest WORK/ws [--out DIR] [--shape single|multi]",
                   "创建工作副本并初始化流程"),
    "disclosure": ("disclosure <pack> [--out DIR]",
                   "构建文档树并生成待办清单（TODO.md）"),
    "dispatch":   ("dispatch <pack> [--out DIR] [--batch-size N] [--refresh-baseline]",
                   "派发前事实补全 + 划批 + 落 prompt + 计数起点"),
    "verify":     ("verify <pack> --state <dispatch/state.json> --expect-fixed <id…> [--splits <json>] [--out DIR]",
                   "集合级对账（闸 1）：该消的消了 · 无新增 · external 不变 · 拆分守恒"),
    "apply":      ("apply <pack> --proposals <提案.json…>  |  apply <pack> --revert <条目 id> [--state STATE] [--out DIR]",
                   "逐条校验并落盘，或用 --revert 回退一条"),
    "deliver":    ("deliver <work/ws> [--dry-run] [--no-push] [--keep-worktree] [--main BRANCH] [--out DIR]",
                   "合并改动回真包并推送"),
    "self-check": ("self-check",
                   "对 SkillWeave 仓库自身跑 disclosure，要求待办清单为空（豁免除外）"),
    "help":       ("help [<command>]",
                   "列出全部子命令；带 <command> 时给该命令的详细说明（用法 / 参数 / 产物 / 示例）"),
}

# argparse 的 `choices`（唯一来源）。COMMANDS 的键集必须与它一致 —— `--self-test` 会断言，
# 防止「加了命令忘更新帮助」或反过来（issue #11）。
SUBCOMMANDS = ("tree", "layers", "checks", "audit", "propose", "judge", "score",
               "visualize", "collapse", "prepare", "disclosure", "dispatch", "verify",
               "apply", "deliver", "self-check", "help")

# `<pack>` 可省略的子命令（默认当前目录）：judge / score 吃的参数本身已定位了包或输入；
# self-check 检查的是**工具自己**（仓库根从 `weavelib` 反推），不需要 `<pack>`；
# help 吃的是子命令名（放在 pack 位置），也不做包分析。
_PACK_OPTIONAL = {"judge", "score", "self-check", "help"}


def print_usage_error(cmd, error, usage, description):
    """统一的参数错误格式：[命令名] 错误描述 + 用法示例 + 一句话说明。"""
    print(f"[{cmd}] 错误: {error}")
    print(f"用法: weave.py {usage}")
    print(f"说明: {description}")


def print_main_help():
    """不带命令时给**简要帮助**（不是 argparse 的整页 usage）。"""
    print("用法: weave.py <command> <pack> [options]")
    print()
    print("常用命令:")
    print("  disclosure  构建文档树并生成待办清单（TODO.md）")
    print("  visualize   生成可视化文件（TREE.md + TREE.html）")
    print("  prepare     创建工作副本并初始化流程")
    print("  deliver     合并改动回真包并推送")
    print()
    print("运行 'weave.py help' 查看全部命令；'weave.py help <command>' 看单个命令的详细说明")
    print("运行 'weave.py <command> --help' 查看具体命令的选项")
    print("运行 'weave.py --self-test' 验证工具自身")
    print("运行 'weave.py self-check' 检查工具合规性")


def _commands_md_path():
    """`references/commands.md` 的绝对路径（本文件在 `<skill>/scripts/weavelib/`）。"""
    here = os.path.dirname(os.path.abspath(__file__))          # …/scripts/weavelib
    return os.path.join(os.path.dirname(os.path.dirname(here)), "references", "commands.md")


def _commands_md_section(cmd):
    """从 `references/commands.md` 切出 `## <cmd>` 小节正文（到下一个 `## ` 或 EOF）。

    帮助文本的**唯一来源**就是这份文档，不手抄第二份 —— 见 issue #11。找不到返回 None
    （调用方回退到 COMMANDS 里的用法 + 一句话说明）。"""
    try:
        with open(_commands_md_path(), encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    head = f"## {cmd}"
    out, on, fence = [], False, False
    for ln in lines:
        if ln.startswith("```"):
            fence = not fence
        if not fence and ln.startswith("## "):
            if ln.rstrip() == head:
                on = True
                continue
            if on:
                break
        if on:
            out.append(ln)
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out) if out else None


def print_help_list():
    """`weave.py help`（无参）：列出**全部**子命令 + 一句话说明。"""
    print(f"SkillWeave 子命令（共 {len(COMMANDS)} 个）:")
    for cmd in sorted(COMMANDS):
        print(f"  {cmd}  {COMMANDS[cmd][1]}")
    print()
    print("用法: weave.py help <command>   查看该命令的详细说明（用法 / 参数 / 产物 / 示例）")
    print("      weave.py <command> --help 同效")


def print_command_help(cmd):
    """`weave.py help <cmd>` / `weave.py <cmd> --help` 的详细帮助。

    结构：结构化表里的 用法 + 说明（与错误消息同源），再接 `references/commands.md` 里
    `## <cmd>` 的完整小节（用法示例 / 参数 / 产物 / 说明）—— 文档是唯一来源，不会漂移。"""
    usage, description = COMMANDS[cmd]
    print(f"[{cmd}]")
    print(f"用法: weave.py {usage}")
    print(f"说明: {description}")
    section = _commands_md_section(cmd)
    if section:
        print()
        print(section)
    print()
    print("提示: 运行 'weave.py help' 查看全部命令；参数错误会显示这一条用法")


def build_parser():
    """构造 argparse 解析器。拆成函数便于 `--self-test` 直接读 `choices` 与帮助对账（issue #11）。"""
    ap = argparse.ArgumentParser(description="SkillWeave·skill pack 文档树与三级披露",
                                 add_help=False)
    ap.add_argument("-h", "--help", action="store_true", help="显示帮助")
    ap.add_argument("cmd", nargs="?", choices=SUBCOMMANDS)
    ap.add_argument("--prompts", default=None)
    ap.add_argument("--key", default=None)
    ap.add_argument("--judge", nargs="*", default=[])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--apply-group", default=None)
    ap.add_argument("--description", default=None)
    ap.add_argument("--entry-dir", default=None)
    ap.add_argument("--dest", default=None)
    ap.add_argument("--shape", default=None)
    ap.add_argument("--executor", default=None, choices=["opencode", "claude-code", "subagent", "manual"],
                    help="prepare 阶段的执行者（非交互指定；不填则在交互终端询问）")
    ap.add_argument("--state", default=None)
    ap.add_argument("--expect-fixed", nargs="*", default=[])
    ap.add_argument("--splits", default=None)
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--refresh-baseline", action="store_true")
    ap.add_argument("--proposals", nargs="*", default=[])
    ap.add_argument("--revert", default=None)
    ap.add_argument("--main", default="main")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--keep-worktree", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("pack", nargs="?")
    ap.add_argument("--out", default=None)
    ap.add_argument("--self-test", action="store_true")
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if a.self_test:
        from .selftest import self_test
        return self_test()
    if a.help:
        # `weave.py --help` 给总览；`weave.py <command> --help` 给该命令的详细帮助。
        if a.cmd:
            print_command_help(a.cmd)
        else:
            print_main_help()
        return 0
    if a.cmd == "help":
        # `weave.py help` 列出全部子命令；`weave.py help <command>` 给详细说明（issue #11）。
        target = a.pack
        if not target:
            print_help_list()
            return 0
        if target not in COMMANDS:
            print(f"[help] 未知命令: {target}")
            print(f"可用命令: {', '.join(sorted(COMMANDS))}")
            print("运行 'weave.py help' 查看全部命令")
            return 2
        print_command_help(target)
        return 0
    if not a.cmd:
        print_main_help()
        return 2
    # 需要 `<pack>` 的子命令：缺了就用统一格式报错（而不是 argparse 的整页 usage）。
    if a.cmd not in _PACK_OPTIONAL and not a.pack:
        print_usage_error(a.cmd, "缺少 <pack> 参数", *COMMANDS[a.cmd])
        return 2

    if a.cmd == "self-check":
        from .analysis import cmd_self_check
        # 仓库根：从 `weavelib/` 向上 4 层 —— scripts/ → skillweave/ → skills/ → 仓库根。
        here = os.path.dirname(os.path.abspath(__file__))       # …/skills/skillweave/scripts/weavelib
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(here))))
        return cmd_self_check(root)

    if a.cmd == "layers":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(root, ".skillweave")
        return cmd_layers(root, out)
    if a.cmd == "checks":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(root, ".skillweave")
        return cmd_checks(root, out)
    if a.cmd == "audit":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(root, ".skillweave")
        return cmd_audit(root, out)
    if a.cmd == "propose":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(root, ".skillweave")
        return cmd_propose(root, out, apply_changes=a.apply, group_map=a.apply_group)
    if a.cmd == "visualize":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or root          # 默认落回 pack 自己：可视化是给仓库看的产物
        return cmd_visualize(root, out)
    if a.cmd == "disclosure":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(root, ".skillweave")
        return cmd_disclosure(root, out)
    if a.cmd == "dispatch":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or root
        return cmd_dispatch(root, out, batch_size=a.batch_size, refresh_baseline=a.refresh_baseline)
    if a.cmd == "apply":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(root, "dispatch")
        if not a.revert and not a.proposals:
            print_usage_error("apply", "需要 --proposals <提案 json…> 或 --revert <条目 id>",
                              *COMMANDS["apply"])
            return 2
        if a.revert and a.proposals:
            print_usage_error("apply", "--proposals 与 --revert 不能同时用（二选一）",
                              *COMMANDS["apply"])
            return 2
        return cmd_apply(root, a.proposals, a.state, out, revert_id=a.revert)
    if a.cmd == "verify":
        root = os.path.abspath(a.pack.rstrip("/"))
        if not a.state:
            print_usage_error("verify", "缺少 --state 参数", *COMMANDS["verify"])
            return 2
        if not a.expect_fixed:
            print_usage_error("verify", "缺少 --expect-fixed 参数", *COMMANDS["verify"])
            return 2
        # RUN.md / PARKED.md 落在 state 旁边（dispatch/），不落临时目录 —— 无人值守跑完要能直接读到
        out = a.out or os.path.dirname(os.path.abspath(a.state))
        return cmd_verify(root, a.state, a.expect_fixed, a.splits, out)
    if a.cmd == "deliver":
        # F 阶段交付：默认合回真包 main + push + 清 worktree/分支（不是等人点头的动作）
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(root, ".skillweave")
        return cmd_deliver(root, out, main_branch=a.main, push=not a.no_push,
                           keep_worktree=a.keep_worktree, dry=a.dry_run)
    if a.cmd == "prepare":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(root, ".skillweave")
        return cmd_prepare(root, out, dest=a.dest, shape=a.shape, description=a.description,
                           executor=a.executor)
    if a.cmd == "collapse":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(root, ".skillweave")
        if a.apply and not a.description:
            print_usage_error("collapse", "--apply 需要 --description",
                              *COMMANDS["collapse"])
            return 2
        return cmd_collapse(root, out, apply_changes=a.apply, description=a.description,
                            entry_dir=a.entry_dir)
    if a.cmd == "judge":
        root = os.path.abspath((a.pack or ".").rstrip("/"))
        out = a.out or os.path.join(root, ".skillweave")
        if not a.prompts:
            print_usage_error("judge", "缺少 --prompts 参数", *COMMANDS["judge"])
            return 2
        return cmd_judge(root, a.prompts, out)
    if a.cmd == "score":
        root = os.path.abspath((a.pack or ".").rstrip("/"))
        out = a.out or os.path.join(root, ".skillweave")
        if not a.key:
            print_usage_error("score", "缺少 --key 参数", *COMMANDS["score"])
            return 2
        if not a.judge:
            print_usage_error("score", "缺少 --judge 参数", *COMMANDS["score"])
            return 2
        return cmd_score(a.key, a.judge, out)
    root = os.path.abspath(a.pack.rstrip("/"))
    if not os.path.isdir(root):
        print(f"[tree] FAIL 目录不存在: {root}")
        return 1
    out = a.out or os.path.join(root, ".skillweave")
    os.makedirs(out, exist_ok=True)

    pack = Pack.load(root)
    if pack is None:
        print("[tree] FAIL 这个目录里没有任何 skill（找不到 SKILL.md）")
        return 1
    skills, skipped, tracked, tree = pack.skills, pack.skipped, pack.tracked, pack.tree
    add_mentions(root, skills)
    for s in skills:
        add_headings(s)
    strip_private(tree)
    tree["pack"] = {"name": os.path.basename(root), "skills": len(skills),
                    "bytes": sum(s["bytes"] for s in skills),
                    "est_tokens": sum(s["est_tokens"] for s in skills),
                    "member_mode": "git-tracked" if tracked is not None else "all",
                    "untracked_skill_dirs": skipped}
    tree["fanout"] = fanout_report(tree)

    jpath = os.path.join(out, "tree.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2, sort_keys=True)
    mpath = os.path.join(out, "TREE.md")
    with open(mpath, "w", encoding="utf-8") as f:
        f.write(render_md(root, tree, skills))

    orph = [(s["id"], o) for s in skills for o in s["orphans"]]
    broke = [(s["id"], b) for s in skills for b in s["broken"]]
    print(f"[tree] pack={os.path.basename(root)}")
    print(f"[tree] 成员口径={'git 跟踪' if tracked is not None else '非 git 目录：全部算成员'}"
          f"（未跟踪且是 skill 形的目录 {len(skipped)} 个：{', '.join(skipped[:3]) or '无'}"
          f"{'…' if len(skipped) > 3 else ''}）")
    print(f"[tree] skills={len(skills)} nodes={count(tree)} bytes={tree['pack']['bytes']} est_tokens={tree['pack']['est_tokens']}")
    print(f"[tree] 孤儿文件={len(orph)} 悬空引用={len(broke)}")
    print(f"[tree] 层（fanout>1）= {sum(1 for r in tree['fanout'] if r['fanout'] > 1)} 个；"
          f"最大 fanout={max((r['fanout'] for r in tree['fanout']), default=0)}")
    print(f"[tree] 出: {jpath}")
    print(f"[tree] 出: {mpath}")
    return 0
