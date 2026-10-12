
---

# 追加 · 2026-10-13（三条待办全做）

## ① 同层抢题：`manage-logs` / `lab-vault-experiment-records` / `audit-log-protein-purification`

F 盲判唯一失手的 P15（「他做 OmcZ 纯化那次为什么和论文里的产率不一样」）暴露出：`manage-logs`
自己的 description 里就写着「asks why his own expression/purification result differs from a paper」，
但那条判别词落在 **57 字符常驻窗口之外**（judge 只读窗口），所以被兄弟 `lab-vault-experiment-records` 抢走。

三轮同一套固定题面（19 题，判官每次都是新起的独立子代理、只读 `judge-input.txt`）：

| 轮 | 改了什么 | 逐题结果（13 trigger / 4 near_confusion / 2 not_trigger） |
|---|---|---|
| R1 | 无（原始 description） | 13/13 · **3/4** · 2/2 —— P15 → `lab-vault-experiment-records`（错叶子） |
| R2 | 四条 description 划界，判别词仍被窗口切掉 | 13/13 · 3/4 · 2/2 —— P15 → `manage-lab-logs`（对岛、但落 L1 不是叶子） |
| R3 | 把「这次结果/产率为什么和论文对不上」整句压进 57 字符窗口 | **13/13 · 4/4 · 2/2** —— P15 → `manage-logs` ✅ |

R3 的分数是逐条把判官答案与金标对照得出的（13 + 4 + 2 全中）；工具输出的分组分只跑到 R2 为止。
另外两级口径都记一下：**「落在正确的 L1」在 R1/R2/R3 都是 19/19**（抢题发生在叶子层，不在岛层）。

改后的四条（每条都写清「不属于本 skill」的去向）：
`manage-logs`（读记录 + 引原文，窗口内含「与论文对不上」）·
`lab-vault-experiment-records`（只做跨库清单式汇总 + 往 `Records/Logs` 落新条目）·
`audit-log-protein-purification`（只审纯化记录合规性，只读）· L1 `manage-lab-logs`（写清三兄弟分工）。

## ② 旧包退役：`AgentSkill-LabProject` → 历史归档

- 删 `skills/`（29 个嵌套 skill 已全量迁入 LabProjectManagement）与 `TREE.md`/`TREE.html`
- 保留 `docs/`（5 份交接/评审/测试/待决件）与 `darwin-results.tsv`（按当时目录名记的 darwin 账本）
- README 换成去向说明 + 8 个 L1 对照表
- 仓库本体没删（git 历史只在 NAS 一份）；要彻底删是一句话的事
- commit `58b0c4e`（tailscale 已回读；`lab` 是 LAN，当前不在那个网络推不上）

## ③ 装库 / 部署 / 预设

| 验收项 | 结果 |
|---|---|
| 库记录 | 8/8 `source_type=git`，`source_ref` = NAS 裸库 URL，实际取件落在正确的 subpath（文件清单只含本 L1） |
| 部署 | 6 个 agent × 8 处软链，逐一 `os.path.islink` + `SKILL.md` 可读 ✅（与旧 `lab-project` 的覆盖面对等） |
| 预设 | `Lab Habit` skill_count = 8 |
| 内容对账 | 库副本 vs 仓库树：8/8 文件级一致（`manage-lab-logs` 28/28 含新落的 `strip-and-ledger.md`） |

**退役的旧安装**：`lab-project`（撤 6 处部署 + 删库记录）与独立 `register-a-protein-sample`
（撤 2 处部署 + 出 `Lab Habit` 预设 + 删库记录）—— 两者内容现在都由上面 8 个 L1 承担。
回读：库里剩 293 条、两者均无；`~/.hermes/skills/` 与各 profile 的旧符号链接全清。

## 并发说明

`LabProjectManagement` 的 `main` 期间被另一条会话推到 `3b46bb0`（`feat(audit-logs): 审 strip 过的文件…`），
它在我的 `75cbc7f` 之上，两条线没有冲突；我按 `3b46bb0` 重跑了一次 `skills update manage-lab-logs`
把库副本补齐。`SkillWeave` 主 clone 里另有别人的 `weavelib/*.py` WIP，本报告一律按路径提交，未触碰。
