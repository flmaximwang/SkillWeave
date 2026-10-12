# 待办 · LabProjectManagement

由 `weave.py disclosure` 生成。术语见 `DISCLOSURE.md` 头部术语表。

- **待办 0 条**（机械可判 0 · 待模型 0）
- **已豁免 11 条**（按包里 `.skillweave/waivers.txt`，共 4 条规则）

## 待办（照着做）

| # | 文档 | 问题 | 数字 | 建议动作 | 谁判 |
|---|---|---|---|---|---|
| — | — | — | — | 没有待办 | — |

## 已豁免（匹配了 waivers.txt，不动它）

| 文档 | 问题 | 数字 | 理由 |
|---|---|---|---|
| `skills/analyze-lab-images/references/sds-page-gel-cropper/config.yaml` | 到不了根 | 153 B | 住在 skill 根的支持文件（venv_path 设置）：解析器不把裸文件名当披露，有意保留 |
| `skills/analyze-lab-images/references/sds-page-gel-cropper/pyproject.toml` | 到不了根 | 236 B | 住在 skill 根的构建配置（Pillow/numpy）：同上，有意保留 |
| `skills/keep-lab-project-in-order/references/graph-local-notes/test-prompts.json` | 到不了根 | 2018 B | 行为测试留档，本来就不该被披露 |
| `skills/manage-lab-ledger/references/find-stock/test-prompts.json` | 到不了根 | 3617 B | 行为测试留档，本来就不该被披露 |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/templates/registry-ab/A_no_registry.sql` | 到不了根 | 2318 B | 对照库的可抄 SQL：PATH_RE 的扩展名表不含 .sql ⇒ 披露链拿不到它，有意保留 |
| `skills/manage-lab-ledger/references/manage-inventory-for-protein-engineering/templates/registry-ab/B_registry_schema.sql` | 到不了根 | 4800 B | 对照库的可抄 SQL：PATH_RE 的扩展名表不含 .sql ⇒ 披露链拿不到它，有意保留 |
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
