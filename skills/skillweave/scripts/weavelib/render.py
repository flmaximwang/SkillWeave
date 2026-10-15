"""渲染：TREE.md · TREE.html · LAYERS · DISCLOSURE · TODO 等产物。

从 weave.py 拆出，逻辑未改。"""
import collections, os, re
from .common import est_tokens, read_text
from .frontmatter import parse_frontmatter
from .graph import _doc_edges, _waived
from .model import git, is_nested_skill, untracked_skill_files
from .pack import Pack




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





ISLAND_COLORS = ["#3b6ea5", "#7a5195", "#bc5090", "#ef5675", "#ff764a", "#ffa600",
                 "#2f7d6b", "#8a6d1f", "#5b6bbf", "#a1421f", "#3f6f8f", "#6b7a3f", "#8f4b7a"]




def _xml(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))




def render_tree_md(root, doc_nodes, doc_edges, rev):
    """文档级 TREE.md：节点 = 每份文档（issue #4）。"""
    roots = sorted(p for p, n in doc_nodes.items() if n["root"])
    # 计算披露深度（BFS）
    depth = {}
    for p in roots:
        depth[p] = 1
    frontier = list(roots)
    while frontier:
        nxt = []
        for p in frontier:
            for q in sorted(doc_edges.get(p, {})):
                if q not in depth:
                    depth[q] = depth[p] + 1
                    nxt.append(q)
        frontier = nxt
    for p in doc_nodes:
        depth.setdefault(p, None)
    # 按层分组
    lv = collections.defaultdict(list)
    for p in doc_nodes:
        lv[depth[p]].append(p)
    levels = sorted(lv, key=lambda x: (x is None, x))
    L = [f"# 文档树 · {os.path.basename(root)}", "",
         f"基准 `{rev}` · 由 `weave.py visualize` 生成，**不要手改**。", "",
         f"文档 {len(doc_nodes)} 个 · 根 {len(roots)} 个（= 形状）", "",
         "> 节点 = 每份文档（`SKILL.md`、`references/*.md`、`scripts/*.py` 各算一份）。",
         "> 根 = 每个 skill 的 `SKILL.md`（多入口 = K 个根；单入口 = 1 个根）。",
         "> 层 = 披露深度（L1 = 根文档；L2 = L1 直接披露的；Ln+1 由 Ln 披露）。", ""]
    for d in levels:
        if d is None:
            L += ["## 到不了的文档（没有任何根披露到它们）", ""]
        else:
            L += [f"## L{d}（{len(lv[d])} 份）", ""]
        L += ["| 文档 | fanout（披露几项） | 体积 | 判定 |", "|---|---|---|---|"]
        for p in sorted(lv[d]):
            n = doc_nodes[p]
            size = (f"{n['tok']} tok / {n['lines']} 行" if n["tok"] is not None
                    else f"{n['bytes']} B")
            bad = []
            if n["root"]:
                bad.append("根")
            L.append(f"| `{p}` | {len(doc_edges.get(p, {}))} | {size} | {' · '.join(bad) or '✅'} |")
        L.append("")
    L += ["## 口径", "",
          "- 节点 = 每份文档（`SKILL.md`、`references/*.md`、`scripts/*.py` 各算一份）。",
          "- 根 = 每个 skill 的 `SKILL.md`（多入口 = K 个根；单入口 = 1 个根）。",
          "- 层 = 披露深度（L1 = 根文档；L2 = L1 直接披露的；Ln+1 由 Ln 披露）。",
          "- 披露 = 正文里真实点到的另一份文档（先按该文件所在目录、再按 pack 根解析）；",
          "URL、围栏里的路径、没有目录部分的裸文件名都不算。",
          f"- `tok` = `est_tokens`：CJK ×1 + 其它 ×0.25（估算）。",
          ""]
    return "\n".join(L)




def render_tree_html(root, doc_nodes, doc_edges, rev):
    """文档级 TREE.html：节点 = 每份文档（issue #4）。

    根 = 每个 skill 的 `SKILL.md`（多入口 = K 个根；单入口 = 1 个根）。
    边 = 披露（正文里真实写出的另一份文档路径，口径同 disclosure）。
    层 = 披露深度（L1 = 根文档；Ln+1 由 Ln 披露）。
    """
    roots = sorted(p for p, n in doc_nodes.items() if n["root"])
    # 计算披露深度（BFS）
    depth = {}
    for p in roots:
        depth[p] = 1
    frontier = list(roots)
    while frontier:
        nxt = []
        for p in frontier:
            for q in sorted(doc_edges.get(p, {})):
                if q not in depth:
                    depth[q] = depth[p] + 1
                    nxt.append(q)
        frontier = nxt
    for p in doc_nodes:
        depth.setdefault(p, None)
    # 按层分组
    lv = collections.defaultdict(list)
    for p, n in doc_nodes.items():
        lv[depth[p]].append(p)
    levels = sorted(lv, key=lambda x: (x is None, x))
    W = 1680
    P = []
    y = 196

    def rect(x, yy, w, h, fill, stroke, rx=8, sw=1.2, op=1.0, cls=None):
        c = f' class="{cls}"' if cls else ""
        P.append(f'<rect{c} x="{x}" y="{yy}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}" opacity="{op}"/>')

    def text(x, yy, t, size=13.0, fill="#e8e8ef", anchor="start", weight="normal", mono=False):
        fam = "ui-monospace,Menlo,monospace" if mono else "system-ui,-apple-system,'Helvetica Neue',sans-serif"
        P.append(f'<text x="{x}" y="{yy}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
                 f'font-weight="{weight}" font-family="{fam}">{_xml(t)}</text>')

    # 标题 + 数字
    text(40, 46, f"文档树 · {os.path.basename(root)}", 24, "#f2f2f7", weight="600")
    text(40, 74, f"{rev} · weave.py visualize 生成 · 不要手改", 12, "#9aa0b0", mono=True)
    nums = [("文档", len(doc_nodes)), ("根", len(roots)),
            ("层数", len([x for x in levels if x is not None])),
            ("到不了根", len(lv.get(None, [])))]
    x = 40
    for k, v in nums:
        rect(x, 92, 150, 40, "#20222c", "#33364a", rx=6)
        text(x + 10, 110, k, 11, "#9aa0b0")
        text(x + 10, 126, str(v), 15, "#f2f2f7", weight="600")
        x += 162

    # 文档树：按层渲染
    text(40, y - 12, "文档树（节点 = 每份文档；层 = 披露深度）", 15, "#c9cdea", weight="600")
    y += 10
    for d in levels:
        if d is None:
            label = "到不了根"
            col = "#7d8496"
        else:
            label = f"L{d}"
            col = ISLAND_COLORS[(d - 1) % len(ISLAND_COLORS)]
        text(40, y + 14, f"{label}（{len(lv[d])} 份）", 12, col, weight="600", mono=True)
        y += 22
        for p in sorted(lv[d]):
            n = doc_nodes[p]
            size = (f"{n['tok']} tok / {n['lines']} 行" if n["tok"] is not None
                    else f"{n['bytes']} B")
            fanout = len(doc_edges.get(p, {}))
            rect(40, y, 1596, 26, "#15171f", col, rx=6, sw=0.9, cls="node")
            text(56, y + 18, p, 12, "#dfe3f2", weight="600", mono=True)
            text(500, y + 18, f"{size} · fanout {fanout}", 11, col, mono=True)
            y += 30
        y += 10

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
 口径：节点 = 每份文档（<code>SKILL.md</code>、<code>references/*.md</code>、<code>scripts/*.py</code> 各算一份）·
 根 = 每个 skill 的 <code>SKILL.md</code>（多入口 = K 个根；单入口 = 1 个根）·
 层 = 披露深度（L1 = 根文档；Ln+1 由 Ln 披露）<br>
 节点框（<code>rect.node</code>）数 = 文档数 = <b>{len(doc_nodes)}</b> 份
（= <code>DISCLOSURE.md</code> 的表行数）。
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




def _doc_stats(nodes, edges, broken, external, over, orphan):
    """文档级 stats：节点数 = 文档数（issue #4）。"""
    roots = [p for p, n in nodes.items() if n["root"]]
    return {"docs": len(nodes), "roots": len(roots),
            "over": len(over), "orphans": len(orphan),
            "broken": len(broken), "external": len(external)}


def cmd_visualize(root, out):
    """把文档树落成两份给人/给 agent 看的产物：`TREE.md` + `TREE.html`。"""
    # 闸：工作区里还有未跟踪的 `SKILL.md` 就**报错退出**，不静默交付空树。
    # collapse 刚改完、还没 commit 时索引里是旧路径，新入口的 SKILL.md 会被 walk_dir 当
    # untracked 跳过 ⇒ `skills=[]` ⇒ 产物是空树，而退出码 0（issue #1 根因 2，实测 63 个里 25 个命中）。
    un = untracked_skill_files(root)
    if un:
        print(f"[visualize] FAIL 工作区里有 {len(un)} 个**未被 git 跟踪**的 SKILL.md：")
        for x in un[:5]:
            print(f"    {x}")
        if len(un) > 5:
            print(f"    …还有 {len(un) - 5} 个")
        print("[visualize] 这多半是刚 collapse 完还没 commit：索引里还是旧路径，新入口会被当成"
              "未跟踪跳过，产物会是一棵空树。**先 commit 再跑**（或 `git add -A`）。")
        return 1
    pack = Pack.load(root)
    if pack is None:
        print("[visualize] FAIL 这个目录里没有任何 skill（找不到 SKILL.md）")
        return 1
    if pack.skipped:
        print(f"[visualize] ⚠️ 跳过 {len(pack.skipped)} 个未跟踪的 skill 形目录："
              f"{', '.join(pack.skipped[:3])}{'…' if len(pack.skipped) > 3 else ''}")
    root, skills = pack.root, pack.skills
    # issue #4：节点 = 文档（每份 `.md` / `.py` / …），不是 SKILL.md。
    # 数据源用 `_doc_nodes()` + `_doc_edges()`（与 disclosure 同一口径），不再用 skill 级数据。
    doc_nodes = _doc_nodes(skills, root)
    broken, external = [], []
    doc_edges = _doc_edges(root, doc_nodes, broken, external)
    rev = _rev(root)
    os.makedirs(out, exist_ok=True)
    md = os.path.join(out, "TREE.md")
    html = os.path.join(out, "TREE.html")
    with open(md, "w", encoding="utf-8") as f:
        f.write(render_tree_md(root, doc_nodes, doc_edges, rev))
    with open(html, "w", encoding="utf-8") as f:
        f.write(render_tree_html(root, doc_nodes, doc_edges, rev))
    stats = _doc_stats(doc_nodes, doc_edges, broken, external, [], [])
    print(f"[visualize] 文档={stats['docs']} 个 · 根={stats['roots']} 个（= 形状）")
    print(f"[visualize] 出: {md}")
    print(f"[visualize] 出: {html}")
    return 0




def _doc_nodes(skills, root):
    """节点 = pack 里的每份文档。**根 = 每个 skill 的 `SKILL.md`**（多入口 = K 个根；单入口 = 1 个）。

    单入口形状下岛内 skill 住在 `<入口>/references/<岛>/<skill>/` —— 契约 §0：**根只有入口那 1 个**，
    岛内 skill 是它 `references/` 里的普通文档（`root=False`），不是根。"""
    nodes = {}
    for s in skills:
        is_root = not is_nested_skill(root, s["id"])
        sk = s["id"] + "SKILL.md"
        nodes[sk] = {"path": sk, "kind": "instructions", "skill": s["id"], "root": is_root,
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




ACTION = {
    "超限": ("拆成多份（拆分方案交模型判断，按主题切不按标题切）", "待模型"),
    "到不了根": ("判：该被引用（加一条引用）· 该删 · 还是刻意的（免检）", "待模型"),
    "悬空": ("**先判**：包内路径写错（改路径）· 还是在说包外文件（免检）→ 再动手", "待模型"),
    "近重复": ("合并 / 改写其中一条 description", "待模型"),
    "披露过深": ("考虑：上提到 L2（让 SKILL.md 直接引用）· 合并到父文档 · 或接受当前深度", "待模型"),
}




def render_todo_md(root, nodes, over_all, orphan_all, broken, dup, waivers, deep_all=()):
    # 返回 (文本, 待办数, 豁免数)：打印与表头都取这里的数，避免两处各算一遍对不上
    """一张能照着做的清单：每条 = 文档 · 问题 · 数字 · 建议动作 · 谁判。豁免的单列一栏。

    `deep_all` = [(path, "L{d}（被 L{d-1} 的 {parent} 引用）"), …]，披露深度 ≥ L3 的文档。"""
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
    for p, num in deep_all:
        a, who = ACTION["披露过深"]
        add("披露过深", p, num, a, who)

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
