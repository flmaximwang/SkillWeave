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
import difflib
import hashlib
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


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


DIGEST_IGNORE = {"version", "updated", "date", "modified"}   # 改这些不算内容变化（内化自 asa 的 digest 口径）


def content_digest(meta, body):
    """内容指纹：忽略版本类键的 frontmatter + 正文。用来判「可 diff」——同一内容必得同一指纹。"""
    keep = {k: v for k, v in meta.items() if k not in DIGEST_IGNORE}
    return hashlib.sha256(
        (json.dumps(keep, sort_keys=True, ensure_ascii=False) + "\n" + body).encode("utf-8")).hexdigest()


def body_counts(body, sections):
    """「该拆」的可量信号（内化自 claude-skills-cli 的告警口径）。
    ponytail: 段落切分按空行 + 排除以 # / 围栏 / 表格 / 标签开头的块；围栏内的段落仍可能被计入，够用。"""
    blocks = body.count("```") // 2
    paras = [p for p in re.split(r"\n\s*\n", body)
             if p.strip() and not p.lstrip().startswith(("#", "```", "~~~", "|", "<"))]
    return {"code_blocks": blocks, "sections": sections,
            "long_paragraphs": sum(1 for p in paras if len(p.split()) > 100),
            "todos": len(re.findall(r"\b(?:TODO|FIXME)\b", body))}


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
    rep["L2"]["counts_totals"] = {k: sum(s["counts"][k] for s in skills)
                                  for k in ("code_blocks", "sections", "long_paragraphs", "todos")}
    rep["L2"]["counts_worst"] = sorted([{"id": s["id"], **s["counts"]} for s in skills],
                                       key=lambda r: -(r["long_paragraphs"] * 10 + r["code_blocks"]))[:5]
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
    ct = rep["L2"]["counts_totals"]
    L.append(f"  可量信号（全 pack）：代码块 {ct['code_blocks']} · 章节 {ct['sections']} · "
             f"长段落 {ct['long_paragraphs']} · TODO/FIXME {ct['todos']}")
    for r in rep["L2"]["counts_worst"]:
        L.append(f"    code_blocks={r['code_blocks']:<4} sections={r['sections']:<4} "
                 f"long={r['long_paragraphs']:<4} todos={r['todos']:<3} {r['id']}")
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
    c = rep["L2"]["counts_totals"]
    print(f"[layers] L2 可量信号：代码块={c['code_blocks']} 章节={c['sections']} "
          f"长段落={c['long_paragraphs']} TODO={c['todos']}")
    print(f"[layers] 出: {os.path.join(out, 'LAYERS.md')}")
    return 0


MAX_FIRST_LAYER = 20   # 出处：Dream 的 check-disclosure.py `MAX_FIRST_LAYER_SKILLS`；口径见 docs/contract.md §4

# 内化自 skill-tools 的检查（`docs/compare-tools.md` §3）：安全/可移植闸 + spec 检查
SECRET_PATTERNS = [
    ("openai-like", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("github-pat", re.compile(r"\bghp_[A-Za-z0-9]{20,}")),
    ("aws-akid", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
HARD_PATH = re.compile(r"(/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/|[A-Za-z]:\\Users\\)")


def iter_text_files(path):
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn not in SKIP_FILES and kind_of_file(fn) != "asset":
                yield os.path.join(dirpath, fn)


def scan_rules(root, skills):
    """跑六条规则，逐条给命中（文件:行号）。返回 {"rule": [hits]}。"""
    hits = {k: [] for k in ("broken_refs", "token_budget", "bom", "binary",
                            "name_mismatch", "hardcoded_path", "embedded_secret")}
    for s in skills:
        skdir = os.path.join(root, s["id"])
        if s["broken"]:
            hits["broken_refs"] += [f"{s['id']}{b}" for b in s["broken"]]
        if s["est_tokens"] > 5000:
            hits["token_budget"].append(f"{s['id']}SKILL.md  est_tokens={s['est_tokens']}")
        if s["name"] != os.path.basename(s["id"].rstrip("/")):
            hits["name_mismatch"].append(f"{s['id']}  name={s['name']!r}")
        for fp in iter_text_files(skdir):
            rel = os.path.relpath(fp, root).replace(os.sep, "/")
            try:
                raw = open(fp, "rb").read()
            except OSError:
                continue
            if raw.startswith(b"\xef\xbb\xbf"):
                hits["bom"].append(rel)
            if b"\x00" in raw[:8192]:
                hits["binary"].append(rel)
            if kind_of_file(rel) not in ("script", "reference", "instructions", "readme", "other"):
                continue
            for i, ln in enumerate(raw.decode("utf-8", "replace").split("\n"), 1):
                if HARD_PATH.search(ln):
                    hits["hardcoded_path"].append(f"{rel}:{i}")
                for name, pat in SECRET_PATTERNS:
                    if pat.search(ln):
                        hits["embedded_secret"].append(f"{rel}:{i}  [{name}]")
    return hits


def cmd_checks(root, out):
    """六条内化检查（skill-tools 口径）：引用存在 / token 预算 / BOM / 二进制 / name-目录一致 / 硬编码路径 / 内嵌密钥。"""
    skills, skipped = [], []
    tracked = tracked_set(root)
    tree = walk_dir(root, "", tracked, skipped, skills)
    if tree is None:
        print("[checks] FAIL 这个目录里没有任何 skill")
        return 1
    os.makedirs(out, exist_ok=True)
    hits = scan_rules(root, skills)
    with open(os.path.join(out, "checks.json"), "w", encoding="utf-8") as f:
        json.dump({"pack": os.path.basename(root), "skills": len(skills), "hits": hits},
                  f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"[checks] pack={os.path.basename(root)} skills={len(skills)}")
    for k, v in hits.items():
        print(f"[checks] {k:<16} {len(v):>5}")
    for k in ("embedded_secret", "hardcoded_path"):
        for h in hits[k][:8]:
            print(f"    {k}: {h}")
    gate = len(hits["embedded_secret"]) + len(hits["hardcoded_path"])
    print(f"[checks] 安全/可移植闸：{'❌ 命中 ' + str(gate) if gate else '✅ 无命中'}")
    print(f"[checks] 出: {os.path.join(out, 'checks.json')}")
    return 1 if gate else 0


def cmd_audit(root, out, top=20):
    """审计四段：size（体积对照）· orphan（孤儿/悬空）· dup（同层近重复抢题）· cost（两组成本）。"""
    skills, skipped = [], []
    tracked = tracked_set(root)
    tree = walk_dir(root, "", tracked, skipped, skills)
    if tree is None:
        print("[audit] FAIL 这个目录里没有任何 skill")
        return 1
    os.makedirs(out, exist_ok=True)
    rep = {"pack": os.path.basename(root), "skills": len(skills)}

    # —— size：正文体积 vs 规范建议值（<5000 est_token；行数三档 50/150/500）
    rep["size"] = sorted(
        [{"id": s["id"], "est_tokens": s["est_tokens"], "lines": s["body_lines"],
          "over_token": s["est_tokens"] > 5000, "line_mode": ("default" if s["body_lines"] <= 50 else
                                                              "lenient" if s["body_lines"] <= 150 else
                                                              "loose" if s["body_lines"] <= 500 else "over-500")}
         for s in skills], key=lambda r: -r["est_tokens"])

    # —— orphan：孤儿文件 + 悬空引用
    rep["orphan"] = {"orphans": [f"{s['id']}{o}" for s in skills for o in s["orphans"]],
                     "broken": [f"{s['id']}{b}" for s in skills for b in s["broken"]]}

    # —— dup：**同一层**（同一父目录）两两比 description 与摘要，找互相抢题的节点
    # ponytail: 层内 O(n²)，最大一层 52 项 ≈ 1.3k 次比较；单层上千项时再换 shingle+倒排。
    by_parent = {}
    for s in skills:
        by_parent.setdefault(s["parent"], []).append(s)
    pairs = []
    for parent, group in by_parent.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                d = difflib.SequenceMatcher(None, a["description"], b["description"]).ratio()
                m = difflib.SequenceMatcher(None, a["summary"] or "", b["summary"] or "").ratio()
                pairs.append({"sim_desc": round(d, 3), "sim_summary": round(m, 3),
                              "score": round(max(d, m), 3), "layer": parent,
                              "a": a["id"], "b": b["id"]})
    rep["dup"] = {"pairs_top": sorted(pairs, key=lambda p: -p["score"])[:top],
                  "pairs_over_050": sum(1 for p in pairs if p["score"] > 0.5),
                  "pairs_total": len(pairs)}

    # —— cost：常驻（L1 菜单）+ 激活（L2 正文）+ 按需（L3）
    resident_text = "\n".join(s["description"] for s in skills)
    l3 = [f for s in skills for f in s["files"] if f["kind"] != "instructions"]
    rep["cost"] = {"resident_chars": sum(len(s["description"]) for s in skills),
                   "resident_est_tokens": est_tokens(resident_text),
                   "l2_est_tokens_all": sum(s["est_tokens"] for s in skills),
                   "l2_est_tokens_median": sorted(s["est_tokens"] for s in skills)[len(skills) // 2],
                   "l3_files": len(l3), "l3_bytes": sum(f["bytes"] for f in l3)}

    with open(os.path.join(out, "audit.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"[audit] pack={rep['pack']} skills={len(skills)}")
    over = [r for r in rep["size"] if r["over_token"]]
    print(f"[audit] size  超 5000 token 的 skill = {len(over)}/{len(skills)}；最大 "
          + "; ".join(f"{r['id'].rstrip('/')}={r['est_tokens']}tok/{r['lines']}行({r['line_mode']})"
                      for r in rep["size"][:3]))
    print(f"[audit] orphan  孤儿 {len(rep['orphan']['orphans'])} · 悬空 {len(rep['orphan']['broken'])}")
    print(f"[audit] dup  同层比较 {rep['dup']['pairs_total']} 对（同层），相似度>0.5 的 {rep['dup']['pairs_over_050']} 对；top:")
    for p in rep["dup"]["pairs_top"][:5]:
        print(f"    {p['score']:.2f} desc={p['sim_desc']:.2f} | {p['a']}  ↔  {p['b']}")
    c = rep["cost"]
    print(f"[audit] cost  常驻 {c['resident_chars']} 字符 ≈ {c['resident_est_tokens']} token · "
          f"L2 全体 {c['l2_est_tokens_all']} tok（中位 {c['l2_est_tokens_median']}）· "
          f"L3 {c['l3_files']} 文件 / {c['l3_bytes']} B")
    print(f"[audit] 出: {os.path.join(out, 'audit.json')}")
    return 0


def cmd_judge(root, prompts_path, out, trunc=57):
    """生成**一个纯文本判官输入**（候选只有 description 截断窗口）+ 独立的金标文件 + 任务书。
    判官只读 judge-input.txt；金标永远不进它。"""
    skills, skipped = [], []
    tracked = tracked_set(root)
    tree = walk_dir(root, "", tracked, skipped, skills)
    if tree is None:
        print("[judge] FAIL 这个目录里没有任何 skill")
        return 1
    prompts = json.load(open(prompts_path, encoding="utf-8"))["prompts"]
    os.makedirs(out, exist_ok=True)
    cand = sorted(((s["id"].rstrip("/"), (s["description"] or "").replace("\n", " ")[:trunc])
                   for s in skills), key=lambda x: x[0])
    L = [f"# 判官输入（只读这一个文件；不要读任何技能目录）", "",
         f"## 候选（{len(cand)} 个；每行：路径 | 描述前 {trunc} 字符）", ""]
    L += [f"{c} | {d}" for c, d in cand]
    L += ["", "## 题面（每题只答一个候选路径，或 `none`）", ""]
    L += [f"P{p['id']}. {p['text']}" for p in prompts]
    L += ["", "## 输出格式（逐行）", "P1 <路径或 none>", "…每行一题…", "DONE"]
    txt = "\n".join(L) + "\n"
    with open(os.path.join(out, "judge-input.txt"), "w", encoding="utf-8") as f:
        f.write(txt)
    key = {"pack": os.path.basename(root), "trunc": trunc,
           "candidates": [c for c, _ in cand], "prompts": prompts}
    with open(os.path.join(out, "judge-key.json"), "w", encoding="utf-8") as f:
        json.dump(key, f, ensure_ascii=False, indent=2, sort_keys=True)
    # 自检：金标不许泄进判官输入
    leak = [p["id"] for p in prompts
            if f"P{p['id']}. {p['text']}" in txt and f" {p.get('gold')}\n" in txt.split(f"P{p['id']}. ")[1][:400]
            and p.get("gold") and p["text"].strip() != p["text"]]
    assert "gold" not in txt, "金标字段泄进判官输入"
    print(f"[judge] 候选 {len(cand)} 个（描述截断 {trunc} 字符）· 题面 {len(prompts)} 条")
    print(f"[judge] 出: {os.path.join(out, 'judge-input.txt')}  ← 判官只读这个")
    print(f"[judge] 出: {os.path.join(out, 'judge-key.json')}  ← 金标，不进判官输入")
    return 0


def cmd_score(key_path, judge_paths, out):
    """吃「判官输出 + 金标」出逐题矩阵、按题型分组、并给**校正随机**分（BoR 口径）。"""
    key = json.load(open(key_path, encoding="utf-8"))
    prompts = {p["id"]: p for p in key["prompts"]}
    n_cand = len(key["candidates"])
    picks = {}
    for jp in judge_paths:
        for ln in open(jp, encoding="utf-8"):
            ln = ln.strip()
            m = re.match(r"^P(\d+)\s+(\S+)$", ln)
            if m:
                picks.setdefault(int(m.group(1)), []).append(m.group(2).rstrip("/"))
    rows, groups = [], {}
    for pid, p in sorted(prompts.items()):
        got = picks.get(pid, [])
        gold = p.get("gold")
        ok = [(g == gold) if p["kind"] in ("should_trigger", "near_confusion") else (g != gold)
              for g in got]
        rows.append({"id": pid, "kind": p["kind"], "gold": gold, "picks": got,
                     "ok": ok, "n_judges": len(got)})
        g = groups.setdefault(p["kind"], {"n": 0, "hits": 0, "judged": 0})
        g["n"] += 1
        g["hits"] += sum(1 for x in ok if x)
        g["judged"] += len(ok)
    for g in groups.values():
        g["acc"] = round(g["hits"] / g["judged"], 3) if g["judged"] else None
        chance = 1 / n_cand if n_cand > 1 else None      # 只有 1 个候选时随机基线无意义
        g["chance"] = round(chance, 4) if chance is not None else None
        g["bor"] = (round((g["acc"] - chance) / (1 - chance), 3)
                    if (g["acc"] is not None and chance is not None and chance < 1) else None)
    rep = {"key": os.path.basename(key_path), "judges": [os.path.basename(j) for j in judge_paths],
           "candidates": n_cand, "rows": rows, "groups": groups}
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "score.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"[score] 候选 {n_cand} 个 · 判官 {len(judge_paths)} 份 · 题 {len(rows)} 条")
    for r in rows:
        mark = "".join("✓" if x else "✗" for x in r["ok"]) or "-"
        print(f"  P{r['id']:<3} {r['kind']:<20} {mark:<3} gold={r['gold']}  picks={r['picks']}")
    for k, g in sorted(groups.items()):
        print(f"[score] {k:<20} acc={g['acc']} chance={g['chance']} BoR={g['bor']}  ({g['hits']}/{g['judged']})")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="SkillWeave·skill pack 文档树与三级披露")
    ap.add_argument("cmd", nargs="?", choices=["tree", "layers", "checks", "audit", "judge", "score"])
    ap.add_argument("--prompts", default=None)
    ap.add_argument("--key", default=None)
    ap.add_argument("--judge", nargs="*", default=[])
    ap.add_argument("pack", nargs="?")
    ap.add_argument("--out", default=None)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
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
        # 内化检查：硬编码路径 + 内嵌密钥 必须命中（放在树断言之后，免得它进孤儿计数）
        with open(os.path.join(skilldir, "references", "leak.md"), "w") as f:
            f.write("见 /Users/someone/project/x.md\nkey = sk-ABCDEFGHIJKLMNOPQRSTUVWX\n")
        out3 = os.path.join(tmp, "o3")
        assert cmd_checks(pack, out3) == 1, "有命中就该退 1"
        ch = json.load(open(os.path.join(out3, "checks.json")))["hits"]
        assert len(ch["hardcoded_path"]) == 1, ch
        assert len(ch["embedded_secret"]) == 1, ch
        assert ch["name_mismatch"] == [], ch
        # 路由评测管线：生成判官输入 → 假判官输出 → 打分（含校正随机分）
        pf = os.path.join(tmp, "prompts.json")
        with open(pf, "w") as f:
            json.dump({"prompts": [{"id": 1, "kind": "should_trigger", "gold": "notes/demo",
                                    "text": "演示题面"}]}, f)
        out4 = os.path.join(tmp, "o4")
        assert cmd_judge(pack, pf, out4) == 0
        txt = open(os.path.join(out4, "judge-input.txt")).read()
        assert "gold" not in txt, "金标泄进判官输入"
        jf = os.path.join(tmp, "judge-A.txt")
        open(jf, "w").write("P1 notes/demo\nDONE\n")
        assert cmd_score(os.path.join(out4, "judge-key.json"), [jf], out4) == 0
        sc = json.load(open(os.path.join(out4, "score.json")))
        assert sc["groups"]["should_trigger"]["acc"] == 1.0, sc["groups"]
        print("[self-test] ✅ 层（pack→类目→skill）/ 折叠 description / 孤儿 / 悬空 / "
              "围栏内标题 / 两次一致 / 硬编码路径 / 内嵌密钥 —— 全过")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
