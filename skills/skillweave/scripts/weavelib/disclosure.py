"""披露链命令：disclosure / dispatch / verify。

从 weave.py 拆出，逻辑未改。"""
import collections, difflib, hashlib, json, os, tempfile, time
from .common import est_tokens, read_text
from .graph import _content_key, _doc_edges, _doc_inbound, _findings, _pack_files, _prompt_for, _read_waivers, _waived
from .model import git
from .pack import Pack
from .render import _doc_nodes, _rev, render_todo_md







CAP_DESC_CHARS = 1024


CAP_BODY_TOKENS = 5000


CAP_BODY_LINES = 500


# 字节上限只管「会被整份读进去的」资源（references/、assets/…）。脚本不属于这类，见 `cap_of`。
CAP_FILE_BYTES = 20000




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
    pack = Pack.load(root)
    if pack is None:
        print("[disclosure] FAIL 这个目录里没有任何 skill（找不到 SKILL.md）")
        return 1
    root, skills = pack.root, pack.skills
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
        # 脚本不设字节上限：Agent 从不整份读脚本 —— 它读 SKILL.md 里那几行调用说明，再按需 grep / 分段读。
        # 所以「脚本多大」不是披露缺陷，拆它只是把一次调用变成几次跳转。脚本这边唯一的披露要求：
        # 被所属的 SKILL.md 点名（不点名就是孤儿）。
        if n["kind"] in ("binary", "script"):
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
         "- **超限**：超过它那类的上限（正文 ≥5000 tok 或 >500 行 · description >1024 字符 · 资源文件 >20000 B）。"
         "**脚本不计**：Agent 不整份读脚本，字节数不是披露缺陷（口径见 `docs/contract.md` §4）。",
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
          f"description ≤{CAP_DESC_CHARS} 字符 · 单份文件（不含 `scripts/`）≤{CAP_FILE_BYTES} B。",
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
