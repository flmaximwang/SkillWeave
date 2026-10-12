"""度量命令：layers / checks / audit / judge / score（只读）。

从 weave.py 拆出，逻辑未改。"""
import codecs, json, os, re
from .common import est_tokens, kind_of_file
from .graph import dup_pairs, iter_text_files
from .model import is_nested_skill, skills_root, top_level_skills
from .pack import Pack




def cmd_layers(root, out):
    """三级披露度量：L1 = pack 层（所有 skill 的 name+description，常驻）·
    L2 = 每个 skill 的 SKILL.md 正文（触发时载入）· L3 = references/scripts/assets（按需）。"""
    pack = Pack.load(root)
    if pack is None:
        print("[layers] FAIL 这个目录里没有任何 skill（找不到 SKILL.md）")
        return 1
    root, tree, skills, skipped = pack.root, pack.tree, pack.skills, pack.skipped
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
    nested = [s for s in skills if is_nested_skill(root, s["id"])]
    if nested:
        # 单入口形状：岛内嵌套 skill 的 description **不是常驻的**（Agent 只看入口那 1 条），
        # 上面那个「常驻」数是多入口口径的账；这里把单入口口径的常驻单独报出来，免得读者误读。
        top = top_level_skills(root, skills)
        top_tok = est_tokens("\n".join(s["description"] for s in top))
        L.append(f"  ↳ 其中 {len(nested)} 个是**岛内嵌套 skill**（住在入口的 `references/` 里）："
                 f"单入口形状下它们不进常驻菜单，常驻只有 {len(top)} 条 = {top_tok} token；"
                 f"上行的 {est_tokens(l1_text)} token 是**多入口**口径（= 契约 §7 的 L1 对比列）。")
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
    pack = Pack.load(root)
    if pack is None:
        print("[checks] FAIL 这个目录里没有任何 skill")
        return 1
    root, skills = pack.root, pack.skills
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
    pack = Pack.load(root)
    if pack is None:
        # `Pack.load` 一并盖住了「目录里有文件但一份 SKILL.md 都没有」（不是 skill pack）——
        # 以前这里只在 `tree is None` 时报错，紧接着算中位数就 IndexError（312 个目录里 246 个命中）。
        print("[audit] FAIL 这个目录里没有任何 skill（找不到 SKILL.md）")
        return 1
    root, skills = pack.root, pack.skills
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

    # —— dup：候选「抢题」对。两个口径都算（父目录 + **岛×岛**），非字面信号也算候选 —— issue #3。
    # 单入口形状下每个岛内没有兄弟，「同层」必须是 Agent 真正看到的那一级（岛），否则跨岛同题永远比不到。
    pairs = dup_pairs(pack)
    rep["dup"] = {"pairs_top": pairs[:top],
                  "pairs_over_050": sum(1 for p in pairs if p["score"] > 0.5),
                  "pairs_candidates": sum(1 for p in pairs if p["candidate"]),
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
    print(f"[audit] dup  候选 {rep['dup']['pairs_candidates']} 对（父目录 + 岛×岛）；"
          f"字面分>0.5 的 {rep['dup']['pairs_over_050']} 对 · 共比 {rep['dup']['pairs_total']} 对；top:")
    for p in rep["dup"]["pairs_top"][:5]:
        sig = " · 信号=" + ",".join(sorted(p["signals"])) if p["signals"] else ""
        print(f"    {p['score']:.2f} desc={p['sim_desc']:.2f} [{'+'.join(p['scopes'])}]{sig} | "
              f"{p['a']}  ↔  {p['b']}")
    c = rep["cost"]
    print(f"[audit] cost  常驻 {c['resident_chars']} 字符 ≈ {c['resident_est_tokens']} token · "
          f"L2 全体 {c['l2_est_tokens_all']} tok（中位 {c['l2_est_tokens_median']}）· "
          f"L3 {c['l3_files']} 文件 / {c['l3_bytes']} B")
    print(f"[audit] 出: {os.path.join(out, 'audit.json')}")
    return 0




def cmd_judge(root, prompts_path, out, trunc=57):
    """生成**一个纯文本判官输入**（候选只有 description 截断窗口）+ 独立的金标文件 + 任务书。
    判官只读 judge-input.txt；金标永远不进它。"""
    pack = Pack.load(root)
    if pack is None:
        print("[judge] FAIL 这个目录里没有任何 skill")
        return 1
    skills = pack.skills
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
