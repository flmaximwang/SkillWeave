# 披露链 · SkillWeave

## 术语表

- **文档 / 节点**：一份文件（`SKILL.md`、`references/*.md`、`scripts/*.py` 各算一份）。
- **根**：起点文档 = 一个 skill 的 `SKILL.md`。**根有几个 = 形状**（1 个 = 单入口，K 个 = 多入口）。
- **披露**：一份文档正文里真的写出了另一份文档的路径。**不算**披露：URL、代码围栏里的示例路径、没有目录的裸文件名。
- **L1/L2/…**：离根几步。根 = L1，根披露的 = L2，依次往下。
- **fanout**：这份文档披露了几份别的文档（某一层「摆出几项」= 该层各文档 fanout 之和）。
- **到不了根**：从任何根顺着披露都走不到它（没有任何文档点到它）。
- **超限**：超过它那类的上限 —— `name` >64 字符 · `description` >1024 字符（agentskills.io，错误）；正文 >5000 tok / >500 行 · `references/` 单文件 >300 行（Anthropic 建议，警告）。**脚本与资源不计**：Agent 不整份读脚本/二进制资源，字节数不是披露缺陷（口径见 `docs/contract.md` §4）。
- **悬空**：写了像本 pack 内的路径，但那个文件不存在。
- **external**：正文里提到的本 pack 之外的文件（不算披露、也不算错）。
- **近重复**：同层两份文档太像，Agent 会选错。

口径：**层 = 披露深度**（L1 = 根文档 `SKILL.md`；L2 = L1 正文直接点到的文档；Ln+1 由 Ln 披露）。不是「按文件类型分三级」那套。

- 根：**1 个**（每个 skill 的 `SKILL.md` 是一个根；1 个 = 单入口形状）
- 文档节点：**23 份** · 层数：**2**
- 超限：**0** 份 · 到不了根：**13** 份 · 自动豁免（资源目录）：**0** 份 · 悬空引用：**12** 条 · 外部引用（不算披露）：**16** 条
- 根选择层近重复（Jaccard≥0.5·靠 description 选根才算）：**0** 对
- **待办 16 条 · 已豁免 0 条** → 见同目录 [`TODO.md`](TODO.md)（豁免规则 0 条，来自包里 `.skillweave/waivers.txt`）

## L1（1 份）

| 文档 | fanout（披露几项） | 体积 | 判定 |
|---|---|---|---|
| `skills/skillweave/SKILL.md` | 10 | 1810 tok / 84 行 | 根 |

## L2（9 份）

| 文档 | fanout（披露几项） | 体积 | 判定 |
|---|---|---|---|
| `skills/skillweave/references/commands.md` | 1 | 3236 tok / 224 行 | ✅ |
| `skills/skillweave/references/concepts.md` | 4 | 2424 tok / 120 行 | ✅ |
| `skills/skillweave/references/group.md` | 1 | 802 tok / 59 行 | ✅ |
| `skills/skillweave/references/merge.md` | 1 | 836 tok / 51 行 | ✅ |
| `skills/skillweave/references/pitfalls.md` | 1 | 1627 tok / 83 行 | ✅ |
| `skills/skillweave/references/rewrite.md` | 0 | 1192 tok / 62 行 | ✅ |
| `skills/skillweave/references/split.md` | 2 | 1438 tok / 75 行 | ✅ |
| `skills/skillweave/references/workflow.md` | 2 | 3053 tok / 148 行 | ✅ |
| `skills/skillweave/scripts/weave.py` | 0 | 549 B | ✅ |

## 到不了的文档（没有任何根披露到它们；`templates/`·`examples/`·`tests/` 自动豁免）

| 文档 | fanout（披露几项） | 体积 | 判定 |
|---|---|---|---|
| `skills/skillweave/scripts/weavelib/__init__.py` | 1 | 974 B | ⚠️ 孤儿 |
| `skills/skillweave/scripts/weavelib/analysis.py` | 2 | 19835 B | ⚠️ 孤儿 |
| `skills/skillweave/scripts/weavelib/cli.py` | 0 | 14089 B | ⚠️ 孤儿 |
| `skills/skillweave/scripts/weavelib/common.py` | 1 | 8347 B | ⚠️ 孤儿 |
| `skills/skillweave/scripts/weavelib/deliver.py` | 0 | 11423 B | ⚠️ 孤儿 |
| `skills/skillweave/scripts/weavelib/disclosure.py` | 2 | 27761 B | ⚠️ 孤儿 |
| `skills/skillweave/scripts/weavelib/frontmatter.py` | 0 | 6927 B | ⚠️ 孤儿 |
| `skills/skillweave/scripts/weavelib/graph.py` | 1 | 27032 B | ⚠️ 孤儿 · ❌ 有悬空引用 |
| `skills/skillweave/scripts/weavelib/model.py` | 2 | 14540 B | ⚠️ 孤儿 · ❌ 有悬空引用 |
| `skills/skillweave/scripts/weavelib/pack.py` | 0 | 4184 B | ⚠️ 孤儿 |
| `skills/skillweave/scripts/weavelib/render.py` | 2 | 23980 B | ⚠️ 孤儿 |
| `skills/skillweave/scripts/weavelib/selftest.py` | 0 | 50873 B | ⚠️ 孤儿 · ❌ 有悬空引用 |
| `skills/skillweave/scripts/weavelib/transform.py` | 0 | 40494 B | ⚠️ 孤儿 |

## 根选择层（L0）

根不是被谁披露出来的，而是**靠 description 选出来的** —— 所以它单独一层，混进 Ln 会让两个形状的层数不可比。

| 根 | description 字符 | 常驻 tok | 同层近重复 |
|---|---|---|---|
| `skills/skillweave/SKILL.md` | 180 | 132 | — |

### 悬空引用

- `skills/skillweave/scripts/weavelib/graph.py:162` → `references/x.md`（不存在）
- `skills/skillweave/scripts/weavelib/model.py:79` → `templates/README.md`（不存在）
- `skills/skillweave/scripts/weavelib/selftest.py:36` → `references/guide.md`（不存在）
- `skills/skillweave/scripts/weavelib/selftest.py:36` → `references/gone.md`（不存在）
- `skills/skillweave/scripts/weavelib/selftest.py:37` → `templates/README.md`（不存在）
- `skills/skillweave/scripts/weavelib/selftest.py:137` → `references/中文说明.md`（不存在）
- `skills/skillweave/scripts/weavelib/selftest.py:143` → `references/x.md`（不存在）
- `skills/skillweave/scripts/weavelib/selftest.py:147` → `references/leaf.md`（不存在）
- `skills/skillweave/scripts/weavelib/selftest.py:166` → `references/ref1.md`（不存在）
- `skills/skillweave/scripts/weavelib/selftest.py:334` → `references/moved2.md`（不存在）
- `skills/skillweave/scripts/weavelib/selftest.py:383` → `references/p1.md`（不存在）
- `skills/skillweave/scripts/weavelib/selftest.py:438` → `references/nope.md`（不存在）

## 口径

- 披露 = 正文里真实点到的另一份文档（先按该文件所在目录、再按 pack 根解析）；URL、围栏里的路径、没有目录部分的裸文件名都不算。
- caps（出处 `docs/contract.md` §4 · 只有 agentskills.io 与 Anthropic 两类来源）：`name` ≤64 字符 · `description` ≤1024 字符（agentskills.io，错误）；正文 建议 <5000 tok / <500 行 · `references/` 单文件 建议 <300 行（Anthropic，警告）。
- 每个文档在表里恰好出现一次（由命令自己核对：节点数 == 表行数）。
