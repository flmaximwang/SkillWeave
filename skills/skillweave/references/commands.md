# 命令参考（`weave.py`）

唯一实现只有一份（本 skill 自包含的入口脚本，见 `SKILL.md`）；仓库根另有一份同名转发脚本，只做 `runpy` 转发。

```bash
SW=<weave.py 的绝对路径>        # 装好后：<skills 目录>/skillweave/scripts/weave.py
PACK=<要分析的 pack 目录>       # 一个含 1..N 个 skill 的仓库或目录
```

**默认落点**：`tree` / `layers` / `checks` / `audit` / `propose` / `disclosure` / `prepare` /
`collapse` / `judge` / `deliver` 的 `--out` 缺省值一律 `<pack>/.skillweave/`（随包 commit，不丢）；
`--out` 可覆盖。`visualize` 是例外 —— 它默认落回 **pack 根**（产物是给仓库看的）。

一个命令的退出码约定：正常 0；`checks` 命中安全/可移植闸退 1；`visualize` 遇到未跟踪的
`SKILL.md` 退 1；参数缺失按 CLI 错误码 2 退。

---

## tree

```bash
python3 "$SW" tree "$PACK"
```

文档树：`pack → 类目 → skill → 章节/文件`。产物 `tree.json` + `TREE.md`，是**按目录层级**的视图
（与 `disclosure` 的按披露深度视图互补）。`tree.json` 里每个 skill 节点带 `children`（标题节点、带行号），
挑「该拆哪几段」就靠它。

## layers

```bash
python3 "$SW" layers "$PACK"
```

老口径的**三级披露**汇总：L1 = 常驻菜单（所有 skill 的 name+description）· L2 = 每个 skill 的
`SKILL.md` 正文（触发时载入）· L3 = `references/` / `scripts/` / `assets/`（按需）。报 L1 入口层条目数、
常驻 token、L2 超限数、L3 文件与 `orphans` / `broken`。产物 `layers.json` + `LAYERS.md`。

新口径（层 = 披露深度）请用 `disclosure`；`layers` 保留作「常驻成本 / 正文规模 / 孤儿悬空」的对照。

## checks

```bash
python3 "$SW" checks "$PACK"
```

内化检查（skill-tools 口径）：引用存在 / token 预算 / BOM / 二进制 / `name`-目录一致 / 硬编码路径 /
内嵌密钥。**先跑它**：命中的硬编码路径或密钥是安全与可移植问题，先解决再谈结构。

**闸** = `embedded_secret` + `hardcoded_path` 两条，命中即退 1。产物 `checks.json`。
函数注释里写「六条」而列表是七项 —— 按实际打印的项为准。

## audit

```bash
python3 "$SW" audit "$PACK"
python3 "$SW" audit "$PACK" --top 30      # dup 段显示前 N 对（默认 20）
```

审计四段：

- **size**：每个 skill 正文体积 vs 建议值（token / 行数）。
- **orphan**：孤儿（到不了根）与悬空引用的清单。
- **dup**：候选「抢题」对，两个口径都算（**同父目录** + 单入口形状下的**岛×岛**），带非字面信号。
- **cost**：常驻（L1 菜单）+ L2 全体/中位 + L3 文件/字节。

产物 `audit.json`。

## propose

```bash
python3 "$SW" propose "$PACK"                                   # 默认 dry-run，不改盘
python3 "$SW" propose "$PACK" --apply --apply-group /tmp/map.json   # 只执行机械那部分
```

四类动作（拆 / 分 / 并 / 改写）的提案。每条提案带 `文件:行` + diff 形状 + 是否 `auto_applyable`；
`needs_model=True` 的那些**必须你来判断**。产物 `proposals.json` + `PROPOSALS.md`。

## judge

```bash
python3 "$SW" judge "$PACK" --prompts 题面.json [--trunc 57]
```

生成**一个纯文本判官输入** `judge-input.txt`（候选只有 description 的截断窗口）+ 独立金标
`judge-key.json` + 任务书。判官只读 `judge-input.txt`；金标永远不进它（命令自带泄漏断言）。
`--trunc` 默认 57 字符（`description` 窗口宽度）。

## score

```bash
python3 "$SW" score --key judge-key.json --judge 判官输出.txt [判官输出2.txt …]
```

吃「判官输出 + 金标」，出逐题矩阵、按题型分组，并给**校正随机分（BoR）**。产物 `score.json`。
只有 1 个候选时随机基线无意义，`chance` / `bor` 记 `null`。

## visualize

```bash
python3 "$SW" visualize "$PACK"        # 默认落 pack 根
```

生成两份产物：`TREE.md`（L1 菜单 → L2 正文 → L3 按需，逐 skill 数字）与 `TREE.html`
（自包含、离线可开；互指图画成圆环 + 弦，节点带编号 + 框内图例）。**两份都是生成物，不要手改。**

- 互指图的边 = 「某个 skill 的任何文本文件里点到另一个 skill 的**目录名**」；岛 = 该图的连通分量。
- 节点 = **每份文档**（`SKILL.md`、`references/*.md`、`scripts/*.py` 各算一份），不是每个 `SKILL.md`。
- **验收判据**：`TREE.html` 里 `rect.node` 的个数 == 本 pack 的文档数（= `DISCLOSURE.md` 的表行数）。
- **护栏**：工作区里存在**未被 git 跟踪**的 `SKILL.md` 时报错退出（退 1），提示先 commit ——
  `collapse` 刚改完还没 commit 时索引里是旧路径，新入口会被当 untracked 跳过、静默出一棵空树。

## collapse

```bash
python3 "$SW" collapse "$PACK"                                   # dry-run：只出账 + 伞体 + git mv 清单
python3 "$SW" collapse "$PACK" --apply --entry-dir using-hermes \
        --description "…"                                        # 真塌：搬目录 + 写伞体与各岛 INDEX.md
```

**可选**的第二种形状（默认不做）：把 pack 塌成「L1 = 1 个 skill 入口」。

- 分工：搬目录、生成伞体与各岛 `INDEX.md` 是机械动作，工具做；**那一条 `description` 必须你写** ——
  它是唯一的常驻触发词、是判断题，所以 `--apply` 不给 `--description` 会**直接拒绝**（不生成半成品）。
- 落盘后回读三件事并一起判：顶层技能数 == 1 · 入口层 == 1 · `frontmatter_selfcheck` 无错且
  `description` 回读一致。
- **构造性假象**：塌完 `孤儿`/`悬空` 会归零 —— 伞体按目录点名了每个 `references/<岛>/`，
  目录级点名把里面全盖住了；不是问题被修好，是这条指标失去分辨力。
- **岛数对口径敏感**（同一份数据 11 / 10 / 13），报岛数必须连口径一起报。
- 塌完**必须 commit 再跑 `visualize`**（否则被护栏拦下）。

## prepare

```bash
python3 "$SW" prepare "$PACK" --dest /tmp/pw/ws
python3 "$SW" prepare "$PACK" --dest /tmp/pw/ws --shape single --executor=opencode
```

**第一步**（可当整条流程的入口）：`cp -Rc` 拷一份副本 → **在副本里确保由 git 管**（拷贝的是仓库就
摘掉所有 remote —— 误推当场失败 —— 再把当前状态提交成起点；输入没有 git 就 `git init` + 一行
`.gitignore` + 初始 commit）→ 量副本、推导 L1（互指岛的岛）→ 出 `BASELINE.md`：副本路径与 rev、
推导的 L1、**单入口/多入口两种形状同口径的账**、以及待用户选定的形状。

- **原目录只读、绝不碰**；形状没定之前不动副本里任何文件。
- `--shape single|multi` 记下用户的选择（形状是**启动参数**，在准备之前就定）。
- `--executor opencode|claude-code|subagent|manual` 记下执行者（非交互指定；不填则在交互终端询问），
  供 `dispatch` 在每个 `batch-N.prompt.md` 末尾追加执行说明。

## disclosure

```bash
python3 "$SW" disclosure "$PACK"
```

**第二步**：层 = **披露深度**（L1 = 根文档 `SKILL.md`；L2 = L1 直接披露的；Lₙ₊₁ 由 Lₙ 披露），
不是「按文件类型分三级」那套。它把每个根文档的披露链递归展开（深度 / fanout / 体积），并对
**每一份文档**跑它那类 cap，跨文档查孤儿（没人披露）、悬空（披露了不存在的）、根选择层近重复。

产物三份：

- `DISCLOSURE.md` —— 体检表，自带术语表 + 根选择层单列；
- `disclosure.json` —— 机器版；
- `TODO.md` —— **照着做的待办清单**：每条 = 文档 · 问题 · 数字 · 建议动作 · 谁判；
  悬空按文件聚合成一行。

命令行自检「表行数 == 节点数」（每个文档恰好出现一次）。

## dispatch

```bash
python3 "$SW" dispatch "$PACK" [--batch-size 25] [--refresh-baseline]
```

派发前**事实补全** + 划批（单位 = skill 子树，批次间文件集合两两不相交）+ 落 prompt + 计数起点。
事实补全把能从树里查到的先算好（悬空 → 包内同名候选；到不了根 → 同目录被披露过的兄弟；
超限 → 行数 + 二级标题清单），让子代理「验路径」而不是「猜路径」。

产物落在 `<pack>/dispatch/`：`plan.json`（批次/条目/`prompt_sha256`）· `state.json`
（`attempts` 计数 + 重派历史）· `baseline.json`（**冻在 pack 里**的基线）· `batch-N.prompt.md`
（生成物，不入库）。

**重派守卫**：`attempts` 重派时继承（不许清零）；某批已有尝试且 `prompt_sha256` 未变 →
**拒绝派发（退 3）** —— 相同输入 = 相同输出，要重派必须按梯子换输入。

## verify

```bash
python3 "$SW" verify "$PACK" --state dispatch/state.json --expect-fixed <id…>
```

**复测（闸）**，四类判据：① 该消的消了（`--expect-fixed` 的 id 重扫后必须消失）；② 无新增
（集合级 diff，新出现的发现一律算回归）；③ `external` 集合不变；④ 拆分守恒（字符序列守恒 +
每个新文件都被披露）。产物：新树 + `RUN.md`（每批过了没 / 哪条判据拦的 / 下一级是什么）+
`PARKED.md`（走完梯子仍不过的）。

失败**不回滚整批**：通过的条目保留，未通过的条目改输入后回 `apply` 继续修。

## apply

```bash
python3 "$SW" apply "$PACK" --proposals 提案.json [提案2.json …]
python3 "$SW" apply "$PACK" --revert <条目 id>
```

逐条校验并落盘：锚点在该行 ±3 内逐字相同、改动只落在「本条目自己的文件 + 披露它的父文档 +
该 skill 的入口 `SKILL.md`」、拆分前后内容守恒、豁免规则只命中本条目自己的文件；
`obsolete` 不自动通过，落 `PARKED.md`。每落一条都写进 `dispatch/patches.json`，
所以回退粒度是单条。

## deliver

```bash
python3 "$SW" deliver "$PACK"                    # 默认动作：交付
python3 "$SW" deliver "$PACK" --dry-run          # 只看要做什么，不动盘
python3 "$SW" deliver "$PACK" --keep-worktree    # 想留在副本上继续改：显式说，别默认
```

**最后一步（默认动作）**：合回真包 `main` + push 各 remote 并**回读**（`ls-remote` 确认远端就是那个
commit）+ 重跑 `visualize` + 清 worktree/分支。一步做完，**不需要额外一句「进入 production 模式」**。

**四道闸不过即停**：主 clone 工作区干净且 checkout 在 `--main`（默认 `main`）上；副本工作区干净；
`--ff-only`（不 ff 先在副本里 rebase 到 main，冲突即 abort 且真包未动）；不 `--force`。
要停在副本上，得用 `--keep-worktree` / `--no-push` 显式说。
