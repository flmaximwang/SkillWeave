# 提案：base-now

共 27 条；其中可机械执行 1 条、需语言模型判断 26 条。

## 1. [rewrite] skills/boc-statement/SKILL.md:1 · skills/ccb-statement/SKILL.md:1
- 判断：改写触发词把两者分开（当前 sim_desc=0.81）：skills/boc-statement/ / skills/ccb-statement/
- 证据：`{"sim_desc": 0.809, "layer": "skills/", "same_names": true, "refcount": {"skills/boc-statement/": 0, "skills/ccb-statement/": 0}, "version": {"skills/boc-statement/": null, "skills/ccb-statement/": null}, "b_skill_sha256": "b40a8205532253fdab80303971e4dc36e1d932cb9bae749eea16c5711049b72e", "mechanical_rule": null}`
- diff 形状：`~ skills/boc-statement/SKILL.md:1` ；`~ skills/ccb-statement/SKILL.md:1`
- 可机械执行：否（要模型判断）

## 2. [rewrite] skills/autonomous-ai-agents/hermes-skills-management/SKILL.md:1 · skills/autonomous-ai-agents/hermes-community-extensions/SKILL.md:1
- 判断：改写触发词把两者分开（当前 sim_desc=0.52）：skills/autonomous-ai-agents/hermes-skills-management/ / skills/autonomous-ai-agents/hermes-community-extensions/
- 证据：`{"sim_desc": 0.519, "layer": "skills/autonomous-ai-agents/", "same_names": false, "refcount": {"skills/autonomous-ai-agents/hermes-skills-management/": 1, "skills/autonomous-ai-agents/hermes-community-extensions/": 1}, "version": {"skills/autonomous-ai-agents/hermes-skills-management/": "1.0.0", "skills/autonomous-ai-agents/hermes-community-extensions/": "1.0.0"}, "b_skill_sha256": "51374cf6fd2c1c829b99065529990aab554560c61b76e8f38f0bb8ac3e32a3df", "mechanical_rule": null}`
- diff 形状：`~ skills/autonomous-ai-agents/hermes-skills-management/SKILL.md:1` ；`~ skills/autonomous-ai-agents/hermes-community-extensions/SKILL.md:1`
- 可机械执行：否（要模型判断）

## 3. [rewrite] skills/autonomous-ai-agents/hermes-mcp-server-integration/SKILL.md:1 · skills/autonomous-ai-agents/hermes-profile-authoring/SKILL.md:1
- 判断：改写触发词把两者分开（当前 sim_desc=0.65）：skills/autonomous-ai-agents/hermes-mcp-server-integration/ / skills/autonomous-ai-agents/hermes-profile-authoring/
- 证据：`{"sim_desc": 0.646, "layer": "skills/autonomous-ai-agents/", "same_names": false, "refcount": {"skills/autonomous-ai-agents/hermes-mcp-server-integration/": 2, "skills/autonomous-ai-agents/hermes-profile-authoring/": 1}, "version": {"skills/autonomous-ai-agents/hermes-mcp-server-integration/": "1.0.0", "skills/autonomous-ai-agents/hermes-profile-authoring/": "1.0.0"}, "b_skill_sha256": "aa5dc8c26db9250fc317dd82312d93249efa4994c9ea9221c3b0930d7a6ec7a6", "mechanical_rule": null}`
- diff 形状：`~ skills/autonomous-ai-agents/hermes-mcp-server-integration/SKILL.md:1` ；`~ skills/autonomous-ai-agents/hermes-profile-authoring/SKILL.md:1`
- 可机械执行：否（要模型判断）

## 4. [rewrite] skills/autonomous-ai-agents/hermes-mcp-server-integration/SKILL.md:1 · skills/autonomous-ai-agents/hermes-profile-configuration/SKILL.md:1
- 判断：改写触发词把两者分开（当前 sim_desc=0.72）：skills/autonomous-ai-agents/hermes-mcp-server-integration/ / skills/autonomous-ai-agents/hermes-profile-configuration/
- 证据：`{"sim_desc": 0.721, "layer": "skills/autonomous-ai-agents/", "same_names": false, "refcount": {"skills/autonomous-ai-agents/hermes-mcp-server-integration/": 2, "skills/autonomous-ai-agents/hermes-profile-configuration/": 0}, "version": {"skills/autonomous-ai-agents/hermes-mcp-server-integration/": "1.0.0", "skills/autonomous-ai-agents/hermes-profile-configuration/": "1.0.0"}, "b_skill_sha256": "1ef957d33b4dff6746225aa760d0fad7be04a8148c3d59cfddd9fbc174e150a2", "mechanical_rule": null}`
- diff 形状：`~ skills/autonomous-ai-agents/hermes-mcp-server-integration/SKILL.md:1` ；`~ skills/autonomous-ai-agents/hermes-profile-configuration/SKILL.md:1`
- 可机械执行：否（要模型判断）

## 5. [rewrite] skills/autonomous-ai-agents/hermes-mcp-server-integration/SKILL.md:1 · skills/autonomous-ai-agents/hermes-projects/SKILL.md:1
- 判断：改写触发词把两者分开（当前 sim_desc=0.56）：skills/autonomous-ai-agents/hermes-mcp-server-integration/ / skills/autonomous-ai-agents/hermes-projects/
- 证据：`{"sim_desc": 0.56, "layer": "skills/autonomous-ai-agents/", "same_names": false, "refcount": {"skills/autonomous-ai-agents/hermes-mcp-server-integration/": 2, "skills/autonomous-ai-agents/hermes-projects/": 0}, "version": {"skills/autonomous-ai-agents/hermes-mcp-server-integration/": "1.0.0", "skills/autonomous-ai-agents/hermes-projects/": "1.0.0"}, "b_skill_sha256": "84f971588c5e69705d2e50840bcf2b5960641f097cf28819dc7f32684c658b5e", "mechanical_rule": null}`
- diff 形状：`~ skills/autonomous-ai-agents/hermes-mcp-server-integration/SKILL.md:1` ；`~ skills/autonomous-ai-agents/hermes-projects/SKILL.md:1`
- 可机械执行：否（要模型判断）

## 6. [rewrite] skills/autonomous-ai-agents/hermes-profile-authoring/SKILL.md:1 · skills/autonomous-ai-agents/hermes-profile-configuration/SKILL.md:1
- 判断：改写触发词把两者分开（当前 sim_desc=0.60）：skills/autonomous-ai-agents/hermes-profile-authoring/ / skills/autonomous-ai-agents/hermes-profile-configuration/
- 证据：`{"sim_desc": 0.602, "layer": "skills/autonomous-ai-agents/", "same_names": false, "refcount": {"skills/autonomous-ai-agents/hermes-profile-authoring/": 1, "skills/autonomous-ai-agents/hermes-profile-configuration/": 0}, "version": {"skills/autonomous-ai-agents/hermes-profile-authoring/": "1.0.0", "skills/autonomous-ai-agents/hermes-profile-configuration/": "1.0.0"}, "b_skill_sha256": "1ef957d33b4dff6746225aa760d0fad7be04a8148c3d59cfddd9fbc174e150a2", "mechanical_rule": null}`
- diff 形状：`~ skills/autonomous-ai-agents/hermes-profile-authoring/SKILL.md:1` ；`~ skills/autonomous-ai-agents/hermes-profile-configuration/SKILL.md:1`
- 可机械执行：否（要模型判断）

## 7. [rewrite] skills/autonomous-ai-agents/hermes-profile-authoring/SKILL.md:1 · skills/autonomous-ai-agents/hermes-projects/SKILL.md:1
- 判断：改写触发词把两者分开（当前 sim_desc=0.72）：skills/autonomous-ai-agents/hermes-profile-authoring/ / skills/autonomous-ai-agents/hermes-projects/
- 证据：`{"sim_desc": 0.717, "layer": "skills/autonomous-ai-agents/", "same_names": false, "refcount": {"skills/autonomous-ai-agents/hermes-profile-authoring/": 1, "skills/autonomous-ai-agents/hermes-projects/": 0}, "version": {"skills/autonomous-ai-agents/hermes-profile-authoring/": "1.0.0", "skills/autonomous-ai-agents/hermes-projects/": "1.0.0"}, "b_skill_sha256": "84f971588c5e69705d2e50840bcf2b5960641f097cf28819dc7f32684c658b5e", "mechanical_rule": null}`
- diff 形状：`~ skills/autonomous-ai-agents/hermes-profile-authoring/SKILL.md:1` ；`~ skills/autonomous-ai-agents/hermes-projects/SKILL.md:1`
- 可机械执行：否（要模型判断）

## 8. [rewrite] skills/autonomous-ai-agents/hermes-profile-housekeeping/SKILL.md:1 · skills/autonomous-ai-agents/hermes-profile-configuration/SKILL.md:1
- 判断：改写触发词把两者分开（当前 sim_desc=0.59）：skills/autonomous-ai-agents/hermes-profile-housekeeping/ / skills/autonomous-ai-agents/hermes-profile-configuration/
- 证据：`{"sim_desc": 0.591, "layer": "skills/autonomous-ai-agents/", "same_names": false, "refcount": {"skills/autonomous-ai-agents/hermes-profile-housekeeping/": 0, "skills/autonomous-ai-agents/hermes-profile-configuration/": 3}, "version": {"skills/autonomous-ai-agents/hermes-profile-housekeeping/": "1.0.0", "skills/autonomous-ai-agents/hermes-profile-configuration/": "1.0.0"}, "b_skill_sha256": "1ef957d33b4dff6746225aa760d0fad7be04a8148c3d59cfddd9fbc174e150a2", "mechanical_rule": null}`
- diff 形状：`~ skills/autonomous-ai-agents/hermes-profile-housekeeping/SKILL.md:1` ；`~ skills/autonomous-ai-agents/hermes-profile-configuration/SKILL.md:1`
- 可机械执行：否（要模型判断）

## 9. [rewrite] skills/autonomous-ai-agents/hermes-projects/SKILL.md:1 · skills/autonomous-ai-agents/hermes-profile-configuration/SKILL.md:1
- 判断：改写触发词把两者分开（当前 sim_desc=0.52）：skills/autonomous-ai-agents/hermes-projects/ / skills/autonomous-ai-agents/hermes-profile-configuration/
- 证据：`{"sim_desc": 0.523, "layer": "skills/autonomous-ai-agents/", "same_names": false, "refcount": {"skills/autonomous-ai-agents/hermes-projects/": 0, "skills/autonomous-ai-agents/hermes-profile-configuration/": 0}, "version": {"skills/autonomous-ai-agents/hermes-projects/": "1.0.0", "skills/autonomous-ai-agents/hermes-profile-configuration/": "1.0.0"}, "b_skill_sha256": "1ef957d33b4dff6746225aa760d0fad7be04a8148c3d59cfddd9fbc174e150a2", "mechanical_rule": null}`
- diff 形状：`~ skills/autonomous-ai-agents/hermes-projects/SKILL.md:1` ；`~ skills/autonomous-ai-agents/hermes-profile-configuration/SKILL.md:1`
- 可机械执行：否（要模型判断）

## 10. [rewrite] skills/productivity/md-docx-writeback/SKILL.md:1 · skills/productivity/figure-generation-and-verification/SKILL.md:1
- 判断：改写触发词把两者分开（当前 sim_desc=0.52）：skills/productivity/md-docx-writeback/ / skills/productivity/figure-generation-and-verification/
- 证据：`{"sim_desc": 0.523, "layer": "skills/productivity/", "same_names": false, "refcount": {"skills/productivity/md-docx-writeback/": 0, "skills/productivity/figure-generation-and-verification/": 0}, "version": {"skills/productivity/md-docx-writeback/": "1.0.0", "skills/productivity/figure-generation-and-verification/": "1.0.0"}, "b_skill_sha256": "1aabeddb50b0531046ac331b85fd0695b17e9b2597a43ad280d80f003b4d3fba", "mechanical_rule": null}`
- diff 形状：`~ skills/productivity/md-docx-writeback/SKILL.md:1` ；`~ skills/productivity/figure-generation-and-verification/SKILL.md:1`
- 可机械执行：否（要模型判断）

## 11. [rewrite] skills/research/a-share-kline-workflow/SKILL.md:1 · skills/research/tushare-kline-pipeline/SKILL.md:1
- 判断：改写触发词把两者分开（当前 sim_desc=0.63）：skills/research/a-share-kline-workflow/ / skills/research/tushare-kline-pipeline/
- 证据：`{"sim_desc": 0.632, "layer": "skills/research/", "same_names": false, "refcount": {"skills/research/a-share-kline-workflow/": 0, "skills/research/tushare-kline-pipeline/": 0}, "version": {"skills/research/a-share-kline-workflow/": null, "skills/research/tushare-kline-pipeline/": null}, "b_skill_sha256": "bf90ab7ab66b6de8e0f10711b32ad4ef7a62e53b54e215712a04ae208fa31b5b", "mechanical_rule": null}`
- diff 形状：`~ skills/research/a-share-kline-workflow/SKILL.md:1` ；`~ skills/research/tushare-kline-pipeline/SKILL.md:1`
- 可机械执行：否（要模型判断）

## 12. [merge] skills/research/tushare/SKILL.md:1 · skills/research/tushare-data/SKILL.md:1
- 判断：保留 skills/research/tushare/（身份），正文取 skills/research/tushare-data/（version 1.1.16）；删 skills/research/tushare-data/（机械可执行）
- 证据：`{"sim_desc": 1.0, "layer": "skills/research/", "same_names": true, "refcount": {"skills/research/tushare/": 1, "skills/research/tushare-data/": 1}, "version": {"skills/research/tushare/": "1.1.12", "skills/research/tushare-data/": "1.1.16"}, "b_skill_sha256": "0a59d6eac7a117afd1a6d95eb5c85c127a03dc1f69c240d6b761436ce00c2acd", "mechanical_rule": "身份取被引用更多的一方（并列取更短名字）、正文取 version 更高的一方"}`
- diff 形状：`- skills/research/tushare-data// (删)` ；`~ skills/research/tushare//SKILL.md (正文取较高 version)`
- 可机械执行：是

## 13. [group] skills/（入口层）
- 判断：入口层摆出 68 项 > 上限 20：把散技能按用途归入类目（类目名要人拍板）
- 证据：`{"L1_items": 68, "cap": 20, "loose": 51, "token_buckets": {"hermes-*": ["hermes-browser-lane-repair", "hermes-desktop-plugins", "hermes-session-routing-forensics", "hermes-themes", "install-hermes-skills", "manage-hermes-cron-jobs", "remove-hermes-skills", "update-hermes-skills"], "maintain-*": ["maintain-hermes-desktop-app", "maintain-hermes-gateway", "maintain-hermes-memory", "maintain-hermes-models", "maintain-hermes-node", "maintain-hermes-profile", "maintain-hermes-profile-skill-parity", "maintain-hermes-profiles", "maintain-hermes-skill-cards", "maintain-hermes-skills"]}}`
- diff 形状：`~ git mv skills/accountancy-workflow skills/<类目>/accountancy-workflow` ；`~ git mv skills/alipay-statement skills/<类目>/alipay-statement` ；`~ git mv skills/boc-statement skills/<类目>/boc-statement` ；`~ git mv skills/ccb-statement skills/<类目>/ccb-statement` ；`~ git mv skills/ci-flake-triage skills/<类目>/ci-flake-triage` ；`~ git mv skills/clean-pytest skills/<类目>/clean-pytest` ；`…`
- 可机械执行：否（要模型判断）

## 14. [split] skills/accountancy-workflow/SKILL.md:572
- 判断：21427 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 21427, "lines": 747, "sections_by_size": [{"title": "记账口径补充（2026-08 实战确认，改规则前先读）", "lines": "572-646", "chars": 4126}, {"title": "资产表：`balances`（每期期末＝下期期初的实际资产量）", "lines": "64-121", "chars": 2889}, {"title": "交付的 xlsx 必须能被 Excel 双击打开（血泪教训）", "lines": "696-743", "chars": 2281}, {"title": "Step 0 入库：多期导出文件先按月拆分", "lines": "214-251", "chars": 1872}]}`
- diff 形状：`~ skills/accountancy-workflow/SKILL.md:572-646 (记账口径补充（2026-08 实战确认，改规则前先读）) → + skills/accountancy-workflow/references/<slug>.md` ；`~ skills/accountancy-workflow/SKILL.md:64-121 (资产表：`balances`（每期期末＝下期期初的实际资产量）) → + skills/accountancy-workflow/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 15. [split] skills/autonomous-ai-agents/hermes-profile-housekeeping/SKILL.md:227
- 判断：9925 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 9925, "lines": 542, "sections_by_size": [{"title": "9. \"I can't turn this skill off\" / \"why does it list N skills?\"", "lines": "227-345", "chars": 10239}, {"title": "13. Adopting an external skill/plugin pack", "lines": "412-458", "chars": 3566}, {"title": "4. Back up, then delete, then verify", "lines": "82-132", "chars": 3121}, {"title": "15. Editing a profile's own context files (SOUL.md, README.md)", "lines": "492-531", "chars": 3116}]}`
- diff 形状：`~ skills/autonomous-ai-agents/hermes-profile-housekeeping/SKILL.md:227-345 (9. "I can't turn this skill off" / "why does it list N skills?") → + skills/autonomous-ai-agents/hermes-profile-housekeeping/references/<slug>.md` ；`~ skills/autonomous-ai-agents/hermes-profile-housekeeping/SKILL.md:412-458 (13. Adopting an external skill/plugin pack) → + skills/autonomous-ai-agents/hermes-profile-housekeeping/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 16. [split] skills/creative/comfyui/SKILL.md:550
- 判断：5871 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 5871, "lines": 585, "sections_by_size": [{"title": "Pitfalls", "lines": "550-599", "chars": 2417}, {"title": "What's in this skill", "lines": "36-69", "chars": 1864}, {"title": "Decision Tree", "lines": "204-230", "chars": 1620}, {"title": "Step 3: Run with parameters", "lines": "149-188", "chars": 1282}]}`
- diff 形状：`~ skills/creative/comfyui/SKILL.md:550-599 (Pitfalls) → + skills/creative/comfyui/references/<slug>.md` ；`~ skills/creative/comfyui/SKILL.md:36-69 (What's in this skill) → + skills/creative/comfyui/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 17. [split] skills/install-hermes-skills/SKILL.md:38
- 判断：6542 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 6542, "lines": 341, "sections_by_size": [{"title": "Non-negotiables (user rules)", "lines": "38-125", "chars": 8109}, {"title": "Route by what you were handed", "lines": "146-192", "chars": 4893}, {"title": "The commands", "lines": "219-265", "chars": 2664}, {"title": "Replacing an installed skill with a better bloodline", "lines": "193-218", "chars": 1831}]}`
- diff 形状：`~ skills/install-hermes-skills/SKILL.md:38-125 (Non-negotiables (user rules)) → + skills/install-hermes-skills/references/<slug>.md` ；`~ skills/install-hermes-skills/SKILL.md:146-192 (Route by what you were handed) → + skills/install-hermes-skills/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 18. [split] skills/ledger-record-reconciliation/SKILL.md:86
- 判断：5125 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 5125, "lines": 124, "sections_by_size": [{"title": "记录（log）对账：三线核对 —— 结构 → 台账 → 协议模板", "lines": "86-101", "chars": 1978}, {"title": "Workflow", "lines": "35-62", "chars": 1562}, {"title": "🚫 不要做什么", "lines": "117-128", "chars": 1030}, {"title": "台账内部对账：盒图 ↔ stock 表（源侧的同一门手艺）", "lines": "102-116", "chars": 903}]}`
- diff 形状：`~ skills/ledger-record-reconciliation/SKILL.md:86-101 (记录（log）对账：三线核对 —— 结构 → 台账 → 协议模板) → + skills/ledger-record-reconciliation/references/<slug>.md` ；`~ skills/ledger-record-reconciliation/SKILL.md:35-62 (Workflow) → + skills/ledger-record-reconciliation/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 19. [split] skills/maintain-hermes-gateway/SKILL.md:184
- 判断：8317 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 8317, "lines": 504, "sections_by_size": [{"title": "A bot that admits messages but never answers: the model-API path", "lines": "184-233", "chars": 4165}, {"title": "Answer shape (this user — non-negotiable)", "lines": "447-479", "chars": 2590}, {"title": "A bot offline while the gateway process is up: read the per-platform state, not the pid", "lines": "152-183", "chars": 2543}, {"title": "4c. Turning a platform OFF everywhere (the inverse task)", "lines": "325-369", "chars": 2522}]}`
- diff 形状：`~ skills/maintain-hermes-gateway/SKILL.md:184-233 (A bot that admits messages but never answers: the model-API path) → + skills/maintain-hermes-gateway/references/<slug>.md` ；`~ skills/maintain-hermes-gateway/SKILL.md:447-479 (Answer shape (this user — non-negotiable)) → + skills/maintain-hermes-gateway/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 20. [split] skills/maintain-hermes-profile/SKILL.md:252
- 判断：17134 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 17134, "lines": 874, "sections_by_size": [{"title": "9. \"I can't turn this skill off\" / \"why does it list N skills?\"", "lines": "252-426", "chars": 14732}, {"title": "16. Removing or restoring skills (three kinds, three mechanisms)", "lines": "631-732", "chars": 8835}, {"title": "7. Report shape", "lines": "151-209", "chars": 4508}, {"title": "10. Hub skills never update themselves, and one name can live in two homes", "lines": "427-469", "chars": 3965}]}`
- diff 形状：`~ skills/maintain-hermes-profile/SKILL.md:252-426 (9. "I can't turn this skill off" / "why does it list N skills?") → + skills/maintain-hermes-profile/references/<slug>.md` ；`~ skills/maintain-hermes-profile/SKILL.md:631-732 (16. Removing or restoring skills (three kinds, three mechanisms)) → + skills/maintain-hermes-profile/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 21. [split] skills/note-taking/repo-structure-spec/SKILL.md:151
- 判断：7475 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 7475, "lines": 355, "sections_by_size": [{"title": "4. Normalising one project against the spec (the audit direction)", "lines": "151-240", "chars": 8154}, {"title": "5. Retiring a heavy artifact that is already committed (the §2 \"separate offer\")", "lines": "274-343", "chars": 6318}, {"title": "2. The house format (fixed shape)", "lines": "76-128", "chars": 4014}, {"title": "The spec-change direction (the user redefines the spec)", "lines": "241-273", "chars": 2683}]}`
- diff 形状：`~ skills/note-taking/repo-structure-spec/SKILL.md:151-240 (4. Normalising one project against the spec (the audit direction)) → + skills/note-taking/repo-structure-spec/references/<slug>.md` ；`~ skills/note-taking/repo-structure-spec/SKILL.md:274-343 (5. Retiring a heavy artifact that is already committed (the §2 "separate offer")) → + skills/note-taking/repo-structure-spec/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 22. [split] skills/pytest-patterns/SKILL.md:1262
- 判断：11872 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 11872, "lines": 1799, "sections_by_size": [{"title": "Example 7: Testing Classes and Methods", "lines": "1262-1331", "chars": 2163}, {"title": "Example 13: Integration Test Example", "lines": "1543-1618", "chars": 2050}, {"title": "Example 5: Mocking External Services", "lines": "1132-1200", "chars": 2014}, {"title": "Example 12: Testing with Fixtures and Mocks", "lines": "1481-1542", "chars": 1853}]}`
- diff 形状：`~ skills/pytest-patterns/SKILL.md:1262-1331 (Example 7: Testing Classes and Methods) → + skills/pytest-patterns/references/<slug>.md` ；`~ skills/pytest-patterns/SKILL.md:1543-1618 (Example 13: Integration Test Example) → + skills/pytest-patterns/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 23. [split] skills/recruit-learning-in-session/SKILL.md:88
- 判断：5843 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 5843, "lines": 279, "sections_by_size": [{"title": "Phase 2 — Route every finding to its owner", "lines": "88-135", "chars": 3750}, {"title": "Phase 1 — Mine the session (read-only subagent)", "lines": "36-87", "chars": 3675}, {"title": "Failure modes", "lines": "195-208", "chars": 2892}, {"title": "Variant — folding MEMORY.md wholesale into skills", "lines": "162-194", "chars": 2702}]}`
- diff 形状：`~ skills/recruit-learning-in-session/SKILL.md:88-135 (Phase 2 — Route every finding to its owner) → + skills/recruit-learning-in-session/references/<slug>.md` ；`~ skills/recruit-learning-in-session/SKILL.md:36-87 (Phase 1 — Mine the session (read-only subagent)) → + skills/recruit-learning-in-session/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 24. [split] skills/research/research-paper-writing/SKILL.md:789
- 判断：17832 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 17832, "lines": 1611, "sections_by_size": [{"title": "Step 6.1: Simulate Reviews (Ensemble Pattern)", "lines": "789-853", "chars": 2802}, {"title": "Step 2.5: Design Human Evaluation (If Applicable)", "lines": "429-469", "chars": 2163}, {"title": "Step 7.9: arXiv & Preprint Strategy", "lines": "1122-1164", "chars": 2065}, {"title": "Step 7.10: Research Code Packaging", "lines": "1165-1226", "chars": 1895}]}`
- diff 形状：`~ skills/research/research-paper-writing/SKILL.md:789-853 (Step 6.1: Simulate Reviews (Ensemble Pattern)) → + skills/research/research-paper-writing/references/<slug>.md` ；`~ skills/research/research-paper-writing/SKILL.md:429-469 (Step 2.5: Design Human Evaluation (If Applicable)) → + skills/research/research-paper-writing/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 25. [split] skills/research/tushare/SKILL.md:712
- 判断：5469 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 5469, "lines": 804, "sections_by_size": [{"title": "Recommended minimal interface set", "lines": "712-751", "chars": 547}, {"title": "Environment check", "lines": "162-181", "chars": 281}, {"title": "Cache and reuse rules", "lines": "662-679", "chars": 266}, {"title": "What this skill is for", "lines": "28-44", "chars": 260}]}`
- diff 形状：`~ skills/research/tushare/SKILL.md:712-751 (Recommended minimal interface set) → + skills/research/tushare/references/<slug>.md` ；`~ skills/research/tushare/SKILL.md:162-181 (Environment check) → + skills/research/tushare/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 26. [split] skills/research/tushare-data/SKILL.md:713
- 判断：5476 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 5476, "lines": 804, "sections_by_size": [{"title": "Recommended minimal interface set", "lines": "713-752", "chars": 547}, {"title": "Environment check", "lines": "163-182", "chars": 281}, {"title": "Cache and reuse rules", "lines": "663-680", "chars": 266}, {"title": "What this skill is for", "lines": "29-45", "chars": 260}]}`
- diff 形状：`~ skills/research/tushare-data/SKILL.md:713-752 (Recommended minimal interface set) → + skills/research/tushare-data/references/<slug>.md` ；`~ skills/research/tushare-data/SKILL.md:163-182 (Environment check) → + skills/research/tushare-data/references/<slug>.md`
- 可机械执行：否（要模型判断）

## 27. [split] skills/terminal/terminal-tool-usage-answers/SKILL.md:34
- 判断：6069 token > 5000：把最大的几个小节下沉到 references/，原位留一行转指
- 证据：`{"est_tokens": 6069, "lines": 136, "sections_by_size": [{"title": "Answer shape (do this first)", "lines": "34-46", "chars": 3833}, {"title": "Validate the exact string before you teach it", "lines": "53-71", "chars": 3302}, {"title": "macOS System Settings: 面板身份 → 深链 → 让用户点", "lines": "135-148", "chars": 2438}, {"title": "Installed GUI app: where is that setting?", "lines": "124-134", "chars": 2429}]}`
- diff 形状：`~ skills/terminal/terminal-tool-usage-answers/SKILL.md:34-46 (Answer shape (do this first)) → + skills/terminal/terminal-tool-usage-answers/references/<slug>.md` ；`~ skills/terminal/terminal-tool-usage-answers/SKILL.md:53-71 (Validate the exact string before you teach it) → + skills/terminal/terminal-tool-usage-answers/references/<slug>.md`
- 可机械执行：否（要模型判断）
