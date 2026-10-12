# 披露链 · base

## 术语表

- **文档 / 节点**：一份文件（`SKILL.md`、`references/*.md`、`scripts/*.py` 各算一份）。
- **根**：起点文档 = 一个 skill 的 `SKILL.md`。**根有几个 = 形状**（1 个 = 单入口，K 个 = 多入口）。
- **披露**：一份文档正文里真的写出了另一份文档的路径。**不算**披露：URL、代码围栏里的示例路径、没有目录的裸文件名。
- **L1/L2/…**：离根几步。根 = L1，根披露的 = L2，依次往下。
- **fanout**：这份文档披露了几份别的文档（某一层「摆出几项」= 该层各文档 fanout 之和）。
- **到不了根**：从任何根顺着披露都走不到它（没有任何文档点到它）。
- **超限**：超过它那类的上限（正文 ≥5000 tok 或 >500 行 · description >1024 字符 · 资源文件 >20000 B）。**脚本不计**：Agent 不整份读脚本，字节数不是披露缺陷（口径见 `docs/contract.md` §4）。
- **悬空**：写了像本 pack 内的路径，但那个文件不存在。
- **external**：正文里提到的本 pack 之外的文件（不算披露、也不算错）。
- **近重复**：同层两份文档太像，Agent 会选错。

口径：**层 = 披露深度**（L1 = 根文档 `SKILL.md`；L2 = L1 正文直接点到的文档；Ln+1 由 Ln 披露）。不是「按文件类型分三级」那套。

- 根：**8 个**（每个 skill 的 `SKILL.md` 是一个根；1 个 = 单入口形状）
- 文档节点：**141 份** · 层数：**4**
- 超限：**3** 份 · 到不了根：**23** 份 · 悬空引用：**2** 条 · 外部引用（不算披露）：**69** 条
- 根选择层近重复（Jaccard≥0.5·靠 description 选根才算）：**0** 对
- **待办 21 条 · 已豁免 7 条** → 见同目录 [`TODO.md`](TODO.md)（豁免规则 1 条，来自包里 `.skillweave/waivers.txt`）

## L1（8 份）

| 文档 | fanout（披露几项） | 体积 | 判定 |
|---|---|---|---|
| `skills/analyze-lab-images/SKILL.md` | 4 | 315 tok / 10 行 | 根 |
| `skills/keep-lab-project-in-order/SKILL.md` | 2 | 287 tok / 8 行 | 根 |
| `skills/manage-lab-ledger/SKILL.md` | 5 | 594 tok / 14 行 | 根 |
| `skills/manage-lab-logs/SKILL.md` | 7 | 703 tok / 16 行 | 根 |
| `skills/model-protein-structures/SKILL.md` | 6 | 482 tok / 12 行 | 根 |
| `skills/operate-lab-instruments/SKILL.md` | 3 | 328 tok / 9 行 | 根 |
| `skills/plan-protein-expression/SKILL.md` | 1 | 238 tok / 7 行 | 根 |
| `skills/run-sample-intake-flows/SKILL.md` | 2 | 406 tok / 11 行 | 根 |

## L2（30 份）

| 文档 | fanout（披露几项） | 体积 | 判定 |
|---|---|---|---|
| `skills/analyze-lab-images/references/align-and-average-repeated-images/SKILL.md` | 2 | 2321 tok / 78 行 | ✅ |
| `skills/analyze-lab-images/references/fiber-image-analysis/SKILL.md` | 3 | 2917 tok / 80 行 | ✅ |
| `skills/analyze-lab-images/references/filament-lumen-analysis/SKILL.md` | 0 | 3921 tok / 239 行 | ✅ |
| `skills/analyze-lab-images/references/sds-page-gel-cropper/SKILL.md` | 0 | 1552 tok / 169 行 | ✅ |
| `skills/keep-lab-project-in-order/references/graph-local-notes/SKILL.md` | 3 | 3577 tok / 132 行 | ✅ |
| `skills/keep-lab-project-in-order/references/lab-project-containers/SKILL.md` | 1 | 3068 tok / 142 行 | ✅ |
| `skills/manage-lab-ledger/references/find-plasmid-entity/SKILL.md` | 0 | 4016 tok / 144 行 | ✅ |
| `skills/manage-lab-ledger/references/find-stock/SKILL.md` | 5 | 4798 tok / 204 行 | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/SKILL.md` | 18 | 8892 tok / 234 行 | ⚠️ 超限 正文 8892 tok > 5000 |
| `skills/manage-lab-ledger/references/map-artifacts-to-ledger-entities/SKILL.md` | 4 | 3850 tok / 87 行 | ✅ |
| `skills/manage-lab-ledger/references/trace-sample-provenance/SKILL.md` | 3 | 3703 tok / 108 行 | ✅ |
| `skills/manage-lab-logs/references/audit-a-lab-note/SKILL.md` | 0 | 3154 tok / 126 行 | ✅ |
| `skills/manage-lab-logs/references/audit-log-protein-characterization/SKILL.md` | 3 | 3150 tok / 120 行 | ✅ |
| `skills/manage-lab-logs/references/audit-log-protein-purification/SKILL.md` | 3 | 2618 tok / 108 行 | ✅ |
| `skills/manage-lab-logs/references/audit-logs/SKILL.md` | 4 | 4586 tok / 199 行 | ✅ |
| `skills/manage-lab-logs/references/lab-vault-experiment-records/SKILL.md` | 1 | 2176 tok / 131 行 | ❌ 有悬空引用 |
| `skills/manage-lab-logs/references/manage-logs/SKILL.md` | 1 | 7478 tok / 124 行 | ⚠️ 超限 正文 7478 tok > 5000 |
| `skills/manage-lab-logs/references/record-a-live-experiment/SKILL.md` | 0 | 1948 tok / 57 行 | ✅ |
| `skills/model-protein-structures/references/pdb-structure-screening/SKILL.md` | 5 | 4887 tok / 257 行 | ✅ |
| `skills/model-protein-structures/references/protein-bvh/SKILL.md` | 1 | 3014 tok / 247 行 | ✅ |
| `skills/model-protein-structures/references/protein-design-tool-analysis/SKILL.md` | 1 | 1486 tok / 62 行 | ❌ 有悬空引用 |
| `skills/model-protein-structures/references/protein-ligand-docking/SKILL.md` | 1 | 916 tok / 72 行 | ✅ |
| `skills/model-protein-structures/references/pymol-structural-visualization/SKILL.md` | 3 | 13919 tok / 1012 行 | ⚠️ 超限 正文 13919 tok > 5000; 正文 1012 行 > 500 |
| `skills/model-protein-structures/references/rosetta-protocol-engineering/SKILL.md` | 1 | 3776 tok / 229 行 | ✅ |
| `skills/operate-lab-instruments/references/cryo-em-machine-time-application/SKILL.md` | 2 | 1679 tok / 53 行 | ✅ |
| `skills/operate-lab-instruments/references/spectramax-operation/SKILL.md` | 0 | 1410 tok / 121 行 | ✅ |
| `skills/operate-lab-instruments/references/spectrophotometry-protocols/SKILL.md` | 4 | 2186 tok / 138 行 | ✅ |
| `skills/plan-protein-expression/references/recombinant-protein-expression/SKILL.md` | 6 | 2210 tok / 120 行 | ✅ |
| `skills/run-sample-intake-flows/references/onboard-a-sample-batch-into-lab-records/SKILL.md` | 0 | 2108 tok / 75 行 | ✅ |
| `skills/run-sample-intake-flows/references/register-a-protein-sample/SKILL.md` | 0 | 1284 tok / 60 行 | ✅ |

## L3（75 份）

| 文档 | fanout（披露几项） | 体积 | 判定 |
|---|---|---|---|
| `skills/analyze-lab-images/references/align-and-average-repeated-images/references/existing-tools.md` | 0 | 2838 B | ✅ |
| `skills/analyze-lab-images/references/align-and-average-repeated-images/scripts/align_and_average.py` | 0 | 9701 B | ✅ |
| `skills/analyze-lab-images/references/fiber-image-analysis/references/frangi-source-notes.md` | 0 | 3249 B | ✅ |
| `skills/analyze-lab-images/references/fiber-image-analysis/references/tem-001-case.md` | 0 | 2070 B | ✅ |
| `skills/analyze-lab-images/references/fiber-image-analysis/scripts/scalebar.py` | 0 | 5446 B | ✅ |
| `skills/keep-lab-project-in-order/references/graph-local-notes/references/filters-and-html.md` | 0 | 6810 B | ✅ |
| `skills/keep-lab-project-in-order/references/graph-local-notes/references/obsidian-link-resolution.md` | 0 | 6435 B | ✅ |
| `skills/keep-lab-project-in-order/references/graph-local-notes/scripts/note_graph.py` | 0 | 58801 B | ✅ |
| `skills/keep-lab-project-in-order/references/lab-project-containers/references/lab-vault-protocols-and-logs.md` | 0 | 6186 B | ✅ |
| `skills/manage-lab-ledger/references/find-stock/references/alias-model.md` | 0 | 5212 B | ✅ |
| `skills/manage-lab-ledger/references/find-stock/references/entity-level-lookup.md` | 1 | 10007 B | ✅ |
| `skills/manage-lab-ledger/references/find-stock/references/provenance-chain.md` | 0 | 7007 B | ✅ |
| `skills/manage-lab-ledger/references/find-stock/scripts/find_stock.py` | 0 | 22232 B | ✅ |
| `skills/manage-lab-ledger/references/find-stock/scripts/trace_chain.py` | 0 | 23050 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/audit-layers.md` | 0 | 9419 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/deriving-more-libraries.md` | 0 | 3121 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/excel-formulas-to-columns.md` | 1 | 7322 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/incremental-landing.md` | 1 | 8122 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/ledger-history-and-design-probes.md` | 2 | 13778 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/ledger-service-push-and-backup.md` | 1 | 7180 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/migration-completeness.md` | 1 | 6114 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/pellet-model-and-usage-accounting.md` | 0 | 5891 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/phasing-and-retirement.md` | 0 | 3423 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/pitfalls.md` | 0 | 9937 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/rebuild-regression.md` | 0 | 3409 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/schema-and-constraints.md` | 0 | 12292 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/schema-change-reference-faces.md` | 0 | 5422 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/source-probing.md` | 2 | 4387 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/write-a-cli-for-the-ledger.md` | 0 | 5847 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/references/write-time-uid-trigger.md` | 0 | 8443 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/scripts/audit_source_columns.py` | 0 | 6201 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/scripts/list_xlsx_formulas.py` | 0 | 3605 B | ✅ |
| `skills/manage-lab-ledger/references/map-artifacts-to-ledger-entities/references/entity-identity-and-aliases.md` | 1 | 6254 B | ✅ |
| `skills/manage-lab-ledger/references/map-artifacts-to-ledger-entities/references/snapgene-format.md` | 1 | 4464 B | ✅ |
| `skills/manage-lab-ledger/references/map-artifacts-to-ledger-entities/scripts/snapgene_dna_probe.py` | 0 | 2725 B | ✅ |
| `skills/manage-lab-ledger/references/map-artifacts-to-ledger-entities/scripts/snapgene_sequence_fingerprint.py` | 0 | 6830 B | ✅ |
| `skills/manage-lab-ledger/references/trace-sample-provenance/references/archive-and-vault-layers.md` | 0 | 6060 B | ✅ |
| `skills/manage-lab-ledger/references/trace-sample-provenance/references/feishu-base-snapshots.md` | 1 | 4527 B | ✅ |
| `skills/manage-lab-ledger/references/trace-sample-provenance/scripts/feishu_base_dump.py` | 0 | 4398 B | ✅ |
| `skills/manage-lab-logs/references/audit-log-protein-characterization/references/criteria-and-chain.md` | 0 | 9596 B | ✅ |
| `skills/manage-lab-logs/references/audit-log-protein-characterization/references/find-stock-coupling.md` | 0 | 4989 B | ✅ |
| `skills/manage-lab-logs/references/audit-log-protein-characterization/scripts/audit_characterization_log.py` | 0 | 47010 B | ✅ |
| `skills/manage-lab-logs/references/audit-log-protein-purification/references/audit-criteria.md` | 1 | 9243 B | ✅ |
| `skills/manage-lab-logs/references/audit-log-protein-purification/references/dolt-stock-lookup.md` | 0 | 5358 B | ✅ |
| `skills/manage-lab-logs/references/audit-log-protein-purification/scripts/audit_purification_log.py` | 0 | 29690 B | ✅ |
| `skills/manage-lab-logs/references/audit-logs/references/config-schema.md` | 1 | 6900 B | ✅ |
| `skills/manage-lab-logs/references/audit-logs/scripts/audit_logs.py` | 0 | 18418 B | ✅ |
| `skills/manage-lab-logs/references/audit-logs/scripts/normalize_frontmatter_style.py` | 0 | 9346 B | ✅ |
| `skills/manage-lab-logs/references/audit-logs/templates/log-audit.example.json` | 0 | 11034 B | ✅ |
| `skills/manage-lab-logs/references/lab-vault-experiment-records/references/zsqlab11-vault.md` | 0 | 4587 B | ✅ |
| `skills/manage-lab-logs/references/manage-logs/references/protocol-diff-vs-paper.md` | 0 | 5900 B | ✅ |
| `skills/model-protein-structures/references/pdb-structure-screening/references/empirical-geometry-datasets.md` | 0 | 4823 B | ✅ |
| `skills/model-protein-structures/references/pdb-structure-screening/references/ligand-placement-and-burial-validation.md` | 0 | 6685 B | ✅ |
| `skills/model-protein-structures/references/pdb-structure-screening/references/parameter-diagram-rendering.md` | 0 | 4520 B | ✅ |
| `skills/model-protein-structures/references/pdb-structure-screening/references/rcsb-search-api-python.md` | 0 | 4719 B | ✅ |
| `skills/model-protein-structures/references/pdb-structure-screening/scripts/apo_screen.py` | 0 | 5632 B | ✅ |
| `skills/model-protein-structures/references/protein-bvh/references/vdw-radii.md` | 0 | 778 B | ✅ |
| `skills/model-protein-structures/references/protein-design-tool-analysis/references/rpxdock-architecture.md` | 0 | 8744 B | ✅ |
| `skills/model-protein-structures/references/protein-ligand-docking/references/diffdock-heme-workaround.md` | 0 | 4407 B | ✅ |
| `skills/model-protein-structures/references/pymol-structural-visualization/references/c5-docking-trajectory-andre-2007.md` | 0 | 17776 B | ✅ |
| `skills/model-protein-structures/references/pymol-structural-visualization/references/histidine-tautomers.md` | 0 | 5834 B | ✅ |
| `skills/model-protein-structures/references/pymol-structural-visualization/references/t-docking-trajectory-andre-2007.md` | 0 | 2737 B | ✅ |
| `skills/model-protein-structures/references/rosetta-protocol-engineering/references/rosetta-cpp-app-build.md` | 0 | 5935 B | ✅ |
| `skills/operate-lab-instruments/references/cryo-em-machine-time-application/references/form-field-maps.md` | 0 | 3434 B | ✅ |
| `skills/operate-lab-instruments/references/cryo-em-machine-time-application/references/nfpss-fee-standards.md` | 0 | 5977 B | ✅ |
| `skills/operate-lab-instruments/references/spectrophotometry-protocols/references/cuvette-material-and-selection.md` | 0 | 6745 B | ✅ |
| `skills/operate-lab-instruments/references/spectrophotometry-protocols/references/heme-quantification-pyridine-hemochrome.md` | 1 | 5453 B | ✅ |
| `skills/operate-lab-instruments/references/spectrophotometry-protocols/references/protein-heme-stoichiometry-methods.md` | 1 | 6722 B | ✅ |
| `skills/operate-lab-instruments/references/spectrophotometry-protocols/references/spectramax-cuvette-blank.md` | 0 | 2776 B | ✅ |
| `skills/plan-protein-expression/references/recombinant-protein-expression/references/c-type-cytochrome-production.md` | 0 | 5066 B | ✅ |
| `skills/plan-protein-expression/references/recombinant-protein-expression/references/heme-uv-vis-spectral-bands.md` | 0 | 2554 B | ✅ |
| `skills/plan-protein-expression/references/recombinant-protein-expression/references/sec-translocation-and-tag-rules.md` | 0 | 4776 B | ✅ |
| `skills/plan-protein-expression/references/recombinant-protein-expression/references/thermostable-solubility-tags.md` | 0 | 4535 B | ✅ |
| `skills/plan-protein-expression/references/recombinant-protein-expression/references/urea-resistant-domains.md` | 1 | 11219 B | ✅ |
| `skills/plan-protein-expression/references/recombinant-protein-expression/scripts/check_construct_against_pdb.py` | 0 | 6315 B | ✅ |

## L4（5 份）

| 文档 | fanout（披露几项） | 体积 | 判定 |
|---|---|---|---|
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/scripts/check_all_columns.py` | 0 | 7376 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/scripts/compare_db_objects.py` | 0 | 2806 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/scripts/dump_db_snapshot.py` | 0 | 8210 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/scripts/fk-semantics-demo.sh` | 0 | 3011 B | ✅ |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/scripts/probe-zero-residue.sh` | 0 | 1933 B | ✅ |

## 到不了的文档（没有任何根披露到它们）

| 文档 | fanout（披露几项） | 体积 | 判定 |
|---|---|---|---|
| `skills/analyze-lab-images/references/sds-page-gel-cropper/config.yaml` | 0 | 153 B | ⚠️ 孤儿 |
| `skills/analyze-lab-images/references/sds-page-gel-cropper/pyproject.toml` | 0 | 236 B | ⚠️ 孤儿 |
| `skills/analyze-lab-images/references/sds-page-gel-cropper/scripts/detect_lanes.py` | 0 | 3769 B | ⚠️ 孤儿 |
| `skills/analyze-lab-images/references/sds-page-gel-cropper/scripts/gel_crop.py` | 0 | 6538 B | ⚠️ 孤儿 |
| `skills/analyze-lab-images/references/sds-page-gel-cropper/scripts/parse_lane_spec.py` | 0 | 1816 B | ⚠️ 孤儿 |
| `skills/analyze-lab-images/references/sds-page-gel-cropper/scripts/refine_boundaries.py` | 0 | 5240 B | ⚠️ 孤儿 |
| `skills/keep-lab-project-in-order/references/graph-local-notes/test-prompts.json` | 0 | 2018 B | ⚠️ 孤儿 |
| `skills/keep-lab-project-in-order/references/lab-project-containers/scripts/verify-note-merge-coverage.py` | 0 | 4401 B | ⚠️ 孤儿 |
| `skills/manage-lab-ledger/references/find-stock/test-prompts.json` | 0 | 3617 B | ⚠️ 孤儿 |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/scripts/schema_fingerprint.py` | 0 | 2740 B | ⚠️ 孤儿 |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/templates/registry-ab/A_no_registry.sql` | 0 | 2318 B | ⚠️ 孤儿 |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/templates/registry-ab/B_registry_schema.sql` | 0 | 4800 B | ⚠️ 孤儿 |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/test-prompts.json` | 0 | 843 B | ⚠️ 孤儿 |
| `skills/manage-lab-logs/references/audit-log-protein-characterization/test-prompts.json` | 0 | 2190 B | ⚠️ 孤儿 |
| `skills/manage-lab-logs/references/audit-log-protein-purification/test-prompts.json` | 0 | 1765 B | ⚠️ 孤儿 |
| `skills/manage-lab-logs/references/audit-logs/test-prompts.json` | 0 | 1707 B | ⚠️ 孤儿 |
| `skills/manage-lab-logs/references/manage-logs/test-prompts.json` | 0 | 588 B | ⚠️ 孤儿 |
| `skills/model-protein-structures/references/protein-bvh/references/implementation-plan.md` | 0 | 4990 B | ⚠️ 孤儿 |
| `skills/model-protein-structures/references/protein-bvh/references/pymol-pseudoatom-visualization.md` | 0 | 4762 B | ⚠️ 孤儿 |
| `skills/model-protein-structures/references/protein-design-tool-analysis/references/rpxdock-search-paths.md` | 0 | 2068 B | ⚠️ 孤儿 |
| `skills/operate-lab-instruments/references/cryo-em-machine-time-application/references/method-justification.md` | 0 | 5069 B | ⚠️ 孤儿 |
| `skills/operate-lab-instruments/references/spectramax-operation/references/softmax-pro-cuvette-workflow.md` | 0 | 2921 B | ⚠️ 孤儿 |
| `skills/plan-protein-expression/references/recombinant-protein-expression/references/mr1-medium-fumarate-lactate.md` | 0 | 4027 B | ⚠️ 孤儿 |

## 根选择层（L0）

根不是被谁披露出来的，而是**靠 description 选出来的** —— 所以它单独一层，混进 Ln 会让两个形状的层数不可比。

| 根 | description 字符 | 常驻 tok | 同层近重复 |
|---|---|---|---|
| `skills/analyze-lab-images/SKILL.md` | 138 | 94 | — |
| `skills/keep-lab-project-in-order/SKILL.md` | 110 | 87 | — |
| `skills/manage-lab-ledger/SKILL.md` | 204 | 146 | — |
| `skills/manage-lab-logs/SKILL.md` | 244 | 172 | — |
| `skills/model-protein-structures/SKILL.md` | 144 | 94 | — |
| `skills/operate-lab-instruments/SKILL.md` | 111 | 78 | — |
| `skills/plan-protein-expression/SKILL.md` | 80 | 68 | — |
| `skills/run-sample-intake-flows/SKILL.md` | 171 | 115 | — |

### 悬空引用

- `skills/manage-lab-logs/references/lab-vault-experiment-records/SKILL.md:126` → `references/bases-formulas.md`（不存在）
- `skills/model-protein-structures/references/protein-design-tool-analysis/SKILL.md:49` → `references/rosetta-symdock-architecture.md`（不存在）

### 超限清单（带超多少）

- `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/SKILL.md` — 正文 8892 tok > 5000
- `skills/manage-lab-logs/references/manage-logs/SKILL.md` — 正文 7478 tok > 5000
- `skills/model-protein-structures/references/pymol-structural-visualization/SKILL.md` — 正文 13919 tok > 5000; 正文 1012 行 > 500

## 口径

- 披露 = 正文里真实点到的另一份文档（先按该文件所在目录、再按 pack 根解析）；URL、围栏里的路径、没有目录部分的裸文件名都不算。
- caps（出处 `docs/contract.md` §4）：正文 <5000 tok / ≤500 行 · description ≤1024 字符 · 单份文件（不含 `scripts/`）≤20000 B。
- 每个文档在表里恰好出现一次（由命令自己核对：节点数 == 表行数）。
