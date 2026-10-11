# 第 1 轮 → 第 2 轮：同题面、同金标、只改了结构

**口径**：14 道题面**逐字相同**（`prompts-r1.json` / `prompts-r2.json`），2 个独立判官，候选只有各技能
`description` 的前 57 字符。两轮的判官输出都用**同一份金标** `round2/judge-key.json` 打分
（r2 相对 r1 只做了一处**语义标注**更正：P10 原本是诱饵题、合并后 `tushare` 就是正确答案；
**题面一字未动、判官 picks 一字未动**），所以这是可比的对照。

**改动**：`skills/research/tushare` 与 `skills/research/tushare-data` 判定为真重复 → 保留 `tushare`、
取 v1.1.16 的内容、删 `tushare-data`（副本 `/tmp/pack-fix`，原仓库未动）。

| 分组 | 第 1 轮（126 候选） | 第 2 轮（125 候选） |
|---|---|---|
| `should_trigger` | 15/16 · acc 0.938 · BoR 0.937 | **16/16 · acc 1.0 · BoR 1.0** |
| `should_not_trigger` | 4/4 · acc 1.0 · BoR 1.0 | 4/4 · acc 1.0 · BoR 1.0 |
| `near_confusion` | 6/8 · acc 0.75 · BoR 0.748 | **8/8 · acc 1.0 · BoR 1.0** |

**结构指标同步对照**

| 指标 | 改前 | 改后 |
|---|---|---|
| 技能数 | 126 | 125 |
| `dup` top 相似度 | **1.00**（tushare ↔ tushare-data） | 0.81（那一对已消失） |
| 同层相似度 >0.5 的对数 | 12 | 11 |
| L1 常驻成本 | 21,302 字符 ≈ 6,694 token | 21,137 字符 ≈ **6,548 token** |
| 孤儿 / 悬空 | 106 / 45 | 103 / 45 |

**结论**：3 处错误全部来自那个 1.00 相似对；合并后**同一批题面、同一批判官口径下全部分组 1.0**，
其余题没有退化。这是「结构度量 → 独立盲判 → 收敛 → 再测」这条闭环第一次走完的实测记录。

**留档**：`round1/judge-{A,B}.txt`、`round2/judge-{A,B}.txt`（判官输出是原件，一个字未改）、
`round2/score/before|after/score.json`。
