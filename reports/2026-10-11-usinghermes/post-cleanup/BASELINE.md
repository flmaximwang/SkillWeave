# 清理后新基线（post-cleanup）

**被测**：`AgentSkill-UsingHermes` @ **`a7dd123`**（除杂完成后）
**怎么测的**：`git worktree add -b skillweave/cleanup-audit ~/Documents/AgentSkill-wt/AgentSkill-UsingHermes-skillweave HEAD`
—— 全部测量与改动都在这个 worktree 里做，**主 clone 一直没动**（按你的规矩：worktree 里不切 main，改动在这里 commit，回主 clone 再 merge）。
**产物**：本目录 `tree.json` / `layers.json` / `audit.json` / `checks.json` / `proposals.json` + `PROPOSALS.md`

## 1. 除杂本身的效果（对比上一版基线 `b8298f4`）

| 指标 | 除杂前 | 除杂后 | 变化 |
|---|---|---|---|
| 技能数 | 125 | **39** | −86（迁走到各自落点包） |
| 入口层条目 | 68（散 51 + 类目 17） | **28（散 26 + 类目 2）** | **−40** |
| 常驻（L1 菜单） | 20,864 字符 ≈ 6,443 tok | **11,611 字符 ≈ 3,310 tok** | **−49%** |
| L2 超限 | 15 | 5 | −10 |
| 孤儿 / 悬空 | 104 / 46 | 26 / 31 | −78 / −15 |
| L3 文件 | 468 | 125 | −343 |
| `checks` 命中 | 116 | 88 | −28 |

**除杂是这次最大的一次结构优化**：光是「把不属于这个包的技能迁出去」，就把入口层从 68 砍到 28、常驻成本砍掉近一半。

## 2. 本次在 worktree 上做的改动：5 个超限 skill 的正文下沉

`propose` 出的 5 条 split 提案，逐条执行（每个都跑行守恒断言）：

| skill | 改前 | 改后 | 下沉 |
|---|---|---|---|
| `maintain-hermes-profile` | 17,134 tok / 874 行 | **4,928 tok / 287 行** | 10 个 reference / 557 行 |
| `autonomous-ai-agents/hermes-profile-housekeeping` | 9,925 tok / 542 行 | **4,380 tok / 253 行** | 5 个 / 272 行 |
| `maintain-hermes-gateway` | 8,317 tok / 504 行 | **4,340 tok / 291 行** | 6 个 / 189 行 |
| `install-hermes-skills` | 6,542 tok / 341 行 | **4,547 tok / 255 行** | 1 个 / 86 行 |
| `recruit-learning-in-session` | 5,843 tok / 279 行 | **4,056 tok / 183 行** | 2 个 / 82 行 |

- **全包 L2 超限 5 → 0**（最胖的现在是 `update-hermes-skills` 4,993 tok —— 贴着上限，7 tok 余量，**下次改动很可能再超**）
- 孤儿 26 → 26（新 reference 全部被正文点名，没变孤儿）
- 悬空 31 → **25**：这不是修好了 6 条，而是**沉下去的那些行不再被扫描**（工具只看 `SKILL.md` 的引用）—— 量测口径造成的下降，不是修复
- 每个 skill 的正文里都留了一行 `> 细节见 references/xxx.md` 转指；内容**逐行原样**搬走（行守恒：原非空行 == 正文 + 搬走 − 转指）

## 3. 没做的两件事，和为什么

**① L1 仍是 28 项 > 上限 20 —— 建议不动（此前挂着的 `T-004#B-004` 现在有答案了）**

你这次除杂把整包**拉平成 `skills/<name>/`**（散技能 26 + 只剩 2 个类目）。在这样一个「业主刚刚亲手拉平」的结构上再塞类目，是逆着你的动作走，而且会重新引入「类目命名要维护」的成本。
实测也支持不动：上一轮 24 项类目形态在盲判里并没有比分更细的形态差，而这轮 28 项 **r6 盲判 14/14**（见 `round6/`）。
→ 建议把 20 当**参考线**而不是硬闸（这个数来自 Dream 的 `MAX_FIRST_LAYER_SKILLS` 常量，不是 agentskills.io 规范要求）。

**② 8 对同层相似 >0.5 与 1 对疑似真重复：只报不改**

| 相似度 | 对 | 判断 |
|---|---|---|
| **疑似真重复** | `autonomous-ai-agents/hermes-skill-card-maintenance` ↔ `maintain-hermes-skill-cards` | 同一件事（hub 卡片异常）：前者 118 行/2 文件、描述只有一句；后者 142 行/3 文件、描述覆盖更多情形（灰开关、`Orphaned:` 行）。**删哪个是你的决定**（删技能比拆文件重） |
| 0.721 | `hermes-mcp-server-integration` ↔ `hermes-profile-configuration` | 不同任务（接 MCP vs 配 profile），只是描述骨架像 |
| 0.717 | `hermes-profile-authoring` ↔ `hermes-projects` | 不同任务（写 SOUL.md vs 改 Project 目录表） |
| 0.60–0.65 | 其余 5 对（都是 `hermes-*` profile 家族） | 同上：靠描述里的宾语区分，结构上没解决 |

改写触发词能压低这类混淆，但它改的是 **L1 唯一的信号**（路由全靠这一行），**要先给你看措辞**再动 —— 这 8 条已列成提案，等你点头。

## 4. 盲判（r6）：清理后 **14/14 全对**

题面是新出的 `../prompts-cleaned.json`（旧题面 11 条金标已被迁走，不能复用），**r6 起是新系列**，不与 r1–r5 混比。
判官 2 个，各 15 行（14 题 + DONE），输出原件在 `../round6/judge-{A,B}.txt`，打分 `../round6/score/score.json`。

| 分组 | 结果 | BoR |
|---|---|---|
| `should_trigger` | **7/7** | 1.0 |
| `should_not_trigger` | **3/3**（全 `none`） | 1.0 |
| `near_confusion` | **4/4** | 1.0 |

（39 候选时校正随机基线 chance = 0.0256）

**两个判官的失手原因说明，比分数更有用**：三题「不该触发」他们都干净地判 `none`，理由写得比候选表还准 ——
P9（从零**写** MCP server）被识别为「候选只覆盖往 Hermes 里**接** MCP」，P10（Chrome 闪退）被识别为
「候选的 browser 相关只讲 Hermes 浏览器通道故障」。四题近邻混淆也都点名了区分词：
`SOUL.md`（authoring）/ `renaming`（configuration）/ `cron`+投递目标（cron-jobs）/ `Gateway lifecycle — per-profile start/stop`（session-list）。

## 5. 合并与清理记录（worktree 收尾）

```
主 clone:  git checkout main → git merge --ff-only skillweave/cleanup-audit → git push origin main
           origin/main = 0de1ca9
移除:      AgentSkill-wt/AgentSkill-UsingHermes-skillweave  （分支 skillweave/cleanup-audit 已删）
           AgentSkill-wt/AgentSkill-UsingHermes-cheatsheet   （在 a7dd123、ahead=0，分支已删；要再开一条命令）
验证:      git worktree list → 只剩主 clone；git branch → 只剩 main；工作区 0 项
```

**顺带清了 AgentSkill-AgentEvolution 的 3 个陈旧 worktree**（别的会话留下的）：每条分支都 `ahead=0`
（无未合并提交）、工作区干净 —— 移除 worktree 后连 8 条已合并分支一起删（含 4 条 `backport-*`、`fix-scan`、
`merge-backports`、`auto-optimize/*`、`skillwt-pack-repo-rule`）。该包现在 `HEAD = origin/main = 7d9fff3`、工作区干净。

## 6. 这一轮的可复现命令

```bash
git -C ~/Documents/AgentSkill/AgentSkill-UsingHermes worktree add \
  -b skillweave/cleanup-audit ~/Documents/AgentSkill-wt/AgentSkill-UsingHermes-skillweave HEAD
SW=~/Repositories/Repo/SkillWeave/skills/skillweave/scripts/weave.py
WT=~/Documents/AgentSkill-wt/AgentSkill-UsingHermes-skillweave
OUT=~/Repositories/Repo/SkillWeave/reports/2026-10-11-usinghermes/post-cleanup
python3 "$SW" tree "$WT" --out $OUT && python3 "$SW" layers "$WT" --out $OUT
python3 "$SW" audit "$WT" --out $OUT && python3 "$SW" checks "$WT" --out $OUT
python3 "$SW" propose "$WT" --out $OUT            # dry-run，不改盘
```
