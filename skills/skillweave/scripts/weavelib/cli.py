"""CLI 入口与子命令派发。

从 weave.py 拆出，逻辑未改。"""
import argparse, json, os, tempfile
from .analysis import cmd_audit, cmd_checks, cmd_judge, cmd_layers, cmd_score
from .common import count, strip_private
from .deliver import cmd_deliver
from .disclosure import cmd_disclosure, cmd_dispatch, cmd_verify
from .graph import add_headings, fanout_report
from .model import add_mentions
from .pack import Pack
from .render import cmd_visualize, render_md
from .transform import cmd_apply, cmd_collapse, cmd_prepare, cmd_propose




def main(argv=None):
    ap = argparse.ArgumentParser(description="SkillWeave·skill pack 文档树与三级披露")
    ap.add_argument("cmd", nargs="?",
                    choices=["tree", "layers", "checks", "audit", "propose", "judge", "score", "visualize",
                             "collapse", "prepare", "disclosure", "dispatch", "verify", "apply", "deliver"])
    ap.add_argument("--prompts", default=None)
    ap.add_argument("--key", default=None)
    ap.add_argument("--judge", nargs="*", default=[])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--apply-group", default=None)
    ap.add_argument("--description", default=None)
    ap.add_argument("--entry-dir", default=None)
    ap.add_argument("--dest", default=None)
    ap.add_argument("--shape", default=None)
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
    a = ap.parse_args(argv)
    if a.self_test:
        from .selftest import self_test
        return self_test()
    if not a.cmd or (a.cmd != "score" and not a.pack):
        ap.print_usage()
        return 2

    if a.cmd == "layers":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(tempfile.gettempdir(), "skillweave-" + os.path.basename(root))
        return cmd_layers(root, out)
    if a.cmd == "checks":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(tempfile.gettempdir(), "skillweave-" + os.path.basename(root))
        return cmd_checks(root, out)
    if a.cmd == "audit":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(tempfile.gettempdir(), "skillweave-" + os.path.basename(root))
        return cmd_audit(root, out)
    if a.cmd == "propose":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(tempfile.gettempdir(), "skillweave-" + os.path.basename(root))
        return cmd_propose(root, out, apply_changes=a.apply, group_map=a.apply_group)
    if a.cmd == "visualize":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or root          # 默认落回 pack 自己：可视化是给仓库看的产物
        return cmd_visualize(root, out)
    if a.cmd == "disclosure":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(tempfile.gettempdir(), "skillweave-" + os.path.basename(root))
        return cmd_disclosure(root, out)
    if a.cmd == "dispatch":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or root
        return cmd_dispatch(root, out, batch_size=a.batch_size, refresh_baseline=a.refresh_baseline)
    if a.cmd == "apply":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(root, "dispatch")
        if not a.revert and not a.proposals:
            print("[apply] 需要 --proposals <提案 json…>，或用 --revert <条目 id> 回退一条")
            return 2
        return cmd_apply(root, a.proposals, a.state, out, revert_id=a.revert)
    if a.cmd == "verify":
        root = os.path.abspath(a.pack.rstrip("/"))
        if not a.state:
            print("[verify] 需要 --state <dispatch/state.json>（计数在那份文件里，不在谁记忆里）")
            return 2
        # RUN.md / PARKED.md 落在 state 旁边（dispatch/），不落临时目录 —— 无人值守跑完要能直接读到
        out = a.out or os.path.dirname(os.path.abspath(a.state))
        return cmd_verify(root, a.state, a.expect_fixed, a.splits, out)
    if a.cmd == "deliver":
        # F 阶段交付：默认合回真包 main + push + 清 worktree/分支（不是等人点头的动作）
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(tempfile.gettempdir(), "skillweave-" + os.path.basename(root))
        return cmd_deliver(root, out, main_branch=a.main, push=not a.no_push,
                           keep_worktree=a.keep_worktree, dry=a.dry_run)
    if a.cmd == "prepare":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(tempfile.gettempdir(), "skillweave-" + os.path.basename(root))
        return cmd_prepare(root, out, dest=a.dest, shape=a.shape, description=a.description)
    if a.cmd == "collapse":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(tempfile.gettempdir(), "skillweave-" + os.path.basename(root))
        return cmd_collapse(root, out, apply_changes=a.apply, description=a.description,
                            entry_dir=a.entry_dir)
    if a.cmd == "judge":
        root = os.path.abspath((a.pack or ".").rstrip("/"))
        out = a.out or os.path.join(tempfile.gettempdir(), "skillweave-" + os.path.basename(root))
        if not a.prompts:
            print("[judge] 需要 --prompts <题面 json>（题面必须冻结，不许现编）")
            return 2
        return cmd_judge(root, a.prompts, out)
    if a.cmd == "score":
        out = a.out or tempfile.gettempdir()
        if not a.key or not a.judge:
            print("[score] 需要 --key <金标 json> --judge <判官输出文件…>")
            return 2
        return cmd_score(a.key, a.judge, out)
    root = os.path.abspath(a.pack.rstrip("/"))
    if not os.path.isdir(root):
        print(f"[tree] FAIL 目录不存在: {root}")
        return 1
    out = a.out or os.path.join(tempfile.gettempdir(), "skillweave-" + os.path.basename(root))
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
