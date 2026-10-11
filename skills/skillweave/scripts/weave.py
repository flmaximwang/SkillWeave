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
import codecs
import collections
import difflib
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

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
    cjk = sum(1 for ch in text if 0x2E80 <= ord(ch) <= 0x9FFF
              or 0x3000 <= ord(ch) <= 0x303F or 0xFF00 <= ord(ch) <= 0xFFEF)
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
        node = analyze_skill(root, path, rel)
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
            sub = walk_dir(root, fp, crel + "/", tracked, skipped, skills)
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
    """找「装技能的那一层」：从 pack 根往下，只要**唯一**的选择项还是个类目就继续下钻；
    遇到两个以上选择项（或唯一选择项已经是 skill）就停 —— 这一层才是 Agent 第一次选择看到的菜单。
    分组后 `skills/` 下面全是类目，入口层仍是 `skills/`（旧实现只认「直接含 skill 的目录」，会错抓成第一个类目）。"""
    node = tree
    while node["kind"] != "pack":
        node = node["children"][0]
    while True:
        choices = [c for c in node["children"] if c["kind"] in ("skill", "category")]
        if len(choices) != 1 or choices[0]["kind"] != "category":
            return node
        node = choices[0]


def cmd_layers(root, out):
    """三级披露度量：L1 = pack 层（所有 skill 的 name+description，常驻）·
    L2 = 每个 skill 的 SKILL.md 正文（触发时载入）· L3 = references/scripts/assets（按需）。"""
    skills, skipped = [], []
    tracked = tracked_set(root)
    tree = walk_dir(root, root, "", tracked, skipped, skills)
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
                # 口径：over_limit = token>5000 **或** 行数>500（两个闸任一超）；
                # over_token = 只用 token 闸，专门给 audit 对拍用（两个命令的数必须能对上）。
                "over_token": [s["id"] for s in sorted(skills, key=lambda s: -s["est_tokens"])
                               if s["est_tokens"] > 5000],
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
            if raw.startswith(codecs.BOM_UTF8):
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
    tree = walk_dir(root, root, "", tracked, skipped, skills)
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
    tree = walk_dir(root, root, "", tracked, skipped, skills)
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


def section_spans(body, body_start_line):
    """按标题切出小节 → [(title, 起始行, 结束行, 字符数)]。拆分的机械部分用它。"""
    hs = headings(body, body_start_line)
    lines = body.split("\n")
    out = []
    for i, h in enumerate(hs):
        end = hs[i + 1]["line"] - 1 if i + 1 < len(hs) else body_start_line + len(lines) - 1
        chunk = "\n".join(lines[h["line"] - body_start_line:end - body_start_line + 1])
        out.append((h["title"], h["line"], max(h["line"], end), len(chunk)))
    return out


def propose_actions(root, cap=20, merge_at=0.97, rewrite_at=0.5):
    """四类动作的**提案**（不改盘）：拆 / 分 / 并 / 改写。每条带 `文件:行`、diff 形状、是否可机械执行。
    需要语言模型的判断（哪段该下沉、进哪个类目、触发词怎么改）一律 `needs_model=True`，CLI 不假装能做。"""
    skills = []
    tree = walk_dir(root, root, "", tracked_set(root), [], skills)
    if tree is None:
        return [{"kind": "none", "needs_model": False, "auto_applyable": False,
                 "evidence": {}, "where": root, "action": "这个目录里没有任何 skill", "diff_shape": [], "paths": []}]
    sr = skills_root(tree)
    l1 = [c for c in sr["children"] if c["kind"] in ("skill", "category")]
    props = []

    # —— 并（近重复）：description 近乎逐字相同 → 合并候选
    by_parent = {}
    for s in skills:
        by_parent.setdefault(s["parent"], []).append(s)
    for parent, group in by_parent.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = sorted([group[i], group[j]], key=lambda s: s["id"])
                sim = difflib.SequenceMatcher(None, a["description"], b["description"]).ratio()
                if sim < rewrite_at:
                    continue
                # 身份取谁？旧写法按 id 排序 —— 尾斜杠会让 `x-data/` 排在 `x/` 前，纯属偶然。
                # 改成 merge.md 的口径：全 pack 正文引用它的次数多的留下；并列取更短的名字。
                def refcount(sid):
                    base = os.path.basename(sid.rstrip("/"))
                    n = 0
                    for dp, _, fs in os.walk(os.path.join(root, "skills")):
                        for f in fs:
                            if f != "SKILL.md" or sid.rstrip("/") in dp:
                                continue
                            try:
                                n += read_text(os.path.join(dp, f)).count(base)
                            except OSError:
                                pass
                    return n
                ra, rb = refcount(a["id"]), refcount(b["id"])
                keep = a if (ra, -len(a["id"])) >= (rb, -len(b["id"])) else b
                drop = b if keep is a else a
                a, b = keep, drop
                fa = sorted(os.path.relpath(os.path.join(dp, f), root)
                            for dp, _, fs in os.walk(os.path.join(root, a["id"].rstrip("/"))) for f in fs)
                fb = sorted(os.path.relpath(os.path.join(dp, f), root)
                            for dp, _, fs in os.walk(os.path.join(root, b["id"].rstrip("/"))) for f in fs)
                names_a = [os.path.basename(x) for x in fa]
                names_b = [os.path.basename(x) for x in fb]
                same_names = names_a == names_b
                ver_a = parse_frontmatter(read_text(os.path.join(root, a["id"].rstrip("/"), "SKILL.md")))[0].get("version")
                ver_b = parse_frontmatter(read_text(os.path.join(root, b["id"].rstrip("/"), "SKILL.md")))[0].get("version")
                # 机械合并规则：文件名集合一致 + 两边都有 version → 身份取被引用更多的一方、同名文件取 version 高的一方。
                auto = bool(same_names and ver_a and ver_b and ver_a != ver_b and sim >= merge_at)
                kind = "merge" if sim >= merge_at else "rewrite"
                winner = b if (auto and ver_a and ver_b and ver_b > ver_a) else a
                props.append({
                    "kind": kind, "needs_model": not auto,
                    "auto_applyable": bool(auto and kind == "merge"),
                    "evidence": {"sim_desc": round(sim, 3), "layer": parent, "same_names": same_names,
                                 "refcount": {a["id"]: ra, b["id"]: rb},
                                 "version": {a["id"]: ver_a, b["id"]: ver_b},
                                 "b_skill_sha256": sha256_file(os.path.join(root, b["id"].rstrip("/"), "SKILL.md")),
                                 "mechanical_rule": "身份取被引用更多的一方（并列取更短名字）、正文取 version 更高的一方"
                                 if auto else None},
                    "where": f"{a['id']}SKILL.md:1 · {b['id']}SKILL.md:1",
                    "action": (f"保留 {a['id']}（身份），正文取 {winner['id']}（version {ver_b if winner is b else ver_a}）；"
                               f"删 {b['id']}" + ("（机械可执行）" if auto else "（要人先看两边正文差异）"))
                    if kind == "merge" else
                    f"改写触发词把两者分开（当前 sim_desc={sim:.2f}）：{a['id']} / {b['id']}",
                    "diff_shape": ([f"- {b['id']}/ (删)", f"~ {a['id']}/SKILL.md (正文取较高 version)"]
                                   if kind == "merge" else [f"~ {a['id']}SKILL.md:1", f"~ {b['id']}SKILL.md:1"]),
                    "paths": [a["id"].rstrip("/") + "/", b["id"].rstrip("/") + "/"] if kind == "merge" else [],
                })

    # —— 分（归入类目压低 L1）：按词根聚类，只出建议不做决定
    if len(l1) > cap:
        loose = [c["id"].rstrip("/").split("/")[-1] for c in l1 if c["kind"] == "skill"]
        buckets = {}
        for n in loose:
            for tok in (n.split("-")[0], n.split("-")[1] if n.count("-") >= 1 else ""):
                if tok and sum(1 for m in loose if m.startswith(tok + "-")) >= 3:
                    buckets.setdefault(tok + "-*", []).append(n)
                    break
        props.append({
            "kind": "group", "needs_model": True, "auto_applyable": False,
            "evidence": {"L1_items": len(l1), "cap": cap, "loose": len(loose),
                         "token_buckets": {k: v for k, v in buckets.items()}},
            "where": f"{sr['id']}（入口层）",
            "action": f"入口层摆出 {len(l1)} 项 > 上限 {cap}：把散技能按用途归入类目（类目名要人拍板）",
            "diff_shape": [f"~ git mv skills/{n} skills/<类目>/{n}" for n in loose[:6]] + (["…"] if len(loose) > 6 else []),
            "paths": [],
        })

    # —— 拆（正文超限）：给出该下沉的小节与目标文件名
    for s in skills:
        if s["est_tokens"] <= 5000:
            continue
        body = read_text(os.path.join(root, s["id"] + "SKILL.md"))
        meta, b, start = parse_frontmatter(body)
        spans = sorted(section_spans(b, start), key=lambda x: -x[3])[:4]
        props.append({
            "kind": "split", "needs_model": True, "auto_applyable": False,
            "evidence": {"est_tokens": s["est_tokens"], "lines": s["body_lines"],
                         "sections_by_size": [{"title": t, "lines": f"{a}-{z}", "chars": c} for t, a, z, c in spans]},
            "where": f"{s['id']}SKILL.md:{spans[0][1] if spans else 1}",
            "action": f"{s['est_tokens']} token > 5000：把最大的几个小节下沉到 references/，原位留一行转指",
            "diff_shape": [f"~ {s['id']}SKILL.md:{a}-{z} ({t}) → + {s['id']}references/<slug>.md"
                           for t, a, z, c in spans[:2]],
            "paths": [],
        })
    return props


def cmd_propose(root, out, apply_changes=False, group_map=None):
    """默认 `--dry-run` 只出提案；`--apply` 执行 auto_applyable 的合并；`--apply-group <map.json>` 执行人给的归位映射。"""
    os.makedirs(out, exist_ok=True)
    props = propose_actions(root)
    with open(os.path.join(out, "proposals.json"), "w", encoding="utf-8") as f:
        json.dump({"pack": os.path.basename(root), "count": len(props), "proposals": props},
                  f, ensure_ascii=False, indent=2, sort_keys=True)
    lines = [f"# 提案：{os.path.basename(root)}", "",
             f"共 {len(props)} 条；其中可机械执行 {sum(1 for p in props if p['auto_applyable'])} 条、"
             f"需语言模型判断 {sum(1 for p in props if p['needs_model'])} 条。", ""]
    for i, p in enumerate(props, 1):
        lines += [f"## {i}. [{p['kind']}] {p['where']}",
                  f"- 判断：{p['action']}",
                  f"- 证据：`{json.dumps(p['evidence'], ensure_ascii=False)}`",
                  f"- diff 形状：" + " ；".join(f"`{d}`" for d in p["diff_shape"]),
                  f"- 可机械执行：{'是' if p['auto_applyable'] else '否（要模型判断）'}", ""]
    with open(os.path.join(out, "PROPOSALS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    for p in props:
        print(f"[propose] {p['kind']:<8} {p['where']:<58} auto={str(p['auto_applyable']):<5} | {p['action'][:64]}")
    print(f"[propose] 出: {os.path.join(out, 'proposals.json')} / PROPOSALS.md")

    if not apply_changes and not group_map:
        print("[propose] dry-run：盘上未改任何文件（加 --apply / --apply-group 才落盘）")
        return 0

    touched, applied, oks = set(), 0, []
    for p in props:
        if not p["auto_applyable"]:
            continue
        a, b = [x.rstrip("/") for x in p["paths"]]
        # ① 同名文件：非 SKILL.md 的用 b 覆盖 a；② SKILL.md 只取 b 的**正文**，frontmatter 保持 a 的身份
        _, body_b, _ = parse_frontmatter(read_text(os.path.join(root, b, "SKILL.md")))
        meta_a, _, _ = parse_frontmatter(read_text(os.path.join(root, a, "SKILL.md")))
        for dp, _, fs in os.walk(os.path.join(root, b)):
            for f in fs:
                rel = os.path.relpath(os.path.join(dp, f), os.path.join(root, b))
                if rel == "SKILL.md":
                    continue
                src_f = os.path.join(dp, f)
                dst = os.path.join(root, a, rel)
                if os.path.exists(dst) and sha256_file(dst) == sha256_file(src_f):
                    continue                       # 内容相同 → 不复制、也不声明（否则对账会报「声明了却没变更」）
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src_f, dst)
                touched.add(f"{a}/{rel}")
        front = read_text(os.path.join(root, a, "SKILL.md")).split("---", 2)
        vers = [v for v in (p["evidence"].get("version") or {}).values() if v]
        ver_w = max(vers) if vers else None
        head = front[1]
        if ver_w:
            head = re.sub(r"(?m)^version:.*$", f"version: {ver_w}", head)     # version 跟胜方走
        open(os.path.join(root, a, "SKILL.md"), "w", encoding="utf-8").write("---" + head + "---" + body_b)
        touched |= {f"{a}/", f"{b}/"}
        git(root, "rm", "-r", "-q", b)
        if os.path.isdir(os.path.join(root, b)):
            shutil.rmtree(os.path.join(root, b))
        ok = not os.path.isdir(os.path.join(root, b))          # 验证：b 真没了
        oks.append((p["kind"], ok))
        applied += 1
    if group_map:
        mapping = json.load(open(group_map, encoding="utf-8"))
        for old, new in sorted(mapping.items()):
            src = os.path.join(root, old)
            if not os.path.isdir(src):
                print(f"[propose] 跳过（不存在）: {old}")
                continue
            os.makedirs(os.path.dirname(os.path.join(root, new)), exist_ok=True)
            git(root, "mv", old, new)
            if os.path.isdir(src):
                shutil.move(src, os.path.join(root, new))
            ok = os.path.isdir(os.path.join(root, new)) and not os.path.isdir(src)
            oks.append(("group:" + os.path.basename(old), ok))
            touched |= {old.rstrip("/") + "/", new.rstrip("/") + "/"}
            applied += 1
    # 路径集合级对账：git 报出来的每个路径都必须落在我声明过的目录里（反之亦然）。
    # 注意 macOS 上中文文件名可能是 NFD，git 索引里是 NFC —— 两边都归一化再比，否则全是假差异。
    nfc = lambda s: unicodedata.normalize("NFC", s)
    raw = (git(root, "status", "--porcelain", "-z") or subprocess.CompletedProcess([], 1, "")).stdout
    fields = [x for x in raw.split("\0") if x]
    actual, i = set(), 0
    while i < len(fields):
        st, path = fields[i][:2], fields[i][3:]
        actual.add(nfc(path))
        if st[0] in "RC" and i + 1 < len(fields):      # rename/copy：下一个字段是旧路径，**没**有状态前缀
            actual.add(nfc(fields[i + 1]))
            i += 1
        i += 1
    declared_prefix = tuple(nfc(t) for t in touched)
    extra = sorted(a for a in actual if not a.startswith(declared_prefix))
    missing = sorted(t for t in declared_prefix if not any(a.startswith(t) for a in actual))
    bad = [k for k, ok in oks if not ok] + extra + missing
    print(f"[propose] --apply：执行 {applied} 条机械动作 → 声明 {len(touched)} 个目录 · git 报出 {len(actual)} 个路径")
    print(f"[propose] 逐条自检 {'✓ 全部落地' if not oks or all(ok for _, ok in oks) else '✗ 失败 '}"
          f"；集合对账 {'✓ 无未声明变更、无声明未发生' if not extra and not missing else '✗ 差异 ' + str((extra + missing)[:5])}")
    print("[propose] git diff --stat（原始输出）：")
    print((git(root, "diff", "--stat", "-M", "HEAD") or subprocess.CompletedProcess([], 1, "")).stdout.rstrip())
    return 0 if not bad else 1


def cmd_judge(root, prompts_path, out, trunc=57):
    """生成**一个纯文本判官输入**（候选只有 description 截断窗口）+ 独立的金标文件 + 任务书。
    判官只读 judge-input.txt；金标永远不进它。"""
    skills, skipped = [], []
    tracked = tracked_set(root)
    tree = walk_dir(root, root, "", tracked, skipped, skills)
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
    ap.add_argument("cmd", nargs="?",
                    choices=["tree", "layers", "checks", "audit", "propose", "judge", "score", "visualize", "collapse", "prepare", "disclosure"])
    ap.add_argument("--prompts", default=None)
    ap.add_argument("--key", default=None)
    ap.add_argument("--judge", nargs="*", default=[])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--apply-group", default=None)
    ap.add_argument("--description", default=None)
    ap.add_argument("--entry-dir", default=None)
    ap.add_argument("--dest", default=None)
    ap.add_argument("--shape", default=None)
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

    skills, skipped = [], []
    tracked = tracked_set(root)
    tree = walk_dir(root, root, "", tracked, skipped, skills)
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


# ---------------------------------------------------------------- 可视化（TREE.md + TREE.html）

ISLAND_COLORS = ["#3b6ea5", "#7a5195", "#bc5090", "#ef5675", "#ff764a", "#ffa600",
                 "#2f7d6b", "#8a6d1f", "#5b6bbf", "#a1421f", "#3f6f8f", "#6b7a3f", "#8f4b7a"]


def cross_skill_edges(root, skills):
    """A→B：A 的任何文本文件里**点到 B 的目录名**（`(?<![\\w-])slug(?![\\w-])`）。权重 = 次数。

    口径固定成这一个，因为「岛数」对口径敏感（实测同一份数据）：
      · 只看 SKILL.md 里的 frontmatter `name` 互指 → 11 个岛
      · 加上「引用解析到别的 skill 目录」的边   → 10 个岛
      · 扫**全部文本文件**、按**目录名**互指（本函数，也是 GRAPH.md 那一轮用的） → 13 个岛
    所以岛数不是事实，是切法；要报必须连口径一起报。选这个口径的理由：目录名是本包既有的稳定标识，
    且 `name` 与目录名并不总是一致（实测 `gateway-session-list/` 的 `name` 是 `gateway-operations`）。"""
    slugs = {os.path.basename(s["id"].rstrip("/")): s["id"] for s in skills}
    edges = collections.Counter()
    for s in skills:
        blob = "\n".join(read_text(fp) for fp in iter_text_files(os.path.join(root, s["id"])))  # O(n²) 名字扫描，pack 规模下够用
        for slug, b in slugs.items():
            if b == s["id"]:
                continue
            hits = len(re.findall(r"(?<![\w-])" + re.escape(slug) + r"(?![\w-])", blob))
            if hits:
                edges[(s["id"], b)] += hits
    return edges


def islands_of(skills, edges):
    """互指图的连通分量 —— 数据给的分层，不是人分的类。"""
    parent = {s["id"]: s["id"] for s in skills}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (a, b) in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    comp = collections.defaultdict(list)
    for s in skills:
        comp[find(s["id"])].append(s["id"])
    return sorted((sorted(v) for v in comp.values()), key=lambda v: -len(v))


def _xml(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def render_tree_md(root, skills, edges, islands, entry, rev):
    byid = {s["id"]: s for s in skills}
    L = [f"# 文档树 · {os.path.basename(root)}", "",
         f"基准 `{rev}` · 由 `weave.py visualize` 生成，**不要手改**。", "",
         f"skill {len(skills)} 个 · 入口层 {len(entry)} 项 · 常驻菜单 "
         f"{est_tokens(chr(10).join(x['description'] for x in skills))} tok · "
         f"互指岛 {len(islands)} 个", "",
         "## L1 常驻菜单（Agent 每轮都看到的）", ""]
    for kind, node_id, members in entry:
        if kind == "category":
            tok = est_tokens("\n".join(byid[i]["description"] for i in members))   # L1 常驻口径
            L.append(f"- **{node_id.rstrip('/')}/** 〔类目〕{len(members)} 项 · {tok} tok")
            for i in members:
                s = byid[i]
                L.append(f"  - {s['name']} — {s['description'][:88]}")
        else:
            s = byid[node_id]
            L.append(f"- **{s['name']}** 〔散项〕{est_tokens(s['description'])} tok — {s['description'][:88]}")
    L += ["", "## L2 每个 skill 的正文与 L3 按需文件", "",
          "| skill | 正文 | 行 | L3 文件 | 孤儿 | 悬空 |", "|---|---|---|---|---|---|"]
    for s in sorted(skills, key=lambda s: -s["est_tokens"]):
        l3 = len(s["files"]) - 1
        L.append(f"| {'  ' * (s['id'].count('/') - 1)}{s['name']} | {s['est_tokens']} tok | "
                 f"{s['body_lines']} | {l3} | {len(s['orphans'])} | {len(s['broken'])} |")
    L += ["", "## 互指岛（数据给的分层）", ""]
    for n, isl in enumerate(islands, 1):
        inner = sum(1 for (a, b) in edges if a in isl and b in isl)
        L.append(f"### 岛 {n} · {len(isl)} 个 · 岛内互指 {inner} 条")
        L.append("")
        for i in isl:
            L.append(f"- {byid[i]['name']}  `{i}`")
        L.append("")
    L += ["## 口径", "",
          "- L1 = 所有 skill 的 `name`+`description`（常驻）；L2 = 单个 `SKILL.md` 正文（触发时载入）；"
          "L3 = `references/scripts/assets`（按需）。",
          f"- `tok` = `est_tokens`：CJK ×1 + 其它 ×0.25（估算）。",
          f"- 互指 = 正文点名同 pack 技能名 + 引用解析到别的 skill 目录；岛 = 互指图的连通分量。",
          "- 入口层 = 从 pack 根往下、唯一选择项还是类目就继续下钻，遇 ≥2 项停；它下面的条目数就是 Agent 第一次看到的菜单大小。",
          ""]
    return "\n".join(L)


def render_tree_html(root, skills, edges, islands, entry, rev, stats):
    byid = {s["id"]: s for s in skills}
    isl_of = {i: n for n, isl in enumerate(islands, 1) for i in isl}
    W = 1680
    P = []          # svg 片段
    y = 196         # 数字卡片占到 132，标题与第一批框都从下面起（第一版压在卡片上，实测）

    def rect(x, yy, w, h, fill, stroke, rx=8, sw=1.2, op=1.0):
        P.append(f'<rect x="{x}" y="{yy}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}" opacity="{op}"/>')

    def text(x, yy, t, size=13.0, fill="#e8e8ef", anchor="start", weight="normal", mono=False):
        fam = "ui-monospace,Menlo,monospace" if mono else "system-ui,-apple-system,'Helvetica Neue',sans-serif"
        P.append(f'<text x="{x}" y="{yy}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
                 f'font-weight="{weight}" font-family="{fam}">{_xml(t)}</text>')

    # 标题 + 数字
    text(40, 46, f"文档树 · {os.path.basename(root)}", 24, "#f2f2f7", weight="600")
    text(40, 74, f"{rev} · weave.py visualize 生成 · 不要手改", 12, "#9aa0b0", mono=True)
    nums = [("skill", stats["skills"]), ("入口层", stats["entry"]), ("常驻 tok", stats["resident"]),
            ("互指岛", stats["islands"]), ("L2 超限", stats["over_l2"]),
            ("孤儿", stats["orphans"]), ("悬空", stats["broken"])]
    x = 40
    for k, v in nums:
        rect(x, 92, 150, 40, "#20222c", "#33364a", rx=6)
        text(x + 10, 110, k, 11, "#9aa0b0")
        text(x + 10, 126, str(v), 15, "#f2f2f7", weight="600")
        x += 162

    # L1 → L2 树
    text(40, y - 12, "L1 常驻菜单 → L2 正文 → L3 按需文件", 15, "#c9cdea", weight="600")
    text(560, y - 12, "· 每个 skill 上的 tok = L2 正文；类目头上的 L1 tok = 描述常驻", 12, "#7d8496")
    for kind, node_id, members in entry:
        isl = isl_of.get(node_id) or isl_of.get(members[0])
        col = ISLAND_COLORS[(isl - 1) % len(ISLAND_COLORS)]
        if kind == "category":
            tok = est_tokens("\n".join(byid[i]["description"] for i in members))   # L1 常驻口径
            h = 30 + 26 * ((len(members) + 2) // 3)
            rect(40, y, 1596, h, "#191b24", col, rx=10, sw=1.6)
            text(56, y + 21, f"{node_id.rstrip('/')}/", 14, "#f2f2f7", weight="600")
            text(250, y + 21, f"〔类目〕{len(members)} 项 · L1 {tok} tok · 岛 {isl}", 12, col, mono=True)
            cx, cy = 56, y + 34
            for i in members:
                s = byid[i]
                chip = f"{s['name']} {s['est_tokens']}tok"
                wpx = 9 * len(chip) + 16
                if cx + wpx > 1600:
                    cx, cy = 56, cy + 26
                rect(cx, cy, wpx, 20, "#232634", "#3a3f52", rx=4, sw=0.8)
                text(cx + 8, cy + 14, chip, 11.5, "#dfe3f2", mono=True)
                cx += wpx + 8
            y += h + 10
        else:
            s = byid[node_id]
            rect(40, y, 1596, 30, "#191b24", col, rx=10, sw=1.6)
            text(56, y + 21, s["name"], 14, "#f2f2f7", weight="600")
            text(420, y + 21, f"〔散项 · 岛 {isl} · 单独成岛——和本包别的 skill 一条互指都没有〕"
                              f"L1 {est_tokens(s['description'])} tok · "
                              f"L2 {s['est_tokens']} tok · L3 {len(s['files']) - 1} 个文件",
                 12, col, mono=True)
            y += 40
    y += 24

    # 互指岛：圆环 + 弦。**不在圆上写长名字** —— 21 个长名绕一圈必然叠字（实测第一版看不清），
    # 改成节点带编号、框内配图例；编号从 12 点方向顺时针。
    text(40, y, f"互指图：{len(islands)} 个岛（岛 = 互指图连通分量；弦 = 一条互指；编号从 12 点方向顺时针，"
                f"对应框内图例）", 15, "#c9cdea", weight="600")
    y += 16
    boxes = []
    for n, isl in enumerate(islands, 1):
        k = len(isl)
        r = 0.0 if k == 1 else 30 + 3.2 * k
        maxlen = max(len(byid[sid]["name"]) for sid in isl)
        cw = int(6.2 * maxlen) + 26
        cols = 1 if k <= 8 else 2
        rows = (k + cols - 1) // cols
        w = max(190, cw + 24) if k == 1 else max(240, cols * cw + 24)
        h = int(2 * r + 8 + rows * 14 + 54) if k > 1 else 152
        boxes.append({"n": n, "isl": isl, "k": k, "r": r, "cols": cols, "rows": rows,
                      "cw": cw, "w": w, "h": h})
    rows_pack = []
    x, cur = 40, []
    for b in boxes:
        if cur and x + b["w"] > 1640:
            rows_pack.append(cur)
            cur = []
            x = 40
        cur.append(b)
        x += b["w"] + 14
    if cur:
        rows_pack.append(cur)
    for packrow in rows_pack:
        rh = max(b["h"] for b in packrow)
        x = 40
        for b in packrow:
            n, isl, k, r, cols, cw, w, h = b["n"], b["isl"], b["k"], b["r"], b["cols"], b["cw"], b["w"], b["h"]
            col = ISLAND_COLORS[(n - 1) % len(ISLAND_COLORS)]
            rect(x, y, w, h, "#15171f", col, rx=10, sw=1.4, op=0.95)
            inner = [(a, bb) for (a, bb) in edges if a in isl and bb in isl]
            text(x + 12, y + 20, f"岛 {n} · {k} 个 · 互指 {len(inner)} 条", 12, col, weight="600", mono=True)
            if k == 1:
                cx, cy = x + w / 2, y + 74
                P.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{col}" stroke="#0d0e14" stroke-width="1.2"/>')
                text(cx, cy + 34, byid[isl[0]]["name"], 10.5, "#b9bfd4", anchor="middle", mono=True)
                text(cx, cy + 50, "与包内其它 skill 一条互指都没有", 9.5, "#7d8496", anchor="middle")
            else:
                cx, cy = x + 20 + r, y + 44 + r
                pos = {}
                for i, sid in enumerate(isl):
                    ang = 2 * math.pi * i / k - math.pi / 2
                    pos[sid] = (cx + r * math.cos(ang), cy + r * math.sin(ang))
                for (a, bb) in inner:
                    (ax, ay), (bx, by) = pos[a], pos[bb]
                    P.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" '
                             f'stroke="{col}" stroke-width="1.1" opacity="0.45"/>')
                for i, sid in enumerate(isl):
                    px, py = pos[sid]
                    ang = 2 * math.pi * i / k - math.pi / 2
                    P.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{col}" stroke="#0d0e14" stroke-width="1.2"/>')
                    text(px + 10 * math.cos(ang), py + 10 * math.sin(ang) + 3, str(i + 1), 8, "#c9cdea",
                         anchor="middle" if abs(math.cos(ang)) < 0.7 else ("start" if math.cos(ang) > 0 else "end"),
                         mono=True)
                ly = y + 44 + 2 * r + 14
                for i, sid in enumerate(isl):
                    c_, r_ = i % cols, i // cols
                    text(x + 12 + c_ * cw, ly + r_ * 14, f"{i + 1}. {byid[sid]['name']}", 9.5, "#b9bfd4", mono=True)
            x += w + 14
        y += rh + 14

    svg = "\n".join(P)
    return f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>文档树 · {_xml(os.path.basename(root))}</title>
<style>
 html,body{{margin:0;padding:0;background:#0d0e14;color:#e8e8ef;
   font-family:system-ui,-apple-system,"Helvetica Neue",sans-serif}}
 .wrap{{padding:0}}
 svg{{display:block}}
 footer{{padding:10px 40px 28px;color:#7d8496;font-size:12px;line-height:1.6}}
 code{{color:#c9cdea}}
</style></head>
<body><div class="wrap">
<svg width="{W}" height="{y + 40}" viewBox="0 0 {W} {y + 40}" xmlns="http://www.w3.org/2000/svg">
<rect width="{W}" height="{y + 40}" fill="#0d0e14"/>
{svg}
</svg>
<footer>
 由 <code>weave.py visualize</code> 生成 · 基准 <code>{_xml(rev)}</code> ·
 口径：L1 = 全部 skill 的 name+description（常驻）· L2 = SKILL.md 正文 · L3 = references/scripts/assets（按需）·
 tok = CJK×1 + 其它×0.25（估算）· 互指 = 正文点名 + 引用落到别的 skill 目录 · 岛 = 互指图连通分量
</footer></div></body></html>
"""


def island_dirs(entry_dir, skills, islands):
    """岛 → 目录名的**机械**取法：整岛同处一个目录且不止一个成员 → 用那个目录名；
    否则用成员自己的目录名（散落的、单成员的岛）。重名时补序号。"""
    used, out = {}, []
    for isl in islands:
        dirs = sorted({os.path.basename(os.path.dirname(i.rstrip("/"))) for i in isl})
        base = dirs[0] if (len(dirs) == 1 and len(isl) > 1) else os.path.basename(isl[0].rstrip("/"))
        n = used.get(base, 0) + 1
        used[base] = n
        out.append((base if n == 1 else f"{base}-{n}", isl))
    return out


def umbrella_body(dirs, byid):
    """伞体正文的机械部分：N 个岛各一行。写法固定，不改语义。"""
    body = ["本 pack 只有这一个入口。先在这 %d 项里选一项，再读该岛的 `INDEX.md` 选具体 skill。" % len(dirs), ""]
    for n, (name, isl) in enumerate(dirs, 1):
        mem = " / ".join(byid[i]["name"] for i in isl[:6]) + (" …" if len(isl) > 6 else "")
        body.append(f"{n}. **{name}**（{len(isl)} 个）— {mem} → `references/{name}/INDEX.md`")
    return body


def island_index_md(name, isl, byid):
    """一个岛的 INDEX.md：成员逐条带 description（这是第三次点击看到的东西）。"""
    return "\n".join([f"# {name}", ""] +          # 指针按 INDEX.md **自己所在目录**写（它就在 references/<岛>/ 下）
                     [f"- **{byid[i]['name']}** — {byid[i]['description']}\n  "
                      f"`{os.path.basename(i.rstrip('/'))}/SKILL.md`" for i in isl]) + "\n"


def _rev(root):
    g = git(root, "rev-parse", "--short", "HEAD")
    return g.stdout.strip() if g is not None and g.returncode == 0 else "?"


def _default_entry_dir(root):
    base = os.path.basename(os.path.abspath(root.rstrip("/")))
    base = re.sub(r"^AgentSkill-", "", base)
    return base.lower()


def render_collapse_md(root, skills, edges, islands, dirs, entry_dir, desc, before):
    byid = {s["id"]: s for s in skills}
    body = umbrella_body(dirs, byid)
    body_tok = est_tokens("\n".join(body))
    idx_tok = sum(est_tokens(island_index_md(n, i, byid)) for n, i in dirs)
    resident_after = est_tokens(desc or "")
    L = [f"# 单入口方案（L1 = 1 个 skill 入口）· {os.path.basename(root)}", "",
         f"由 `weave.py collapse` 生成（**默认 dry-run，不改盘**）。基准 `{before['rev']}`。", "",
         "## 形状", "", "```",
         f"L1  1 项      {entry_dir}/（description = 常驻菜单，唯一一条）",
         f"L2  {len(dirs)} 项     伞体里的岛索引（每岛一行）→ references/<岛>/INDEX.md",
         f"L3  {len(skills)} 篇   各 skill 的正文（原目录整棵搬进 references/<岛>/<skill>/，内部相对引用不破）",
         "```", "",
         "## 本方案的账（同一台机器上量的）", "",
         "| 项 | 现在（多入口） | 改成单入口 |", "|---|---|---|",
         f"| L1 常驻 | {before['skills']} 条 description = **{before['resident']} tok** | 1 条 = "
         f"**{resident_after} tok**（写出来的 description 多长就是多少） |",
         f"| 第一次点击 | {before['entry']} 项 | **1 项** |",
         f"| 第二次点击 | — | **{len(dirs)} 项**（岛索引，载入时付 **{body_tok} tok**） |",
         f"| 第三次点击 | 无 | **{len(skills)} 项**（岛的 `INDEX.md`，**{idx_tok} tok**） |",
         f"| 独立可装 | 每个 skill 各自能装 | **只剩这一个 skill**（39 个不再是 skill） |", "",
         "## 伞体（`SKILL.md` 正文，机械生成的部分）", "", "```markdown"] + \
        ["---", f"name: {entry_dir}", f"description: {desc or '（必须你写：这是触发词，工具不许代笔）'}", "---", ""] + \
        body + ["```", "",
                f"> `description` 由模型写（触发词是判断题）。`weave.py collapse --apply` 不带 `--description` 会拒绝执行。", "",
                "## 要执行的机械动作", "", "```bash"]
    for name, isl in dirs:
        L.append(f"mkdir -p skills/{entry_dir}/references/{name}")
        for i in isl:
            L.append(f"git mv {i.rstrip('/')} skills/{entry_dir}/references/{name}/"
                     f"{os.path.basename(i.rstrip('/'))}")
    L += ["```", "", "## 每个岛的 INDEX.md", ""]
    for name, isl in dirs:
        L += [f"### {name}", "", "```markdown", island_index_md(name, isl, byid).rstrip(), "```", ""]
    L += ["## 换口径时的注意", "",
          "- 「岛」= 互指图（谁在正文/引用里点到谁的目录名）的连通分量；口径见 `docs/contract.md` §3。",
          "- 岛数对口径敏感（同一份数据 11 / 10 / 13），报数必须连口径一起报。",
          "- 单入口的代价是**独立可装**：39 个 skill 变成 1 个 skill 的 `references/`。"
          "别的包/人想单独装其中一个就没法装了。",
          ""]
    return "\n".join(L)


def cmd_visualize(root, out):
    """把文档树落成两份给人/给 agent 看的产物：`TREE.md` + `TREE.html`。"""
    skills, skipped = [], []
    tree = walk_dir(root, root, "", tracked_set(root), skipped, skills)
    if tree is None:
        print("[visualize] FAIL 这个目录里没有任何 skill（找不到 SKILL.md）")
        return 1
    add_mentions(root, skills)
    edges = cross_skill_edges(root, skills)
    islands = islands_of(skills, edges)
    # 入口层：复用 tree 的类目/散项划分
    sr = skills_root(tree)
    entry = []
    for c in sr["children"]:
        if c["kind"] == "category":
            entry.append(("category", c["id"], sorted(x["id"] for x in _leaves(c))))
        elif c["kind"] == "skill":
            entry.append(("skill", c["id"], [c["id"]]))
    byid = {s["id"]: s for s in skills}
    over_l2 = [s for s in skills if s["est_tokens"] > 5000 or s["body_lines"] > 500]
    l1_text = "\n".join(s["description"] for s in skills)      # 与 layers 同一口径
    stats = {"skills": len(skills), "entry": len(entry), "islands": len(islands),
             "resident": est_tokens(l1_text),
             "resident_chars": sum(s["description_chars"] for s in skills),
             "over_l2": len(over_l2),
             "orphans": sum(len(s["orphans"]) for s in skills),
             "broken": sum(len(s["broken"]) for s in skills)}
    rev = _rev(root)
    os.makedirs(out, exist_ok=True)
    md = os.path.join(out, "TREE.md")
    html = os.path.join(out, "TREE.html")
    with open(md, "w", encoding="utf-8") as f:
        f.write(render_tree_md(root, skills, edges, islands, entry, rev))
    with open(html, "w", encoding="utf-8") as f:
        f.write(render_tree_html(root, skills, edges, islands, entry, rev, stats))
    print(f"[visualize] 入口层={len(entry)} 互指岛={len(islands)} 常驻={stats['resident']}tok "
          f"孤儿={stats['orphans']} 悬空={stats['broken']}")
    print(f"[visualize] 出: {md}")
    print(f"[visualize] 出: {html}")
    return 0


def _leaves(node):
    if node["kind"] == "skill":
        return [node]
    out = []
    for c in node["children"]:
        out += _leaves(c)
    return out




# ---------------------------------------------------------------- 披露链递归（层 = 披露深度）

CAP_DESC_CHARS = 1024
CAP_BODY_TOKENS = 5000
CAP_BODY_LINES = 500
CAP_FILE_BYTES = 20000
TEXT_LIKE = {".md", ".markdown", ".txt", ".py", ".sh", ".bash", ".js", ".ts", ".json",
             ".yaml", ".yml", ".csv", ".tsv", ".toml", ".ini", ".cfg", ".html", ".svg"}


def _doc_nodes(skills, root):
    """节点 = pack 里的每份文档。**根 = 每个 skill 的 `SKILL.md`**（多入口 = K 个根；单入口 = 1 个）。"""
    nodes = {}
    for s in skills:
        sk = s["id"] + "SKILL.md"
        nodes[sk] = {"path": sk, "kind": "instructions", "skill": s["id"], "root": True,
                     "bytes": s["bytes"], "tok": s["est_tokens"], "lines": s["body_lines"],
                     "desc_chars": s["description_chars"], "name": s["name"]}
        for f in s["files"]:
            if f["kind"] == "instructions" and f["path"] == "SKILL.md":
                continue                      # 这个 skill 自己的 SKILL.md 已经是根节点，别被覆盖
            n = {"path": s["id"] + f["path"], "kind": f["kind"], "skill": s["id"],
                 "root": False, "bytes": f["bytes"], "tok": None, "lines": None,
                 "desc_chars": None, "name": os.path.basename(f["path"])}
            if f["kind"] == "instructions":   # 嵌套的 SKILL.md（单入口形状下就住在 references/<岛>/ 里）
                t = read_text(os.path.join(root, n["path"]))
                meta, body, _ = parse_frontmatter(t)
                n["tok"], n["lines"] = est_tokens(t), len(body.split("\n"))
                n["desc_chars"] = len((meta.get("description") or "").strip())
                n["name"] = meta.get("name") or n["name"]
            nodes[n["path"]] = n
    return nodes


def _doc_edges(root, nodes, broken, external):
    """边 = 披露：一份文档正文里**真实点到**的另一份（先按该文件所在目录、再按 pack 根解析）。
    口径与 `analyze_skill` 一致：URL、围栏里的路径、没有目录部分的裸文件名都不算披露。"""
    out = {}
    for p, n in sorted(nodes.items()):
        if os.path.splitext(p)[1].lower() not in TEXT_LIKE:
            continue                          # 二进制/图片只报体积，不解析
        text = read_text(os.path.join(root, p))
        fenced = fence_lines(text)
        for target, line in extract_declared_refs(text, p):
            t = target.lstrip("./")
            bare = "/" not in t and t != "SKILL.md"
            if bare or line in fenced:
                continue
            skill_dir = os.path.join(root, n["skill"])
            for cand in (os.path.normpath(os.path.join(root, os.path.dirname(p), t)),
                         os.path.normpath(os.path.join(skill_dir, t)),
                         os.path.normpath(os.path.join(root, t))):
                if not cand.startswith(root):
                    continue                  # 指出 pack 外的，不算本 pack 的披露
                rel = os.path.relpath(cand, root)
                if rel in nodes:
                    out.setdefault(p, {})[rel] = line
                    break
                if os.path.exists(cand):
                    out.setdefault(p, {})[rel] = line
                    break
            else:
                # 与 `analyze_skill` 同一口径：非本 skill 的 L1 目录（references/scripts/assets/templates）
                # 或往包外走的（`../`），算 **external**（正文里提到的外部文件），不是悬空。
                if t.startswith(("../", "/")) or not t.startswith(("references/", "scripts/",
                                                                   "assets/", "templates/")):
                    external.append((p, t, line))
                else:
                    broken.append((p, t, line))
    return out


def cmd_disclosure(root, out):
    """**第二步**：以每个根文档为起点，把披露链递归展开到 L1..Ln，并逐文档体检 → `DISCLOSURE.md`。

    层 = **披露深度**（L1 = 根文档；L2 = L1 直接披露的；Ln+1 由 Ln 披露），不是文件类型那套。
    体检判据取 `docs/contract.md` §4 的 caps，按文档类型分派；跨文档查孤儿（没人披露）与悬空（披露了不存在）。"""
    skills, skipped = [], []
    tree = walk_dir(root, root, "", tracked_set(root), skipped, skills)
    if tree is None:
        print("[disclosure] FAIL 这个目录里没有任何 skill（找不到 SKILL.md）")
        return 1
    nodes = _doc_nodes(skills, root)
    broken, external = [], []
    edges = _doc_edges(root, nodes, broken, external)
    roots = sorted(p for p, n in nodes.items() if n["root"])

    depth, frontier = {}, list(roots)
    for p in roots:
        depth[p] = 1
    while frontier:
        nxt = []
        for p in frontier:
            for q in sorted(edges.get(p, {})):
                if q not in depth:
                    depth[q] = depth[p] + 1
                    nxt.append(q)
        frontier = nxt
    for p in nodes:                            # 没被任何根披露到的文档 = 到不了 → 记 None
        depth.setdefault(p, None)
    indeg = collections.Counter()
    for p, ts in edges.items():
        for q in ts:
            indeg[q] += 1

    def cap_of(n):
        if n["root"] or n["kind"] == "instructions":
            over = []
            if n["tok"] > CAP_BODY_TOKENS:
                over.append(f"正文 {n['tok']} tok > {CAP_BODY_TOKENS}")
            if n["lines"] > CAP_BODY_LINES:
                over.append(f"正文 {n['lines']} 行 > {CAP_BODY_LINES}")
            if (n["desc_chars"] or 0) > CAP_DESC_CHARS:
                over.append(f"description {n['desc_chars']} 字符 > {CAP_DESC_CHARS}")
            return over
        if n["kind"] in ("binary",):
            return []
        if n["bytes"] > CAP_FILE_BYTES:
            return [f"{n['bytes']} B > {CAP_FILE_BYTES} B"]
        return []

    over_all, orphan_all = [], []
    for p, n in sorted(nodes.items()):
        n["over"] = cap_of(n)
        n["orphan"] = (not n["root"]) and indeg.get(p, 0) == 0
        n["depth"] = depth[p]
        if n["over"]:
            over_all.append((p, n["over"]))
        if n["orphan"]:
            orphan_all.append(p)

    lv = collections.defaultdict(list)
    for p, n in nodes.items():
        lv[n["depth"]].append(p)
    levels = sorted(lv, key=lambda x: (x is None, x))
    # 根选择层（L1）的近重复：Agent 靠 description 选根，所以这一层单独查「同层抢题」
    dup = []
    descs = {p: (nodes[p].get("name") or "") + " " + (next((s["description"] for s in skills
             if s["id"] == nodes[p]["skill"]), "")) for p in roots}
    for i, a in enumerate(roots):
        for b in roots[i + 1:]:
            r = difflib.SequenceMatcher(None, descs[a], descs[b]).ratio()
            if r >= 0.5:
                dup.append((round(r, 3), a, b))

    L = [f"# 披露链 · {os.path.basename(root)}", "",
         "## 术语表", "",
         "- **文档 / 节点**：一份文件（`SKILL.md`、`references/*.md`、`scripts/*.py` 各算一份）。",
         "- **根**：起点文档 = 一个 skill 的 `SKILL.md`。**根有几个 = 形状**（1 个 = 单入口，K 个 = 多入口）。",
         "- **披露**：一份文档正文里真的写出了另一份文档的路径。**不算**披露：URL、代码围栏里的示例路径、没有目录的裸文件名。",
         "- **L1/L2/…**：离根几步。根 = L1，根披露的 = L2，依次往下。",
         "- **fanout**：这份文档披露了几份别的文档（某一层「摆出几项」= 该层各文档 fanout 之和）。",
         "- **到不了根**：从任何根顺着披露都走不到它（没有任何文档点到它）。",
         "- **超限**：超过它那类的上限（正文 ≥5000 tok 或 >500 行 · description >1024 字符 · 资源文件 >20000 B）。",
         "- **悬空**：写了像本 pack 内的路径，但那个文件不存在。",
         "- **external**：正文里提到的本 pack 之外的文件（不算披露、也不算错）。",
         "- **近重复**：同层两份文档太像，Agent 会选错。", "",
         "口径：**层 = 披露深度**（L1 = 根文档 `SKILL.md`；L2 = L1 正文直接点到的文档；Ln+1 由 Ln 披露）。"
         "不是「按文件类型分三级」那套。", "",
         f"- 根：**{len(roots)} 个**（每个 skill 的 `SKILL.md` 是一个根；1 个 = 单入口形状）",
         f"- 文档节点：**{len(nodes)} 份** · 层数：**{len([x for x in levels if x is not None])}**",
         f"- 超限：**{len(over_all)}** 份 · 到不了根：**{len(orphan_all)}** 份 · "
         f"悬空引用：**{len(broken)}** 条 · 外部引用（不算披露）：**{len(external)}** 条",
         f"- 根选择层近重复（Jaccard≥0.5·靠 description 选根才算）：**{len(dup)}** 对", ""]
    for d in levels:
        if d is None:
            L += ["## 到不了的文档（没有任何根披露到它们）", ""]
        else:
            L += [f"## L{d}（{len(lv[d])} 份）", ""]
        L += ["| 文档 | fanout（披露几项） | 体积 | 判定 |", "|---|---|---|---|"]
        for p in sorted(lv[d]):
            n = nodes[p]
            size = (f"{n['tok']} tok / {n['lines']} 行" if n["tok"] is not None else f"{n['bytes']} B")
            bad = []
            if n["over"]:
                bad.append("⚠️ 超限 " + "; ".join(n["over"]))
            if n["orphan"]:
                bad.append("⚠️ 孤儿")
            if any(b[0] == p for b in broken):
                bad.append("❌ 有悬空引用")
            if n["root"]:
                bad.append("根")
            L.append(f"| `{p}` | {len(edges.get(p, {}))} | {size} | {' · '.join(bad) or '✅'} |")
        L.append("")
    if dup:
        L += ["### 根选择层近重复", ""] + [f"- {r} `{a}` ↔ `{b}`" for r, a, b in sorted(dup, reverse=True)] + [""]
    if broken:
        L += ["### 悬空引用", ""] + [f"- `{p}:{ln}` → `{t}`（不存在）" for p, t, ln in broken] + [""]
    if over_all:
        L += ["### 超限清单（带超多少）", ""] + [f"- `{p}` — " + "; ".join(o) for p, o in over_all] + [""]
    L += ["## 口径", "",
          "- 披露 = 正文里真实点到的另一份文档（先按该文件所在目录、再按 pack 根解析）；"
          "URL、围栏里的路径、没有目录部分的裸文件名都不算。",
          f"- caps（出处 `docs/contract.md` §4）：正文 <{CAP_BODY_TOKENS} tok / ≤{CAP_BODY_LINES} 行 · "
          f"description ≤{CAP_DESC_CHARS} 字符 · 单份文件 ≤{CAP_FILE_BYTES} B。",
          "- 每个文档在表里恰好出现一次（由命令自己核对：节点数 == 表行数）。", ""]

    os.makedirs(out, exist_ok=True)
    md = os.path.join(out, "DISCLOSURE.md")
    rows = sum(len(lv[d]) for d in levels)
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    with open(os.path.join(out, "disclosure.json"), "w", encoding="utf-8") as f:
        json.dump({"roots": roots, "levels": {str(k): sorted(v) for k, v in lv.items()},
                   "nodes": {p: {k: v for k, v in n.items()} for p, n in nodes.items()},
                   "edges": {p: ts for p, ts in edges.items()}, "broken": broken, "external": external,
                   "over": over_all, "orphans": orphan_all, "root_near_dup": dup},
                  f, ensure_ascii=False, indent=1, sort_keys=True)
    assert rows == len(nodes), f"对账失败：表行数 {rows} != 节点数 {len(nodes)}"
    print(f"[disclosure] 根 {len(roots)} 个（=形状）· 层 " +
          " → ".join(f"L{d}={len(lv[d])}" if d is not None else f"未分层={len(lv[d])}" for d in levels) +
          f" · 文档 {len(nodes)} 份（表行数 {rows} 对账 ✅）· 超限 {len(over_all)} · "
          f"到不了根 {len(orphan_all)} · 悬空 {len(broken)} · external {len(external)}")
    print(f"[disclosure] 出: {md}")
    return 0


def _clone_copy(pack, dest):
    """拷贝一份副本。macOS 走 APFS clonefile（`cp -Rc`，秒级、几乎不占额外空间），不支持就退回 `cp -R`。"""
    r = subprocess.run(["cp", "-Rc", pack, dest], capture_output=True, text=True)
    if r.returncode == 0:
        return "cp -Rc（clonefile）"
    subprocess.run(["cp", "-R", pack, dest], check=True, capture_output=True)
    return "cp -R（本机不支持 clonefile，整份拷）"


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


def cmd_prepare(pack, out, dest=None, shape=None, description=None):
    """第一步：把「一整个目录的 skill」变成一份**可回滚、可对账**的工作副本。

    ① clonefile 拷贝（原目录只读，不碰）；② 副本里确保由 git 管（自带 git 就摘 remote + 记起点，
    没有就 `git init` + `.gitignore` + 初始 commit）；③ 量副本、推导 L1（互指图的连通分量 = 岛）；
    ④ 出 `BASELINE.md`：副本路径 · 副本 rev · 推导的 L1 · **两种形状（单入口/多入口）同口径的账** ·
    待用户选定的形状。

    形状必须用户定：`--shape single|multi` 用来记下选择；不填就留 ⏳ 待选。
    """
    pack = os.path.abspath(pack.rstrip("/"))
    if not os.path.isdir(pack):
        print(f"[prepare] FAIL 目录不存在: {pack}")
        return 1
    if shape not in (None, "single", "multi"):
        print("[prepare] FAIL --shape 只能是 single 或 multi")
        return 2
    name = os.path.basename(pack)
    dest = os.path.abspath(dest or os.path.join(tempfile.gettempdir(), "planweave-" + name))
    if os.path.exists(dest):
        print(f"[prepare] FAIL 副本已存在，不覆盖: {dest}（换 --dest 或先删掉它）")
        return 2
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    how = _clone_copy(pack, dest)
    log = [f"副本：`{dest}`（{how}）· 原目录只读，未动"]
    rev = _ensure_git_copy(dest, log)

    skills, skipped = [], []
    tree = walk_dir(dest, dest, "", tracked_set(dest), skipped, skills)
    if tree is None:
        print("[prepare] FAIL 副本里没有任何 skill（找不到 SKILL.md）")
        return 1
    add_mentions(dest, skills)
    edges = cross_skill_edges(dest, skills)
    islands = islands_of(skills, edges)
    dirs = island_dirs(_default_entry_dir(dest), skills, islands)
    byid = {s["id"]: s for s in skills}
    resident = est_tokens("\n".join(s["description"] for s in skills))
    body_tok = est_tokens("\n".join(umbrella_body(dirs, byid)))
    idx_tok = sum(est_tokens(island_index_md(n, i, byid)) for n, i in dirs)

    L = [f"# BASELINE · {name}（PlanWeave 第一步的产物）", "",
         f"生成：`weave.py prepare`。**这份文件是后面每一步的对账基准。**", "",
         "## 工作副本", ""] + [f"- {x}" for x in log] + [
         f"- 成员口径：{'git 跟踪' if tracked_set(dest) is not None else '非 git 目录，全部算成员'}"
         f"（未跟踪的 skill 形目录 {len(skipped)} 个）", "",
         "## 输入是什么", "",
         f"- **{len(skills)} 个 skill** · 入口层摆出 **{len(first_layer_entries(tree))} 项**"
         f" · 常驻菜单 {resident} tok（{len(skills)} 条 description）",
         "- 推导的 L1（= 互指图的连通分量，不是人分的类）：**%d 个岛**" % len(islands), ""]
    for n, (dn, isl) in enumerate(dirs, 1):
        L.append(f"  {n}. `{dn}` — {len(isl)} 个：{', '.join(byid[i]['name'] for i in isl[:8])}"
                 f"{' …' if len(isl) > 8 else ''}")
    L += ["", "## 两种形状，同口径的账（请选一个）", "",
          f"**A 单入口**：推导的 L1 降为 L2，L1 = 1 条 description。",
          f"  常驻 {resident} → **{est_tokens(description or '')} tok**（那条 description 还没定；由 agent 起草、你确认）· "
          f"第一次点击 1 项 · 第二次点击 {len(dirs)} 项（伞体 {body_tok} tok）· "
          f"第三次点击 {len(skills)} 项（各岛 INDEX 合计 {idx_tok} tok）· "
          f"**独立可装 {len(skills)} → 1**",
          f"**B 多入口**：直接用推导的 L1。",
          f"  常驻 {resident} tok 不变 · 第一次点击 {len(first_layer_entries(tree))} 项"
          f"（或按岛重排成 {len(dirs)} 项）· 独立可装仍是 {len(skills)}",
          "",
          f"## 形状：{'**' + ('A 单入口' if shape == 'single' else 'B 多入口') + '**（已定）' if shape else '⏳ 待用户选'}",
          "",
          "定了形状再进第二步（改结构）。形状没定之前，不动副本里的任何文件。", ""]
    os.makedirs(out, exist_ok=True)
    md = os.path.join(out, "BASELINE.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"[prepare] 副本 {dest} · rev {rev} · skill {len(skills)} · 入口层 {len(first_layer_entries(tree))} 项 "
          f"· 推导的 L1 = {len(dirs)} 个岛 · 常驻 {resident} tok")
    print(f"[prepare] 形状：{'A 单入口' if shape == 'single' else ('B 多入口' if shape == 'multi' else '⏳ 待用户选')}")
    print(f"[prepare] 出: {md}")
    return 0


def first_layer_entries(tree):
    """入口层摆出几项（tree 口径，与 layers 一致）。"""
    return [c["id"] for c in skills_root(tree)["children"] if c["kind"] in ("skill", "category")]


def cmd_collapse(root, out, apply_changes=False, description=None, entry_dir=None):
    """把 pack 塌成「L1 = 1 个 skill 入口」：**默认 dry-run**，写一份 `COLLAPSE.md`（数字 + 伞体 + 要跑的 git mv）。

    分工：机械的（搬目录、生成伞体与各岛 `INDEX.md`）工具做；**那一条 description 必须人来写**——
    它是唯一的常驻触发词，是判断题。所以没 `--description` 时 `--apply` 直接拒绝，不生成半成品。
    """
    skills, skipped = [], []
    tree = walk_dir(root, root, "", tracked_set(root), skipped, skills)
    if tree is None:
        print("[collapse] FAIL 这个目录里没有任何 skill（找不到 SKILL.md）")
        return 1
    add_mentions(root, skills)
    edges = cross_skill_edges(root, skills)
    islands = islands_of(skills, edges)
    entry = entry_dir or _default_entry_dir(root)
    dirs = island_dirs(entry, skills, islands)
    before = {"skills": len(skills), "entry": len(first_layer_entries(tree)),
              "resident": est_tokens("\n".join(s["description"] for s in skills)),
              "rev": _rev(root)}
    os.makedirs(out, exist_ok=True)
    md = os.path.join(out, "COLLAPSE.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write(render_collapse_md(root, skills, edges, islands, dirs, entry, description, before))
    print(f"[collapse] 现在: L1 {before['entry']} 项 / 常驻 {before['resident']} tok → "
          f"单入口: L1 1 项 / L2 {len(dirs)} 项（岛）/ L3 {len(skills)} 篇")
    print(f"[collapse] 出: {md}")
    if not apply_changes:
        print("[collapse] dry-run：盘上未改任何文件（加 --apply --description \"...\" 才落盘）")
        return 0
    if not description:
        print("[collapse] 拒绝执行：--description 必填 —— 那一条 description 是唯一的常驻触发词，工具不许代笔")
        return 2

    byid = {s["id"]: s for s in skills}
    for name, isl in dirs:
        ddir = os.path.join(root, "skills", entry, "references", name)
        os.makedirs(ddir, exist_ok=True)
        for i in isl:
            src = i.rstrip("/")
            dst = f"skills/{entry}/references/{name}/{os.path.basename(src)}"
            g = git(root, "mv", src, dst)
            if g is None or g.returncode != 0:
                shutil.move(os.path.join(root, src), os.path.join(root, dst))
        with open(os.path.join(ddir, "INDEX.md"), "w", encoding="utf-8") as f:
            f.write(island_index_md(name, isl, byid))
    head = ("---\nname: %s\ndescription: %s\n---\n\n# %s\n\n" % (entry, description.strip(), entry))
    with open(os.path.join(root, "skills", entry, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(head + "\n".join(umbrella_body(dirs, byid)) + "\n")
    # 落盘后回读：技能数必须是 1、入口层必须是 1
    skills2, skipped2 = [], []
    tree2 = walk_dir(root, root, "", tracked_set(root), skipped2, skills2)
    n_entry = len(first_layer_entries(tree2)) if tree2 else -1
    ok = (len(skills2) == 1 and n_entry == 1)
    print(f"[collapse] 落盘后回读：技能 {len(skills2)} 个 · 入口层 {n_entry} 项 —— "
          f"{'✅' if ok else '❌ 没塌成单入口'} · 岛 {len(dirs)} 个 · 各岛 INDEX.md 已写")
    return 0 if ok else 1


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
            # 假密钥**运行时拼出来**：文件里不留像真 key 的字面量 —— 否则安全扫描会把本工具
            # 自己判成「凭证泄漏」（实测撞过：scan 判 dangerous，Hermes 拒绝安装）。
            f.write("见 /Users/someone/project/x.md\nkey = " + "s" + "k-" + "A" * 24 + "\n")
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
        # 提案器：这个 fixture 只有一个 skill、L1=1 项、正文很小 —— 正确行为是**一条都不提**（不误报）
        out5 = os.path.join(tmp, "o5")
        assert cmd_propose(pack, out5) == 0
        pr = json.load(open(os.path.join(out5, "proposals.json")))
        assert pr["count"] == 0, pr["proposals"]
        assert os.path.isfile(os.path.join(out5, "PROPOSALS.md"))
        # 跨命令口径对拍：layers 的 token 单口径必须与 audit 一致（两边不一致就是自相矛盾）
        assert cmd_layers(pack, out5) == 0 and cmd_audit(pack, out5) == 0
        l2 = json.load(open(os.path.join(out5, "layers.json")))["L2"]["over_token"]
        au = [r["id"] for r in json.load(open(os.path.join(out5, "audit.json")))["size"] if r["over_token"]]
        assert l2 == au, (l2, au)
        # 可视化：两份产物都要出，且每个 skill 在互指图上正好一个点（丢节点就是画错了）
        assert cmd_visualize(pack, out5) == 0
        mdv = open(os.path.join(out5, "TREE.md"), encoding="utf-8").read()
        htv = open(os.path.join(out5, "TREE.html"), encoding="utf-8").read()
        assert "notes/demo/" in mdv and "demo" in htv, (mdv[:200], htv[:200])
        assert htv.count("<circle") == 1, htv.count("<circle")
        # 第二步 disclosure：层 = 披露深度；每个文档恰好出现一次；超限带「超多少」
        out8 = os.path.join(tmp, "o8")
        assert cmd_disclosure(pack, out8) == 0
        dj = json.load(open(os.path.join(out8, "disclosure.json")))
        assert len(dj["roots"]) == 1, dj["roots"]                       # fixture 只有一个 skill → 1 个根
        assert str(1) in dj["levels"] and dj["levels"]["1"] == dj["roots"], dj["levels"]
        dm = open(os.path.join(out8, "DISCLOSURE.md"), encoding="utf-8").read()
        assert "L1（1 份）" in dm and "口径：**层 = 披露深度**" in dm, dm[:200]
        assert dj["levels"].get("2"), "demo 的 references/guide.md 应该在 L2"    # guide.md 被点名
        # 第一步 prepare：非 git 的输入 → 副本由 git 管、原目录不被碰、BASELINE.md 出两种形状的账
        out7 = os.path.join(tmp, "o7")
        dest7 = os.path.join(tmp, "ws", "pack")
        assert cmd_prepare(pack, out7, dest=dest7) == 0
        assert os.path.isdir(os.path.join(dest7, ".git")), "副本没有被 git 管"
        assert git(dest7, "log", "--oneline").stdout.strip(), "副本没有起点 commit"
        assert not os.path.exists(os.path.join(pack, ".git")), "原目录被动了"
        base = open(os.path.join(out7, "BASELINE.md"), encoding="utf-8").read()
        assert "A 单入口" in base and "B 多入口" in base and "待用户选" in base, base[:200]
        assert cmd_prepare(pack, out7, dest=dest7) == 2, "副本已存在时必须拒绝覆盖"
        # 单入口方案：干跑必须算出 L1=1；--apply 不给 description 必须拒绝（不许生成半成品）
        out6 = os.path.join(tmp, "o6")
        assert cmd_collapse(pack, out6) == 0
        cm = open(os.path.join(out6, "COLLAPSE.md"), encoding="utf-8").read()
        assert "L1  1 项" in cm and "notes/demo" in cm, cm[:200]
        assert cmd_collapse(pack, out6, apply_changes=True) == 2      # 缺 description → 拒绝
        assert cmd_collapse(pack, out6, apply_changes=True, description="演示：把 demo 收成一个入口。") == 0
        print("[self-test] ✅ 层（pack→类目→skill）/ 折叠 description / 孤儿 / 悬空 / "
              "围栏内标题 / 两次一致 / 硬编码路径 / 内嵌密钥 / 提案器四类动作 / "
              "layers↔audit 口径对拍 —— 全过")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
