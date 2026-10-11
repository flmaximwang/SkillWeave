# 独立复核报告：UsingHermes 审计报告（round4）

**复核者**：独立子代理（只读；未改动 pack / 报告 / 工具 / 判据）
**复核对象**：`reports/2026-10-11-usinghermes/report-usinghermes.md`（§11 复现清单 8 条）
**被测 pack**：`~/Documents/AgentSkill/AgentSkill-UsingHermes` 的**只读副本** `/tmp/verify-base`
**实际测的 commit**：`b8298f4d0a3c7004085c3f9ef9a0ab6fc6b9ad9a`
（与报告 §11#1 声明的 `b8298f4…` **完全一致**；上游未推进，本次不存在「数字因上游变化」的干扰）
**工具**：`scripts/weave.py`（复核时未改动）。**输出目录**：`/tmp/verify-out`（不覆盖报告自带产物）

> 报告自带产物 `baseline-current/base-rev.txt` = `b8298f4d0a3c7004085c3f9ef9a0ab6fc6b9ad9a`，与 HEAD 一致。
> 逐条命令均前台执行，用 `perl -e 'alarm N; exec @ARGV'` 做 ≤500s 硬超时；未起任何后台进程。

---

## 一、§11 复现清单 8 条逐项核对

| # | 报告写的 | 我实测的 | ✓/✗ | 证据（命令+输出片段） |
|---|---|---|---|---|
| 1 | `git rev-parse HEAD` → `b8298f4…` | `b8298f4d0a3c7004085c3f9ef9a0ab6fc6b9ad9a` | ✓ | `git -C /tmp/verify-base rev-parse HEAD` → `b8298f4d0a3c7004085c3f9ef9a0ab6fc6b9ad9a` |
| 2 | `tree` → `skills=125` · 最大 fanout `68` | `skills=125` · 最大 fanout `68` | ✓ | `python3 scripts/weave.py tree /tmp/verify-base --out /tmp/verify-out` → `[tree] skills=125 nodes=1925 bytes=1470082 est_tokens=385991` / `[tree] 层（fanout>1）= 14 个；最大 fanout=68`；另 `len(skills/ 节点 children)=68` |
| 3 | `layers` → 入口层 68（散 51 + 类目 17）· 常驻 ≈6443 token · L2 超限 16 | 入口层 68（散 51 + 类目 17）· 常驻 6443 token · L2 超限 16 | ✓ | `[layers] L1 技能=125 · 入口层 \`skills/\` 摆出 68 项（散技能 51 + 类目 17）· 常驻 20864 字符 ≈ 6443 token · ❌ 超上限 20` / `L2 正文超限=16 个`；`layers.json` → `first_layer_entries:68 loose:51 categories:17 resident_chars:20864 resident_est_tokens:6443`，`over_limit len=16 / over_token len=14` |
| 4 | `audit` → 孤儿 104 · 悬空 46 · >0.5 对 12 · top 1.00 是 tushare 那对 | 孤儿 104 · 悬空 46 · >0.5 对 12 · top 1.00 = tushare ↔ tushare-data | ✓ | `[audit] orphan  孤儿 104 · 悬空 46` / `dup  同层比较 1621 对（同层），相似度>0.5 的 12 对；top: 1.00 desc=1.00 | skills/research/tushare/ ↔ skills/research/tushare-data/` |
| 5 | `checks` → `❌ 命中 116`（exit 1）· checks.json 里 7 类键 | `❌ 命中 116`，exit code = 1；`hits` 下 7 类键 | ✓ | `[checks] 安全/可移植闸：❌ 命中 116`；`CHECKS_EXIT=1`；`json(checks.json)['hits'].keys()` = `['binary','bom','broken_refs','embedded_secret','hardcoded_path','name_mismatch','token_budget']`（7 个） |
| 6 | `propose` → 27 条（split14/rewrite11/merge1/group1）· dry-run | 27 条（split 14 · rewrite 11 · merge 1 · group 1）· dry-run | ✓ | 逐条计数：rewrite 11 行 + merge 1 + group 1 + split 14 = 27；`[propose] dry-run：盘上未改任何文件（加 --apply / --apply-group 才落盘）`；仅 `merge` 一条 `auto=True` |
| 7 | `--self-test` → 全过（含 layers↔audit 口径对拍） | 全过，exit 0 | ✓ | `[self-test] ✅ 层（pack→类目→skill）/ … / layers↔audit 口径对拍 —— 全过`；`SELFTEST_EXIT=0` |
| 8 | 两个数相等（14 14） | `14 14` | ✓ | `python3 -c "…print(len(l['L2']['over_token']), sum(1 for r in a['size'] if r['over_token']))"` → `14 14`；`CMD8_EXIT=0` |

**§11 八条：8/8 全部复现。**

---

## 二、报告其余数字的抽查（不在 §11，但同属报告断言）

| 报告写的 | 我实测的 | ✓/✗ |
|---|---|---|
| L2 最大三个：`accountancy-workflow` 21427tok/747行 · `research/research-paper-writing` 17832tok/1611行 · `maintain-hermes-profile` 17134tok/874行 | 完全一致（layers 输出逐字相同） | ✓ |
| L2 单口径 `over_token`=14，闸口径 `over_limit`=16 | `over_token`=14 · `over_limit`=16 | ✓ |
| L3 = 468 文件 / 6,862,852 B | `L3 文件=468`；`cost … L3 468 文件 / 6862852 B` | ✓ |
| 全体 L2 = 385,991 token（中位 2,282） | `L2 全体 385991 tok（中位 2282）` | ✓ |
| `description` 超 1024 字符的 **0** 个 | `layers.json:L1.over_1024_chars` 长度 = 0 | ✓ |
| `hardcoded_path` 分布：`maintain-hermes-skills` 32 · `autonomous-ai-agents` 17 · `maintain-hermes-node` 12 | 32 / 17 / 12（按 `skills/<层级>` 归组，总和 116） | ✓ |
| `checks.json` 7 类键 | `hits` 下 7 类键 | ✓ |
| checks「命中 116（全部是 hardcoded_path）」 | 工具源码 `gate = len(embedded_secret)+len(hardcoded_path)` = 0+116 = **116**；embedded_secret=0 | ✓ |
| 1.00 那对：`description` 逐字相同 · `references/数据接口.md` 逐字节相同 · `slug`/`version` 之差（1.1.12 vs 1.1.16） | desc 相同=True；`cmp references/数据接口.md` 两目录**完全相同**；`grep version` → `1.1.12` vs `1.1.16` | ✓ |
| §8 改后四数（`/tmp/pack-fix3` 存在，可直接验）：L1 24（散0+类目24）· 常驻 6298 · skills 124 · 孤儿 101 · 悬空 46 | `L1 技能=124 · 入口层 \`skills/\` 摆出 24 项（散技能 0 + 类目 24）· 常驻 20699 字符 ≈ 6298 token`；`orphan 孤儿 101 · 悬空 46` | ✓ |
| §8 改前（当前 HEAD）：L1 68 · 常驻 6443 · 孤儿 104 · 悬空 46 · `dup>0.5`=12 | `/tmp/base-now`（= b8298f4）→ 同上，一致 | ✓ |

### ✗ 不一致 1 — §4「引用分类」三个数不可复现

报告 §4 第 69 行写：

> 引用分类（全 pack）：`resolved` **241** · `external` **206** · `example` **267** · `broken` **46**

我对 `tree.json` 做**穷尽递归扫描**（收集所有节点 `refs[].kind`），**我的副本**与**报告自带产物** `baseline-current/tree.json` 得到**同一组数**：

```
EXHAUSTIVE tree refs:          {'external': 203, 'example': 255, 'resolved': 240, 'broken': 46}
EXHAUSTIVE baseline tree refs: {'external': 203, 'example': 255, 'resolved': 240, 'broken': 46}
```

- `broken` = 46 ✓（与报告一致）
- `resolved` = **240**（报告 241，+1）
- `external` = **203**（报告 206，+3）
- `example` = **255**（报告 267，+12）

即：**报告的 `broken` 对，但 `resolved/external/example` 三个数与它自己的产物 `baseline-current/tree.json` 都对不上**（也不是去重口径 —— 去重后是 227/130/179/38）。判定：**报告数字有误**（或来自一份未随报告落盘的旧工具版本），复现不出 241/206/267。

### ✗ 不一致 2 — §8「`dup` >0.5 对数 改后 = 11」不可复现（实测 13）

报告 §8 表：

| 指标 | 改前 | 改后 |
|---|---|---|
| `dup` >0.5 对数 | 12 | **11（那对 1.00 消失）** |

在 §8 的**同一件改后产物** `/tmp/pack-fix3` 上（该产物的其它四个数 24/6298/101/124 全部复现，见上表），实测：

```
[audit] dup  同层比较 553 对（同层），相似度>0.5 的 13 对
```

**>0.5 的对数从 12 变成 13（升了），不是 11。**

原因（我列出全部 >0.5 对核对）：1.00 的 `tushare ↔ tushare-data` 确实消失了，但**归入类目本身把 `accountancy/` 三条同族放进了同一层**，凭空多出 **2 对**：

```
0.58  skills/accountancy/boc-credit-statement/  <->  skills/accountancy/boc-statement/
0.57  skills/accountancy/boc-credit-statement/  <->  skills/accountancy/ccb-statement/
```

净效果 −1 +2 = +1。另注意「同层」基数也从 1621 对缩到 553 对（属另一口径变化，报告未提）。

报告括号里只写「那对 1.00 消失」，与「11」一样，像是把**只做合并、没做归位**时的中间态（12→11）填进了「两刀都做完」的列里 —— 与同表 L1=24（做完归位）的口径不一致。判定：**§8 该格数字有误**（改后应为 13）。

### ⚠ 不一致 3 — §8 与所引 `PROPOSER-ACCEPTANCE.md` 的「改前」口径互斥

| 来源 | 常驻「改前」 | 孤儿「改前」 |
|---|---|---|
| 报告 §8 | 6,443 token | 104 |
| `PROPOSER-ACCEPTANCE.md` §④ | 20,748 字符 ≈ **6,311** token | **101** |

两者**都不是笔误**：`PROPOSER-ACCEPTANCE` 明确标注它的数是跑在 15:46 取的**旧快照**（后被别的 agent 推进到 `b8298f4`），而报告 §8 的「改前」= `b8298f4`（我实测：`/tmp/base-now` 常驻 6443 / 孤儿 104，对得上）。所以是**同一张「改前」标签下挂了两份不同快照的数**，跨文档引用时会打架。判定：**文档一致性问题**（数字各自在其快照上成立，但报告 §8 引 `PROPOSER-ACCEPTANCE` 为出处时，两处「改前」不是同一个东西）。

---

## 三、未能复现的项（诚实标注）

- **§8 路由盲判分数表**（r1 0.938 / r2 1.0 / r3 1.0、near_confusion 0.75→1.0）：需要判官模型，非确定性，**未重跑**。仅核对到 `round1/2/3` 的 `judge-*.txt` 原件存在、`round3/COMPARISON-3ROUNDS.md` 的表格与报告 §8 逐格一致（r1 L1=69、r2/r3 =1.0）。
- §8「只做合并那一步」的中间态没有独立产物落盘（`/tmp/sw-fix3` 只有 proposals.json），故「12→11」既不能从产物验证、也不等于最终态 —— 见不一致 2。

---

## 四、结论：我同意 / 不同意报告

**同意的部分（主体）**：§11 复现清单 **8/8 全部逐字复现**，退出码（checks=1、其余=0）也全对。报告的核心事实性断言——入口层 68 项（散 51 + 类目 17）、最大 fanout 68、常驻 ≈6443 token、L2 超限 16（单口径 14）、L3 468 文件、孤儿 104、悬空 46、同层 1621 对/>0.5 12 对/top 1.00 tushare 对、checks 命中 116 且 exit 1、提案 27 条（14/11/1/1）、两处口径对拍 14=14——**在我的 `b8298f4` 副本上一一坐实**。报告的「入口层超载」「同层确有抢题」「两刀已实测」三句结论，有可重跑的产物支撑，我**同意**。

**不同意的部分（3 处）**：

1. **§4 引用分类 241/206/267 是错的**，实际 240/203/255（连报告自带的 tree.json 都不支持它）。这是**报告本身写错的数字**，不是上游推进所致 —— 需回到产生该行的块整改。
2. **§8「`dup`>0.5 改后=11」是错的**，在它自己的改后产物上是 **13**；归位反而多造了 2 对同层近重复（boc-credit ↔ boc / ccb），报告漏报了这个副作用。
3. **§8「改前」与所引 `PROPOSER-ACCEPTANCE.md` 的「改前」不是同一快照**（6443/104 vs 6311/101），跨文档引用会互相打脸，需注明各自基准。

未发现「因 pack 被上游从 `b8298f4` 推进而导致数字变化」的情况：我取到的 HEAD 与报告声明**一致**。

---

### 附：本次实际执行的关键命令（可照抄重跑）

```bash
rm -rf /tmp/verify-base && cp -R ~/Documents/AgentSkill/AgentSkill-UsingHermes /tmp/verify-base
git -C /tmp/verify-base rev-parse HEAD        # b8298f4d0a3c7004085c3f9ef9a0ab6fc6b9ad9a
OUT=/tmp/verify-out; mkdir -p $OUT
python3 scripts/weave.py tree    /tmp/verify-base --out $OUT
python3 scripts/weave.py layers  /tmp/verify-base --out $OUT
python3 scripts/weave.py audit   /tmp/verify-base --out $OUT
python3 scripts/weave.py checks  /tmp/verify-base --out $OUT   # exit 1
python3 scripts/weave.py propose /tmp/verify-base --out $OUT   # dry-run
python3 scripts/weave.py --self-test
python3 -c "import json;l=json.load(open('$OUT/layers.json'));a=json.load(open('$OUT/audit.json'));print(len(l['L2']['over_token']), sum(1 for r in a['size'] if r['over_token']))"  # 14 14
# 改后态（报告 §8）复核：/tmp/pack-fix3 仍在，直接跑
python3 scripts/weave.py layers /tmp/pack-fix3 --out /tmp/v-fix3   # 24 项 / 6298 tok / 124 skills
python3 scripts/weave.py audit  /tmp/pack-fix3 --out /tmp/v-fix3   # 孤儿 101 · dup>0.5 = 13
```
