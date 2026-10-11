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
import fnmatch
import time
import sys
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
# 路径字符集含非 ASCII：包里的文件名可能是中文（实测 Loomerto 的段落文件），
# 只认 ASCII 会让这些文件被判成「到不了根」——那是工具的盲点，不是包的问题。
PATH_RE = re.compile(
    r"(?:[A-Za-z0-9_./-]|[\u0080-\uffff])+\.(?:md|markdown|py|sh|bash|js|ts|json|ya?ml|txt|csv|tsv|toml|ini|cfg|png|jpe?g|svg|gif|html|pdf)\b")
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
                    choices=["tree", "layers", "checks", "audit", "propose", "judge", "score", "visualize",
                             "collapse", "prepare", "disclosure", "dispatch", "verify", "apply"])
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
    n_skills = len(skills)
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
         f"| 独立可装 | 每个 skill 各自能装 | **只剩这一个 skill**（其余 {n_skills} 个不再是 skill） |", "",
         "## 伞体（`SKILL.md` 正文，机械生成的部分）", "", "```markdown"] + \
        ["---", f"name: {entry_dir}", f"description: {desc or '（待写：这是触发词，由模型定，工具不代笔）'}", "---", ""] + \
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
          f"- 单入口的代价是**独立可装**：{n_skills} 个 skill 变成 1 个 skill 的 `references/`。"
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


def nearest_skill_dir(root, rel):
    """从某份文档出发向上找最近的含 `SKILL.md` 的目录，返回绝对路径；找不到返回 None。
    用途：单入口形状下正文住在 `references/<岛>/<skill>/`，里面写 `references/x.md` 是按**它自己的根**写的。"""
    d = os.path.dirname(rel)
    while True:
        if d and os.path.isfile(os.path.join(root, d, "SKILL.md")):
            return os.path.join(root, d)
        if not d:
            return None
        d = os.path.dirname(d)


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
            raw = target
            t = target[2:] if target.startswith("./") else target   # 只去一个前导 `./`
            bare = "/" not in t and t != "SKILL.md"
            if bare or line in fenced:
                continue
            skill_dir = os.path.join(root, n["skill"])
            for cand in (os.path.normpath(os.path.join(root, os.path.dirname(p), t)),
                         os.path.normpath(os.path.join(skill_dir, t)),
                         # 最近的 SKILL.md 所在目录：嵌套 skill 的相对引用是按**它自己的根**写的
                         os.path.normpath(os.path.join(nearest_skill_dir(root, p) or "\0none", t)),
                         os.path.normpath(os.path.join(root, t))):
                if cand is None:
                    continue
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
                if raw.startswith(("../", "/")) or not t.startswith(("references/", "scripts/",
                                                                     "assets/", "templates/")):
                    external.append((p, raw, line))
                else:
                    broken.append((p, raw, line))
    return out



def _read_waivers(root):
    """包内的**免检表**：`<pack>/.skillweave/waivers.txt`，一行一条 `<glob>  <理由>`（`#` 开头是注释）。

    为什么放包里不放工具里：「哪张 png 是给人看的」「哪个 json 是测试留档」是**包主的判断**，
    不是通用真理。工具只负责匹配 + 标豁免 + 单独计数。"""
    p = os.path.join(root, ".skillweave", "waivers.txt")
    out = []
    if os.path.isfile(p):
        for ln in read_text(p).split("\n"):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            parts = re.split(r"\s{2,}|\t+", ln, 1)
            out.append((parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""))
    return out


def _waived(path, waivers):
    """glob 匹配路径本身、或路径尾部、或纯文件名（写 `test-*.json` 这种就按名字匹配）。"""
    for g, why in waivers:
        if (fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, "*/" + g)
                or fnmatch.fnmatch(os.path.basename(path), g)):
            return why or "（未写理由）"
    return None


ACTION = {
    "超限": ("拆成多份（拆分方案交模型判断，按主题切不按标题切）", "待模型"),
    "到不了根": ("判：该被引用（加一条引用）· 该删 · 还是刻意的（免检）", "待模型"),
    "悬空": ("**先判**：包内路径写错（改路径）· 还是在说包外文件（免检）→ 再动手", "待模型"),
    "近重复": ("合并 / 改写其中一条 description", "待模型"),
}


def render_todo_md(root, nodes, over_all, orphan_all, broken, dup, waivers):
    # 返回 (文本, 待办数, 豁免数)：打印与表头都取这里的数，避免两处各算一遍对不上
    """一张能照着做的清单：每条 = 文档 · 问题 · 数字 · 建议动作 · 谁判。豁免的单列一栏。"""
    todo, waived = [], []

    def add(kind, path, num, action, who, extra=""):
        why = _waived(path, waivers)
        if not why and extra:                      # 近重复那条有两个路径，任一中豁免都算豁免
            why = _waived(extra, waivers)
        row = {"kind": kind, "path": path, "num": num, "action": action, "who": who, "why": why}
        (waived if why else todo).append(row)

    for p, o in over_all:
        a, who = ACTION["超限"]
        add("超限", p, "; ".join(o), a, who)
    for p in orphan_all:
        a, who = ACTION["到不了根"]
        add("到不了根", p, f"{nodes[p]['bytes']} B", a, who)
    by_file = collections.defaultdict(list)
    for p, t, ln in broken:
        by_file[p].append((ln, t))
    for p, items in sorted(by_file.items()):
        a, who = ACTION["悬空"]
        items = sorted(items)
        ex = " · ".join(f"{ln}: `{t}`" for ln, t in items[:3]) + (" …" if len(items) > 3 else "")
        add("悬空", p, f"{len(items)} 条（{ex}）", a, who)
    for r, a_, b_ in dup:
        a, who = ACTION["近重复"]
        add("近重复", f"{a_} ↔ {b_}", f"相似度 {r}", a, who, extra=b_)

    L = [f"# 待办 · {os.path.basename(root)}", "",
         "由 `weave.py disclosure` 生成。术语见 `DISCLOSURE.md` 头部术语表。", "",
         f"- **待办 {len(todo)} 条**（机械可判 {sum(1 for r in todo if r['who'] == '机械可判')} · "
         f"待模型 {sum(1 for r in todo if r['who'] == '待模型')}）",
         f"- **已豁免 {len(waived)} 条**（按包里 `.skillweave/waivers.txt`，共 {len(waivers)} 条规则）", "",
         "## 待办（照着做）", "",
         "| # | 文档 | 问题 | 数字 | 建议动作 | 谁判 |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(todo, 1):
        L.append(f"| {i} | `{r['path']}` | {r['kind']} | {r['num']} | {r['action']} | {r['who']} |")
    if not todo:
        L.append("| — | — | — | — | 没有待办 | — |")
    L += ["", "## 已豁免（匹配了 waivers.txt，不动它）", "",
          "| 文档 | 问题 | 数字 | 理由 |", "|---|---|---|---|"]
    for r in waived:
        L.append(f"| `{r['path']}` | {r['kind']} | {r['num']} | {r['why']} |")
    if not waived:
        L.append("| — | — | — | 没有命中豁免规则 |")
    L += ["", "## 免检表长什么样（`<pack>/.skillweave/waivers.txt`）", "",
          "```",
          "# 一行一条：<glob>  两个以上空格  理由（# 开头是注释）",
          "*/assets/*.png             给人看的图，Agent 不读",
          "*/test-prompts.json        测试留档，本来就不该被披露",
          "```", "",
          "豁免是**包主的判断**，写在包里、工具只匹配；没写规则的按上面的建议动作办。", ""]
    return "\n".join(L), len(todo), len(waived)


# ────────────────────────── 派发与验收（第三步的机械部分） ──────────────────────────
# 口径（docs/contract.md §8）：
#   · 派发前**事实补全**：能从树里查到的（目标候选路径、兄弟文件、文件行数）先算好塞进 prompt，
#     让子代理「验路径」而不是「猜路径」——这是第一次成功率的大头。
#   · 单位 = skill 子树；批次间文件集合两两不相交（断言）。
#   · 重派不许打转：prompt hash 相同就拒绝重派；每级换的是输入（R1 证据 → R2 减粒度 → R3 喂事实 →
#     R4 换执行者 → R5 落 PARKED.md）。
#   · 计数在文件里（dispatch/state.json），不在谁的记忆里。

def _scan_fresh(root, tag="scan"):
    """跑一遍 disclosure 到临时目录再读回 —— 复用同一条代码路径，避免两套算法漂移。"""
    tmp = tempfile.mkdtemp(prefix=f"skillweave-{tag}-")
    if cmd_disclosure(root, tmp) != 0:
        return None, tmp
    with open(os.path.join(tmp, "disclosure.json"), encoding="utf-8") as f:
        return json.load(f), tmp


def _item_id(kind, path):
    """条目 id：**按 (kind, path)**，不带行号 —— 同一个文件里的多条悬空是一件事，
    与 TODO.md 的行口径一致（悬空按文件聚合），也让 id 在行号漂移后保持稳定。"""
    return f"{kind}-{hashlib.sha1(path.encode()).hexdigest()[:8]}"


def _findings(dj, root):
    """把 disclosure.json 里的发现拉平成 {id: {...}}，id 稳定（kind + path:line 的短 hash）。"""
    F = {}

    def add(kind, path, num):
        i = _item_id(kind, path)
        F[i] = {"id": i, "kind": kind, "path": path, "num": num, "refs": [], "target": "",
                "owner": _owner_of(path, dj, root), "who": "待模型"}

    for p, o in dj["over"]:
        add("超限", p, "; ".join(o))
    for p in dj["orphans"]:
        add("到不了根", p, f"{dj['nodes'][p]['bytes']} B")
    for src, tgt, ln in dj["broken"]:                     # 同一文件的多条悬空 = 一件事
        it = F.get(_item_id("悬空", src)) or (add("悬空", src, "") or F[_item_id("悬空", src)])
        it["refs"].append({"line": ln, "target": tgt})
    for i in list(F):
        if F[i]["kind"] == "悬空" and F[i]["refs"]:
            F[i]["num"] = f"{len(F[i]['refs'])} 条引用"
    for r, a, b in dj.get("root_near_dup", []):
        add("近重复", a, f"相似度 {r}")
        F[_item_id("近重复", a)]["target"] = b
    return F


def _owner_of(path, dj, root):
    """文件归属哪个 skill = 最长前缀匹配的 SKILL.md 所在目录；没匹配上归伞/包根。"""
    cands = [p for p in dj["nodes"] if p.endswith("SKILL.md") and path.startswith(os.path.dirname(p) + "/")]
    if cands:
        return max(cands, key=len)
    return path if path.endswith("SKILL.md") else "(pack)"


def _doc_inbound(dj, path):
    n = sum(1 for _s, ts in dj["edges"].items() if path in ts)
    return n


def _pack_files(root):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in (".git", ".skillweave")]
        for fn in fns:
            out.append(os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, "/"))
    return out


def _facts_for(item, root, dj, files):
    """**事实补全**：把能从树/包里查到的机械事实算出来，喂给子代理。判断留给它。"""
    lines = read_text(os.path.join(root, item["path"])).split("\n") if \
        os.path.isfile(os.path.join(root, item["path"])) else [""]
    if item["kind"] == "悬空":
        out = {}
        for r in item["refs"]:
            base = os.path.basename(r["target"])
            cands = sorted(p for p in files if os.path.basename(p) == base)
            out[f"第 {r['line']} 行 `{r['target']}`"] = cands or ["（包内没有同名文件 —— 可能是包外文件，判豁免）"]
            out[f"第 {r['line']} 行原文"] = lines[r["line"] - 1].strip() if 0 < r["line"] <= len(lines) else "?"
        return out
    if item["kind"] == "到不了根":
        sibs = sorted(p for p in dj["nodes"]
                      if os.path.dirname(p) == os.path.dirname(item["path"]) and p != item["path"])
        return {"同目录兄弟（谁被披露了照它办）": sibs or ["（没有兄弟）"],
                "首行": next((l for l in lines if l.strip()), "")}
    if item["kind"] == "近重复":
        return {"与谁重": item["target"], "本文件 description 首句": next((l for l in lines if l.strip()), "")}
    if item["kind"] == "超限":
        hs = [l for l in lines if re.match(r"^##?\s", l)]
        return {"二级标题（拆分只能按主题切，标题只是线索）": hs[:20] or ["（没有二级标题）"],
                "行数": len(lines)}
    return {}


def _prompt_for(batch, root, F, files, dj, base_rev, pack):
    rules = f"""# 派发批次 {batch['id']} · skill 子树

你是 SkillWeave 的修复执行者。**只产出提案，不要写盘、不要改仓库、不许开后台进程**。
仓库副本：`{root}`（git rev `{base_rev}`）。你的范围只有下面列出的 skill：

{chr(10).join('- `' + s + '`' for s in batch['skills'])}

## 铁律
1. 只改**引用路径**与**拆分**，不改文义、不加新内容、不删没让你删的。
2. 改动必须**逐条**对应下面的条目 id：每条回一个对象，不许合并、不许漏。
3. **删引用**必须给理由码：`external`（在说包外文件）· `obsolete`（内容已失效）· `typo-fixed`（拼错，已改对）。
   标 `external` 的会要求进免检表；标 `obsolete` 的一律不自动通过。
4. **拆分**：按**主题**切，不按标题机械切；拆分必须给 `parts`（new_path → 正文），
   且拆完每个新文件都要被该 skill 的 `SKILL.md` 披露（否则它立刻变成新的「到不了根」）。
   拆分只允许「搬家」：删掉空行与标题行后，原文的字符序列必须等于各 part 拼接 —— 不许重写。
5. 判不了的（该删还是该留、拆几份）→ 回 `"verdict": "parked"` + 理由，**不要硬做**。

## 输出（严格 JSON，一个对象，不要解释）
```json
{{"batch": "{batch['id']}", "results": [
  {{"id": "条目id", "verdict": "fixed|waived|parked",
    "edits": [{{"file": "相对路径", "line": 12, "before": "原行逐字", "after": "新行"}}],
    "parts": {{"新文件相对路径": "正文"}},
    "reason_code": "external|obsolete|typo-fixed|",
    "reason": "一句话"}}]}}
```

## 条目与事实（事实已替你查好；据此判断，不要另猜）
"""
    body = [rules]
    for it in batch["items"]:
        f = _facts_for(it, root, dj, files)
        body.append(f"### `{it['id']}` · {it['kind']} · `{it['path']}`"
                    + (f" → `{it['target']}`" if it["target"] else "")
                    + (f"（{it['num']}）" if it["num"] else "") + "\n")
        for k, v in f.items():
            body.append(f"- {k}: " + ("; ".join(f"`{x}`" for x in v) if isinstance(v, list) else f"`{v}`"))
    return "\n".join(body) + "\n"



# ────────────────────────── D 阶段落盘器 ──────────────────────────
# 规格见 docs/flow.md 第三节 D：
#   · 锚点校验：待改文本必须落在声明行 ±3 行内，逐字相同；不做模糊替换。
#   · 白名单：只允许改「本条目自己的文件」「披露它的父文档」「该 skill 的入口 SKILL.md」，
#     拆分产生的新文件必须落在同 skill 目录下。
#   · 拆分守恒：去掉空行与标题行后的字符序列必须与原文一致，只搬移不重写。
#   · 豁免规则白名单：新增的 waivers 规则只允许命中本条目自己的文件，不许顺带命中别的 skill。
#   · 逐条 patch 记录：写在 dispatch/patches.json，回退粒度 = 单条。
#   · obsolete 不自动通过，落 PARKED.md；parked 原样记录不改盘。

APPLY_FAILS = []


def lines_of(root, path):
    return read_text(os.path.join(root, path)).split("\n")


def _plan_items(out):
    """从 dispatch/plan.json 读条目表，返回 {id: item}。"""
    p = os.path.join(out, "plan.json")        # out = 那个 dispatch 目录
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        plan = json.load(f)
    return {it["id"]: it for b in plan["batches"] for it in b["items"]}


def _allowed_files(item, dj):
    """本条目允许改动的文件集合：它自己 + 披露它的父文档 + 该 skill 的入口 SKILL.md。"""
    allowed = {item["path"]}
    for src, ts in dj.get("edges", {}).items():
        if item["path"] in ts:
            allowed.add(src)
    if item["owner"] and item["owner"] != "(pack)":
        allowed.add(item["owner"])
    return allowed


def _find_anchor(lines, want, at):
    """在 at 的 ±3 行内找与 want 逐字相同的行，返回行号（1 起）或 None。"""
    w = want.strip()
    for i in range(max(0, at - 4), min(len(lines), at + 3)):
        if lines[i].strip() == w:
            return i + 1
    return None


def _apply_item(root, item, res, dj, waivers):
    """校验并落盘一条提案。返回 (ok, note, patch)。任一步不通过就整条不动。"""
    if res.get("verdict") == "parked":
        return True, "parked：由提案方标记为不处理", None
    if res.get("reason_code") == "obsolete":
        return True, "obsolete：不自动通过，记 PARKED", None
    edits = res.get("edits") or []
    parts = res.get("parts") or {}
    waived_only = res.get("verdict") == "waived" or res.get("reason_code") == "external"
    if not edits and not parts and not waived_only:
        return False, "既没有 edits 也没有 parts", None
    allowed = _allowed_files(item, dj)
    # 逐文件先在内存里算好改动，全部通过才写盘
    plan_writes, plan_deletes = {}, {}
    patch = {"id": item["id"], "kind": item["kind"], "files": [], "parts": [], "removed": [],
             "waiver_rule": None, "reason_code": res.get("reason_code", ""),
             "reason": res.get("reason", "")}
    # 同一文件内**按行号降序**应用：删行不会把后面的行号挤歪。
    # 删行用**严格同位**（行号与内容都要对得上），不按内容找 —— 空行到处一样，按内容找会误删别处。
    by_file = collections.defaultdict(list)
    for e in edits:
        f = (e.get("file") or "").lstrip("./")
        if f not in allowed:
            return False, f"越界改动 `{f}`，本条目只允许改 {sorted(allowed)}", None
        if not os.path.isfile(os.path.join(root, f)):
            return False, f"文件不存在 `{f}`", None
        if isinstance(e.get("after"), str) and "\n" in e["after"]:
            return False, "`after` 只能是单行（要改多行就拆成多条 edit，或把整段搬到新文件）", None
        by_file[f].append(e)
    for f, es in by_file.items():
        lines = plan_writes.get(f, read_text(os.path.join(root, f)).split("\n"))
        dels = plan_deletes.setdefault(f, set())
        for e in sorted(es, key=lambda x: -int(x.get("line", 0))):
            n = int(e.get("line", 0))
            if not (1 <= n <= len(lines)):
                return False, f"行号超出范围 `{f}`:{n}", None
            if "after" in e and e["after"] is None:
                now = lines[n - 1].strip()
                if now != (e.get("before") or "").strip():
                    return False, (f"删行对不上 `{f}`:{n} —— 该行现在是 `{now[:40]}`，"
                                   f"记录里是 `{(e.get('before') or '').strip()[:40]}`"), None
                dels.add(n)
                patch["files"].append({"file": f, "line": n, "before": e.get("before", ""), "after": None})
            else:
                hit = _find_anchor(lines, e.get("before", ""), n)
                if hit is None:
                    return False, f"锚点对不上 `{f}`:{n} —— 待改文本在该行 ±3 内找不到", None
                lines[hit - 1] = e.get("after", "")
                patch["files"].append({"file": f, "line": hit, "before": e.get("before", ""),
                                       "after": e.get("after", "")})
        plan_writes[f] = lines
    dirs_ok = {os.path.dirname(item["path"])}                 # 允许落在该 skill 目录之下，不要求同目录
    if item.get("owner") and item["owner"] != "(pack)":
        dirs_ok.add(os.path.dirname(item["owner"]))
    def _parts_conserve(item_path):
        """parts 拼起来是否等于原文件：是 → 这是一次**拆分**（删原件）；否 → 是**搬出**（留原件）。"""
        orig = read_text(os.path.join(root, item_path))
        got = "".join(_content_key("\n".join(plan_writes[p])) for p in parts if p in plan_writes)
        return orig, (got == _content_key(orig))

    if parts and edits:
        # 先按「拆分」试：parts 等于原文就删原件；否则当搬出（原文保留，指针行自己给）。
        for p, body in parts.items():
            p = p.lstrip("./")
            if not any(p == d or p.startswith(d + "/") for d in dirs_ok):
                return False, f"搬出的 `{p}` 不落在 {sorted(dirs_ok)} 之下", None
            plan_writes[p] = body.split("\n")
            patch["parts"].append(p)
        _orig, _is_split = _parts_conserve(item["path"])
        if _is_split:                 # parts 就是原文的拆分：删掉原件，指针行由 edits 负责换成两份
            patch["removed"].append({"file": item["path"], "content": _orig})
    elif parts:                       # 只给 parts：一律按拆分处理，守恒不过就拒
        orig = read_text(os.path.join(root, item["path"]))
        for p, body in parts.items():
            p = p.lstrip("./")
            if not any(p == d or p.startswith(d + "/") for d in dirs_ok):
                return False, f"拆出的 `{p}` 不落在 {sorted(dirs_ok)} 之下", None
            plan_writes[p] = body.split("\n")
            patch["parts"].append(p)
        got = "".join(_content_key("\n".join(plan_writes[p])) for p in patch["parts"])
        if _content_key(orig) != got:
            return False, "拆分不守恒：去掉空行与标题行后，原文与各新文件拼起来不一致", None
        patch["removed"].append({"file": item["path"], "content": orig})
    # 豁免规则：只允许命中本条目自己的文件
    if res.get("verdict") == "waived" or res.get("reason_code") == "external":
        rule = f"{item['path']}    {res.get('reason') or '包外引用，不参与待办'}"
        before = {p: _waived(p, waivers) for p in [item["path"]]}
        after = {p: _waived(p, waivers + [(item["path"], "x")]) for p in [item["path"]]}
        if not after[item["path"]]:
            return False, "新增的豁免规则没命中本条目自己的文件", None
        patch["waiver_rule"] = rule
    # 落盘
    for f, lines in plan_writes.items():
        dels = plan_deletes.get(f) or set()
        if dels:
            lines = [l for i, l in enumerate(lines, 1) if i not in dels]
        fp = os.path.join(root, f)
        os.makedirs(os.path.dirname(fp) or root, exist_ok=True)
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
    for r in patch["removed"]:
        fp = os.path.join(root, r["file"])
        if os.path.isfile(fp):
            os.remove(fp)
    if patch["waiver_rule"]:
        wp = os.path.join(root, ".skillweave", "waivers.txt")
        os.makedirs(os.path.dirname(wp), exist_ok=True)
        with open(wp, "a", encoding="utf-8") as fh:
            fh.write(patch["waiver_rule"] + "\n")
    return True, f"落盘 {len(patch['files'])} 行改动 · 新增 {len(patch['parts'])} 份 · 删 {len(patch['removed'])} 份", patch


def cmd_apply(root, proposals, state_path, out, revert_id=None):
    """校验并落盘提案。`--revert <id>` 反向应用一条已记录的 patch。"""
    if not out:
        out = os.path.join(root, "dispatch")
    pfile = os.path.join(out, "patches.json")
    if revert_id:
        return _revert_item(root, pfile, revert_id)
    items = _plan_items(out)
    if items is None:
        print("[apply] FAIL 找不到 dispatch/plan.json，先跑 dispatch")
        return 2
    results, batches = [], set()
    for p in proposals:
        if not os.path.isfile(p):
            print(f"[apply] FAIL 提案文件不存在 {p}")
            return 2
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
        batches.add(doc.get("batch", "?"))
        results += doc.get("results", [])
    got = [r.get("id") for r in results]
    if len(got) != len(set(got)):
        print("[apply] FAIL 提案里有重复的条目 id")
        return 1
    # 闭合校验：本次提案覆盖了哪些条目，就必须是条目表里的
    unknown = [i for i in got if i not in items]
    if unknown:
        print(f"[apply] FAIL 提案里有不属于本次派发的条目：{unknown[:5]}")
        return 1
    dj = json.load(open(os.path.join(out, "baseline.json"), encoding="utf-8")) \
        if os.path.isfile(os.path.join(out, "baseline.json")) else None
    if dj is None:
        print("[apply] FAIL 找不到 dispatch/baseline.json，先跑 dispatch")
        return 2
    waivers = _read_waivers(root)
    applied, parked, failed = [], [], []
    for r in results:
        it = items[r["id"]]
        ok, note, patch = _apply_item(root, it, r, dj, waivers)
        if not ok:
            failed.append((r["id"], note))
            print(f"[apply] ⛔ {r['id']} {note}")
            continue
        if patch is None:
            parked.append((r["id"], note))
            print(f"[apply] ⏸ {r['id']} {note}")
            continue
        patch["applied_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        applied.append(patch)
        print(f"[apply] ✅ {r['id']} {note}")
    # 逐条 patch 记录，追加写
    hist = []
    if os.path.isfile(pfile):
        with open(pfile, encoding="utf-8") as f:
            hist = json.load(f)
    hist += applied
    os.makedirs(out, exist_ok=True)
    with open(pfile, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2, sort_keys=True)
    if parked:
        with open(os.path.join(out, "PARKED.md"), "a", encoding="utf-8") as f:
            f.write(f"\n## {time.strftime('%Y-%m-%d')} · 落盘阶段未自动处理\n\n")
            for i, n in parked:
                f.write(f"- `{i}` · {n}\n")
    print(f"[apply] 落盘 {len(applied)} 条 · 未自动处理 {len(parked)} 条 · 失败 {len(failed)} 条 · 记录 {pfile}")
    return 1 if failed else 0


def _revert_item(root, pfile, item_id):
    """反向应用一条 patch：还原旧行、删掉新增文件、恢复被删文件、去掉它加的豁免规则。"""
    if not os.path.isfile(pfile):
        print("[apply] FAIL 没有 patches.json，无记录可回退")
        return 2
    with open(pfile, encoding="utf-8") as f:
        hist = json.load(f)
    hit = [h for h in hist if h["id"] == item_id]
    if not hit:
        print(f"[apply] FAIL 记录里没有 `{item_id}`")
        return 2
    p = hit[-1]
    # 先删新文件、再恢复被删的原件，最后才回退行改动 —— 拆分过的原文件在回退前是不存在的
    for q in p["parts"]:
        fp = os.path.join(root, q)
        if os.path.isfile(fp):
            os.remove(fp)
    for r in p["removed"]:
        fp = os.path.join(root, r["file"])
        os.makedirs(os.path.dirname(fp) or root, exist_ok=True)
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write(r["content"])
    _removed = {r["file"] for r in p["removed"]}
    for e in reversed(p["files"]):
        if e["file"] in _removed:
            continue                  # 这份是被拆掉的原件：恢复回来的内容就是改动前的状态，不用再回退行
        fp = os.path.join(root, e["file"])
        lines = read_text(fp).split("\n")
        if "after" in e and e["after"] is None:      # 这一行是被删掉的：按原行号插回
            lines.insert(max(0, int(e["line"]) - 1), e["before"])
        else:
            at = _find_anchor(lines, e["after"], e["line"])
            if at is None:
                print(f"[apply] ⛔ 回退不了 `{e['file']}`:{e['line']} —— 当前内容与 patch 记录不符")
                return 1
            lines[at - 1] = e["before"]
        with open(fp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
    if p.get("waiver_rule"):
        wp = os.path.join(root, ".skillweave", "waivers.txt")
        lines = [l for l in read_text(wp).split("\n") if l.strip() != p["waiver_rule"].strip()]
        with open(wp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
    with open(pfile, "w", encoding="utf-8") as f:
        json.dump([h for h in hist if h is not p], f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"[apply] ↩ 已回退 `{item_id}`（还原 {len(p['files'])} 行 · 删 {len(p['parts'])} 份 · 恢复 {len(p['removed'])} 份）")
    return 0


def cmd_dispatch(root, out, batch_size=25, refresh_baseline=False):   # batch_size = 每批最多几条
    """派发前的事实补全 + 批次划分 + prompt 落盘 + 计数起点。产物：dispatch/{plan.json,state.json,batch-*.md}"""
    dj, _ = _scan_fresh(root, "dispatch")
    if dj is None:
        print("[dispatch] FAIL 这个 pack 里没有 skill")
        return 1
    files = _pack_files(root)
    F = _findings(dj, root)
    waivers = _read_waivers(root)
    todo = {i: it for i, it in F.items() if not _waived(it["path"], waivers)}
    by_skill = collections.defaultdict(list)
    for it in todo.values():
        by_skill[it["owner"]].append(it)
    order = sorted(by_skill, key=lambda s: -len(by_skill[s]))
    batches, cur, cur_n = [], [], 0
    for sk in order:                # 按**条目数**填批（一个 skill 不拆成两批；每批 ≤10 个 skill）
        n = len(by_skill[sk])
        if cur and (cur_n + n > batch_size or len(cur) >= 10):
            batches.append(cur)
            cur, cur_n = [], 0
        cur.append(sk)
        cur_n += n
    if cur:
        batches.append(cur)
    base_rev = _rev(root)
    d = os.path.join(out, "dispatch")
    os.makedirs(d, exist_ok=True)
    plan = {"pack": os.path.basename(root), "base_rev": base_rev, "batch_size": batch_size,
            "baseline": os.path.join(d, "baseline.json"), "batches": []}
    for n, skills in enumerate(batches, 1):
        items = sorted((it for sk in skills for it in by_skill[sk]), key=lambda x: (x["kind"], x["path"]))
        b = {"id": f"B{n}", "skills": skills, "items": items}
        text = _prompt_for(b, root, F, files, dj, base_rev, os.path.basename(root))
        b["prompt"] = f"dispatch/batch-{n}.prompt.md"
        b["prompt_sha256"] = hashlib.sha256(text.encode()).hexdigest()[:16]
        with open(os.path.join(d, f"batch-{n}.prompt.md"), "w", encoding="utf-8") as f:
            f.write(text)
        plan["batches"].append(b)
    # 断言：批次间文件集合两两不相交（否则两个 agent 会改同一个文件）
    seen = {}
    for b in plan["batches"]:
        for it in b["items"]:
            if it["path"] in seen and seen[it["path"]] != b["id"]:
                print(f"[dispatch] FAIL 文件 `{it['path']}` 同时落在 {seen[it['path']]} 与 {b['id']} —— 归属没切干净")
                return 1
            seen[it["path"]] = b["id"]
    plan["todo"] = sum(len(b["items"]) for b in plan["batches"])
    with open(os.path.join(d, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2, sort_keys=True)
    with open(plan["baseline"], "w", encoding="utf-8") as f:     # 基线进 pack：可提交、可对账，别指临时目录
        json.dump(dj, f, ensure_ascii=False, indent=2, sort_keys=True)
    if plan["todo"] != sum(1 for i in todo.values()):
        print("[dispatch] FAIL 条目数对不上（聚合口径漂了）")
        return 1
    # **不许打转**：计数从旧 state 继承（重派不许把账清零）；同一批 prompt 没换过就拒绝重派
    st_path = os.path.join(d, "state.json")
    prev = json.load(open(st_path, encoding="utf-8")) if os.path.isfile(st_path) else None
    if prev and not refresh_baseline:
        for b in plan["batches"]:
            ids = [it["id"] for it in b["items"]]
            n = sum(prev.get("attempts", {}).get(i, 0) for i in ids)
            if n and prev.get("prompt_hash", {}).get(b["id"]) == b["prompt_sha256"]:
                print(f"[dispatch] 拒绝重派 {b['id']}：prompt 与上次一模一样（hash {b['prompt_sha256']}）——"
                      f"相同输入 = 相同输出。按梯子改输入（R1 加证据 / R2 减粒度 / R3 喂事实 / R4 换执行者）再派。")
                return 3
    attempts = {it["id"]: 0 for b in plan["batches"] for it in b["items"]}
    if prev:
        attempts.update({k: v for k, v in prev.get("attempts", {}).items() if k in attempts})
    state = {"pack": plan["pack"], "base_rev": base_rev, "baseline": plan["baseline"],
             "attempts": attempts, "prompt_hash": {b["id"]: b["prompt_sha256"] for b in plan["batches"]},
             "history": (prev or {}).get("history", [])}
    with open(os.path.join(d, "state.json"), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"[dispatch] {len(plan['batches'])} 批 · {plan['todo']} 条 · 基线 rev {base_rev}")
    for b in plan["batches"]:
        print(f"[dispatch]   {b['id']}: {len(b['skills'])} 个 skill / {len(b['items'])} 条 → {b['prompt']}")
    print(f"[dispatch] 出: {os.path.join(d, 'plan.json')}")
    return 0


LADDER = [
    "R1 给证据：把拦截判据的原文 + 上次 diff 塞进 prompt（多数失败是它不知道自己错在哪）",
    "R2 减粒度：一个 agent 只做一条（锚点唯一、上下文窄）",
    "R3 喂事实：把候选路径/父文档/正确拼写直接给它，不让它推理",
    "R4 换执行者：同 prompt 换模型（执行者与判官分离）",
    "R5 落 PARKED.md：停止重试，记条目 + 证据 + 建议",
]


def _content_key(text):
    """内容守恒用的归一化：去掉空行与标题行后的字符序列（拆分允许新增标题/分家，但不许改字）。"""
    keep = [l.strip() for l in text.split("\n")
            if l.strip() and not re.match(r"^#{1,6}\s", l.strip())]
    return "".join(keep)


def cmd_verify(root, state_path, expect_fixed, splits_path, out):
    """**验收（闸 1）**：集合级对账 —— 该消的消了 · 无新增 · 外部集合不变 · 拆分守恒 + 新文件被披露。

    不过就**整批回滚**（不逐条打补丁），并按梯子 R1..R5 决定下一次派发要改什么。"""
    with open(state_path, encoding="utf-8") as f:
        st = json.load(f)
    with open(st["baseline"], encoding="utf-8") as f:
        base = json.load(f)
    dj, _ = _scan_fresh(root, "verify")
    if dj is None:
        print("[verify] FAIL 扫不动这个 pack")
        return 1
    _wv = _read_waivers(root)                    # 已记豁免的条目算已解决，不再出现在待办与对账里
    before = {i: f for i, f in _findings(base, root).items() if not _waived(f["path"], _wv)}
    after = {i: f for i, f in _findings(dj, root).items() if not _waived(f["path"], _wv)}
    fails = []
    new = sorted(set(after) - set(before))
    if new:
        fails.append("新增发现（回归）：" + "; ".join(f"{after[i]['kind']} `{after[i]['path']}`" for i in new[:5]))
    missing = [i for i in expect_fixed if i in after]
    if missing:
        fails.append(f"该消的没消：{len(missing)} 条 —— " + "; ".join(f"{i}" for i in missing[:5]))
    def _ext_key(lst):                     # external 是 [[src,target,line],…]（可重复引用），比成字符串集合
        return sorted(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in lst)
    if _ext_key(base.get("external", [])) != _ext_key(dj.get("external", [])):
        fails.append("external 集合变了（说明有人动了包外引用的判断）")
    if splits_path:
        with open(splits_path, encoding="utf-8") as f:
            for orig, parts in json.load(f).items():
                g = git(root, "show", f"{st['base_rev']}:{orig}")
                if g is not None and g.returncode == 0:
                    want = _content_key(g.stdout)
                    got = "".join(_content_key(read_text(os.path.join(root, p)))
                                  for p in parts if os.path.isfile(os.path.join(root, p)))
                    if want != got:
                        fails.append(f"拆分不守恒：`{orig}` 的内容与 {len(parts)} 个新文件拼起来不一致")
                for p in parts:
                    if os.path.isfile(os.path.join(root, p)) and _doc_inbound(dj, p) == 0:
                        fails.append(f"拆出来的 `{p}` 没人披露 —— 它现在是新的「到不了根」")
    # 记账 + 梯子：**回归项也算在账上**（新增的发现同样要走 R1..R5，否则它会悄悄留在地上）
    targets = list(expect_fixed) + [i for i in new if i in after]
    for i in targets:
        st["attempts"][i] = st["attempts"].get(i, 0) + 1
    rounds = {}
    for i in targets:
        n = st["attempts"][i]
        tag = "回归 " if i in new else ""
        rounds[i] = f"✅ 已修" if i not in after else f"{tag}{LADDER[n - 1] if n <= len(LADDER) else LADDER[-1]}"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2, sort_keys=True)
    parked = [i for i in targets if i in after and st["attempts"][i] >= len(LADDER)]
    os.makedirs(out, exist_ok=True)
    run = os.path.join(out, "RUN.md")
    with open(run, "a", encoding="utf-8") as f:
        f.write(f"\n## 验收 {time.strftime('%Y-%m-%d %H:%M:%S')} · rev {_rev(root)}\n\n")
        f.write(("**PASS**" if not fails else "**FAIL**") + f" · 验 {len(expect_fixed)} 条\n\n")
        for i in targets:
            f.write(f"- `{i}` → {rounds[i]}\n")
        for x in fails:
            f.write(f"- ⛔ {x}\n")
    if parked:
        pk = os.path.join(out, "PARKED.md")
        with open(pk, "a", encoding="utf-8") as f:
            f.write(f"\n## {time.strftime('%Y-%m-%d')} · 走完梯子仍未过（不是能力问题，是口径分歧）\n\n")
            for i in parked:
                f.write(f"- `{i}` · {after[i]['kind']} · `{after[i]['path']}`"
                        + f"（{after[i]['num']}）"
                        + f" · 尝试 {st['attempts'][i]} 次 —— 需要一条规则（豁免/该删/该合）才能自动过\n")
    for i in targets:
        if i not in after:
            print(f"[verify] ✅ {i} 已修")
    for x in fails:
        print(f"[verify] ⛔ {x}")
    if not fails:
        print(f"[verify] PASS · rev {_rev(root)} · 记录 → {run}")
        return 0
    print("[verify] FAIL —— 不整批回滚：通过的条目保留，未通过的条目按以下级别改输入后在已改动的树上继续修；"
          "只有无法修正的条目才用 `apply --revert <id>` 回退它自己那一条。")
    for i in targets:
        if i in after:
            print(f"[verify]   {i}: {rounds[i]}")
    print(f"[verify] 记录 → {run}")
    return 1


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

    waivers = _read_waivers(root)
    os.makedirs(out, exist_ok=True)
    todo_md = os.path.join(out, "TODO.md")
    todo_text, n_todo, n_waived_rows = render_todo_md(root, nodes, over_all, orphan_all, broken, dup, waivers)
    with open(todo_md, "w", encoding="utf-8") as f:
        f.write(todo_text)

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
         f"- 根选择层近重复（Jaccard≥0.5·靠 description 选根才算）：**{len(dup)}** 对",
         f"- **待办 {n_todo} 条 · 已豁免 {n_waived_rows} 条** → 见同目录 [`TODO.md`](TODO.md)"
         f"（豁免规则 {len(waivers)} 条，来自包里 `.skillweave/waivers.txt`）", ""]
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
    L += ["## 根选择层（L0）", "",
          "根不是被谁披露出来的，而是**靠 description 选出来的** —— 所以它单独一层，混进 Ln 会让两个形状的层数不可比。", "",
          "| 根 | description 字符 | 常驻 tok | 同层近重复 |", "|---|---|---|---|"]
    dup_of = {}
    for r, a, b in dup:
        dup_of.setdefault(a, []).append((r, b))
        dup_of.setdefault(b, []).append((r, a))
    for p in roots:
        n = nodes[p]
        d = ", ".join(f"{r} ↔ `{q}`" for r, q in dup_of.get(p, [])) or "—"
        L.append(f"| `{p}` | {n['desc_chars']} | {est_tokens(next((s['description'] for s in skills if s['id'] == n['skill']), ''))} | {d} |")
    L += [""]
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
    print(f"[disclosure] 待办清单 → {todo_md}")
    print(f"[disclosure] 根 {len(roots)} 个（=形状）· 层 " +
          " → ".join(f"L{d}={len(lv[d])}" if d is not None else f"未分层={len(lv[d])}" for d in levels) +
          f" · 文档 {len(nodes)} 份（表行数 {rows} 对账 ✅）· 超限 {len(over_all)} · "
          f"到不了根 {len(orphan_all)} · 悬空 {len(broken)} · external {len(external)}")
    print(f"[disclosure] 出: {md}")
    return 0


def _in_git_repo(pack):
    """输入目录是不是在一个 git 仓库里，是就返回仓库根。"""
    g = git(pack, "rev-parse", "--show-toplevel")
    if g is not None and g.returncode == 0 and (g.stdout or "").strip():
        return os.path.realpath(g.stdout.strip())
    return None


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
    log, wt = [], None
    if _in_git_repo(pack):                      # 原本在 git 仓库里 → 开 worktree
        work, extra = _worktree_copy(pack, dest, log)
        if work is None:
            print(f"[prepare] FAIL 开 worktree 失败：{extra}")
            return 1
    else:                                       # 不是 git 仓库 → 拷副本再 git init
        how = _clone_copy(pack, dest)
        log.append(f"副本：`{dest}`（{how}）· 原目录只读，未动")
        work = dest
    rev = _rev(work)
    if rev in (None, "", "?"):                 # `_rev` 没 git 时返回 "?"，是 truthy，要显式判
        rev = _ensure_git_copy(work, log)
    log.append(f"工作区：`{work}`")
    dest = work

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
                    "模板见 `templates/README.md`，随手写个 `run.py` 与 `fig.pdf`。\n"
                    "包外见 `../outside-repo/thing.md`。\n\n"
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
        # 口径：中文文件名要能被认作披露（实测 Loomerto 的段落文件是中文名，只认 ASCII 会误判成到不了根）
        _cjk = os.path.join(os.path.dirname(os.path.join(skilldir, "x")), "references", "中文说明.md")
        with open(_cjk, "w") as f:
            f.write("中文文件名\n")
        with open(os.path.join(skilldir, "SKILL.md"), "a") as f:
            f.write("另见 `references/中文说明.md`。\n")
        _oc = os.path.join(tmp, "o-cjk")
        assert cmd_disclosure(pack, _oc) == 0
        _dc = json.load(open(os.path.join(_oc, "disclosure.json"), encoding="utf-8"))
        assert "notes/demo/references/中文说明.md" in _dc["nodes"], "中文文件名该被认成节点"
        assert "notes/demo/references/中文说明.md" not in _dc["orphans"], "中文文件名该能被披露（不是到不了根）"
        # 口径：嵌套 skill 里写的 `references/x.md` 按**它自己的根**解析
        _n = os.path.join(skilldir, "references", "nested")
        os.makedirs(_n, exist_ok=True)
        with open(os.path.join(_n, "SKILL.md"), "w") as f:
            f.write("---\nname: nested\ndescription: 嵌套样例。\n---\n\n见 `references/leaf.md`。\n")
        os.makedirs(os.path.join(_n, "references"), exist_ok=True)
        with open(os.path.join(_n, "references", "leaf.md"), "w") as f:
            f.write("leaf\n")
        _on = os.path.join(tmp, "o-nested")
        assert cmd_disclosure(pack, _on) == 0
        _dn = json.load(open(os.path.join(_on, "disclosure.json"), encoding="utf-8"))
        _leaf = "notes/demo/references/nested/references/leaf.md"
        assert _leaf not in _dn["broken"], "嵌套 skill 里的 `references/x.md` 该按它自己的根解析，不该算悬空"
        assert _dn["edges"].get("notes/demo/references/nested/SKILL.md", {}).get(_leaf), \
            "嵌套 skill 的披露边该连到它自己目录下的文件"
        _d8 = json.load(open(os.path.join(out8, "disclosure.json"), encoding="utf-8"))
        assert _d8["external"], "fixture 里放了一条包外引用，external 不该是空的"
        todo_md = os.path.join(out8, "TODO.md")
        assert os.path.isfile(todo_md), "缺 TODO.md"
        t0 = open(todo_md, encoding="utf-8").read()
        assert "待办" in t0 and "免检表长什么样" in t0, t0[:200]
        # 包内免检表：命中就不算待办，改列「已豁免」
        os.makedirs(os.path.join(pack, ".skillweave"), exist_ok=True)
        open(os.path.join(pack, ".skillweave", "waivers.txt"), "w", encoding="utf-8").write(
            "# 一行一条\n*unused.md   没人点名是刻意的\n")
        out9 = os.path.join(tmp, "o9")
        assert cmd_disclosure(pack, out9) == 0
        t1 = open(os.path.join(out9, "TODO.md"), encoding="utf-8").read()
        assert "没人点名是刻意的" in t1, t1[:400]
        # prepare 的两条路：git 仓库 → worktree；非 git → copy + git init
        _repo = os.path.join(tmp, "repo-in")
        os.makedirs(os.path.join(_repo, "skills", "demo"))
        with open(os.path.join(_repo, "skills", "demo", "SKILL.md"), "w") as f:
            f.write("---\nname: demo\ndescription: 做一件事时用。\n---\n\n见 `references/x.md`。\n")
        with open(os.path.join(_repo, "README.md"), "w") as f:
            f.write("repo\n")
        git(_repo, "init", "-q")
        git(_repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        git(_repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
        _wt = os.path.join(tmp, "repo-wt")
        assert cmd_prepare(_repo, os.path.join(tmp, "o-prep-wt"), dest=_wt, shape="multi") == 0, \
            "git 仓库输入该走 worktree"
        assert os.path.isfile(os.path.join(_wt, ".git")), "worktree 的 .git 该是个文件，不是目录"
        wl = git(_repo, "worktree", "list")
        assert _wt in (wl.stdout or ""), "主 clone 里该能看到这个 worktree"
        git(_repo, "worktree", "remove", "--force", _wt)
        # 非 git 输入：拷副本 + git init
        _plain = os.path.join(tmp, "plain-in")
        os.makedirs(os.path.join(_plain, "skills", "demo"))
        with open(os.path.join(_plain, "skills", "demo", "SKILL.md"), "w") as f:
            f.write("---\nname: demo\ndescription: 做一件事时用。\n---\n\n见 `references/x.md`。\n")
        _cp = os.path.join(tmp, "plain-copy")
        assert cmd_prepare(_plain, os.path.join(tmp, "o-prep-cp"), dest=_cp, shape="multi") == 0, \
            "非 git 输入该走拷贝"
        assert git(_cp, "rev-parse", "--git-dir") is not None, "副本该被 git 管起来"
        assert not os.path.exists(os.path.join(_plain, ".git")), "原目录不该被 git init"

        # 派发：事实补全 + 批次 + 计数起点
        assert cmd_dispatch(pack, out9, batch_size=10) == 0, "dispatch 该成功"
        pl = json.load(open(os.path.join(out9, "dispatch", "plan.json"), encoding="utf-8"))
        ids = [it["id"] for b in pl["batches"] for it in b["items"]]
        assert ids and len(ids) == len(set(ids)), "条目 id 必须唯一"
        pr = open(os.path.join(out9, "dispatch", "batch-1.prompt.md"), encoding="utf-8").read()
        assert "只产出提案" in pr and "不许开后台进程" in pr, pr[:200]
        assert "## 条目与事实" in pr and ("包内没有同名文件" in pr or "候选" in pr or "二级标题" in pr), \
            "prompt 里必须有事实补全段"
        assert os.path.isfile(os.path.join(out9, "dispatch", "state.json")), "缺 state.json"

        st = os.path.join(out9, "dispatch", "state.json")
        # ── 落盘器：锚点 / 白名单 / 拆分守恒 / 单条回退 ──
        b1 = json.load(open(os.path.join(out9, "dispatch", "plan.json"), encoding="utf-8"))["batches"][0]
        broken = next(it for it in b1["items"] if it["kind"] == "悬空")
        bfull = os.path.join(pack, broken["path"])          # 用条目自己的路径，不猜
        blines = read_text(bfull).split("\n")
        bl = broken["refs"][0]["line"]
        old_line = blines[bl - 1]                       # 锚点是整行逐字比对，所以取真行
        new_line = old_line.replace("references/gone.md", "references/guide.md")
        good = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed", "reason_code": "typo-fixed",
             "edits": [{"file": broken["path"], "line": bl, "before": old_line, "after": new_line}]}]}
        gpath = os.path.join(tmp, "prop-good.json")
        with open(gpath, "w", encoding="utf-8") as f:
            json.dump(good, f, ensure_ascii=False)
        assert cmd_apply(pack, [gpath], st, os.path.join(out9, "dispatch")) == 0, "合法提案该落盘"
        assert "references/gone.md" not in read_text(bfull), "改动没落盘"
        pj = json.load(open(os.path.join(out9, "dispatch", "patches.json"), encoding="utf-8"))
        assert pj and pj[0]["files"][0]["file"], "缺逐条 patch 记录"
        assert cmd_apply(pack, [], st, os.path.join(out9, "dispatch"), revert_id=broken["id"]) == 0, "回退该成功"
        assert old_line in read_text(bfull), "回退没把整行原文还原回去"
        bad = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": broken["path"], "line": bl,
                        "before": "这句原文根本不存在", "after": "x"}]}]}
        bpath = os.path.join(tmp, "prop-bad.json")
        with open(bpath, "w", encoding="utf-8") as f:
            json.dump(bad, f, ensure_ascii=False)
        assert cmd_apply(pack, [bpath], st, os.path.join(out9, "dispatch")) == 1, "锚点对不上必须失败"
        out_of_range = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": "README.md", "line": 1, "before": "x", "after": "y"}]}]}
        rpath = os.path.join(tmp, "prop-range.json")
        with open(rpath, "w", encoding="utf-8") as f:
            json.dump(out_of_range, f, ensure_ascii=False)
        assert cmd_apply(pack, [rpath], st, os.path.join(out9, "dispatch")) == 1, "越界改动必须失败"
        # 拆分守恒：把 SKILL.md 拆成两份，第二份不守恒就该被拒
        orig = read_text(bfull)
        sp = {"batch": "B1", "results": [                      # 只给 parts、不给 edits = 整篇拆分，要守恒
            {"id": broken["id"], "verdict": "fixed",
             "parts": {os.path.join(os.path.dirname(broken["path"]) or ".", "half.md"): "少了内容"}}]}
        sppath = os.path.join(tmp, "prop-split.json")
        with open(sppath, "w", encoding="utf-8") as f:
            json.dump(sp, f, ensure_ascii=False)
        assert cmd_apply(pack, [sppath], st, os.path.join(out9, "dispatch")) == 1, "拆分不守恒必须失败"
        assert orig == read_text(bfull), "失败的提案不许留下半个改动"
        # 新形态：edits 与 parts 同时给 → 原文保留、新文件创建（把段落搬出去、留一行指针）
        mv = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": broken["path"], "line": bl, "before": old_line, "after": new_line}],
             "parts": {os.path.join(os.path.dirname(broken["path"]) or ".", "moved.md"): "搬出去的那几段\n"}}]}
        mvpath = os.path.join(tmp, "prop-move.json")
        with open(mvpath, "w", encoding="utf-8") as f:
            json.dump(mv, f, ensure_ascii=False)
        assert cmd_apply(pack, [mvpath], st, os.path.join(out9, "dispatch")) == 0, "搬段落的提案该落盘"
        assert os.path.isfile(os.path.join(pack, os.path.dirname(broken["path"]) or ".", "moved.md")), \
            "搬出的新文件该创建"
        assert os.path.isfile(bfull), "搬段落时原文不该被删"
        assert new_line in read_text(bfull), "原文该留下指针行"
        assert cmd_apply(pack, [], st, os.path.join(out9, "dispatch"), revert_id=broken["id"]) == 0, \
            "该能把这一条回退掉"
        assert not os.path.isfile(os.path.join(pack, os.path.dirname(broken["path"]) or ".", "moved.md")), \
            "回退该删掉搬出的文件"
        assert old_line in read_text(bfull), "回退该把指针行还原"

        # 删行 + 多行替换：把段落「搬出去 + 原文留一行指针」用的就是这两招
        blines2 = read_text(bfull).split("\n")
        keep_line = blines2[bl - 1]
        mv2 = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": broken["path"], "line": bl, "before": keep_line,
                        "after": "## 指针 → 见 `references/moved2.md`"},
                       {"file": broken["path"], "line": bl + 1, "before": blines2[bl], "after": None}],
             "parts": {os.path.join(os.path.dirname(broken["path"]) or ".", "moved2.md"): "搬走的正文\n"}}]}
        mv2p = os.path.join(tmp, "prop-move2.json")
        with open(mv2p, "w", encoding="utf-8") as f:
            json.dump(mv2, f, ensure_ascii=False)
        _orig_text = read_text(bfull)                  # 回退的判据用「逐字节还原」，比逐行断言更硬
        _before_n = len(read_text(bfull).split("\n"))
        assert cmd_apply(pack, [mv2p], st, os.path.join(out9, "dispatch")) == 0, "删行 + 多行替换该落盘"
        _after = read_text(bfull).split("\n")
        assert "## 指针 → 见 `references/moved2.md`" in _after, "指针行没写进去"
        assert len(_after) == _before_n - 1, "删了一行，总行数该少 1"
        assert cmd_apply(pack, [], st, os.path.join(out9, "dispatch"), revert_id=broken["id"]) == 0, \
            "该能回退（删行 + 指针替换）"
        assert read_text(bfull) == _orig_text, "回退该把文件逐字节还原：\n" + "\n".join(
            difflib.unified_diff(_orig_text.split("\n"), read_text(bfull).split("\n"), lineterm=""))

        ml = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": broken["path"], "line": bl, "before": old_line, "after": "两行\n内容"}]}]}
        mlp = os.path.join(tmp, "prop-multiline.json")
        with open(mlp, "w", encoding="utf-8") as f:
            json.dump(ml, f, ensure_ascii=False)
        assert cmd_apply(pack, [mlp], st, os.path.join(out9, "dispatch")) == 1, "多行 after 该被拒"

        # 删空行不能误删别处：空行到处一样，按内容找会删错行
        _orig_lines = read_text(bfull).split("\n")
        _blanks = [i for i, l in enumerate(_orig_lines, 1) if l.strip() == ""]
        _pick = _blanks[2] if len(_blanks) > 2 else _blanks[0]
        delp = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": broken["path"], "line": _pick, "before": "", "after": None}],
             "parts": {os.path.join(os.path.dirname(broken["path"]) or ".", "blank-test.md"): "占位\n"}}]}
        delpp = os.path.join(tmp, "prop-delblank.json")
        with open(delpp, "w", encoding="utf-8") as f:
            json.dump(delp, f, ensure_ascii=False)
        assert cmd_apply(pack, [delpp], st, os.path.join(out9, "dispatch")) == 0, "删空行该落盘"
        assert read_text(bfull).split("\n") == _orig_lines[:_pick - 1] + _orig_lines[_pick:], \
            "删空行必须只删掉那一行，别处的空行不许动"
        assert cmd_apply(pack, [], st, os.path.join(out9, "dispatch"), revert_id=broken["id"]) == 0, "该能回退"
        assert read_text(bfull).split("\n") == _orig_lines, "回退该逐行还原"

        # parts 拼起来等于原文 → 按拆分处理，原件要删掉（否则「拆了但原件还在」）
        _sp_orig = read_text(bfull)
        _half = len(_sp_orig.split("\n")) // 2
        _lns = _sp_orig.split("\n")
        sp2 = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": broken["path"], "line": bl, "before": _lns[bl - 1],
                        "after": "## 指针 → 见 `references/p1.md`"}],
             "parts": {os.path.join(os.path.dirname(broken["path"]) or ".", "p1.md"): "\n".join(_lns[:_half]),
                       os.path.join(os.path.dirname(broken["path"]) or ".", "p2.md"): "\n".join(_lns[_half:])}}]}
        sp2p = os.path.join(tmp, "prop-split2.json")
        with open(sp2p, "w", encoding="utf-8") as f:
            json.dump(sp2, f, ensure_ascii=False)
        assert cmd_apply(pack, [sp2p], st, os.path.join(out9, "dispatch")) == 0, "守恒的拆分该落盘"
        assert not os.path.isfile(bfull), "拆分后原件该被删掉"
        assert os.path.isfile(os.path.join(os.path.dirname(bfull), "p1.md")), "拆出的两份该落盘"
        assert cmd_apply(pack, [], st, os.path.join(out9, "dispatch"), revert_id=broken["id"]) == 0, "该能回退"
        assert read_text(bfull) == _sp_orig, "回退该把原件整份恢复回来"
        assert not os.path.isfile(os.path.join(os.path.dirname(bfull), "p1.md")), "回退该删掉拆出的两份"

        # 只写豁免、没有 edits 的提案：要能落盘、写进 waivers、让条目离开待办
        _wp = os.path.join(pack, ".skillweave", "waivers.txt")
        _bk = read_text(_wp) if os.path.isfile(_wp) else None      # 测完要还原，否则后面的对账会漂
        wprop = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "waived", "reason_code": "external",
             "reason": "这个引用在说包外的文件"}]}
        wpath = os.path.join(tmp, "prop-waive.json")
        with open(wpath, "w", encoding="utf-8") as f:
            json.dump(wprop, f, ensure_ascii=False)
        assert cmd_apply(pack, [wpath], st, os.path.join(out9, "dispatch")) == 0, "只写豁免的提案也该落盘"
        wf = open(os.path.join(pack, ".skillweave", "waivers.txt"), encoding="utf-8").read()
        assert broken["path"] in wf, "豁免规则没写进 waivers.txt"
        _fw = os.path.join(out9, "waive-todo")
        assert cmd_disclosure(pack, _fw) == 0
        assert broken["id"] not in open(os.path.join(_fw, "TODO.md"), encoding="utf-8").read(), \
            "豁免后该条目不该还在待办里"
        _wv = _read_waivers(pack)
        _bf = {i: f for i, f in _findings(json.load(open(os.path.join(out9, "dispatch",
              "baseline.json"), encoding="utf-8")), pack).items() if not _waived(f["path"], _wv)}
        assert broken["id"] not in _bf, "豁免的条目不该再被当成待解决"
        if _bk is None:
            os.remove(_wp)
        else:
            with open(_wp, "w", encoding="utf-8") as f:
                f.write(_bk)
        before_att = json.load(open(st, encoding="utf-8"))["attempts"]
        assert cmd_dispatch(pack, out9, batch_size=10) == 0, "重派（无尝试记录）应被允许"
        after_att = json.load(open(st, encoding="utf-8"))["attempts"]
        assert set(after_att) == set(before_att), "重派不许把条目账改掉"
        # 不许打转：某批已有尝试且 prompt 未变 → 再派必须被拒（退 3）
        stj = json.load(open(st, encoding="utf-8"))
        b1 = json.load(open(os.path.join(out9, "dispatch", "plan.json"), encoding="utf-8"))["batches"][0]
        stj["attempts"][b1["items"][0]["id"]] = 1
        with open(st, "w", encoding="utf-8") as f:
            json.dump(stj, f, ensure_ascii=False)
        assert cmd_dispatch(pack, out9, batch_size=10) == 3, "prompt 没换就重派，必须被拒（相同输入=相同输出）"
        # 验收：干净 → PASS；注入一条新悬空 → FAIL，并给梯子
        assert cmd_verify(pack, st, [], None, out9) == 0, "没改动的 pack、没声称修过任何东西 → 应 PASS"
        try:
            p2 = os.path.join(pack, "第二只", "SKILL.md")
            os.makedirs(os.path.dirname(p2), exist_ok=True)
            with open(p2, "w", encoding="utf-8") as f:
                f.write("---\nname: 第二只\ndescription: 另一只 demo，用来测新增悬空。\n---\n\n见 `references/nope.md`。\n")
            assert cmd_verify(pack, st, [], None, out9) == 1, "新增悬空必须 FAIL"
            run = open(os.path.join(out9, "RUN.md"), encoding="utf-8").read()
            assert "⛔" in run and "R1" in run, "FAIL 时要写拦截判据与下一级 R 指令"
        finally:
            shutil.rmtree(os.path.join(pack, "第二只"), ignore_errors=True)
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
              "layers↔audit 口径对拍 / 派发划批 / 验收（集合级回归拦截 + 梯子）—— 全过")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
