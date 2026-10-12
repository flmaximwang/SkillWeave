"""渲染：TREE.md · TREE.html · LAYERS · DISCLOSURE · TODO 等产物。

从 weave.py 拆出，逻辑未改。"""
import collections, math, os, re
from .common import est_tokens, read_text
from .frontmatter import parse_frontmatter
from .graph import _waived
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




def render_tree_md(root, skills, edges, islands, entry, rev, nested_map=None):
    byid = {s["id"]: s for s in skills}
    nested_map = nested_map or {}
    L = [f"# 文档树 · {os.path.basename(root)}", "",
         f"基准 `{rev}` · 由 `weave.py visualize` 生成，**不要手改**。", "",
         f"skill {len(skills)} 个 · 入口层 {len(entry)} 项 · 常驻菜单 "
         f"{est_tokens(chr(10).join(x['description'] for x in skills))} tok · "
         f"互指岛 {len(islands)} 个", "",
         "> `skill N 个` = 本 pack 里 `SKILL.md` 的份数。单入口形状下入口只有 1 项（入口层 1 项），",
         "> 但岛内嵌套 skill（住在入口的 `references/<岛>/<skill>/`）各算一个 —— 所以 N 可以 > 1。", "",
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
            for ns in nested_map.get(node_id) or []:
                L.append(f"  - ↳ **{ns['name']}** 〔岛内嵌套 skill〕`{ns['id']}` · "
                         f"{ns['est_tokens']} tok — {ns['description'][:80]}")
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




def render_tree_html(root, skills, edges, islands, entry, rev, stats, nested_map=None):
    byid = {s["id"]: s for s in skills}
    nested_map = nested_map or {}
    isl_of = {i: n for n, isl in enumerate(islands, 1) for i in isl}
    W = 1680
    P = []          # svg 片段
    y = 196         # 数字卡片占到 132，标题与第一批框都从下面起（第一版压在卡片上，实测）

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
            rect(40, y, 1596, h, "#191b24", col, rx=10, sw=1.6, cls="node")
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
            rect(40, y, 1596, 30, "#191b24", col, rx=10, sw=1.6, cls="node")
            text(56, y + 21, s["name"], 14, "#f2f2f7", weight="600")
            nest = nested_map.get(node_id) or []
            text(420, y + 21, f"〔散项 · 岛 {isl} · 单独成岛——和本包别的 skill 一条互指都没有〕"
                              f"L1 {est_tokens(s['description'])} tok · "
                              f"L2 {s['est_tokens']} tok · L3 {len(s['files']) - 1} 个文件",
                 12, col, mono=True)
            y += 40
            if nest:      # 入口之下还住着 skill（单入口形状：`references/<岛>/<skill>/`）→ 逐个画框
                # 这些框是 `stats["skills"]` 的一部分：旧实现不下钻，岛内 skill 一个框都不画
                text(64, y + 12, f"↳ 入口之下还有 {len(nest)} 个 skill（岛内嵌套，住在这个入口的 "
                                 f"references/ 里）—— 它们各自也是本 pack 的一个 skill", 11.5, "#9aa0b0")
                y += 24
                for ns in nest:
                    depth = ns["id"].count("/") - node_id.count("/")
                    x0 = 40 + 26 * depth
                    rect(x0, y, 1596 - (x0 - 40), 26, "#15171f", "#3a3f52", rx=6, sw=0.9, cls="node")
                    text(x0 + 14, y + 18, ns["name"], 12.5, "#dfe3f2", weight="600")
                    text(x0 + 260, y + 18, f"`{ns['id']}` · L2 {ns['est_tokens']} tok · "
                                           f"L3 {len(ns['files'])} 个文件 · 岛 {isl}",
                         11, col, mono=True)
                    y += 30
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
 tok = CJK×1 + 其它×0.25（估算）· 互指 = 正文点名 + 引用落到别的 skill 目录 · 岛 = 互指图连通分量<br>
 节点框（<code>rect.node</code>）数 = 本 pack 的 <code>SKILL.md</code> 份数 = <b>{stats["skills"]}</b> 个 skill
（单入口形状下入口层仍是 1 项；岛内嵌套 skill 各画一个框）。
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
    edges, islands, entry = pack.edges(), pack.islands(), pack.entry()
    over_l2 = [s for s in skills if s["est_tokens"] > 5000 or s["body_lines"] > 500]
    stats = {"skills": len(skills), "entry": len(entry), "islands": len(islands),
             "resident": pack.resident_tokens(),
             "resident_chars": sum(s["description_chars"] for s in skills),
             "over_l2": len(over_l2),
             "orphans": sum(len(s["orphans"]) for s in skills),
             "broken": sum(len(s["broken"]) for s in skills)}
    rev = _rev(root)
    # 每个入口 skill 之下的嵌套 skill（单入口形状的岛内 skill）→ 交给渲染器画出来，
    # 这样「TREE.html 节点框数 == 本 pack 的 SKILL.md 数」这条验收判据才成立。
    nested_map = pack.nested_skill_nodes()
    os.makedirs(out, exist_ok=True)
    md = os.path.join(out, "TREE.md")
    html = os.path.join(out, "TREE.html")
    with open(md, "w", encoding="utf-8") as f:
        f.write(render_tree_md(root, skills, edges, islands, entry, rev, nested_map))
    with open(html, "w", encoding="utf-8") as f:
        f.write(render_tree_html(root, skills, edges, islands, entry, rev, stats, nested_map))
    print(f"[visualize] 入口层={len(entry)} 互指岛={len(islands)} 常驻={stats['resident']}tok "
          f"孤儿={stats['orphans']} 悬空={stats['broken']}")
    print(f"[visualize] skill={stats['skills']} 个（= 本 pack 的 SKILL.md 数；岛内嵌套 skill 也算）")
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
