"""pack 量测：扫树、逐 skill 分析 —— 树的形状与成员。

从 weave.py 拆出，逻辑未改。"""
import os, re, subprocess
from .common import body_counts, content_digest, est_tokens, extract_declared_refs, fence_lines, first_sentence, headings, kind_of_file, read_text, sha256_file
from .frontmatter import meta_list, parse_frontmatter


# `.skillweave` = **工具自己的目录**（包主的免检表 + 该包的历史轮次档案 + 量出来的数字）：
# **不是 pack 成员**。一处修齐 —— `graph._pack_files()` 早就排除了它，walker 没排除，于是
# 「工具自己写下的产物」会变成下一次运行量出来的发现（`DISCLOSURE.md` 落进包里就成了一份
# 「到不了根」的文档），同一个包跑两遍给出两个数。口径见 `docs/contract.md` §9。
SKIP_DIRS = {".git", ".github", "node_modules", "__pycache__", ".venv", "venv", ".skillweave"}


SKIP_FILES = {".DS_Store"}





def analyze_skill(root, path, rel):
    """一个 skill 目录 → 契约里的 skill 节点字段。要换成 `asa --json` 就换这一个函数。
    `root` = pack 根：引用解析的第二个基准（契约 §3：先按 skill 目录、再按 pack 根）。
    旧实现写死 `path/../..`，pack 多一层类目就错位 —— 实测会把本来能解析的引用误报成悬空。"""
    sk_path = os.path.join(path, "SKILL.md")
    text = read_text(sk_path)
    meta, body, body_line = parse_frontmatter(text)
    node = {
        "id": rel, "kind": "skill",
        "name": meta.get("name") or os.path.basename(path.rstrip("/")),
        "bytes": len(text.encode("utf-8")), "est_tokens": est_tokens(text),
        "body_lines": len(body.split("\n")),
        "summary": None, "summary_source": None,
        "refs": [], "mentions": [], "files": [], "headings": [], "children": [],
    }
    desc = (meta.get("description") or "").strip()
    node["description"] = desc
    node["description_chars"] = len(desc)
    if desc:
        node["summary"] = desc.split("\n")[0][:200]
        node["summary_source"] = f"{rel}SKILL.md frontmatter.description"
    else:
        sent, line = first_sentence(body, body_line)
        if sent:
            node["summary"] = sent
            node["summary_source"] = f"{rel}SKILL.md:{line} 首段首句"

    # 元数据里的**非字面**信号（issue #3）：跨语言/同义改写的「同一件事」字面分贴近 0，
    # 但 metadata.hermes.related_skills / tags 常逐字相同。解析器不认嵌套映射，故用 meta_list。
    node["tags"] = meta_list(text, "tags")
    node["related_skills"] = meta_list(text, "related_skills")

    declared = extract_declared_refs(body, rel)
    fenced = fence_lines(body)
    resolved, broken, external = set(), set(), set()
    refs = []
    for target, line in declared:
        t = target.lstrip("./")
        # 对拍结论（docs/compare-tools.md §5）：围栏里的路径、以及没有目录部分的裸文件名，
        # 都是**示例**，不是本 skill 的引用 —— 旧版把它们算成 broken，实测 6 条里 4 条是误报。
        bare = "/" not in t and t != "SKILL.md"
        if bare or line in fenced:
            refs.append({"target": t, "kind": "example", "line": line})
            continue
        local = os.path.normpath(os.path.join(path, t))
        at_pack = os.path.normpath(os.path.join(root, t))
        if os.path.exists(local):
            kind, resolved = "resolved", resolved | {t}
        elif os.path.exists(at_pack):
            kind, resolved = "resolved", resolved | {t}
        elif t.startswith("../") or not t.startswith(("references/", "scripts/", "assets/", "templates/")):
            kind, external = "external", external | {t}
        else:
            kind = "broken"
            broken.add(t)
        refs.append({"target": t, "kind": kind, "line": line})
    node["refs"] = refs
    # 目录级点名：正文点名了 `templates/README.md` ⇒ `templates/` 整目录算被点名
    named_dirs = set()
    for r in refs:
        d = os.path.dirname(r["target"])
        while d:
            named_dirs.add(d.rstrip("/") + "/")
            d = os.path.dirname(d)
    node["named_dirs"] = sorted(named_dirs)

    # 文件清单 + 孤儿（skill 目录内除 SKILL.md 外，没有任何祖先点名的文件）
    # 嵌套 skill（单入口形状下岛内 skill 住在 `<入口>/references/<岛>/<skill>/`）**不算本 skill 的文件**：
    # 它们各自会被 walk_dir 当成独立 skill 分析，两边都算就会把同一份文件重复计入两个 skill。
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS
                             and not os.path.isfile(os.path.join(dirpath, d, "SKILL.md")))
        for fn in sorted(filenames):
            if fn in SKIP_FILES:
                continue
            fp = os.path.join(dirpath, fn)
            frel = os.path.relpath(fp, path).replace(os.sep, "/")
            try:
                size = os.path.getsize(fp)
            except OSError:
                size = 0
            fkind = kind_of_file(frel)
            named = (frel in resolved
                     or any(frel.endswith(r.lstrip("./")) for r in resolved)
                     or any(frel.startswith(d) for d in named_dirs))     # 目录级点名
            node["files"].append({"path": frel, "kind": fkind, "bytes": size,
                                  "sha256": sha256_file(fp),
                                  "orphan": (fkind != "instructions" and not named)})
    node["orphans"] = [f["path"] for f in node["files"] if f["orphan"]]
    node["broken"] = sorted(broken)
    hs = headings(body, body_line)
    node["headings"] = hs
    node["counts"] = body_counts(body, len(hs))            # 内化：该拆的可量信号
    node["digest"] = content_digest(meta, body)            # 内化：内容指纹（改 version 不变）
    node["license"] = next((f["path"] for f in node["files"] if f["kind"] == "license"), None)
    node["readme"] = next((f["path"] for f in node["files"] if f["kind"] == "readme"), None)
    by_kind = {}
    for f in node["files"]:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + f["bytes"]
    node["size_by_kind"] = by_kind                         # 内化：指令重量 vs 资源重量
    return node





def git(root, *args):
    """**唯一的 subprocess 出口**：所有 git 调用都从这里走。两个好处：
    ① 安全扫描按调用点计数，一处胜过五处；② 统一 60s 超时 —— git 挂住不会把工具一起挂住。
    没法用 git 时返回 None，调用方一律按「降级」处理（不假定环境有 git）。"""
    try:
        return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None




def tracked_set(pack):
    """git 跟踪清单（pack 在 git 仓库里时）。**不假定一定有 git**：不是仓库就返回 None = 全部算成员。"""
    p = git(pack, "ls-files", "-z")
    if p is None or p.returncode != 0:
        return None
    return {x for x in p.stdout.split("\0") if x}




def walk_dir(root, path, rel, tracked, skipped, skills):
    """递归：含 SKILL.md 的目录 = skill；含 skill 后代的目录 = category；其余目录 = asset（折叠成一个节点）。
    `tracked` 非 None 时只算 git 成员（未跟踪的 skill 形目录记进 `skipped`，不混进度量）。

    **含 SKILL.md 的目录仍要下钻**：collapse 是本工具自己的功能，它把成员搬到了
    `<入口>/references/<岛名>/<skill>/` —— 那些 `SKILL.md` 全在入口目录的子树里。
    旧实现一遇 `SKILL.md` 就 `return`，于是岛内 skill 从来没被访问过：`skills` 只有 1 项、
    `stats["skills"]=1`、TREE.md 的 L2 表是空的、TREE.html 只画 1 个节点框（issue #1）。
    下钻到的嵌套 skill 挂成入口节点的**子节点**（`references/` 这条路必须是达得到的）。"""
    node = None
    if os.path.isfile(os.path.join(path, "SKILL.md")):
        node = analyze_skill(root, path, rel)
        node["parent"] = os.path.dirname(rel.rstrip("/"))
        node["parent"] = (node["parent"] + "/") if node["parent"] else ""
        node["tracked"] = True
        skills.append(node)                     # 先登记父再下钻：`skills` 保持前序（父在前）

    children = _walk_children(root, path, rel, tracked, skipped, skills)
    if node is not None:
        node["children"] = node["children"] + children
        return node
    if not children:
        return None
    has_skill = any(c["kind"] == "skill" or c.get("has_skill") for c in children)
    kind = "pack" if rel == "" else ("category" if has_skill else "asset")
    if kind == "asset":                       # 非技能目录折叠成一个节点：不进 fanout、不逐文件列
        total = 0
        for dp, dns, fns in os.walk(path):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            for f in fns:
                if f in SKIP_FILES:
                    continue
                r = os.path.relpath(os.path.join(dp, f), path).replace(os.sep, "/")
                if _is_member(tracked, rel + r):
                    total += os.path.getsize(os.path.join(dp, f))
        children = []
        bsum = total
    else:
        bsum = sum(c["bytes"] for c in children)
    return {"id": rel, "kind": kind, "parent":
            ((os.path.dirname(rel.rstrip("/")) + "/") if os.path.dirname(rel.rstrip("/")) else ""),
            "bytes": bsum, "est_tokens": sum(c.get("est_tokens", 0) for c in children),
            "has_skill": has_skill, "tracked": True,
            "summary": None, "summary_source": None,
            "refs": [], "mentions": [], "children": children}




def _is_member(tracked, rel):
    """`tracked` 为 None（非 git 目录）= 全部算成员；否则要在 git 跟踪清单里。"""
    return tracked is None or rel in tracked




def _subtree_tracked(tracked, d):
    if tracked is None:
        return True
    d = d.rstrip("/")
    pre = d + "/"
    return any(t == d or t.startswith(pre) for t in tracked)




def _walk_children(root, path, rel, tracked, skipped, skills):
    """扫 `path` 的直接子目录与文件 → children 列表。子目录递归回 `walk_dir`（可能返回 skill 节点）。"""
    children = []
    for n in sorted(os.listdir(path)):
        if n in SKIP_DIRS or n in SKIP_FILES:
            continue
        crel = rel + n
        fp = os.path.join(path, n)
        if os.path.isdir(fp):
            if not _subtree_tracked(tracked, crel):
                if any("SKILL.md" in fns for _, _, fns in os.walk(fp)):
                    skipped.append(crel + "/")
                continue
            sub = walk_dir(root, fp, crel + "/", tracked, skipped, skills)
            if sub is not None:
                children.append(sub)
        elif _is_member(tracked, crel):
            size = os.path.getsize(fp)
            children.append({"id": crel, "kind": kind_of_file(crel), "parent": rel,
                             "bytes": size, "tracked": True,
                             "est_tokens": est_tokens(read_text(fp)) if size < 2_000_000 else 0,
                             "summary": None, "summary_source": None,
                             "refs": [], "mentions": [], "children": []})
    return children




def is_nested_skill(root, rel):
    """这个 skill 是否住在**另一个 skill 的目录之下**（单入口形状下岛内 skill 就住在
    `<入口>/references/<岛>/<skill>/`）。契约 §0：单入口 = 1 个根，岛内 skill 不是根。"""
    d = os.path.dirname(rel.rstrip("/"))
    while d:
        if os.path.isfile(os.path.join(root, d, "SKILL.md")):
            return True
        d = os.path.dirname(d)
    return False




def top_level_skills(root, skills):
    """只算不在别的 skill 目录之下的 skill —— `collapse` 的输入单位。
    嵌套 skill 已经在某个入口的 `references/` 里，属于「已经收过」，不再是入口候选。"""
    return [s for s in skills if not is_nested_skill(root, s["id"])]




def untracked_skill_files(pack):
    """工作区里**未被 git 跟踪**的 `SKILL.md`（相对 pack 根的路径，排序）。不是 git 仓库 → 空列表。

    为什么值得报错：collapse 刚改完工作区、还没 commit 时，索引里还是旧路径，新入口的 `SKILL.md`
    未跟踪 —— `walk_dir` 会把它当 untracked 跳过，`skills` 变空，而命令退出码 0、产物是一棵空树
    （issue #1 根因 2）。这种「一次不落到的空跑」该报错，不该静默交付。"""
    p = git(pack, "ls-files", "-o", "--exclude-standard", "-z")
    if p is None or p.returncode != 0:
        return []
    return sorted(x for x in p.stdout.split("\0") if x.endswith("SKILL.md"))




def add_mentions(root, skills):
    """mentions 边：正文里点到同 pack 的其它技能名（路由信号）。"""
    names = {s["name"]: s["id"] for s in skills}
    for s in skills:
        body = read_text(os.path.join(root, s["id"], "SKILL.md"))
        s["mentions"] = sorted({n for n in names
                                if n != s["name"] and re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", body)})





def skills_root(tree):
    """找「装技能的那一层」：从 pack 根往下，只要**唯一**的选择项还是个类目就继续下钻；
    遇到两个以上选择项（或唯一选择项已经是 skill）就停 —— 这一层才是 Agent 第一次选择看到的菜单。
    分组后 `skills/` 下面全是类目，入口层仍是 `skills/`（旧实现只认「直接含 skill 的目录」，会错抓成第一个类目）。

    边界：pack 根自己就含 `SKILL.md`（单入口形状的入口直接摆在根）时，tree 的 kind 是 `skill` 不是
    `pack` —— 这时它自己就是入口层，直接返回它（旧写法会 `children[0]` 一路下钻到 IndexError）。"""
    node = tree
    while node["kind"] != "pack":
        if node["kind"] == "skill":
            return node
        if not node["children"]:
            return node
        node = node["children"][0]
    while True:
        choices = [c for c in node["children"] if c["kind"] in ("skill", "category")]
        if len(choices) != 1 or choices[0]["kind"] != "category":
            return node
        node = choices[0]
