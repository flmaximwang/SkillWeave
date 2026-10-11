#!/usr/bin/env python3
"""从文档树本身推出 39 个 skill 的关系图：谁能被谁点到。
只用两处机械证据：① 正文里指向别的 skill 的路径/名字 ② 名字前缀家族。
输出：连通分量 + 前缀家族，用来回答「顶层到底有几个端点」。"""
import os, re, json, sys, collections

P = "/Users/maxim/Documents/AgentSkill/AgentSkill-UsingHermes"
SK = os.path.join(P, "skills")

# 1) 枚举 skill：目录含 SKILL.md
skills = {}   # slug -> (relpath, name, desc)
for dp, dn, fn in os.walk(SK):
    if "SKILL.md" in fn:
        slug = os.path.basename(dp)
        t = open(os.path.join(dp, "SKILL.md"), encoding="utf-8", errors="replace").read()
        m = re.search(r"(?m)^name:\s*(.+?)\s*$", t)
        d = re.search(r"(?m)^description:\s*(.+?)\s*$", t)
        rel = os.path.relpath(dp, P)
        nm = (m.group(1).strip().strip('"') if m else slug)
        ds = (d.group(1).strip().strip('"') if d else "")
        skills[slug] = dict(rel=rel, name=nm, desc=ds)
print("skills:", len(skills))

slugs = sorted(skills)
# 2) 证据 A：正文（SKILL.md + references/**）里提到别的 skill
edges = collections.Counter()      # (a,b) 有向：a 的内容提到 b
for slug in slugs:
    base = os.path.join(SK, skills[slug]["rel"].split("/", 1)[1]) if False else os.path.join(P, skills[slug]["rel"])
    text = []
    for dp, dn, fn in os.walk(base):
        for f in fn:
            if f.endswith((".md", ".py", ".sh", ".json", ".yaml", ".yml", ".txt")):
                try:
                    text.append(open(os.path.join(dp, f), encoding="utf-8", errors="replace").read())
                except OSError:
                    pass
    blob = "\n".join(text)
    for other in slugs:
        if other == slug:
            continue
        # 路径式 `.../<other>/` 或 `.../<other>` 出现，或裸名出现（用非单词字符边界）
        hits = len(re.findall(r"(?<![\w-])" + re.escape(other) + r"(?![\w-])", blob))
        if hits:
            edges[(slug, other)] = hits

# 3) 连通分量（忽略方向）
parent = {s: s for s in slugs}
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[rb] = ra
for (a, b), n in edges.items():
    if n >= 1:
        union(a, b)

comp = collections.defaultdict(list)
for s in slugs:
    comp[find(s)].append(s)
comps = sorted((sorted(v) for v in comp.values()), key=lambda v: -len(v))
print("\n=== 连通分量（按正文互指）: %d 个 ===" % len(comps))
for i, c in enumerate(comps, 1):
    print(f"[{i}] {len(c)} 个: " + ", ".join(c))

# 4) 每个 skill 的出度/入度（被引用多的 = 更靠内层）
indeg = collections.Counter()
outdeg = collections.Counter()
for (a, b), n in edges.items():
    outdeg[a] += 1
    indeg[b] += 1
print("\n=== 被最多别的 skill 点到（入度）top12 ===")
for s, n in indeg.most_common(12):
    print(f"  {n:2d}  <- {s}")
print("\n=== 指向最多别的 skill（出度）top12 ===")
for s, n in outdeg.most_common(12):
    print(f"  {n:2d}  -> {s}")

# 5) 前缀家族（机械）
def family(s):
    for p in ("maintain-hermes-", "install-hermes-", "remove-hermes-", "update-hermes-",
              "hermes-", "manage-", "recruit-", "dispatch-", "load-"):
        if s.startswith(p):
            return p.rstrip("-")
    return s
fam = collections.defaultdict(list)
for s in slugs:
    fam[family(s)].append(s)
print("\n=== 名字前缀家族: %d 个 ===" % len(fam))
for k in sorted(fam, key=lambda k: -len(fam[k])):
    print(f"  {len(fam[k]):2d}  {k}: " + ", ".join(fam[k]))

json.dump({"skills": skills, "edges": {f"{a}->{b}": n for (a, b), n in edges.items()},
           "components": comps,
           "indeg": dict(indeg), "outdeg": dict(outdeg),
           "families": {k: v for k, v in fam.items()}},
          open("/tmp/sw-graph.json", "w"), indent=1, ensure_ascii=False)
print("\n-> /tmp/sw-graph.json")
