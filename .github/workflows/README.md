# CI 流程（GitHub Actions）

[`test.yml`](test.yml) 在每次 push（`main` / `develop`）与 PR（`main`）上运行，串起**两条门禁**。
两条都退 0 才算通过；任一条失败，这个 job 就是红的。

## 两条门禁各管什么

| 门禁 | 命令 | 管什么 |
|---|---|---|
| **自举合规** | `python3 scripts/weave.py self-check` | 对 **SkillWeave 自己**跑一遭 `disclosure`，要求待办清单为空（豁免除外）。守住「工具自己符合规范」：`SKILL.md` 不超限、没有到不了根的孤儿文档、披露链完整。 |
| **fixture 回归** | `python3 scripts/weave.py --self-test` | 跑**全部自带 fixture**：caps 表、披露链递归、豁免规则、安全/可移植闸、派发划批、验收回归拦截、交付 `deliver` 等。守住「已有行为不被改坏」。 |

两条在干净 checkout 上跑，不碰任何真实 pack；`self-check` 的产物落临时目录，不回写仓库。

## 失败怎么排查

1. **先看是哪一条红的**。`self-check` 失败会在日志里列出未解决问题（路径 + 类型 + 说明），
   并提示完整清单落在临时目录的 `TODO.md`。
2. **本地重跑同一条命令**（结果一致，便于迭代）：
   ```bash
   python3 scripts/weave.py self-check
   python3 scripts/weave.py --self-test
   ```
3. **下载 Artifacts**。job 失败时会上传 `disclosure-report`，包含：
   - `skillweave-self-*/` —— `self-check` 的 `disclosure.json` / `TODO.md` / `DISCLOSURE.md`
   - `weave-selftest-*/` —— `--self-test` 各 fixture 的产物（tree / layers / audit / disclosure 等）

   路径不存在时会跳过（`if-no-files-found: warn`），不额外制造失败。

## 本地与 CI 的差异

本地 `self-check` 的临时目录前缀同样是 `skillweave-self-`（`tempfile.mkdtemp`），
在 ubuntu-latest 上默认落在 `/tmp`；workflow 同时兜底 `${{ runner.temp }}` 与 `--self-test` 的
`weave-selftest-*`，避免 `TMPDIR` 变化导致报告抓不到。
