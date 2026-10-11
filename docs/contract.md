# 契约：文档树的节点 schema 与「三级披露」的定义

这份文件是 SkillWeave 的**唯一契约**：所有脚本、报告、判据都按它读。改这里就等于改全仓库的口径。

**输入的单位是 pack，不是单个 skill**：一个 skill pack = 一个仓库/目录，含 1..N 个 skill；
输入 = 一整套含 `SKILL.md` 的文件夹树（工具自己认出 skill / 类目 / 资源）。

## 0. 三级披露（层 = 选择发生的级，不是文件层级）

| 级 | 是什么（节点范围） | 每次会话/每次触发的代价 | 要量的量 | 闸 |
|---|---|---|---|---|
| **L1 第一级** | pack 里**所有 skill 的 `name` + `description`**；若用类目，L1 被拆成两级（先选类目 → 再选技能），每级的选项数都要报 | **常驻**（每会话必付） | 入口层（最顶层装技能的那一个目录）的**直接子项数** = 散技能数 + 类目数；常驻字符数 + 估算 token；`description` 长度分布 | 入口层条目 ≤ `MAX_FIRST_LAYER`(20)；`description` ≤ 1024 字符（规范硬约束） |
| **L2 第二级** | 单个 skill 的 `SKILL.md` 正文（选中后载入） | 触发时载入 | 正文估算 token / 行数；正文点名了多少同 pack 兄弟（转指出去的选择数） | < 5000 est_token；行数三档 50 / 150 / 500 |
| **L3 第三级** | 该 skill 的 `references/` `scripts/` `assets/` | 按需读 | 文件数与体积、最大单文件、**孤儿**、**悬空引用**、从入口到文件的跳数 | 孤儿 = 0；单份 `references/*.md` ≤ 20000 B |

- 「入口层」的判定：自上而下第一个**直接**含 skill 的目录（本机 packs 里通常是 `skills/`）。
  入口层的**直接子项数**就是 Agent 第一次选择看到的菜单大小 —— Dream 的
  `MAX_FIRST_LAYER_SKILLS` 量的正是这个数。
- 类目层让 L1 变成两小步：`skills/`（17 个类目 + 52 个散技能 = 69 项）→ 点进 `skills/research/`（17 项）。
  「把散技能归入类目」这个优化动作改的就是 L1 的选项数，不动 L2/L3。

节点与字段名**沿用 `tanker327/agent-skill-analysis` 的口径**（见 `docs/similar-work.md` A1），
以便将来把 per-skill 部分换成 `asa --json` 时不必重命名；本仓库只多出 **pack / 类目** 这一层。

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

## 4. caps（阈值）与出处

| 阈值 | 值 | 出处与口径 |
|---|---|---|
| `SKILL.md` 正文 | 建议 **< 5000 token** | agentskills.io 规范 / Claude 作者规范；拆文件建议 |
| 正文行数（三档） | 50 / 150 / 500 | `claude-skills-cli` 的 default / `--lenient` / `--loose`（500 = 官方上限） |
| L1 元数据 | **< 200 字符** | `claude-skills-cli` 的 L1 上限 |
| `description` | hard ≤ **1024 字符** | agentskills.io 规范（硬约束） |
| 单份 `references/*.md` | 报超 **20000 字节** | Dream 的 `check-disclosure.py` 常量（本机既有口径，沿用） |
| `fanout` | **不设死值**，报分布 + 校正随机分 | Meta arXiv:2605.24660 |
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
