# 待办 · base

由 `weave.py disclosure` 生成。术语见 `DISCLOSURE.md` 头部术语表。

- **待办 21 条**（机械可判 0 · 待模型 21）
- **已豁免 7 条**（按包里 `.skillweave/waivers.txt`，共 1 条规则）

## 待办（照着做）

| # | 文档 | 问题 | 数字 | 建议动作 | 谁判 |
|---|---|---|---|---|---|
| 1 | `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/SKILL.md` | 超限 | 正文 8892 tok > 5000 | 拆成多份（拆分方案交模型判断，按主题切不按标题切） | 待模型 |
| 2 | `skills/manage-lab-logs/references/manage-logs/SKILL.md` | 超限 | 正文 7478 tok > 5000 | 拆成多份（拆分方案交模型判断，按主题切不按标题切） | 待模型 |
| 3 | `skills/model-protein-structures/references/pymol-structural-visualization/SKILL.md` | 超限 | 正文 13919 tok > 5000; 正文 1012 行 > 500 | 拆成多份（拆分方案交模型判断，按主题切不按标题切） | 待模型 |
| 4 | `skills/analyze-lab-images/references/sds-page-gel-cropper/config.yaml` | 到不了根 | 153 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 5 | `skills/analyze-lab-images/references/sds-page-gel-cropper/pyproject.toml` | 到不了根 | 236 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 6 | `skills/analyze-lab-images/references/sds-page-gel-cropper/scripts/detect_lanes.py` | 到不了根 | 3769 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 7 | `skills/analyze-lab-images/references/sds-page-gel-cropper/scripts/gel_crop.py` | 到不了根 | 6538 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 8 | `skills/analyze-lab-images/references/sds-page-gel-cropper/scripts/parse_lane_spec.py` | 到不了根 | 1816 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 9 | `skills/analyze-lab-images/references/sds-page-gel-cropper/scripts/refine_boundaries.py` | 到不了根 | 5240 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 10 | `skills/keep-lab-project-in-order/references/lab-project-containers/scripts/verify-note-merge-coverage.py` | 到不了根 | 4401 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 11 | `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/scripts/schema_fingerprint.py` | 到不了根 | 2740 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 12 | `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/templates/registry-ab/A_no_registry.sql` | 到不了根 | 2318 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 13 | `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/templates/registry-ab/B_registry_schema.sql` | 到不了根 | 4800 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 14 | `skills/model-protein-structures/references/protein-bvh/references/implementation-plan.md` | 到不了根 | 4990 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 15 | `skills/model-protein-structures/references/protein-bvh/references/pymol-pseudoatom-visualization.md` | 到不了根 | 4762 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 16 | `skills/model-protein-structures/references/protein-design-tool-analysis/references/rpxdock-search-paths.md` | 到不了根 | 2068 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 17 | `skills/operate-lab-instruments/references/cryo-em-machine-time-application/references/method-justification.md` | 到不了根 | 5069 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 18 | `skills/operate-lab-instruments/references/spectramax-operation/references/softmax-pro-cuvette-workflow.md` | 到不了根 | 2921 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 19 | `skills/plan-protein-expression/references/recombinant-protein-expression/references/mr1-medium-fumarate-lactate.md` | 到不了根 | 4027 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 20 | `skills/manage-lab-logs/references/lab-vault-experiment-records/SKILL.md` | 悬空 | 1 条（126: `references/bases-formulas.md`） | **先判**：包内路径写错（改路径）· 还是在说包外文件（免检）→ 再动手 | 待模型 |
| 21 | `skills/model-protein-structures/references/protein-design-tool-analysis/SKILL.md` | 悬空 | 1 条（49: `references/rosetta-symdock-architecture.md`） | **先判**：包内路径写错（改路径）· 还是在说包外文件（免检）→ 再动手 | 待模型 |

## 已豁免（匹配了 waivers.txt，不动它）

| 文档 | 问题 | 数字 | 理由 |
|---|---|---|---|
| `skills/keep-lab-project-in-order/references/graph-local-notes/test-prompts.json` | 到不了根 | 2018 B | 行为测试留档，本来就不该被披露 |
| `skills/manage-lab-ledger/references/find-stock/test-prompts.json` | 到不了根 | 3617 B | 行为测试留档，本来就不该被披露 |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/test-prompts.json` | 到不了根 | 843 B | 行为测试留档，本来就不该被披露 |
| `skills/manage-lab-logs/references/audit-log-protein-characterization/test-prompts.json` | 到不了根 | 2190 B | 行为测试留档，本来就不该被披露 |
| `skills/manage-lab-logs/references/audit-log-protein-purification/test-prompts.json` | 到不了根 | 1765 B | 行为测试留档，本来就不该被披露 |
| `skills/manage-lab-logs/references/audit-logs/test-prompts.json` | 到不了根 | 1707 B | 行为测试留档，本来就不该被披露 |
| `skills/manage-lab-logs/references/manage-logs/test-prompts.json` | 到不了根 | 588 B | 行为测试留档，本来就不该被披露 |

## 免检表长什么样（`<pack>/.skillweave/waivers.txt`）

```
# 一行一条：<glob>  两个以上空格  理由（# 开头是注释）
*/assets/*.png             给人看的图，Agent 不读
*/test-prompts.json        测试留档，本来就不该被披露
```

豁免是**包主的判断**，写在包里、工具只匹配；没写规则的按上面的建议动作办。
