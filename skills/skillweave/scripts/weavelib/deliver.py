"""F 阶段交付：worktree → 合回真包 main → push → 回读。

从 weave.py 拆出，逻辑未改。"""
import os
from .graph import _in_git_repo
from .model import git
from .render import _rev, cmd_visualize




def _worktree_copy(pack, dest, log, branch=None):
    """输入原本就在 git 仓库里 → **开 worktree**，不拷整份（用户 2026-10-12 定的规则）。
    好处：改动能按包仓库的规矩合回；坏处：worktree 共享同一个 .git，所以 push 一律回主 clone 做。"""
    root = _in_git_repo(pack)
    rel = os.path.relpath(os.path.realpath(pack), root)
    branch = branch or ("skillweave/" + os.path.basename(os.path.realpath(pack)).lower())
    head = (git(root, "rev-parse", "HEAD") or type("x", (), {"stdout": ""})()).stdout.strip()
    r = git(root, "worktree", "add", "-b", branch, dest, head)
    if r is None or r.returncode != 0:
        return None, (r.stderr.strip() if r is not None else "git worktree add 失败")
    log.append(f"输入在 git 仓库 `{root}` 里 → 开 worktree `{dest}`（分支 `{branch}`，基于 `{head[:9]}`）")
    log.append("worktree 与主 clone 共享 .git：**push 与合并回主 clone 做**，别在 worktree 里切 main")
    return os.path.join(dest, rel), branch




def _ensure_git_copy(dest, log):
    """副本必须由 git 管起来 —— 输入目录有没有 git 都不影响这一步。
    · 副本自带 `.git`（拷的是个仓库）：**先摘掉所有 remote**（误推当场失败），再把当前状态提交成起点；
    · 副本没有 git：`git init` + 一行 `.gitignore` + 初始 commit。"""
    fresh = False
    if git(dest, "rev-parse", "--git-dir") is not None and git(dest, "rev-parse", "--git-dir").returncode == 0:
        remotes = [r.strip() for r in (git(dest, "remote") or type("x", (), {"stdout": ""})()).stdout.split() if r.strip()]
        for r in remotes:
            git(dest, "remote", "remove", r)
        log.append(f"副本自带 git：已摘掉 {len(remotes)} 个 remote（{', '.join(remotes) or '无'}），误推会当场失败")
    else:
        git(dest, "init", "-q")
        with open(os.path.join(dest, ".gitignore"), "w", encoding="utf-8") as f:
            f.write(".DS_Store\n")
        log.append("副本原本没有 git：已 `git init` + 一行 .gitignore（挡 .DS_Store）")
        fresh = True
    st = git(dest, "status", "--porcelain")
    dirty = len((st.stdout or "").split("\n")) - 1 if st is not None and st.returncode == 0 else 0
    git(dest, "add", "-A")
    if dirty:
        git(dest, "-c", "user.name=planweave", "-c", "user.email=planweave@local",
            "commit", "-q", "-m", "planweave: 工作副本起点（原样拷贝，未改内容）")
    rev = _rev(dest)
    log.append(f"起点 commit `{rev}`；" + ("全部文件已作为起点提交" if fresh else
                ("工作区干净" if dirty == 0 else f"原样带 {dirty} 项未提交改动，已一并记为起点")))
    return rev





def cmd_deliver(work, out=None, main_branch="main", push=True, keep_worktree=False, dry=False):
    """F 阶段交付的机械部分：把工作副本的分支**合回真包的 main**，推远端，清 worktree 与分支。

    **这是流程走完的最后一步的默认动作**，不是等人点头的动作：`prepare` 开那条分支，本来就是给它合回去的。
    要停在副本上不交付，得用 `--keep-worktree` / `--no-push` 显式说出来 —— 默认不是「不改真包」。

    四道闸都不猜，任一不过就停（不自动解冲突、不 --force）：
    ① 它是 `prepare` 开的工作副本（worktree）才有 main 可合；主 clone 本身没有可合的分支；
    ② 主 clone 的工作区干净、且 checkout 在 `--main`（默认 main）上 —— 别人未提交的改动不许卷进 merge；
    ③ 副本工作区干净（未提交的改动先 commit，或明确丢掉）；
    ④ 合回只走 `--ff-only`；不 ff 就先在副本里 `rebase` 到 main，冲突即 abort 并停在副本里。
    """
    work = os.path.realpath(os.path.abspath(work.rstrip("/")))
    if not os.path.isdir(work):
        print(f"[deliver] FAIL 工作副本不存在: {work}")
        return 1
    common = git(work, "rev-parse", "--git-common-dir")
    if common is None or common.returncode != 0:
        print(f"[deliver] FAIL {work} 由 git 管着吗？不是 git 就没有 main 可合（非 git 输入的交付是手动拷回）")
        return 1
    gdir = common.stdout.strip()
    gdir = os.path.realpath(gdir if os.path.isabs(gdir) else os.path.join(work, gdir))
    if gdir == os.path.realpath(os.path.join(work, ".git")):
        print(f"[deliver] FAIL {work} 就是主 clone 本身，没有可合回的分支（工作副本由 prepare 生成）")
        return 1
    main_clone = os.path.dirname(gdir)
    br = git(work, "rev-parse", "--abbrev-ref", "HEAD")
    branch = (br.stdout or "").strip() if br is not None and br.returncode == 0 else ""
    if not branch or branch == "HEAD":
        print("[deliver] FAIL 副本不在任何分支上（detached HEAD），先 git switch 一条分支")
        return 1
    cur = git(main_clone, "rev-parse", "--abbrev-ref", "HEAD")
    cur_branch = (cur.stdout or "").strip() if cur is not None and cur.returncode == 0 else "?"
    if cur_branch != main_branch:
        print(f"[deliver] FAIL 主 clone `{main_clone}` 现在 checkout 在 `{cur_branch}`，不是 `{main_branch}`"
              f"（别人改到一半的分支别往上合）；切回 {main_branch} 或 --main <名字> 指定")
        return 1
    for tag, path in (("副本", work), ("主 clone", main_clone)):
        st = git(path, "status", "--porcelain")
        if st is not None and st.returncode == 0 and (st.stdout or "").strip():
            n = len([x for x in st.stdout.split("\n") if x.strip()])
            print(f"[deliver] FAIL {tag} `{path}` 有 {n} 项未提交改动：先 commit 或明确丢掉，交付不猜")
            return 1
    remotes = [r for r in ((git(main_clone, "remote") or type("x", (), {"stdout": ""})()).stdout or "").split() if r]

    def _remote_head(r):
        """远端 main 的 SHA（回读用）；读不到返回空串。"""
        ls = git(main_clone, "ls-remote", r, f"refs/heads/{main_branch}")
        if ls is None or ls.returncode != 0:
            return ""
        return ((ls.stdout or "").split() or [""])[0]

    def _pushed(r, want):
        p = git(main_clone, "push", r, main_branch)
        ok = p is not None and p.returncode == 0
        got = _remote_head(r)
        print(f"[deliver] {'✅' if ok and got == want else '⛔'} push {r} {main_branch}"
              f"{'' if ok else '：' + ((p.stderr.strip().splitlines() or [''])[0] if p is not None else 'git 不可用')}"
              f"{' · 回读一致' if got == want else ' · 回读不一致（' + (got[:9] or '远端读不到') + '）'}")
        return ok and got == want
    before = (_rev(main_clone) or "?")
    head = (git(work, "rev-parse", "HEAD") or type("x", (), {"stdout": ""})()).stdout.strip()
    print(f"[deliver] 副本 `{work}`（分支 `{branch}` @ {head[:9]}）→ 主 clone `{main_clone}`（`{main_branch}` @ {before[:9]}）")
    if dry:
        print(f"[deliver] --dry-run：合回 {main_branch} · 推 {('、'.join(remotes) or '无 remote')} · "
              f"{'保留 worktree' if keep_worktree else '删 worktree + 删分支'}")
        return 0
    ff = git(main_clone, "merge", "--ff-only", branch)
    if ff is None or ff.returncode != 0:
        why = (ff.stderr.strip() if ff is not None else "git 不可用").split("\n")[0]
        print(f"[deliver] 不能 ff（{why}）→ 先在副本里 rebase 到 {main_branch}（真包还没动）")
        rb = git(work, "rebase", main_branch)
        if rb is None or rb.returncode != 0:
            git(work, "rebase", "--abort")
            print("[deliver] FAIL rebase 冲突，已 abort；副本原样留着，真包未动（解完再跑一次）")
            return 1
        ff = git(main_clone, "merge", "--ff-only", branch)
        if ff is None or ff.returncode != 0:
            print(f"[deliver] FAIL 合回失败：{(ff.stderr.strip().splitlines() or [''])[0] if ff is not None else 'git 不可用'}")
            return 1
    after = _rev(main_clone)
    full = (git(main_clone, "rev-parse", "HEAD") or type("x", (), {"stdout": ""})()).stdout.strip()
    print(f"[deliver] ✅ 合回 {main_branch}：{before[:9]} → {after[:9]}（真包 `{main_clone}` 现在是 {after[:9]}）")
    rc = 0
    if push:
        if not remotes:
            print("[deliver] 包上没有 remote，跳过 push")
        for r in remotes:
            if not _pushed(r, full):
                rc = 1
    else:
        print("[deliver] --no-push：只合回本地真包，没推远端")
    # 交付时重跑 visualize（F 的规定）：只在包里已经带 TREE.md 的 pack 上做，新产物不硬塞
    if os.path.isfile(os.path.join(main_clone, "TREE.md")):
        cmd_visualize(main_clone, main_clone)
        st = git(main_clone, "status", "--porcelain")
        if st is not None and st.returncode == 0 and (st.stdout or "").strip():
            git(main_clone, "-c", "user.name=skillweave", "-c", "user.email=skillweave@local",
                "add", "TREE.md", "TREE.html")
            git(main_clone, "-c", "user.name=skillweave", "-c", "user.email=skillweave@local",
                "commit", "-q", "-m", "chore(skillweave): 交付时重跑 visualize（TREE.md + TREE.html）")
            after = _rev(main_clone)
            full = (git(main_clone, "rev-parse", "HEAD") or type("x", (), {"stdout": ""})()).stdout.strip()
            print(f"[deliver] visualize 刷新后追加一条提交 {after[:9]}")
            if push:
                for r in remotes:
                    if not _pushed(r, full):
                        print(f"[deliver] ⛔ 上面这条 push 是 visualize 追加的提交 {after[:9]} 没上去")
                        rc = 1
    if keep_worktree:
        print(f"[deliver] --keep-worktree：副本 `{work}` 与分支 `{branch}` 都留着")
    else:
        rm = git(main_clone, "worktree", "remove", work)
        if rm is None or rm.returncode != 0:
            print(f"[deliver] ⛔ worktree 没删掉：{(rm.stderr.strip().splitlines() or [''])[0] if rm is not None else 'git 不可用'}"
                  f"（手动 git worktree remove {work}）")
            rc = 1
        else:
            bd = git(main_clone, "branch", "-d", branch)
            print(f"[deliver] ✅ 删 worktree + " + (f"删分支 `{branch}`" if bd is not None and bd.returncode == 0
                                                   else f"⛔ 分支 `{branch}` 没删掉（git branch -d 手动）"))
    if out:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "DELIVER.md"), "w", encoding="utf-8") as f:
            f.write(f"# 交付 · {os.path.basename(main_clone)}\n\n"
                    f"- 真包：`{main_clone}` · 分支 `{main_branch}` · {before[:9]} → {after[:9]}\n"
                    f"- 工作副本：`{work}` · 分支 `{branch}`（{'保留' if keep_worktree else '已删'}）\n"
                    f"- remote：{', '.join(remotes) or '无'}{'（已 push 并回读）' if push else '（--no-push，未推）'}\n")
        print(f"[deliver] 出: {os.path.join(out, 'DELIVER.md')}")
    return rc
