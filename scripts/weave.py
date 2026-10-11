#!/usr/bin/env python3
"""SkillWeave · 把一个 skill pack 解析成文档树（契约见 docs/contract.md）。

用法:
  python3 scripts/weave.py tree <pack 目录> [--out DIR]     # 产 tree.json + TREE.md
  python3 scripts/weave.py --self-test                      # 自带 fixture 自检

不依赖任何 agent 框架、不依赖第三方包（纯 stdlib）。字段名与 kind 分类沿用
agent-skill-analysis 的口径（见 docs/similar-work.md A1），便于将来把 per-skill 段
换成 `asa --json`；替换点是 analyze_skill() 一个函数。

ponytail: 只做「树 + 每层 fanout」，不做语义索引/向量；规模上按 pack 目录线性扫一遍，
          pack 数到几千个 skill 时仍是秒级。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

FENCE = ("```", "~~~")
PATH_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:md|markdown|py|sh|bash|js|ts|json|ya?ml|txt|csv|tsv|toml|ini|cfg|png|jpe?g|svg|gif|html|pdf)\b")
SKIP_DIRS = {".git", ".github", "node_modules", "__pycache__", ".venv", "venv"}
SKIP_FILES = {".DS_Store"}
SCRIPT_EXT = {".py", ".sh", ".bash", ".js", ".ts", ".rb", ".pl"}
ASSET_EXT = {".png", ".jpg", ".jpeg", ".svg", ".gif", ".pdf", ".zip", ".ico", ".woff", ".ttf"}


# ---------------------------------------------------------------- 基础

def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def est_tokens(text):
    """契约口径：CJK 字符 ×1 + 其它字符 ×0.25（估算，报告里必须写明）。"""
    cjk = sum(1 for ch in text if "\u2e80" <= ch <= "\u9fff"
              or "\u3000" <= ch <= "\u303f" or "\uff00" <= ch <= "\uffef")
    return int(round(cjk + (len(text) - cjk) * 0.25))


def parse_frontmatter(text):
    """返回 (meta, body, body 起始行号)。只为 frontmatter 子集写的最小 YAML：
    支持 `key: value`、`key: >-` / `|` 折叠块、引号、续行。"""
    if not text.startswith("---"):
        return {}, text, 1
    lines = text.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return {}, text, 1
    parts, key = {}, None
    for ln in lines[1:end]:
        m = re.match(r"^([A-Za-z_][\w.-]*)\s*:\s*(.*)$", ln)
        if m:
            key = m.group(1)
            parts[key] = [m.group(2)]
        elif key is not None:
            parts[key].append(ln.strip())
    meta = {}
    for k, vs in parts.items():
        head, rest = vs[0].strip(), [v for v in vs[1:] if v and not v.startswith("#")]
        if head in (">-", ">", "|-", "|", "|+", ">+"):
            val = " ".join(rest) if head.startswith(">") else "\n".join(rest)
        elif head == "" and rest:
            val = " ".join(rest)
        else:
            val = " ".join([head] + rest)
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        meta[k] = val
    return meta, "\n".join(lines[end + 1:]), end + 2


def fence_lines(body):
    """处于代码围栏内的**行号集合**（1-based，相对 body）。围栏里的路径是示例，不是本 skill 的引用。"""
    inside, f = set(), False
    for i, ln in enumerate(body.split("\n"), start=1):
        if ln.strip().startswith(FENCE):
            f = not f
            inside.add(i)
            continue
        if f:
            inside.add(i)
    return inside


def headings(body, body_start_line):
    """正文标题；代码围栏内的 `#` 不算（逐行维护围栏状态）。"""
    out, fence = [], None
    for i, ln in enumerate(body.split("\n")):
        s = ln.strip()
        if s.startswith(FENCE):
            fence = None if fence else s[:3]
            continue
        if fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            out.append({"line": body_start_line + i, "level": len(m.group(1)),
                        "title": m.group(2).strip()})
    return out


def first_sentence(body, body_start_line):
    """正文首个非标题、非围栏、非空段落的首句（摘要回退源）。"""
    fence = False
    for i, ln in enumerate(body.split("\n")):
        s = ln.strip()
        if s.startswith(FENCE):
            fence = not fence
            continue
        if fence or not s or s.startswith("#") or s.startswith("<!--"):
            continue
        sent = re.split(r"(?<=[。！？.!?])\s", s)[0]
        return sent[:200], body_start_line + i
    return None, None


def kind_of_file(rel):
    name = os.path.basename(rel)
    up = name.upper()
    if name == "SKILL.md":
        return "instructions"
    if up.startswith("README"):
        return "readme"
    if up.startswith(("LICENSE", "COPYING")):
        return "license"
    head = rel.split("/")[0]
    if head == "references":
        return "reference"
    if head == "scripts":
        return "script"
    if head == "assets":
        return "asset"
    ext = os.path.splitext(name)[1].lower()
    if ext in SCRIPT_EXT:
        return "script"
    if ext in ASSET_EXT:
        return "asset"
    return "other"


def extract_declared_refs(body, skill_rel):
    """正文里**真实出现**的相对路径引用：反引号片段 + markdown / wiki 链接。"""
    cands = [(m.group(1), m.start()) for m in re.finditer(r"`([^`\n]{1,200})`", body)]
    cands += [(m.group(1), m.start()) for m in re.finditer(r"\]\(([^)\s]{1,200})\)", body)]
    out, seen = [], set()
    for c, off in cands:
        if "://" in c:                       # URL 不是本 skill 的相对引用（否则 www.x/a/b.md 会被当成路径）
            continue
        for mm in PATH_RE.finditer(c):
            target = mm.group(0)
            if target in seen or "://" in target:
                continue
            seen.add(target)
            line = body[:off + mm.start()].count("\n") + 1
            out.append((target, line))
    return out


# ---------------------------------------------------------------- per-skill 分析（替换点）

def analyze_skill(path, rel):
    """一个 skill 目录 → 契约里的 skill 节点字段。要换成 `asa --json` 就换这一个函数。"""
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
        at_pack = os.path.normpath(os.path.join(path, "..", "..", t))
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
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
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
                                  "orphan": (fkind != "instructions" and not named)})
    node["orphans"] = [f["path"] for f in node["files"] if f["orphan"]]
    node["broken"] = sorted(broken)
    node["headings"] = headings(body, body_line)
    return node


# ---------------------------------------------------------------- 树

def tracked_set(pack):
    """git 跟踪清单（pack 在 git 仓库里时）。**不假定一定有 git**：不是仓库就返回 None = 全部算成员。"""
    try:
        p = subprocess.run(["git", "-C", pack, "ls-files", "-z"],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return {x for x in p.stdout.split("\0") if x}


def walk_dir(path, rel, tracked, skipped, skills):
    """递归：含 SKILL.md 的目录 = skill；含 skill 后代的目录 = category；其余目录 = asset（折叠成一个节点）。
    `tracked` 非 None 时只算 git 成员（未跟踪的 skill 形目录记进 `skipped`，不混进度量）。"""
    def member(r):
        return tracked is None or r in tracked

    def subtree_tracked(d):
        if tracked is None:
            return True
        d = d.rstrip("/")
        pre = d + "/"
        return any(t == d or t.startswith(pre) for t in tracked)

    if os.path.isfile(os.path.join(path, "SKILL.md")):
        node = analyze_skill(path, rel)
        node["parent"] = os.path.dirname(rel.rstrip("/"))
        node["parent"] = (node["parent"] + "/") if node["parent"] else ""
        node["tracked"] = True
        skills.append(node)
        return node

    children, names = [], sorted(os.listdir(path))
    for n in names:
        if n in SKIP_DIRS or n in SKIP_FILES:
            continue
        crel = rel + n
        fp = os.path.join(path, n)
        if os.path.isdir(fp):
            if tracked is not None and not subtree_tracked(crel):
                if any("SKILL.md" in fns for _, _, fns in os.walk(fp)):
                    skipped.append(crel + "/")
                continue
            sub = walk_dir(fp, crel + "/", tracked, skipped, skills)
            if sub is not None:
                children.append(sub)
        elif member(crel):
            size = os.path.getsize(fp)
            children.append({"id": crel, "kind": kind_of_file(crel), "parent": rel,
                             "bytes": size, "tracked": True,
                             "est_tokens": est_tokens(read_text(fp)) if size < 2_000_000 else 0,
                             "summary": None, "summary_source": None,
                             "refs": [], "mentions": [], "children": []})
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
                if member(rel + r):
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


def add_headings(node):
    """把 skill 的正文标题挂成 heading 子节点，供 depth-to-needle 用。"""
    hs = node.pop("headings", [])
    for h in hs:
        node["children"].append({"id": f"{node['id']}SKILL.md#{h['line']}", "kind": "heading",
                                 "parent": node["id"], "bytes": 0, "est_tokens": 0,
                                 "summary": h["title"], "summary_source": f"{node['id']}SKILL.md:{h['line']}",
                                 "level": h["level"], "refs": [], "mentions": [], "children": []})
    return node


def add_mentions(root, skills):
    """mentions 边：正文里点到同 pack 的其它技能名（路由信号）。"""
    names = {s["name"]: s["id"] for s in skills}
    for s in skills:
        body = read_text(os.path.join(root, s["id"], "SKILL.md"))
        s["mentions"] = sorted({n for n in names
                                if n != s["name"] and re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", body)})


def fanout_report(root):
    """每层的选择数：pack/category 的子节点数 + star 技能被点名的同 pack 技能数。"""
    rows = []

    def rec(node):
        if node["kind"] in ("pack", "category"):
            rows.append({"node": node["id"] or "<pack>/", "kind": node["kind"],
                         "fanout": len(node["children"]),
                         "options": [c["id"] for c in node["children"]][:50]})
        for c in node["children"]:
            rec(c)
    rec(root)
    return rows


# ---------------------------------------------------------------- 三级披露（L1/L2/L3）

def skills_root(tree):
    """找到「装技能的那一层」：自上而下第一个**直接**含 skill 的目录节点。
    pack 第一级披露的选项数就取它的直接子项数（= Agent 第一次选择看到的菜单）。"""
    node = tree
    while node["kind"] != "pack":
        node = node["children"][0]
    while True:
        if any(c["kind"] == "skill" for c in node["children"]):
            return node
        nxt = [c for c in node["children"] if c["kind"] in ("category",) or any(
            d["kind"] in ("skill", "category") for d in c["children"])]
        if not nxt:
            return node
        node = nxt[0]


def cmd_layers(root, out):
    """三级披露度量：L1 = pack 层（所有 skill 的 name+description，常驻）·
    L2 = 每个 skill 的 SKILL.md 正文（触发时载入）· L3 = references/scripts/assets（按需）。"""
    skills, skipped = [], []
    tracked = tracked_set(root)
    tree = walk_dir(root, "", tracked, skipped, skills)
    if tree is None:
        print("[layers] FAIL 这个目录里没有任何 skill（找不到 SKILL.md）")
        return 1
    tree["pack"] = {"name": os.path.basename(root),
                    "member_mode": "git-tracked" if tracked is not None else "all"}
    sr = skills_root(tree)
    entries = sr["children"]
    loose = [c for c in entries if c["kind"] == "skill"]
    cats = [c for c in entries if c["kind"] == "category"]
    l1_chars = sum(s["description_chars"] for s in skills)
    l1_text = "\n".join(s["description"] for s in skills)
    os.makedirs(out, exist_ok=True)

    over_l2 = [s for s in skills if s["est_tokens"] > 5000 or s["body_lines"] > 500]
    l3_files = [f for s in skills for f in s["files"] if f["kind"] != "instructions"]
    orphans = [(s["id"], o) for s in skills for o in s["orphans"]]
    broken = [(s["id"], b) for s in skills for b in s["broken"]]
    big_l3 = sorted([f for s in skills for f in s["files"]
                     if f["kind"] != "instructions"], key=lambda f: -f["bytes"])[:5]

    rep = {
        "pack": os.path.basename(root),
        "member_mode": tree["pack"]["member_mode"],
        "untracked_skill_dirs": skipped,
        "L1": {"skills": len(skills), "skills_root": sr["id"] or "<pack>/",
               "first_layer_entries": len(entries),
               "first_layer_loose_skills": len(loose), "first_layer_categories": len(cats),
               "menu_entries": [c["id"] for c in entries],
               "resident_chars": l1_chars, "resident_est_tokens": est_tokens(l1_text),
               "over_1024_chars": [s["id"] for s in skills if s["description_chars"] > 1024]},
        "L2": {"over_limit": [{"id": s["id"], "est_tokens": s["est_tokens"], "lines": s["body_lines"]}
                              for s in sorted(over_l2, key=lambda s: -s["est_tokens"])],
               "max_many": sorted([{"id": s["id"], "est_tokens": s["est_tokens"], "lines": s["body_lines"]}
                                   for s in skills], key=lambda r: -r["est_tokens"])[:5],
               "sibling_mentions_max": sorted([{"id": s["id"], "mentions": len(s["mentions"])}
                                               for s in skills], key=lambda r: -r["mentions"])[:5]},
        "L3": {"files": len(l3_files), "bytes": sum(f["bytes"] for f in l3_files),
               "orphans": len(orphans), "broken": len(broken),
               "largest": big_l3},
    }
    with open(os.path.join(out, "layers.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2, sort_keys=True)

    L = [f"# 三级披露 · {os.path.basename(root)}", ""]
    L.append(f"**L1（第一级 · 常驻菜单）** 技能 {len(skills)} 个 · 入口层 `{sr['id'] or '<pack>/'}` 摆出 "
             f"**{len(entries)} 项**（散技能 {len(loose)} + 类目 {len(cats)}）· "
             f"常驻 {l1_chars} 字符 ≈ {est_tokens(l1_text)} token")
    if len(entries) > MAX_FIRST_LAYER:
        L.append(f"  ❌ 第一层条目 {len(entries)} > 上限 {MAX_FIRST_LAYER}（口径见 docs/contract.md §4）")
    if rep["L1"]["over_1024_chars"]:
        L.append(f"  ❌ description 超 1024 字符: {rep['L1']['over_1024_chars']}")
    L.append("")
    L.append(f"**L2（第二级 · 触发后载入 `SKILL.md` 正文）** 超限 {len(over_l2)} 个"
             f"（>5000 est_token 或 >500 行）")
    for r in rep["L2"]["max_many"]:
        L.append(f"  {r['est_tokens']:>6} tok {r['lines']:>4} 行  {r['id']}")
    L.append("")
    L.append(f"**L3（第三级 · 按需读）** 文件 {len(l3_files)} 个 / {rep['L3']['bytes']} B · "
             f"孤儿 {len(orphans)} · 悬空引用 {len(broken)}")
    for f in big_l3:
        L.append(f"  {f['bytes']:>8} B  {f['path']}")
    L.append("")
    with open(os.path.join(out, "LAYERS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print(f"[layers] pack={os.path.basename(root)} 成员口径={tree['pack']['member_mode']}"
          f"（未跟踪 skill 形目录 {len(skipped)} 个{': ' + ', '.join(skipped[:3]) if skipped else ''}）")
    print(f"[layers] L1 技能={len(skills)} · 入口层 `{sr['id'] or '<pack>/'}` 摆出 {len(entries)} 项"
          f"（散技能 {len(loose)} + 类目 {len(cats)}）· 常驻 {l1_chars} 字符 ≈ {est_tokens(l1_text)} token"
          f" · {'❌ 超上限 ' + str(MAX_FIRST_LAYER) if len(entries) > MAX_FIRST_LAYER else '✅ 在上限内'}")
    print(f"[layers] L2 正文超限={len(over_l2)} 个 · 最大: "
          + "; ".join(f"{r['id']}={r['est_tokens']}tok/{r['lines']}行" for r in rep['L2']['max_many'][:3]))
    print(f"[layers] L3 文件={len(l3_files)} 孤儿={len(orphans)} 悬空={len(broken)}")
    print(f"[layers] 出: {os.path.join(out, 'LAYERS.md')}")
    return 0


MAX_FIRST_LAYER = 20   # 出处：Dream 的 check-disclosure.py `MAX_FIRST_LAYER_SKILLS`；口径见 docs/contract.md §4


def main(argv=None):
    ap = argparse.ArgumentParser(description="SkillWeave·skill pack 文档树与三级披露")
    ap.add_argument("cmd", nargs="?", choices=["tree", "layers"])
    ap.add_argument("pack", nargs="?")
    ap.add_argument("--out", default=None)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.cmd or not a.pack:
        ap.print_usage()
        return 2
    if a.cmd == "layers":
        root = os.path.abspath(a.pack.rstrip("/"))
        out = a.out or os.path.join(tempfile.gettempdir(), "skillweave-" + os.path.basename(root))
        return cmd_layers(root, out)
    root = os.path.abspath(a.pack.rstrip("/"))
    if not os.path.isdir(root):
        print(f"[tree] FAIL 目录不存在: {root}")
        return 1
    out = a.out or os.path.join(tempfile.gettempdir(), "skillweave-" + os.path.basename(root))
    os.makedirs(out, exist_ok=True)

    skills, skipped = [], []
    tracked = tracked_set(root)
    tree = walk_dir(root, "", tracked, skipped, skills)
    if tree is None:
        print("[tree] FAIL 这个目录里没有任何 skill（找不到 SKILL.md）")
        return 1
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


def strip_private(node):
    node.pop("_kinds", None)
    node.pop("has_skill", None)
    for c in node["children"]:
        strip_private(c)


def count(node):
    return 1 + sum(count(c) for c in node["children"])


def render_md(root, tree, skills):
    L = [f"# 文档树 · {os.path.basename(root)}", "",
         f"skills={len(skills)} · bytes={tree['pack']['bytes']} · est_tokens={tree['pack']['est_tokens']}",
         "", "```"]
    def rec(node, ind):
        if node["kind"] in ("pack", "category", "skill"):
            kids = len(node["children"])
            L.append(f"{'  ' * ind}{node['id'] or '.'}  [{node['kind']}] bytes={node['bytes']} fanout={kids}")
            for c in node["children"]:
                rec(c, ind + 1)
    rec(tree, 0)
    L += ["```", "", "## 每层选择数（fanout>1）", "", "```"]
    for r in tree["fanout"]:
        if r["fanout"] > 1:
            L.append(f"{r['fanout']:>4}  {r['node']}")
    L += ["```", "", "## 孤儿文件 / 悬空引用", "", "```"]
    for s in skills:
        for o in s["orphans"]:
            L.append(f"orphan  {s['id']}{o}")
        for b in s["broken"]:
            L.append(f"broken  {s['id']} -> {b}")
    L += ["```", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- 自检

def self_test():
    tmp = tempfile.mkdtemp(prefix="weave-selftest-")
    pack = os.path.join(tmp, "pack")
    skilldir = os.path.join(pack, "notes", "demo")     # pack → 类目 → skill
    try:
        os.makedirs(os.path.join(skilldir, "references"))
        os.makedirs(os.path.join(skilldir, "templates"))
        with open(os.path.join(skilldir, "templates", "README.md"), "w") as f:
            f.write("模板说明\n")
        with open(os.path.join(skilldir, "templates", "a.tex"), "w") as f:
            f.write("模板正文\n")
        with open(os.path.join(skilldir, "loose.txt"), "w") as f:
            f.write("没人点名\n")
        with open(os.path.join(skilldir, "SKILL.md"), "w") as f:
            f.write("---\nname: demo\ndescription: >-\n  做一件事时用。\n  带触发词。\n---\n\n"
                    "# Demo\n\n见 `references/guide.md`，另见 `references/gone.md`。\n"
                    "模板见 `templates/README.md`，随手写个 `run.py` 与 `fig.pdf`。\n\n"
                    "```\n# 这是围栏里的假标题\npython `scripts/nothere.py`\n```\n\n## 小节\n")
        with open(os.path.join(skilldir, "references", "guide.md"), "w") as f:
            f.write("guide\n")
        with open(os.path.join(skilldir, "references", "unused.md"), "w") as f:
            f.write("nobody points here\n")
        out1 = os.path.join(tmp, "o1")
        out2 = os.path.join(tmp, "o2")
        assert main(["tree", pack, "--out", out1]) == 0
        assert main(["tree", pack, "--out", out2]) == 0
        t = json.load(open(os.path.join(out1, "tree.json")))

        def find(node, kind):
            if node["kind"] == kind:
                return node
            for c in node["children"]:
                r = find(c, kind)
                if r:
                    return r
            return None

        assert t["kind"] == "pack", t["kind"]
        cat = find(t, "category")
        assert cat and cat["id"] == "notes/", cat
        s = find(t, "skill")
        assert s and s["id"] == "notes/demo/", s
        assert s["name"] == "demo", s["name"]
        assert s["summary"] == "做一件事时用。 带触发词。", s["summary"]      # 折叠块被解析
        assert ">-" not in json.dumps(s), "frontmatter 折叠标记漏进产物"
        assert s["orphans"] == ["loose.txt"], s["orphans"]
        assert s["broken"] == ["references/gone.md"], s["broken"]
        ex = sorted(r["target"] for r in s["refs"] if r["kind"] == "example")
        assert ex == ["fig.pdf", "run.py", "scripts/nothere.py"], ex      # 示例 ≠ broken
        assert "templates/" in s["named_dirs"], s["named_dirs"]
        hs = [c["summary"] for c in s["children"] if c["kind"] == "heading"]
        assert "这是围栏里的假标题" not in hs and "小节" in hs, hs            # 围栏内标题不算
        assert cat["parent"] == "", cat["parent"]
        assert s["parent"] == "notes/", s["parent"]
        a = open(os.path.join(out1, "tree.json"), "rb").read()
        b = open(os.path.join(out2, "tree.json"), "rb").read()
        assert a == b, "两次运行产物不一致（不可重建）"
        print("[self-test] ✅ 层（pack→类目→skill）/ 折叠 description / 孤儿 / 悬空 / "
              "围栏内标题 / 两次一致 —— 全过")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
