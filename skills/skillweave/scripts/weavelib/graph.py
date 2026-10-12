"""派生图：互指边 / 互指岛 / 披露链（文档图）。

从 weave.py 拆出，逻辑未改。"""
import collections, fnmatch, hashlib, json, os, re, subprocess
from .common import extract_declared_refs, fence_lines, headings, kind_of_file, read_text
from .model import SKIP_DIRS, SKIP_FILES, git, skills_root




def add_headings(node):
    """把 skill 的正文标题挂成 heading 子节点，供 depth-to-needle 用。"""
    hs = node.pop("headings", [])
    for h in hs:
        node["children"].append({"id": f"{node['id']}SKILL.md#{h['line']}", "kind": "heading",
                                 "parent": node["id"], "bytes": 0, "est_tokens": 0,
                                 "summary": h["title"], "summary_source": f"{node['id']}SKILL.md:{h['line']}",
                                 "level": h["level"], "refs": [], "mentions": [], "children": []})
    return node




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




def iter_text_files(path):
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn not in SKIP_FILES and kind_of_file(fn) != "asset":
                yield os.path.join(dirpath, fn)




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




def entry_items(tree):
    """入口层摆出的项 → `[(kind, id, member_skill_ids)]`。

    契约 §0：入口层 = 从 pack 根往下、唯一选择项还是类目就继续下钻，遇 ≥2 项停。
    pack 根自己就是 skill（入口直接摆根上）时，入口层就是这一个 skill。
    **岛内嵌套 skill 不进入口层** —— 单入口形状下入口层就该是 1 项（issue #1 的验收判据）。"""
    sr = skills_root(tree)
    if sr["kind"] == "skill":
        return [("skill", sr["id"], [sr["id"]])]
    out = []
    for c in sr["children"]:
        if c["kind"] == "category":
            out.append(("category", c["id"], sorted(x["id"] for x in _leaves(c))))
        elif c["kind"] == "skill":
            out.append(("skill", c["id"], [c["id"]]))
    return out




def nested_skill_nodes(node):
    """`node` 之下的**嵌套 skill 节点**（不含 node 自己，深度优先、按 id 排序）。"""
    out = []
    for c in node.get("children") or []:
        if c["kind"] == "skill":
            out.append(c)
            out += nested_skill_nodes(c)
        else:
            out += nested_skill_nodes(c)
    return out




def _leaves(node):
    if node["kind"] == "skill":
        return [node]
    out = []
    for c in node["children"]:
        out += _leaves(c)
    return out


TEXT_LIKE = {".md", ".markdown", ".txt", ".py", ".sh", ".bash", ".js", ".ts", ".json",
             ".yaml", ".yml", ".csv", ".tsv", ".toml", ".ini", ".cfg", ".html", ".svg"}




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




def _content_key(text):
    """内容守恒用的归一化：去掉空行与标题行后的字符序列（拆分允许新增标题/分家，但不许改字）。"""
    keep = [l.strip() for l in text.split("\n")
            if l.strip() and not re.match(r"^#{1,6}\s", l.strip())]
    return "".join(keep)




def _in_git_repo(pack):
    """输入目录是不是在一个 git 仓库里，是就返回仓库根。"""
    g = git(pack, "rev-parse", "--show-toplevel")
    if g is not None and g.returncode == 0 and (g.stdout or "").strip():
        return os.path.realpath(g.stdout.strip())
    return None




def _clone_copy(pack, dest):
    """拷贝一份副本。macOS 走 APFS clonefile（`cp -Rc`，秒级、几乎不占额外空间），不支持就退回 `cp -R`。"""
    r = subprocess.run(["cp", "-Rc", pack, dest], capture_output=True, text=True)
    if r.returncode == 0:
        return "cp -Rc（clonefile）"
    subprocess.run(["cp", "-R", pack, dest], check=True, capture_output=True)
    return "cp -R（本机不支持 clonefile，整份拷）"




def first_layer_entries(tree):
    """入口层摆出几项（tree 口径，与 layers 一致）。"""
    return [c["id"] for c in skills_root(tree)["children"] if c["kind"] in ("skill", "category")]
