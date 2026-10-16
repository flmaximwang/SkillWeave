# 交付报告 · SkillWeave 对齐新 skill 管理规范

**日期**: 2026-10-16 · **分支**: main · **HEAD**: 5a7ac25
**输入规范**: `/Users/maxim/Documents/Habit/SkillManagement/skills/0-manage-skills-by-maxim/SKILL.md`
**流程**: grill-me → to-spec → to-tickets → opencode 并行执行（worktree 隔离）

---

## 一、最终验收：spec 清单逐项真跑

| # | 验收标准 | 实测读数 | 结果 |
|---|---|---|---|
| 1 | `skills/skillweave/SKILL.md` < 100 行 | **89 行**（原 184） | ✅ |
| 2 | `weave.py disclosure .` 待办 0 条 | **待办 0 条**（机械可判 0 · 待模型 0） | ✅ |
| 3 | `weave.py self-check` 通过 | **PASS**（exit 0） | ✅ |
| 4 | `docs/contract.md` §4 只引 agentskills.io + Anthropic | Dream/包主口径仅存于「**已删除的旧口径**」列表 | ✅ |
| 5 | README 示例能一次跑通 | prepare→disclosure→dispatch 真跑通（1 批 · prompt 末尾含执行方式） | ✅ |
| 6 | 所有 fixture 测试通过 | `--self-test` **全过** | ✅ |
| 7 | CI 流程通过 | test.yml YAML 合法；两条门禁在 **Python 3.10.16** 上 exit 0 | ✅ |

**核心指标前后对照**（`weave.py disclosure .` 真跑）：

```
改前：超限 1 · 到不了根 13 · 悬空 12      文档 19 份 · L1=1 → L2=4
改后：超限 0 · 到不了根  0 · 悬空  0      文档 23 份 · L1=1 → L2=22
```

---

## 二、10 个 ticket 的落地情况

| # | 内容 | 交付方式 | 关键读数 |
|---|---|---|---|
| 01 | caps 表统一为 agentskills.io + Anthropic | merge | 删 Dream 20000B、50/150/500 三档、MAX_FIRST_LAYER 硬闸 |
| 02 | templates/examples/tests 自动豁免 | merge | 资源目录不进待办，单列「已豁免」 |
| 03 | SKILL.md 两层重构 | **按路径重放** | 5164 tok/180 行 → 1810 tok/89 行；4 个新 references 全在 L2 |
| 04 | 披露深度 L3+ 只警告不退出 | **按路径重放** | L4 fixture：exit 0 + 警告 + depth_histogram |
| 05 | self-check + 脚本不做悬空检查 + 目录级点名 | merge | 三项归零；反向闸验证 markdown 悬空照报 |
| 06 | prepare 询问并持久化执行者 | merge | dispatch/executor.json |
| 07 | dispatch 输出「执行方式」章节 | merge | prompt 末尾含填好占位符的命令 |
| 08 | CLI 错误消息统一 | merge | 用法 + 说明 + 简要帮助 |
| 09 | CI 两条门禁 | merge | .github/workflows/test.yml + 徽章 |
| 10 | README/文档/CHANGELOG | **按路径重放** | 两层披露改写；18 个 md 内链失效 0 |

---

## 三、执行中发现并绕过的问题（附证据）

### 1. 并行 worktree 的「静默回退」陷阱（3 次）

ticket-04 / 03 / 10 的分支各自基于**当时**的 main，而 main 在此后又被别的 ticket 推进。
直接 `git merge` 会**静默回退**后来者的成果：

| 分支 | 整分支 merge 会造成的破坏 | 实际处理 |
|---|---|---|
| ticket-04 | 回退 ticket-01/02 的 caps 表与自动豁免 | 取纯改动重放 |
| ticket-03 | 回退 ticket-07 的 dispatch 改动（-38 行） | 按路径取 7 个内容文件 |
| ticket-10 | **删掉 `.github/workflows/`**（-75 行） | 按路径取 8 个内容文件 |

**判据**：不信任「merge 成功」，改用 `git diff <分支点> <分支>` 取纯改动，再用**集合级 diff** 验证
（broken / orphans 新增 = 0），而不是比计数。

### 2. 工具自身的盲点（本轮最有价值的发现）

fixture 字符串与注释里的示例路径被当成「悬空引用」：`selftest.py:166` 的 `` `references/ref1.md` ``
让悬空计数 11 → 12。这不是包的问题，是工具口径的问题——已由 ticket 05 按「脚本不做悬空检查」修正，
并留**反向闸**（markdown 悬空照报）。我用独立探针验证：

```
markdown SKILL.md:7 写 `references/nope.md`   → 仍报悬空 ✅
脚本 helper.py 写 `references/also-missing.md` → 不报 ✅
```

### 3. 两处「声称但我实测推翻」

| 声称 | 实测 | 处理 |
|---|---|---|
| ticket-07：disclosure `external 21` | 实为 **13**（笔误） | 在提交信息更正 |
| ticket-10：旧 URL 已 **404** 故替换 | 实测 **200**（并未失效） | 替换保留（新页更精确），理由更正为「更精确」 |

---

## 四、遗留事项

1. **未 push**：所有改动在本地 main（HEAD `5a7ac25`），未推到 origin。
2. **10 个 ticket-* 分支未删**：其中 03/04/10 分支的原始提交未进 main 历史（以重放形式落地），
   删除会丢记录；如需清理请明示。
3. **CI 未在真 GitHub 上跑过**：仅本地验证 YAML 合法 + 两条门禁在 Python 3.10.16 退 0。
   push 后首次 workflow 运行才算真验证。
4. **`.skillweave/` 快照已随包提交**（契约 §9）：`DISCLOSURE.md` / `disclosure.json` / `TODO.md`。
5. **spec 中未做的**：CLI 的 `help <command>` 子命令（ticket 08 只做了错误消息统一与简要帮助）。

---

## 五、清理阶段的新发现（2026-10-16 补充）

### 5.1 一个「迟到提交」造成的真缺口（已修复）

清理分支时发现 `ticket-01` 的 tip 不是我提交的 `3eb3bc1`，而是 `5265afd`「（补全）」——
最早那批 opencode 进程在我提交之后、**仍在后台运行时**又自己提交的一个。

逐文件核对后确认：它对 `transform.py` / `split.md` / `contract.md` 的改动已被
ticket-06 / 03 / 10 超越，**唯一真缺口在 `analysis.py`**：

| 位置 | 声称 | 实际（修复前） |
|---|---|---|
| `CHANGELOG.md:31` | 硬闸「已收敛为参考线」 | — |
| `references/concepts.md:78` | 列入「已删除的旧口径」 | — |
| `common.py:35` | 「已删除 `MAX_FIRST_LAYER=20` 硬闸」 | — |
| `docs/contract.md:221` | 「收敛为参考线」 | — |
| `analysis.py:81/122` | —— | 仍 `len(entries) > MAX_FIRST_LAYER` 判 ❌，且本地重定义该常量，注释仍指 Dream |

**4 处文档与代码自相矛盾**，已修复（commit `b643479`）：改用 `common.FIRST_LAYER_REFERENCE`，
措辞由「❌ 超上限」改「⚠️ 超参考线（非规范要求）」，阈值改引 `CAP_*` 常量，删除本地副本。
实测：`layers .` 现输出「✅ 在参考线内」。

### 5.2 self-check 的边界（重要）

`self-check` **没有**发现 5.1 这条缺陷。它校验的是**披露结构**
（超限 / 到不了根 / 悬空 / 披露过深），**不校验「文档声称」与「代码实现」是否一致**。
这类不一致目前只能靠人工比对发现 —— 记在此处，避免误以为 self-check 是万能的。

### 5.3 分支清理前的内容核验（不靠分支状态，靠特征标记）

`git merge-base --is-ancestor` 会因分支被重放而误报「未合入」。改用**内容标记**逐项核验
main 是否含 10 个 ticket 的成果，10 项全 ✅ 后才清理。核验方法：

| ticket | 核验标记 |
|---|---|
| 01 | `common.py` 含 `SRC_AGENTSKILLS` |
| 02 | `disclosure.py` 含 `AUTO_WAIVED_DIRS` |
| 03 | `SKILL.md` 89 行 + `references/` 8 个文件 |
| 04 | `disclosure.py` 含 `depth_histogram` |
| 05 | `cli.py` 含 `self-check` |
| 06 | `transform.py` 含 `executor` |
| 07 | `disclosure.py` 含 `执行方式` |
| 08 | `cli.py` 含 `print_main_help` |
| 09 | `.github/workflows/test.yml` 存在 |
| 10 | `README.md` 含「两层披露」+ `CHANGELOG.md` |
