#!/usr/bin/env python3
"""把「互指图」+「名字/描述词面」两轴合起来，数顶层端点。
互指 = 硬证据（谁真的指到谁）；词面 = 弱证据（只在互指没连上时用来补）。
输出：合并后的分量数 + 每条补边的分数 + 仍然孤立者。"""
import json, re, collections
g = json.load(open("/tmp/sw-graph.json"))
skills = g["skills"]
edges = {tuple(k.split("->")): v for k, v in g["edges"].items()}
slugs = sorted(skills)

STOP = set("the a an and or of to in on for with your you is are be it its this that when use used using "
           "skill skills hermes agent agents file files note notes hermes-om profile profiles only not "
           "把 的 了 在 是 用 时 我 你 它 这 那 和 与 或".split())
def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2}
def jac(a, b):
    return len(a & b) / len(a | b) if (a | b) else 0.0

desc = {s: toks(skills[s]["desc"] + " " + skills[s]["name"]) for s in slugs}

parent = {s: s for s in slugs}
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[rb] = ra

for (a, b) in edges:                       # 硬证据
    union(a, b)

# 弱证据：词面相似度够高就并（只在两边不同分量时才记一条）
added = []
for i, a in enumerate(slugs):
    for b in slugs[i+1:]:
        if find(a) == find(b):
            continue
        sim = jac(desc[a], desc[b])
        if sim >= 0.30:
            union(a, b); added.append((round(sim, 2), a, b))
print("=== 词面补边（desc+name 的 jaccard ≥ 0.30，仅列出真并了的）: %d 条 ===" % len(added))
for s, a, b in sorted(added, reverse=True):
    print(f"  {s}  {a}  ~  {b}")

comp = collections.defaultdict(list)
for s in slugs: comp[find(s)].append(s)
comps = sorted((sorted(v) for v in comp.values()), key=lambda v: -len(v))
print("\n=== 合并后顶层分量: %d 个 ===" % len(comps))
for i, c in enumerate(comps, 1):
    print(f"[{i}] {len(c)}: " + ", ".join(c))

# 只看互指孤立的 9 个，它们各自最像谁
solo = [s for s in slugs if not any((s in e or s in (e[1], e[0])) for e in edges)]
print("\n=== 互指孤立的 %d 个，各自词面最近的三个 ===" % len(solo))
for s in solo:
    near = sorted(((jac(desc[s], desc[o]), o) for o in slugs if o != s), reverse=True)[:3]
    print(f"  {s:34s} " + " | ".join(f"{o}({v:.2f})" for v, o in near))
