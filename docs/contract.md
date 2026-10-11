# 契约：文档树的节点 schema 与「三级披露」的定义

这份文件是 SkillWeave 的**唯一契约**：所有脚本、报告、判据都按它读。改这里就等于改全仓库的口径。

**输入的单位是 pack，不是单个 skill**：一个 skill pack = 一个仓库/目录，含 1..N 个 skill；
输入 = 一整套含 `SKILL.md` 的文件夹树（工具自己认出 skill / 类目 / 资源）。

## 0. 层 = **披露深度**（用户 2026-10-11 定口径）

**层不是文件类型，也不是「选择发生的级」——层是文档之间的披露关系：**

- **L1 = 根文档**（`SKILL.md`）——Agent 最先拿到的那份。
- **L2 = L1 直接披露的文档**（L1 正文里真实点到的路径）。
- **L3 = L2 直接披露的** …… **Lₙ₊₁ 由 Lₙ 披露**。

「一层摆出几项」= **该层每份文档各自披露了几项**（fanout），不是「全 pack 的描述菜单有多大」。
披露 = 正文里真实点到的一份文档（先按该文件所在目录、再按该 skill 目录、再按 pack 根解析）；
URL、代码围栏里的路径、没有目录部分的裸文件名都**不算**披露。指出 pack 外的记 `external`，指到不存在的记悬空。

**根的数量 = 形状**：

| 形状 | 根 | 典型 | 代价 |
|---|---|---|---|
| **多入口** | **K 个根**（每个 skill 的 `SKILL.md` 都是可能的 L1，Agent 先按 description 选根） | 39 个 skill → 39 个根 | 常驻 = 全部 description；独立可装 = K |
| **单入口** | **1 个根**（伞的 `SKILL.md`，其余全是它的 `references/`） | 伞 → 13 岛 → 39 篇正文 → 118 份资源 | 常驻 = 1 条 description；**独立可装 = 1** |

UsingHermes 实测（`weave.py disclosure`，2026-10-11）：

```
单入口：L1=1 → L2=13 → L3=39 → L4=118 · 到不了根=31 · 文档 202 份 · 超限 10 · 悬空 130 · external 389
多入口：L1=39 → L2=118 → L3=3          · 到不了根=28 · 文档 188 份 · 超限 10 · 悬空  91 · external 388
```

**逐文档体检**（同一张判据表按层 × 文档类型跑，每个文档都要过自己那类 cap）：

| 文档类型 | 闸 | 出处 |
|---|---|---|
| 根文档 / 任何 `SKILL.md` | 正文 < 5000 est_token；行数三档 50 / 150 / 500 | agentskills.io / `claude-skills-cli` |
| 任意文档的 `description` | ≤ 1024 字符 | agentskills.io（硬约束） |
| 任意资源文件（`references/ scripts/ assets/`） | ≤ 20000 B | Dream `check-disclosure.py` 常量 |
| 跨文档 | 孤儿（in-degree 0 且非根）；悬空（披露了不存在的）；根选择层近重复（靠 description 选根才算） | 本仓库契约 |

**仍然适用的旧口径**（不要丢）：`MAX_FIRST_LAYER = 20` 是**参考线不是硬闸**（§4）；
「入口层」= 从 pack 根下钻到 ≥2 个选择项为止的那一层（多入口形状下它给出「Agent 第一次点击看到几项」）。

节点与字段名**沿用 `tanker327/agent-skill-analysis` 的口径**（见 `docs/similar-work.md` A1），
以便将来把 per-skill 部分换成 `asa --json` 时不必重命名；本仓库只多出 **pack / 类目** 这一层。

## 0.5 术语表（报告里出现这些词就是这些意思）

| 词 | 定义 | 出处/判据 |
|---|---|---|
| 文档 / 节点 | 一份文件（`SKILL.md`、`references/*.md`、`scripts/*.py` 各算一份） | — |
| 根 | 起点文档 = 一个 skill 的 `SKILL.md`；**根有几个 = 形状**（1 = 单入口，K = 多入口） | §0 |
| 披露 | 一份文档正文里真的写出了另一份的路径；**不算**：URL、围栏里的示例路径、没有目录的裸文件名 | 与 `analyze_skill` 的 `refs` 同口径 |
| L1 / L2 / … | 离根几步（根 = L1） | §0 |
| fanout | 该文档披露了几份别的文档 | — |
| 到不了根 | 从任何根顺着披露都走不到它（in-degree 0 且非根） | 旧名「孤儿」，同一件事 |
| 超限 | 超过它那类的上限；**报告必须写超多少** | §4 的 caps |
| 悬空 | 写了像本 pack 内的路径但文件不存在 | 与 `refs.kind == broken` 同一件事 |
| external | 正文里提到的本 pack 之外的文件（不算披露、也不算错） | 与 `refs.kind == external` 同一件事 |
| 近重复 | 同层两份文档太像（描述或内容），Agent 会选错 | `audit.json:dup` / 根选择层 |

**报数规则**：报告里出现上面任何一个词，读者都应该能只靠这张表读懂；数字必须能被同一条命令复跑出来。

## 0.6 第二步的出口与免检表

- **出口 = `TODO.md`**（不是体检表）：每条待办 = `文档 · 问题 · 数字 · 建议动作 · 谁判`。谁判只有两种：`机械可判`（能直接动手）
  与 `待模型`（要判断）。体检表明细（`DISCLOSURE.md`）留作附件；第三步只吃 `TODO.md`。
- **免检表在包里、不在工具里**：`<pack>/.skillweave/waivers.txt`，一行一条 `<glob>` + 两个以上空格 + 理由（`#` 注释）。
  命中的记「已豁免」并单独计数。理由：「哪张 png 是给人看的」「哪个 json 是测试留档」是**包主的判断**，
  不是通用真理 —— 写进工具就等于替所有包做决定。
- **悬空按文件聚合**成一行（`N 条（行号: 目标 …）`），否则一个文件十几条会把待办清单淹掉。

## 0.7 派发与验收（第三步的机械部分）

两个命令，产物落在 `<pack>/dispatch/`：

- **`dispatch <pack> [--batch-size 10]`** —— 派发前**事实补全** + 划批 + 落 prompt + 计数起点。
  - 单位 = **skill 子树**（文件归属 = 最长前缀匹配的 `SKILL.md` 目录）；断言**批次间文件集合两两不相交**。
  - **事实补全**（能从树/包里查到的先算好，让子代理「验路径」而不是「猜路径」）：悬空 → 包内同名候选；
    到不了根 → 同目录里**被披露过的兄弟**；超限 → 行数 + 二级标题清单。这是第一次成功率的大头。
  - 产物：`plan.json`（批次/条目/`prompt_sha256`）· `state.json`（`attempts` 计数）· `batch-N.prompt.md`。
  - 条目 id = `kind-<sha1(path:line)[:8]>`（稳定，可跨命令引用）。
- **`verify <pack> --state … --expect-fixed <id…> [--splits <json>]`** —— **闸 1**，四类判据：
  1. **该消的消了**（`--expect-fixed` 的 id 在重扫后必须消失）；
  2. **无新增**（集合级 diff：新出现的发现一律算回归 —— 不是比计数）；
  3. **external 集合不变**；
  4. **拆分守恒**：删掉空行与标题行后，原文的字符序列 == 各新文件拼接；且**每个新文件都被披露**（否则它立刻变成新的「到不了根」）。
- 失败 = **整批回滚**（不逐条打补丁，否则后续测量失去基准），并按梯子决定下次派发改什么输入：
  `R1 给证据 → R2 减粒度 → R3 喂事实 → R4 换执行者 → R5 落 PARKED.md`。**回归项也计账**。
- **不许打转**：同一 prompt hash 不许重派（相同输入 = 相同输出）；计数写在 `state.json`，不在谁的记忆里。
- 跑完读两个文件：`RUN.md`（每批：过了没 · 哪条判据拦的 · 下一级是什么）与 `PARKED.md`（走完梯子仍不过的，等一条规则）。

## 1. 节点

每个节点最少这几个字段（`tree.json` 里一棵树，人读视图是 `TREE.md`）：

| 字段 | 含义 | 来源（必须是可指认的） |
|---|---|---|
| `id` | pack 内唯一，等于从 pack 根算起的相对路径（目录带尾 `/`），章节用 `#<行号>` 后缀 | 文件系统 / 正文行号 |
| `kind` | `pack` / `category` / `skill` / `heading` / `instructions` / `reference` / `script` / `asset` / `readme` / `license` / `other` | 见 §2 判定规则 |
| `parent` | 父节点 `id`；pack 根为 `null` | 树结构 |
| `bytes` | 该节点自身内容的字节数（目录 = 其自身文件之和，不含子节点重复计） | `os.path.getsize` |
| `est_tokens` | 估算 token：CJK 字符 ×1 + 其它字符 ×0.25，四舍五入（**估算**，报告里必须写明口径） | 文件内容 |
| `summary` | 一行摘要；**只能来自文件自身内容**，禁止手写 | frontmatter `description` 优先，否则正文首个非标题段落首句，都没有则 `null` |
| `summary_source` | `summary` 的出处，如 `SKILL.md:3 frontmatter.description`；`null` 时也写 `null` | 行号 |
| `refs` | 该节点正文里**真实出现**的引用：`[{target, kind: declared\|resolved\|broken\|external\|example, line}]` | 正文（反引号/链接里的相对路径） |
| `mentions` | 正文里点到的**同 pack 其它技能名**（路由信号，来自 pack 自己的技能名清单） | 正文 |
| `children` | 子节点数组，按 `id` 排序 | 树结构 |

**内化自上游的字段（2026-10-11 加，出处见 `docs/compare-tools.md` §3）**：每文件 `sha256`；skill 节点
`digest`（忽略 `version`/`updated`/`date`/`modified` 的内容指纹，用来判「同一内容是否变了」）、
`license` / `readme`（命中的路径，无则 `null`）、`size_by_kind`（按 `kind` 的字节分解 = 指令重量 vs 资源重量）、
`counts`（`code_blocks` / `sections` / `long_paragraphs` / `todos` —— 「该拆」的可量信号）。

**`kind` 判定（唯一一处定义）**

1. 有 `SKILL.md` 的目录 = `skill`。
2. 在 `skill` 之下（或 pack 根之下）的**目录**且不含 `SKILL.md`：
   - 若它**含**至少一个 `skill` 后代 → `category`；
   - 否则 → 按它所在位置归 `asset`。
3. 文件按路径与角色：`SKILL.md` = `instructions`；`README*` = `readme`；`LICENSE*` = `license`；
   `references/**` = `reference`；`scripts/**` 或可执行/脚本后缀 = `script`；`assets/**` 或二进制/图片 = `asset`；
   其余 `other`。
4. 正文里的 `#` 标题 = `heading`（**代码围栏内不算**，围栏状态要逐行维护）。

## 2. 「层」（layer）的定义

> **层 = 从 pack 入口走到某个需求所在节点时，路上遇到的每一个 `fanout > 1` 的节点。**

- `fanout(node)` = 该节点**在同一层上摆出的选项数**：
  - `pack` / `category`：它的子节点数（即「这一层要你在 N 个类目/技能里选」）；
  - `heading` 节点不算层（同一文件内的标题不是独立选择代价）；
  - `skill`：它在正文里点名的**同 pack 技能数** + 它自己（即「这个技能把读者转指到 N 个兄弟」）。
- 每层要报两个数：**选项数**（可数）与**该层被选对的成功率**（T-005 的判官评测给；未测时留空，不许猜）。
- 全局报 `fanout` 的分布直方图，不设"每层最多 N 个"的死值——
  依据：Meta（arXiv:2605.24660）表明层深 K 应当被当作**评估对象**、用校正随机（BoR）判好坏，
  而不是拍一个常量；`skill-tools` 的「Progressive Disclosure」维度也是打分而非硬闸。

## 3. 树的其它口径

- **可重建、可 diff**：同一 pack 连跑两次 → `tree.json` 逐字节相同（无时间戳、键序稳定、子节点排序）。
  改一个文件只应让相关节点及其祖先的 `bytes`/`est_tokens` 变动。
- **引用解析基准**：`ref` 一律先按**该 skill 目录**解析，再按 pack 根解析；两者都不中就记 `broken`；
  指向 pack 外的记 `external`。**两类不算引用、记 `example`**：① 出现在代码围栏内的路径（示例脚本/产物名）；
  ② 没有目录部分的裸文件名（`run.py`、`fig.pdf`、`README.md` 这类正文里泛指的名字；裸 `SKILL.md` 是自指，仍按 resolved 记）。
  依据：对拍实测（`docs/compare-tools.md` §5）旧口径把示例当 broken，6 条里 4 条是误报。
- **孤儿**：skill 目录内除 `SKILL.md` 外的文件，**没有被任何祖先点名** = `orphans`。
  「点名」含**目录级**：正文点名了 `templates/README.md`，则 `templates/` 整目录算被点名（该目录下的文件都不算孤儿）。
  0 容忍，但报告里只列清单，不自动删。
- **互指边与「岛」（`visualize` 用）**：A→B 当且仅当 **A 的任何一个文本文件里出现 B 的目录名**
  （`(?<![\w-])<slug>(?![\w-])`）。岛 = 该有向图**忽略方向**后的连通分量。
  **岛数对口径敏感，报必须连口径一起报**——同一份数据实测：只看 `SKILL.md` 里 frontmatter `name` 互指 → 11 个岛；
  再加「引用解析到别的 skill 目录」的边 → 10 个岛；扫全部文本文件、按**目录名**互指 → 13 个岛。
  选目录名口径的理由：它是包内既有的稳定标识（`name` 与目录名不总一致，实测 `gateway-session-list/` 的 `name` 是 `gateway-operations`）。
  **岛是数据给的分层**（谁真的指到谁），不是人分的类；`visualize` 只画它，不做合并建议。

## 4. caps（阈值）与出处

| 阈值 | 值 | 出处与口径 |
|---|---|---|
| `SKILL.md` 正文 | 建议 **< 5000 token** | agentskills.io 规范 / Claude 作者规范；拆文件建议 |
| 正文行数（三档） | 50 / 150 / 500 | `claude-skills-cli` 的 default / `--lenient` / `--loose`（500 = 官方上限） |
| L1 元数据 | **< 200 字符** | `claude-skills-cli` 的 L1 上限 |
| `description` | hard ≤ **1024 字符** | agentskills.io 规范（硬约束） |
| 单份 `references/*.md` | 报超 **20000 字节** | Dream 的 `check-disclosure.py` 常量（本机既有口径，沿用） |
| `fanout` | **不设死值**，报分布 + 校正随机分 | Meta arXiv:2605.24660 |
| 入口层条目数 | `MAX_FIRST_LAYER = 20`，**参考线不是硬闸** | 出自 Dream 的 `check-disclosure.py` 的 `MAX_FIRST_LAYER_SKILLS`，**不是规范要求**。2026-10-11 定：超了只提示；实际处置走「按互指岛分组」而不是往 20 上削（UsingHermes：28 → 13 项） |
| 孤儿 | **0** | 本仓库契约（`agent-skill-analysis` 同口径报 `orphans`） |

表中每个数字都必须能追到 `docs/similar-work.md` / `docs/prior-art.md` 的对应条目；**不许出现没有出处的自创数字**。

## 5. 最小示例（真实产物片段：`tree.json` 里的一个 skill 节点）

```json
{
  "id": "skills/demo/", "kind": "skill", "parent": "skills/", "tracked": true,
  "name": "demo", "bytes": 1024, "est_tokens": 210, "body_lines": 40,
  "summary": "做一件事时用。", "summary_source": "skills/demo/SKILL.md frontmatter.description",
  "refs": [{"target": "references/guide.md", "kind": "resolved", "line": 9}],
  "orphans": [], "broken": [], "mentions": ["other-skill"],
  "files": [{"path": "references/guide.md", "kind": "reference", "bytes": 300, "orphan": false}],
  "children": [{"id": "skills/demo/SKILL.md#12", "kind": "heading", "parent": "skills/demo/",
                "level": 2, "summary": "小节", "summary_source": "skills/demo/SKILL.md:12"}]
}
```

读它的判据：`python3 -c "import json; json.load(open('tree.json'))"` 能读；
每个 `kind` 都必须落在 §1 的枚举里；`refs[].kind` 必须是 `declared|resolved|broken|external|example`。

## 6. 依赖与内化政策（用户 2026-10-11 定，硬约束）

- **不引外部依赖**：不引 Node / npm / 第三方 Python 包。工具只依赖 `python3` 标准库与 `git`（且 git 缺失时降级为「全部算成员」）。
  理由（用户原话）：「agent-skill-analysis 只是一个科研项目，还没有在社区中得到广泛的应用，后续的优化更新会受限，
  所以我倾向于不使用外部依赖，只是在其他项目效果更好时将其内化」。
- **内化的定义**：把别人的**规则、检查清单、字段口径、判断方法**搬进本仓库自行实现（纯 stdlib），
  并在 `docs/compare-tools.md` 记录来源与实测对照；**不搬代码、不绑版本**。
- **只在实测更好时内化**：先对拍（同一份 skill 上跑出可比数字），确认对方某项更准/更全，才内化那一条；
  对拍结果与结论进 `docs/compare-tools.md`。
- **允许的例外**：一次性的对拍脚本可以调外部工具（只为取数、不进主路径、不作为运行前提）。

## 7. 两种形状：多入口（默认）与单入口（可选）

同一个 pack 有两种摆法，工具两种都能算、能画、能落。**默认多入口；单入口要专门点名才做**。

| | 多入口（默认） | 单入口（`weave.py collapse`） |
|---|---|---|
| L1 | pack 里**所有 skill** 的 `name`+`description`（常驻菜单） | **1 个**伞 skill 的 `description` |
| L2 | 某个 skill 触发后载入的 `SKILL.md` 正文 | 伞体里的**岛索引**（每岛一行）→ `references/<岛>/INDEX.md` |
| L3 | 该 skill 的 `references/scripts/assets` | 39 篇原正文 + 各自的支持文件，整棵搬进 `references/<岛>/<skill>/` |
| 独立可装 | 每个 skill 各自能装 | **只剩伞那一个**（其余不再是 skill） |

UsingHermes 上实测（`0de1ca9` 起，`--entry-dir using-hermes`，在被测包的**副本**上真跑）：

| 项 | 多入口 | 单入口 |
|---|---|---|
| 常驻 | 39 条 description = **3,310 tok** | 1 条 = **58 tok**（description 写多长就是多少） |
| 第一次点击 | 13 项 | **1 项** |
| 第二次点击 | — | **13 项**（伞体 **556 tok**） |
| 第三次点击 | 无 | **39 项**（13 份 `INDEX.md` 合计 **4,344 tok**，均值 334） |
| L3 文件 | 149 | 162（+13 个 `INDEX.md`） |
| 独立可装 | **39** | **1** |

两条必须一起报的**口径陷阱**：

1. 单入口下 `孤儿`/`悬空` 会归零（26/25 → 0/0）——伞体按**目录**点名了每个 `references/<岛>/`，
   目录级点名把里面所有文件都盖住了。**这是构造性假象，不是问题被修好**：指标在这套摆法下失去分辨力。
2. 「岛」数依互指口径而定（§3）：同一份数据 11 / 10 / 13。报数必须连口径一起报。

分工不变：搬目录、生成伞体与各岛 `INDEX.md` 是机械的，工具做；**那一条 `description` 由模型写**
（它是唯一的常驻触发词），所以 `--apply` 不给 `--description` 直接拒绝退出，不生成半成品。
