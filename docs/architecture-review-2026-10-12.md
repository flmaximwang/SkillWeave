# weave.py 架构优化（improve-codebase-architecture · 2026-10-12）

## 现状实测（探针输出，非印象）

- **3452 行 / 1 个文件 / 91 个顶层函数 / 15 个子命令**。中位函数 17 行，最长的 `self_test` 453 行。
- **文件是按时间顺序堆的，不是按结构**：`main()` 在 L1182（文件中腰），`cmd_deliver` 在 L3011，
  `self_test` 在 L3001。→ **23 处前向引用**（先调用、后定义）。
- **8 个命令各自重复同一段「装包」样板**（`walk_dir` + 空判 + `skipped`）：
  L616 `cmd_layers` · L779 `cmd_checks` · L804 `cmd_audit` · L1101 `cmd_judge` ·
  L1718 `cmd_visualize` · L2596 `cmd_disclosure` · L2914 `cmd_collapse`（另 `propose_actions` L889、`cmd_prepare` L2820）。
- `walk_dir(root, root, …)` 出现 **14 次**；`print("[X] FAIL 这个目录里没有任何 skill")` **8 次**；
  `os.makedirs(out)` **13 次**。
- **这个重复就是 issue #1 的现场**：`cmd_audit` 少了 `or not skills` 那半句 → 无 SKILL.md 的目录直接
  IndexError（312 个目录里 246 个命中）。同一个 bug 的变体只可能出现在「每个调用点各写一遍」的代码里。
- 死代码：`APPLY_FAILS`（L2149 定义，全文只出现 1 次）+ `lines_of` 未被调用。
- 真环只有 2 个：`walk_dir <-> _walk_children`（正常相互递归）、`main <-> self_test`（测试调 CLI）。

## 硬约束（决定方案形状）

1. **入口路径动不了**：`skills/skillweave/scripts/weave.py` 是 skills-manager 的入口，仓库根
   `scripts/weave.py` 是 `runpy` 转发器指向它，README/`SKILL.md`/`docs/flow.md` 全按这个路径写。
   **更正（2026-10-12 晚）**：我第一次写的是「部署单元只有这一个文件」——**查错了**。实测
   `skills-manager.db` 里 `source_subpath=skills/skillweave`、每个 target 都是 symlink，
   部署单元是**整个 `skills/skillweave/` 子树**（6 个文件，含 `references/`）。所以包**可以拆**，
   只要入口路径不变。
2. **契约 §6：不引外部依赖**，只用 stdlib + git。
3. 交付判据：**`--self-test` 全过** + 312 个 pack × 7 命令无 traceback。

## 方案（三级，按「删 > 合并 > 移」排序）

### ① `Pack` façade —— 一个深模块吃掉 8 份重复（主菜）
把「给定目录 → 量出一份 pack 事实」收进一个类：`root / tracked / tree / skills / skipped`，
外加 `islands()` / `edges()` / `entry()` 这些按需算的派生量。
8 个命令的前导从 6 行样板缩成 1 行 `pack = Pack.load(root)`，空判只写一次。
**删掉那个重复，就删掉了 issue #1 那一类 bug 的温床。**

### ② 按结构重排章节 —— 干掉 23 处前向引用
顺序改成：常量 → 基础工具 → YAML → 模型（walk/analyze/skills_root）→ 渲染 → 命令 → `main`/`self_test`。
纯移动，不改逻辑，diff 里全是移动。

### ③ 删死代码
`APPLY_FAILS`、`lines_of`。

## 不做（写清理由，防止后人再提）

- **不引入测试框架**：契约 §6 禁依赖；`--self-test` 已是唯一测试面。
- **不做「章节重排」这种纯移动**：拆包已按依赖 DAG 落地了模块边界，前向引用问题从结构上消失，
  再单独做一次 3452 行的纯移动没有额外收益。

## 2026-10-12 落地记录

**实际重复是 9 处不是 8 处** —— 探针第一次跑时 `cmd_tree` 的内联样板（写在 `main()` 里）被漏数了，
随后发现 `cmd_deliver`（L3011）也没进首轮名单。教训：按「装包样板出现次数」这类机械判据来核对，
别按函数名单肉眼数。

### 做了

| 项 | 内容 |
|---|---|
| ① façade | `class Pack`：`load()` 给出 `root/tree/skills/skipped/tracked`；派生量 `edges/islands/entry/by_id/resident_tokens/nested_skill_nodes/top` 惰性 + 缓存。10 处调用点各缩成 1 行 `Pack.load(root)`，空判只写一次 |
| ② 删死代码 | `APPLY_FAILS`、`lines_of` |
| ③ 架构回归断言 | `--self-test` 数全文装包样板：只许 2 处（`Pack.load` 自己 + `cmd_collapse` 落盘后的重读），第 3 处就红 |

**`cmd_collapse` 的 edges/islands 是特例**：它必须用**顶层** skill 算，不能用 `Pack.edges()`
（那是「全部 skill」口径）—— 否则重跑会把已收进 `references/` 的嵌套 skill 再搬一层，
正是它 docstring 警告过的行为。已就地注释说明。

### 等价性验证

`/tmp/weave_before.py` = 修复提交 `277d825`（重构前）。两份各跑同一批 pack × 7 命令，
比对退出码 + stdout（归一化临时路径/rev/日期）+ 产物 sha256：
- 定向样本（`UsingHermes` 47 skill / `UsingGit` 18 skill / 单入口 / flat / 空目录）：**35 runs，0 差异**
- 40 个随机 pack：见 `/tmp/widesweep.log`

### 312 个 pack 里 247 个是「空 pack」—— 这是**行为变更**，不是回归

312 个 pack 里 **247 个一份 `SKILL.md` 都没有**（只有 `skills/<pkg>/` 骨架或 `.gitignore`）。
等价性扫描第一版把它们全标成差异，看着像重构打碎了 247 个命令 —— 逐个查完，结论相反：

| | 重构前 | 重构后 |
|---|---|---|
| 空 pack | `exit=0`，产出一份 `tree.json`（节点是 `.gitignore` / 空 `skills/` 骨架，`skills=0`）+ `PROPOSALS.md` | `exit=1` + `FAIL 这个目录里没有任何 skill`，不产产物 |

**旧行为是错的**：它拿目录骨架冒充 skill 树、产出一份看着合法的空报告。65 个真 pack 的行为一个字节没变。
唯一算「修 bug」的是 `propose`：它以前会打印一条 `none … 这个目录里没有任何 skill`，读起来像一条合法提案。
现在与其余 8 个命令一致 FAIL。

### 第二轮（同日晚）：真的把单文件拆了

用户否决了「不拆」。复核后发现自己**记错了约束**（见上文「更正」）——部署单元是整个
`skillweave/` 子树，不是单个 `weave.py`。于是拆了。

**拆法**（机械搬运，不手抄 3650 行）：
- 用 AST 取每个顶层 def/常量 + 其前注释，按**依赖 DAG 的分层**分配 —— 不按原章节注释，
  因为那些章节互相引用（可视化 ↔ 三级披露 ↔ 披露链递归），不是干净的模块边界。
- 常量自动落到「使用它的最低层模块」（第一次手工放错 `TEXT_LIKE`/`ACTION`/`LADDER`，
  正好制造了 3 条回边 → 环；改自动放置后全消）。
- `scripts/weave.py` 变薄壳（`sys.path` 插自己所在目录 + `from weavelib.cli import main`），
  **入口路径与用法完全不变**，根转发器 `runpy` 照旧可用。
- 12 个模块构成一条 **DAG，无环**；唯一的历史环 `cli ↔ selftest` 用**延迟导入**打破
  （正常跑不再加载 508 行的自检模块）。

产物：

| 模块 | 行 | 职责 |
|---|---|---|
| `common` | 207 | 读文件 / token / 摘要 / 文本解析 + 全局常量 |
| `frontmatter` | 146 | frontmatter 解析与安全写出（契约 §7.1） |
| `model` | 300 | 扫树、逐 skill 分析（树的形状与成员） |
| `pack` | 85 | `Pack` 门面 |
| `graph` | 463 | 互指边 / 互指岛 / 披露链（文档图） |
| `render` | 522 | TREE.md/html · LAYERS · DISCLOSURE · TODO |
| `analysis` | 354 | layers / checks / audit / judge / score |
| `transform` | 644 | propose / apply / collapse / prepare |
| `deliver` | 189 | worktree → 合回真包 main → push → 回读 |
| `disclosure` | 397 | disclosure / dispatch / verify |
| `cli` | 167 | CLI 入口与派发 |
| `selftest` | 508 | `--self-test` 的全部断言 |

**验证**：`--self-test` 全过（薄壳入口 + 根转发器两条都试）；12 个模块逐一独立 import 通过；
定向 5 pack × 7 命令 = **35 runs，0 差异**；40 随机 pack × 7 命令 = **280 runs，
非空 pack 0 差异**（空 pack 的 `exit 0→1` 是上面记的行为变更）。

**架构回归断言同时升级**：原断言只扫单文件，拆包后改成扫 `weavelib/*.py` + 入口 `weave.py` 全包，
装包样板仍只许 2 处。
