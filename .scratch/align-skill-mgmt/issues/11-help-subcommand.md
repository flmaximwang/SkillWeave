# 11: 补 `help <command>` 子命令（ticket 08 的遗留）

**What to build:** 用户 `weave.py help <command>` 时看到该子命令的详细说明（用法 / 参数 / 产物 / 示例），
不必翻 `references/commands.md`。ticket 08 只做了「参数错误时的用法提示」与「无参数时的简要帮助」，
本 ticket 补齐逐命令的详细帮助。

**Blocked by:** None（ticket 08 已合并）

**Status:** ready-for-agent

- [ ] `cli.py` 的 `choices` 加入 `"help"`，并实现分支：
  - `weave.py help`（无参）→ 列出全部 15 个子命令 + 一句话说明（可复用现有的简要帮助）
  - `weave.py help <command>` → 该命令的详细说明
- [ ] 帮助文本的**唯一来源**：不要手抄一份与 `references/commands.md` 漂移的副本。
  两种做法择一（选哪个都行，但要在提交信息里说明理由）：
  - (a) 从 `references/commands.md` 里按 `## <command>` 小节切出来打印；
  - (b) 在 `cli.py` 里维护一份结构化表（usage/desc/produces），并**加 fixture 断言它所列的
        子命令集合与 argparse 的 `choices` 完全一致**（防止加了命令忘更新帮助）。
- [ ] 未知命令：`weave.py help nosuch` → 明确提示未知 + 列出可用的，退 2。
- [ ] fixture（`selftest.py`）：断言 `help` 无参列出全部子命令；`help disclosure` 含用法与产物；
  `help nosuch` 退 2。把「帮助所列命令集合 == argparse choices」写成断言。
- [ ] 验收（真跑，读数进提交信息）：
  - `python3 scripts/weave.py help` → 列出全部子命令，退 0
  - `python3 scripts/weave.py help disclosure` → 含用法/产物，退 0
  - `python3 scripts/weave.py help nosuch` → 退 2
  - `python3 scripts/weave.py --self-test` → 全过
  - `python3 scripts/weave.py self-check` → PASS
  - `python3 scripts/weave.py disclosure .` → 超限 0 · 到不了根 0 · 悬空 0（不引入新问题）
- [ ] 收尾：在仓库根重跑 `disclosure`（默认落包内 `.skillweave/`）并一起提交，别让包内数字过期。
- [ ] 同步 `references/commands.md` 与 `README.md`：说明 `help` 子命令的用法（若你选了 (a) 方案，
      确保切分锚点稳定）。
