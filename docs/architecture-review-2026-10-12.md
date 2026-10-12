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

1. **入口路径动不了**：可安装目录 `skillweave/scripts/weave.py` 是 `skills-manager` 的部署单元，
   仓库根 `scripts/weave.py` 是 `runpy` 转发器指向它、README/`SKILL.md`/`docs/flow.md` 全部按这个路径写。
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

- **不拆成多文件包**：会把部署单元从 1 个文件变成 N 个，且入口路径必须保持 `scripts/weave.py`
  （转发器 + 文档 + 安装器都钉死了它）—— 风险远大于收益。单文件 3452 行、有 7 个章节分隔、
  91 个函数，靠重排 + façade 已能把「一处概念要跳几个地方」这件事压下来。
- **不引入测试框架**：契约 §6 禁依赖；`--self-test` 已是唯一测试面。

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

### 做了什么决定，没做什么

- **没拆成多文件包**：部署单元会被 skills-manager 拆成 N 个文件，且入口路径钉死在 `scripts/weave.py`。
- **没做章节重排**（原计划 ②）：23 处前向引用是阅读顺序问题，收益比风险小；真要做，留作一次
  「只移动、不动逻辑」的独立提交。
