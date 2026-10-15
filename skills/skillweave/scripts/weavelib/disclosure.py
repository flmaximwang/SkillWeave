"""披露链命令：disclosure / dispatch / verify。

从 weave.py 拆出，逻辑未改。"""
import collections, difflib, hashlib, json, os, tempfile, time
from .common import (CAP_BODY_LINES, CAP_BODY_TOKENS, CAP_DESC_CHARS, CAP_NAME_CHARS,
                     CAP_REF_LINES, est_tokens, read_text)
from .graph import _content_key, _doc_edges, _doc_inbound, _findings, _pack_files, _prompt_for, _read_waivers, _waived
from .model import git
from .pack import Pack
from .render import _doc_nodes, _rev, render_todo_md


# 资源目录**自动豁免**：这三个目录下的文件不要求被 SKILL.md 显式引用。它们进「已豁免」而不进
# 「待办」，waivers.txt 不必手写（口径 docs/contract.md §0.6）。但若确实被引用，路径仍要存在 ——
# 悬空照报，豁免的只是「到不了根」这一条。
AUTO_WAIVED_DIRS = ["templates", "examples", "tests"]


AUTO_WAIVE_REASON = "自动豁免：资源目录"


def _auto_waived(path):
    """路径里带 `templates/` · `examples/` · `tests/` **目录段** = 自动豁免的资源文件。

    只看目录段（末尾是文件名，不算）：一份文件叫 `templates`（无后缀）不该被误判。"""
    return any(d in AUTO_WAIVED_DIRS for d in path.replace(os.sep, "/").split("/")[:-1])


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




def _executor_section(executor, batch_num):
    """D 阶段给每个 prompt 追加的「## 执行方式」：把执行者配置的命令模板填成**可照抄的一行**。

    配置来自 prepare 写下的 executor.json（落在副本的 dispatch 目录下；ticket 06 定结构：
    type、model、command_template 三个字段）。{model} / {input} / {output} 三个占位符在这里换成实际值 ——
    用户（或 CI）看到 prompt 文件末尾就知道怎么执行，不必回头翻文档或回忆。"""
    prompt_name = f"batch-{batch_num}.prompt.md"
    output_name = f"batch-{batch_num}.proposal.json"
    cmd = (executor.get("command_template") or "")
    cmd = cmd.replace("{model}", executor.get("model", ""))
    cmd = cmd.replace("{input}", prompt_name)
    cmd = cmd.replace("{output}", output_name)
    lines = ["---", "", "## 执行方式", "",
             f"**类型**: {executor.get('type', '?')}", "",
             "**命令**:", "```bash", cmd, "```", "",
             "**说明**:",
             f"- `{{input}}`: 本文件路径（{prompt_name}）",
             f"- `{{output}}`: 提案输出文件（{output_name}）", ""]
    if executor.get("type") == "manual":
        lines += ["请手动执行上述 prompt，将提案以 JSON 格式写入输出文件。", ""]
    return "\n".join(lines)


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
    # 执行者配置（ticket 06 由 prepare 写进副本 → ticket 07 在这里读）：副本 dispatch 目录下的 executor.json。
    # 读到了就把执行说明追加进每个 prompt、并把整份配置记进 plan.json；**读不到只警告，不阻塞**。
    executor = None
    executor_config_path = os.path.join(root, "dispatch", "executor.json")
    if os.path.exists(executor_config_path):
        with open(executor_config_path, encoding="utf-8") as f:
            executor = json.load(f)
    plan = {"pack": os.path.basename(root), "base_rev": base_rev, "batch_size": batch_size,
            "baseline": os.path.join(d, "baseline.json"), "batches": []}
    if executor is not None:
        plan["executor"] = executor
    for n, skills in enumerate(batches, 1):
        items = sorted((it for sk in skills for it in by_skill[sk]), key=lambda x: (x["kind"], x["path"]))
        b = {"id": f"B{n}", "skills": skills, "items": items}
        text = _prompt_for(b, root, F, files, dj, base_rev, os.path.basename(root))
        if executor is not None:               # 说明也进 prompt hash：换执行者 = 换了输入（R4）
            text = text.rstrip("\n") + "\n\n" + _executor_section(executor, n)
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
    if executor is None:
        # 不阻塞：没有执行者配置照常派发（prompt 仍然完整），只是少一节「怎么执行」的提示。
        print("[dispatch] 警告：未找到执行者配置（dispatch/executor.json）")
        print("           提示：运行 prepare 时选择执行者，或手动创建配置文件")
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
        # 来源与违规行为见 `docs/contract.md` §4 / `common.CAPS`：
        #   name / description = agentskills.io（硬约束，错误）；正文 token / 行数、references/ 行数 = Anthropic 实践（警告）。
        if n["root"] or n["kind"] == "instructions":
            over = []
            if len(n.get("name") or "") > CAP_NAME_CHARS:
                over.append(f"name {len(n['name'])} 字符 > {CAP_NAME_CHARS}")
            if n["tok"] > CAP_BODY_TOKENS:
                over.append(f"正文 {n['tok']} tok > {CAP_BODY_TOKENS}")
            if n["lines"] > CAP_BODY_LINES:
                over.append(f"正文 {n['lines']} 行 > {CAP_BODY_LINES}")
            if (n["desc_chars"] or 0) > CAP_DESC_CHARS:
                over.append(f"description {n['desc_chars']} 字符 > {CAP_DESC_CHARS}")
            return over
        # 脚本不设上限：Agent 从不整份读脚本 —— 它读 SKILL.md 里那几行调用说明，再按需 grep / 分段读。
        # 所以「脚本多大」不是披露缺陷，拆它只是把一次调用变成几次跳转。脚本这边唯一的披露要求：
        # 被所属的 SKILL.md 点名（不点名就是孤儿）。
        if n["kind"] in ("binary", "script", "asset"):
            return []
        # `references/` 单文件：Anthropic 建议 < 300 行（警告，不拦）。
        if n["kind"] == "reference" and (n["lines"] or 0) > CAP_REF_LINES:
            return [f"{n['lines']} 行 > {CAP_REF_LINES}"]
        return []

    over_all, orphan_all, auto_waived_all = [], [], []
    for p, n in sorted(nodes.items()):
        n["over"] = cap_of(n)
        n["orphan"] = (not n["root"]) and indeg.get(p, 0) == 0
        n["waived"] = bool(n["orphan"] and _auto_waived(p))
        n["waive_reason"] = AUTO_WAIVE_REASON if n["waived"] else None
        n["depth"] = depth[p]
        if n["over"]:
            over_all.append((p, n["over"]))
        if n["waived"]:
            auto_waived_all.append(p)
        elif n["orphan"]:
            orphan_all.append(p)

    # 披露深度：报分布，L3+ **只警告不退出**（spec §4 —— 量出完整问题清单，不拒绝分析）。
    # 一个节点可能有多条入边；取「depth == d-1 的那条」当它的父，作为「谁引用了它」的证据。
    inbound = collections.defaultdict(list)
    for src, ts in edges.items():
        for q in ts:
            inbound[q].append(src)
    max_depth = max((n["depth"] for n in nodes.values() if n["depth"] is not None), default=1)
    depth_histogram = {d: sum(1 for n in nodes.values() if n["depth"] == d)
                       for d in range(1, max_depth + 1)}
    deep_docs = []                              # [(path, depth, parent_path)]，按深度降序
    for p in sorted(nodes, key=lambda x: (-(nodes[x]["depth"] or 0), x)):
        d = nodes[p]["depth"]
        if d is None or d < 3:
            continue
        parents = sorted(q for q in inbound.get(p, []) if nodes.get(q, {}).get("depth") == d - 1)
        deep_docs.append((p, d, parents[0] if parents else "?"))
    deep_all = [(p, f"L{d}（被 L{d - 1} 的 {parent} 引用）") for p, d, parent in deep_docs]

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
    todo_text, n_todo, n_waived_rows = render_todo_md(
        root, nodes, over_all, orphan_all, broken, dup, waivers, auto_waived_all, deep_all)
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
         "- **超限**：超过它那类的上限 —— `name` >64 字符 · `description` >1024 字符（agentskills.io，错误）；"
         "正文 >5000 tok / >500 行 · `references/` 单文件 >300 行（Anthropic 建议，警告）。"
         "**脚本与资源不计**：Agent 不整份读脚本/二进制资源，字节数不是披露缺陷（口径见 `docs/contract.md` §4）。",
         "- **悬空**：写了像本 pack 内的路径，但那个文件不存在。",
         "- **external**：正文里提到的本 pack 之外的文件（不算披露、也不算错）。",
         "- **近重复**：同层两份文档太像，Agent 会选错。", "",
         "口径：**层 = 披露深度**（L1 = 根文档 `SKILL.md`；L2 = L1 正文直接点到的文档；Ln+1 由 Ln 披露）。"
         "不是「按文件类型分三级」那套。", "",
         f"- 根：**{len(roots)} 个**（每个 skill 的 `SKILL.md` 是一个根；1 个 = 单入口形状）",
         f"- 文档节点：**{len(nodes)} 份** · 层数：**{len([x for x in levels if x is not None])}**",
         f"- 超限：**{len(over_all)}** 份 · 到不了根：**{len(orphan_all)}** 份 · "
         f"自动豁免（资源目录）：**{len(auto_waived_all)}** 份 · "
         f"悬空引用：**{len(broken)}** 条 · 外部引用（不算披露）：**{len(external)}** 条",
         f"- 根选择层近重复（Jaccard≥0.5·靠 description 选根才算）：**{len(dup)}** 对",
         f"- **待办 {n_todo} 条 · 已豁免 {n_waived_rows} 条** → 见同目录 [`TODO.md`](TODO.md)"
         f"（豁免规则 {len(waivers)} 条，来自包里 `.skillweave/waivers.txt`）", ""]
    for d in levels:
        if d is None:
            L += ["## 到不了的文档（没有任何根披露到它们；`templates/`·`examples/`·`tests/` 自动豁免）", ""]
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
                bad.append("自动豁免（资源目录）" if n["waived"] else "⚠️ 孤儿")
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
          f"- caps（出处 `docs/contract.md` §4 · 只有 agentskills.io 与 Anthropic 两类来源）："
          f"`name` ≤{CAP_NAME_CHARS} 字符 · `description` ≤{CAP_DESC_CHARS} 字符（agentskills.io，错误）；"
          f"正文 建议 <{CAP_BODY_TOKENS} tok / <{CAP_BODY_LINES} 行 · `references/` 单文件 建议 <{CAP_REF_LINES} 行（Anthropic，警告）。",
          "- 每个文档在表里恰好出现一次（由命令自己核对：节点数 == 表行数）。", ""]

    md = os.path.join(out, "DISCLOSURE.md")
    rows = sum(len(lv[d]) for d in levels)
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    with open(os.path.join(out, "disclosure.json"), "w", encoding="utf-8") as f:
        json.dump({"roots": roots, "levels": {str(k): sorted(v) for k, v in lv.items()},
                   "nodes": {p: {k: v for k, v in n.items()} for p, n in nodes.items()},
                   "edges": {p: ts for p, ts in edges.items()}, "broken": broken, "external": external,
                   "over": over_all, "orphans": orphan_all, "auto_waived": auto_waived_all,
                   "root_near_dup": dup,
                   "depth_histogram": {str(k): v for k, v in depth_histogram.items()}},
                  f, ensure_ascii=False, indent=1, sort_keys=True)
    assert rows == len(nodes), f"对账失败：表行数 {rows} != 节点数 {len(nodes)}"
    print(f"[disclosure] 待办清单 → {todo_md}")
    print(f"[disclosure] 根 {len(roots)} 个（=形状）· 层 " +
          " → ".join(f"L{d}={len(lv[d])}" if d is not None else f"未分层={len(lv[d])}" for d in levels) +
          f" · 文档 {len(nodes)} 份（表行数 {rows} 对账 ✅）· 超限 {len(over_all)} · "
          f"到不了根 {len(orphan_all)} · 自动豁免 {len(auto_waived_all)} · "
          f"悬空 {len(broken)} · external {len(external)}")
    print(f"[disclosure] 披露深度：" +
          " → ".join(f"L{d}={depth_histogram[d]}" for d in range(1, max_depth + 1)))
    if max_depth >= 3:
        print(f"  ⚠️ 检测到 L{max_depth} 层（Anthropic 建议不超过 L2）")
        print(f"  深层文档 {len(deep_docs)} 份（显示前 5 个）：")
        for p, d, _parent in deep_docs[:5]:
            print(f"    L{d} {p}")
    print(f"[disclosure] 出: {md}")
    return 0
