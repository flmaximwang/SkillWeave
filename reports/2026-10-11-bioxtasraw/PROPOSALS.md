# 提案：AgentSkill-UsingBioXTASRAW

共 7 条；其中可机械执行 0 条、需语言模型判断 7 条。

## 1. [split] skills/analyze-time-resolved-series/SKILL.md:142
- 判断：5393 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 5393, "lines": 189, "sections_by_size": [{"title": "E — 执行步骤 (Execution)", "lines": "142-168", "chars": 2086}, {"title": "A1 — 案例 (Past Application)", "lines": "76-114", "chars": 2042}, {"title": "R — 原文 (Reading)", "lines": "18-55", "chars": 1960}, {"title": "I — 骨架 (Interpretation)", "lines": "56-75", "chars": 1580}]}`
- diff 形状：`~ skills/analyze-time-resolved-series/SKILL.md:142-168 (E — 执行步骤 (Execution)) → + skills/analyze-time-resolved-series/references/<slug>.md` ；`~ skills/analyze-time-resolved-series/SKILL.md:76-114 (A1 — 案例 (Past Application)) → + skills/analyze-time-resolved-series/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 2. [split] skills/assess-guinier-fit-quality/SKILL.md:20
- 判断：6748 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 6748, "lines": 217, "sections_by_size": [{"title": "R — 原文 (Reading)", "lines": "20-82", "chars": 2526}, {"title": "E — 执行步骤 (Execution)", "lines": "164-191", "chars": 2065}, {"title": "I — 骨架 (Interpretation)", "lines": "83-100", "chars": 1774}, {"title": "B — 边界 (Boundary)", "lines": "192-223", "chars": 1691}]}`
- diff 形状：`~ skills/assess-guinier-fit-quality/SKILL.md:20-82 (R — 原文 (Reading)) → + skills/assess-guinier-fit-quality/references/<slug>.md` ；`~ skills/assess-guinier-fit-quality/SKILL.md:164-191 (E — 执行步骤 (Execution)) → + skills/assess-guinier-fit-quality/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 3. [split] skills/compute-and-validate-p-of-r/SKILL.md:18
- 判断：5670 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 5670, "lines": 232, "sections_by_size": [{"title": "R — 原文 (Reading)", "lines": "18-69", "chars": 1944}, {"title": "E — 执行步骤 (Execution)", "lines": "184-208", "chars": 1578}, {"title": "B — 边界 (Boundary)", "lines": "209-237", "chars": 1383}, {"title": "A1 — 案例 (Past Application)", "lines": "136-158", "chars": 1249}]}`
- diff 形状：`~ skills/compute-and-validate-p-of-r/SKILL.md:18-69 (R — 原文 (Reading)) → + skills/compute-and-validate-p-of-r/references/<slug>.md` ；`~ skills/compute-and-validate-p-of-r/SKILL.md:184-208 (E — 执行步骤 (Execution)) → + skills/compute-and-validate-p-of-r/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 4. [split] skills/configure-bioxtas-raw-for-a-dataset/SKILL.md:124
- 判断：5070 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 5070, "lines": 175, "sections_by_size": [{"title": "B — 边界 (Boundary)", "lines": "124-181", "chars": 3158}, {"title": "配置怎么造出来：六步链（判据与顺序约束）", "lines": "53-69", "chars": 1169}, {"title": "A2 — 触发场景 (Future Trigger)", "lines": "85-108", "chars": 695}, {"title": "E — 执行步骤 (Execution)", "lines": "109-123", "chars": 679}]}`
- diff 形状：`~ skills/configure-bioxtas-raw-for-a-dataset/SKILL.md:124-181 (B — 边界 (Boundary)) → + skills/configure-bioxtas-raw-for-a-dataset/references/<slug>.md` ；`~ skills/configure-bioxtas-raw-for-a-dataset/SKILL.md:53-69 (配置怎么造出来：六步链（判据与顺序约束）) → + skills/configure-bioxtas-raw-for-a-dataset/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 5. [split] skills/deconvolve-overlapping-elution-peaks/SKILL.md:24
- 判断：6556 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 6556, "lines": 265, "sections_by_size": [{"title": "R — 原文 (Reading)", "lines": "24-119", "chars": 3402}, {"title": "A1 — 案例 (Past Application)", "lines": "154-186", "chars": 2267}, {"title": "E — 执行步骤 (Execution)", "lines": "212-244", "chars": 1917}, {"title": "B — 边界 (Boundary)", "lines": "245-274", "chars": 1496}]}`
- diff 形状：`~ skills/deconvolve-overlapping-elution-peaks/SKILL.md:24-119 (R — 原文 (Reading)) → + skills/deconvolve-overlapping-elution-peaks/references/<slug>.md` ；`~ skills/deconvolve-overlapping-elution-peaks/SKILL.md:154-186 (A1 — 案例 (Past Application)) → + skills/deconvolve-overlapping-elution-peaks/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 6. [split] skills/evaluate-a-shape-reconstruction/SKILL.md:20
- 判断：6857 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 6857, "lines": 245, "sections_by_size": [{"title": "R — 原文 (Reading)", "lines": "20-101", "chars": 3297}, {"title": "I — 骨架 (Interpretation)", "lines": "102-144", "chars": 2362}, {"title": "E — 执行步骤 (Execution)", "lines": "195-215", "chars": 2167}, {"title": "B — 边界 (Boundary)", "lines": "216-251", "chars": 1779}]}`
- diff 形状：`~ skills/evaluate-a-shape-reconstruction/SKILL.md:20-101 (R — 原文 (Reading)) → + skills/evaluate-a-shape-reconstruction/references/<slug>.md` ；`~ skills/evaluate-a-shape-reconstruction/SKILL.md:102-144 (I — 骨架 (Interpretation)) → + skills/evaluate-a-shape-reconstruction/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 7. [split] skills/fit-a-high-resolution-model-to-data/SKILL.md:18
- 判断：6271 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 6271, "lines": 208, "sections_by_size": [{"title": "R — 原文 (Reading)", "lines": "18-66", "chars": 2162}, {"title": "I — 骨架 (Interpretation)", "lines": "67-102", "chars": 2076}, {"title": "E — 执行步骤 (Execution)", "lines": "160-183", "chars": 1969}, {"title": "A1 — 案例 (Past Application)", "lines": "103-129", "chars": 1706}]}`
- diff 形状：`~ skills/fit-a-high-resolution-model-to-data/SKILL.md:18-66 (R — 原文 (Reading)) → + skills/fit-a-high-resolution-model-to-data/references/<slug>.md` ；`~ skills/fit-a-high-resolution-model-to-data/SKILL.md:67-102 (I — 骨架 (Interpretation)) → + skills/fit-a-high-resolution-model-to-data/references/<slug>.md`
- 可机械执行：否（要模型判断）
