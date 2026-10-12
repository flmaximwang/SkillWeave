"""改写命令：propose / apply / collapse / prepare。

从 weave.py 拆出，逻辑未改。"""
import collections, difflib, json, os, re, shutil, subprocess, tempfile, time, unicodedata
from .common import description_health, est_tokens, read_text, sha256_file
from .deliver import _ensure_git_copy, _worktree_copy
from .frontmatter import frontmatter_selfcheck, parse_frontmatter, yaml_scalar
from .graph import _allowed_files, _clone_copy, _content_key, _find_anchor, _in_git_repo, _plan_items, _read_waivers, _waived, cross_skill_edges, dup_pairs, first_layer_entries, islands_of, section_spans
from .model import add_mentions, git, skills_root, top_level_skills, tracked_set, walk_dir
from .pack import Pack
from .render import _default_entry_dir, _rev, island_dirs, island_index_md, render_collapse_md, umbrella_body




def propose_actions(root, cap=20, merge_at=0.97, rewrite_at=0.5):
    """四类动作的**提案**（不改盘）：拆 / 分 / 并 / 改写。每条带 `文件:行`、diff 形状、是否可机械执行。
    需要语言模型的判断（哪段该下沉、进哪个类目、触发词怎么改）一律 `needs_model=True`，CLI 不假装能做。"""
    pack = Pack.load(root)
    if pack is None:
        # 空目录：与其余 8 个命令一致 FAIL 退 1。别产一份 count=0 的报告冒充成功，
        # 也别打印一条 `none …` 看着像合法提案（重构时真踩了这个坑）。
        print(f"[propose] FAIL 这个目录里没有任何 skill（找不到 SKILL.md）")
        return 1
    root = pack.root
    tree, skills = pack.tree, pack.skills
    sr = skills_root(tree)
    l1 = [c for c in sr["children"] if c["kind"] in ("skill", "category")]
    props = []

    # —— 并（近重复）：候选对来自 dup_pairs —— 父目录 + **岛×岛** + 非字面信号（issue #3）。
    # 旧写法只比同父目录的兄弟，单入口形状下跨岛同题永远进不了候选集。
    by_id = {s["id"]: s for s in skills}
    for rec in dup_pairs(pack, score_at=rewrite_at):
        if not rec["candidate"]:
            continue          # 非候选不提案（恢复被 dup_pairs 放宽掉的那道闸）
        a, b = by_id.get(rec["a"]), by_id.get(rec["b"])
        if a is None or b is None:
            continue
        a, b = sorted([a, b], key=lambda s: s["id"])
        sim = rec["sim_desc"]
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
            "evidence": {"sim_desc": round(sim, 3), "scopes": rec["scopes"], "signals": rec["signals"],
                         "same_names": same_names,
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

    pack_obj = Pack.load(dest)
    if pack_obj is None:
        print("[prepare] FAIL 副本里没有任何 skill（找不到 SKILL.md）")
        return 1
    skills, skipped = pack_obj.skills, pack_obj.skipped
    tree = pack_obj.tree
    edges, islands = pack_obj.edges(), pack_obj.islands()
    dirs = island_dirs(_default_entry_dir(dest), skills, islands)
    byid = pack_obj.by_id()
    resident = pack_obj.resident_tokens()
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




def cmd_collapse(root, out, apply_changes=False, description=None, entry_dir=None):
    """把 pack 塌成「L1 = 1 个 skill 入口」：**默认 dry-run**，写一份 `COLLAPSE.md`（数字 + 伞体 + 要跑的 git mv）。

    分工：机械的（搬目录、生成伞体与各岛 `INDEX.md`）工具做；**那一条 description 必须人来写**——
    它是唯一的常驻触发词，是判断题。所以没 `--description` 时 `--apply` 直接拒绝，不生成半成品。

    单位 = **顶层 skill**（`top_level_skills`）：已经收进某个入口 `references/` 的嵌套 skill 不再搬一次，
    否则在 collapse 过的 pack 上重跑会把岛内 skill 又搬一层。"""
    pack_obj = Pack.load(root)
    if pack_obj is None:
        print("[collapse] FAIL 这个目录里没有任何 skill（找不到 SKILL.md）")
        return 1
    skills = pack_obj.top()
    if not skills:
        print("[collapse] FAIL 顶层没有 skill（全都住在别的 skill 的 references/ 里 —— 已经是单入口）")
        return 1
    tree = pack_obj.tree
    # **只用顶层 skill 算互指与岛**：`Pack.edges()` 是「全部 skill」口径，而 collapse 的单位是顶层 ——
    # 混用会把已收进 `references/` 的嵌套 skill 再当成岛搬一层（docstring 里那条警告）。
    add_mentions(root, skills)
    edges = cross_skill_edges(root, skills)
    islands = islands_of(skills, edges)
    entry = entry_dir or _default_entry_dir(root)
    dirs = island_dirs(entry, skills, islands)
    before = {"skills": len(skills), "entry": len(first_layer_entries(tree)),
              "resident": pack_obj.resident_tokens(),
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
    # `--description` 落盘前体检（issue #2 的建议 3）：值照写（yaml_scalar 保证合法），但征兆要说出来
    for w in description_health(description):
        print(f"[collapse] ⚠️ --description：{w}")

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
    # frontmatter 用 `yaml_scalar` 写：值里带 `: `、` #`、块指示符 `>-` 一律加双引号转义，
    # 不再裸拼 —— 旧写法（`description: %s`）只要值里有 `: ` 就写出非法 YAML（issue #2）。
    head = ("---\nname: %s\ndescription: %s\n---\n\n# %s\n\n"
            % (yaml_scalar(entry), yaml_scalar(description.strip()), entry))
    sk_path = os.path.join(root, "skills", entry, "SKILL.md")
    with open(sk_path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(umbrella_body(dirs, byid)) + "\n")
    # 落盘后回读：① **顶层**技能数必须是 1（入口）、入口层必须是 1；② **写出的 frontmatter 必须自己读得回去**
    # （真 YAML 解析器 / Hermes skill loader / skills-manager 都会读它，工具自带的宽松解析器吃得下坏文件）。
    # 注意：回读到的 skills2 含岛内嵌套 skill（它们也是 skill），所以判「塌成单入口」要看**顶层**数。
    skills2, skipped2 = [], []
    tree2 = walk_dir(root, root, "", tracked_set(root), skipped2, skills2)
    n_top = len(top_level_skills(root, skills2)) if tree2 else -1
    n_entry = len(first_layer_entries(tree2)) if tree2 else -1
    meta2, _, _ = parse_frontmatter(read_text(sk_path))
    fm_errs = frontmatter_selfcheck(read_text(sk_path))
    desc_ok = meta2.get("description") == description.strip()
    ok = (n_top == 1 and n_entry == 1 and not fm_errs and desc_ok)
    print(f"[collapse] 落盘后回读：顶层技能 {n_top} 个（含岛内嵌套共 {len(skills2)} 个）· "
          f"入口层 {n_entry} 项 —— {'✅ 已塌成单入口' if ok else '❌ 没塌成单入口'}"
          f" · 岛 {len(dirs)} 个 · 各岛 INDEX.md 已写")
    if fm_errs:
        for e in fm_errs:
            print(f"[collapse] ⛔ 写出的 frontmatter 不合法：{e}")
    elif not desc_ok:
        print(f"[collapse] ⛔ description 回读不一致（写出 {description.strip()!r}，读回 {meta2.get('description')!r}）")
    else:
        print("[collapse] ✅ frontmatter 自检：合法 YAML（未加引号的标量里没有 `: `）· description 回读一致")
    return 0 if ok else 1
