# 拆（split）：把超限的正文下沉到 `references/`

**目标**：让 `SKILL.md` 回到「第一层薄入口」，细节按需读。

## 判据（先量，再动）

```bash
python3 "$SW" audit "$PACK" --out /tmp/sw
python3 "$SW" layers "$PACK" --out /tmp/sw
```

- 需要拆的信号：`est_tokens > 5000`，或行数落在 `loose`/`over-500` 档（50 / 150 / 500 三档口径见
  `docs/contract.md` §4），或 `counts.long_paragraphs / code_blocks` 明显偏高（它们就是「该拆」的可量信号）。
- 具体到哪几段：`tree` 里该 skill 的 `children` 是标题节点（带行号），挑**成块**的标题整段下沉。

## 怎么切（你的判断，边界要能一句话说清）

1. **按标题边界切，不要切段落中间**：一个二级/三级标题连同它的内容整段搬走。
2. **第一层必须留下**：这个 skill 什么时候用 · 它做什么 · 主流程的骨架 · 每个下沉文件**一行**转指。
3. **下沉顺序按「用到频率」倒序**：平台特例、错误排查表、长清单、示例代码先走；判据、边界、顺序留下。
4. **表与清单优先下沉**：它们占行数最多、但只在具体分支上才需要。
5. **一处只留一份**：条款若在两处出现，删掉重复的那份，别把同一规则换个标题再写一遍。

## 落盘（在副本上）

```bash
cp -R "$PACK" /tmp/pack-fix && cd /tmp/pack-fix        # 绝不在原 pack 上试
mkdir -p skills/<分类>/<skill>/references
#   把整段移进 references/<主题>.md，原位留一行：
#   - `references/<主题>.md` — <一句话说它承担什么>
```

## 改完怎么验（缺一条就不算做完）

```bash
python3 "$SW" layers /tmp/pack-fix --out /tmp/sw-fix    # 看该 skill：est_tokens/行数/token_budget 是否落到档内
python3 "$SW" tree   /tmp/pack-fix --out /tmp/sw-fix    # 看 orphans：新下沉的文件必须被 SKILL.md 点名（不能变孤儿）
python3 "$SW" audit  /tmp/pack-fix --out /tmp/sw-fix    # 看 size 段超限数是否下降；成本是否有对照
```

**前后对照表**：该 skill 的 `est_tokens`、行数、`orphans` 三个数（改前 → 改后）；全 pack 的
`size 超 5000 token` 条数与 `cost.resident/chars` 也要贴出来（拆会把内容从 L2 挪到 L3，
**常驻成本不该上升**）。

## 反例（会判不通过）

- 把整段删掉而不是搬走（内容消失，且 `references/` 里没有对应文件）。
- 搬走后原位不留转指（那就成了孤儿文件，`tree` 里会进 `orphans`）。
- 为了过 token 数把正文压成一句话（丢掉判据/错误串/具体数字）。
- 在第一层留「详见 references/」但不写文件名（转指必须带路径，能被 `tree` 解析到）。
