# 契约：文档树的节点 schema 与「层」的定义

这份文件是 SkillWeave 的**唯一契约**：所有脚本、报告、判据都按它读。改这里就等于改全仓库的口径。

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
| `refs` | 该节点正文里**真实出现**的引用：`[{target, kind: declared\|resolved\|broken\|external, line}]` | 正文（反引号/链接里的相对路径） |
| `mentions` | 正文里点到的**同 pack 其它技能名**（路由信号，来自 pack 自己的技能名清单） | 正文 |
| `children` | 子节点数组，按 `id` 排序 | 树结构 |

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
  指向 pack 外的记 `external`。
- **孤儿**：skill 目录内除 `SKILL.md` 外的文件，**没有任何祖先节点点名**（`refs` 里不出现）= `orphans`。
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
每个 `kind` 都必须落在 §1 的枚举里；`refs[].kind` 必须是 `declared|resolved|broken|external`。
