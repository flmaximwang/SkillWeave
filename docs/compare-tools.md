# 上游工具 vs SkillWeave：同一份 skill 上的对拍（2026-10-11 实测）

被测对象：`AgentSkill-UsingHermes/skills/research/research-paper-writing/`（56 个文件、`SKILL.md` 1611 行）
本机：Node v26.7.0 / npm 11.19.0；Python 3.9（Xcode 自带）。命令与输出都留在本机，可重跑。

## 1. 准确性（同一份 skill、逐项对比）

| 项 | `asa`（agent-skill-analysis） | SkillWeave | 判定 |
|---|---|---|---|
| 文件清单 | 56 | 56 | ✅ 一致 |
| heading 数 | 89 | 89 | ✅ 一致（两个独立实现同一数字） |
| 正文行数 | 1611 | 1611 | ✅ 一致 |
| token 估算 | 17,699（`tokenizer: approx-chars-4`） | 17,832（CJK×1+其它×0.25） | ✅ 差 <1%，口径不同都已写明 |
| 引用：declared / resolved | 10 / 10 | 19 / 11 | ❌ **我多抓了 8 条**：代码示例里的 `run.py`、`fig.pdf`、`README.md` 这类**示例路径**被我当成真引用 |
| 引用：broken | **0** | 6 | ⚠️ **双向错**：我这 6 条里 4 条是示例误报；但 `scripts/reproduce_table1.sh`、`scripts/make_figure2.py` 是**真缺失**（`skill-tools` 独立报出这两条）——**asa 漏报真问题** |
| 孤儿文件 | 0 | 44 | ⚠️ 口径不同：我按「文件必须被正文点名」；`templates/*.tex` 只在 `templates/README.md` 里被点名 ⇒ 我算孤儿。**我的规则过严**，需要「目录级点名」例外 |
| 我没有的字段 | `sha256`/文件、内容 `digest`、`license`/`readme` 检测、`specVersion`、`diagnostics`、按 kind 的体积分解 | — | ✅ asa 更全，这些值得内化 |

**结论**：单 skill 的**结构数字三家一致**（互验通过）；差异全在**语义判断**上 ——
`asa` 对示例路径不误报但会漏报真缺失；我的引用抽取需要区分「示例」与「真引用」，孤儿规则需要「目录级点名」。

## 2. 效率（真跑计时）

| 工具 | 用时 | 范围 | 依赖 |
|---|---|---|---|
| `asa` | 冷 **6.58 s** / 热 **1.46 s** | **1 个** skill（56 文件） | Node ≥20 + npm（首次需联网取包） |
| `skill-tools check` | **11.38 s** | 1 个 skill | Node + npm |
| `claude-skills-cli validate` | **7.22 s** | 1 个 skill | Node + npm |
| SkillWeave `tree` | **3.06 s** | **整个 pack：126 skill / 1941 节点** | 纯 stdlib python3，离线 |
| SkillWeave `layers` | 同量级（一遍走树） | 整个 pack | 同上 |

**结论**：per-skill 上三者与我同量级；**pack 规模上我一次走完 126 个 skill 只要 3 s**，
它们是「一个目录一次调用」，按 pack 跑要 N 次进程启动（Node 冷启 ~1.5 s/次）。

## 3. 它们做的、我该内化的（不引入 Node 依赖）

| 来源 | 内化什么 | 为什么值得 |
|---|---|---|
| `asa` | 每文件 `sha256`、内容 `digest`（忽略 `metadata.version` 的指纹）、`license`/`readme` 检测、按 kind 的体积分解、产物里写明 token 口径 | 全是 stdlib 可做；digest 让「可重建、可 diff」有硬指纹 |
| `skill-tools` 的检查清单 | 20 条 spec 检查里的：引用文件存在、token 预算、BOM、二进制内容、`name` 与目录名一致；10 条 lint 里的：**无硬编码路径**、**无内嵌密钥**、description 用具体动词、正文含示例 | 前两类是**安全/可移植闸**（真会拦下坏 skill），且都是纯文本规则 |
| `claude-skills-cli` 的量化告警 | 正文里代码块数、章节数、长段落（>100 词）数、TODO 占位符数 | 这正是「该拆」的可量信号，直接服务 `references/split.md` 的判断 |

## 4. 不内化的部分（以及为什么）

- **不硬依赖 Node/npm**：`npx` 每次要联网解析包、冷启 1.5–6.6 s；本仓库要能被任意 agent 装上就跑，
  引入运行时依赖会毁掉这一点。
- **可选适配器**：`weave.py tree --from-asa <dir>`（本机有 Node 时吃它的 JSON 补 sha256/digest），
  没装就跳过 —— 代码只有一处读它，不是必须路径。
- **不建议现在做**：`skill-tools` 的 BM25 检索式路由（我们要的是**判官式**路由归因评测，口径不同）；
  `claude-skills-cli` 的 `init` 脚手架（本仓库不做生成）。

## 5. 本次对拍直接带来的两个待修 bug（已进 plan）

1. **引用抽取要区分「示例」与「真引用」**：代码围栏内、以及 `` ``run.py`` `` 这种演示用的路径，
   应标 `example` 而不是进 `broken` —— 现状会误报（实测 6 条 broken 里 4 条是误报）。
2. **孤儿规则要加「目录级点名」**：`templates/README.md` 被点名，则该目录下的模板算被点名
   （现状 44 条孤儿里绝大多数是 `templates/*`）。
