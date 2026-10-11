# 文档树能推出什么关系：39 个 skill 的互指图

基准：`AgentSkill-UsingHermes` @ `0de1ca9`（清理后 · 39 skill · 入口层 28 项 · 常驻 3,310 tok）
脚本：`~/.hermes/cache/scratch/skillweave-graph{,-2}.py`（一次性分析，不进主路径）
原始边：`graph.json`（本目录）

## 1 方法

不看名字猜，只看两处机械证据：

- **证据 A（硬）**：某个 skill 的任何文件（`SKILL.md` + `references/**`）里**提到**另一个 skill 的目录名（`(?<![\w-])<slug>(?![\w-])`）。这是一个"谁指到谁"的有向图。
- **证据 B（弱）**：`name + description` 的分词 Jaccard 相似度，用来在 A 没连上时补边。

## 2 结果：13 个互指岛

| 岛 | 成员数 | 内容 |
|---|---|---|
| 1 | **21** | 主干（见 §3） |
| 2 | 4 | `hermes-profile-housekeeping` · `hermes-projects` · `hermes-skill-card-maintenance` · `session-librarian` |
| 3 | 3 | `hermes-mcp-server-integration` · `hermes-skills-management` · `hermes-source-hotfix` |
| 4 | 2 | `hermes-community-extensions` · `hermes-profile-authoring` |
| 5–13 | 各 1 | `dispatch-work-to-another-profile` · `gateway-session-list` · `hermes-browser-lane-repair` · `hermes-desktop-plugins` · `hermes-profile-configuration` · `hermes-pycache-cleanup` · `hermes-themes` · `kimi-moonshot-brotli-fix` · `maintain-hermes-node` |

**证据 B 补边数 = 0**：39 条 description 的两两 Jaccard **最大只有 0.12**（`hermes-desktop-plugins ↔ diagnose-a-failed-hermes-update`）。也就是说**词面数据完全不支持任何"该分几组"的结论**——描述写得足够互斥。

## 3 主干 21 个内部：确实有枢纽

被最多别的 skill 点到（入度）：

```
10  install-hermes-skills        9  maintain-hermes-gateway       9  maintain-hermes-skills
 8  update-hermes-skills         8  remove-hermes-skills         5  hermes-session-routing-forensics
 5  recruit-learning-in-profile  5  maintain-hermes-profile      4  maintain-hermes-desktop-app
 4  recruit-learning-in-session  4  maintain-hermes-memory       3  install-a-hermes-plugin
```

指向最多别的 skill（出度）：`diagnose-a-failed-hermes-update`(11) · `maintain-hermes-profile`(9) · `recruit-learning-in-*`(9/9) · `maintain-hermes-skills`(8)。

→ 你包里真有一条**主链**：`install → maintain → update → remove`（skills 生命周期），旁挂 plugin 两件套、profile 系、gateway 系。这不是我分的类，是正文自己指出来的。

## 4 数据真正说该改的地方

1. **9 个完全孤立**（没人指它、它也不指人）。同题却没互指的例子：
   - `hermes-desktop-plugins`（写桌面插件）vs `install-/remove-a-hermes-plugin`（装/删插件）——同题，0 条互指。
   - `hermes-themes`、`hermes-profile-configuration`、`hermes-profile-authoring`、`hermes-profile-housekeeping`、`hermes-projects` 与 `maintain-hermes-profile*` 家族——同题，各自孤岛。
2. **一对描述逐字雷同**：`hermes-skill-card-maintenance` 与 `maintain-hermes-skill-cards` —— description 都是 "Use when a hub-installed skill shows 2 cards or Hub. Also for a card with a grey, ON, unclickable switch over…"（待合并，见请求 2）。
3. **三件套重叠**：`hermes-skills-management`（"Install, place, and troubleshoot Hermes skills"）与 `install-hermes-skills` / `maintain-hermes-skills` 同题不同岛。

## 5 「顶层到底有几个端点」

- **严格按互指（硬证据）**：**13 个**。
- **把孤立项按同题归位（我的判断，非数据结论）**：**9 个**——① skill 生命周期（install/update/remove/maintain + plugin×2 + skill-cards×2 + skills-management + load-external-skill-index）② profile 与配置（maintain-hermes-profile/-profiles/-profile-skill-parity + profile-{authoring,configuration,housekeeping} + hermes-projects + dispatch）③ gateway 与运行时（maintain-hermes-gateway + gateway-session-list + session-routing-forensics + browser-lane-repair + maintain-hermes-node）④ 定时常驻（cron + heartbeat）⑤ 记忆与学习（maintain-hermes-memory + recruit×2 + session-librarian）⑥ 桌面与外观（desktop-app + desktop-plugins + themes）⑦ 扩展与 MCP（community-extensions + mcp-server-integration）⑧ 模型（models）⑨ 源码级修（source-hotfix + pycache-cleanup + kimi-fix + diagnose-a-failed-update）
- **1 个**：要付 §（前面的 A 方案）里那三条代价。

**结论**：端点数不是数据事实，是切法。数据只证明两件事——存在一个 21 个的主干岛，以及 9 个没接进树的孤立项。任何 2–13 之间的数字都需要人拍板。

## 6 附：这一步没做的事

改互指只让"树长出来"，**不减入口层条目数**（入口层 28 来自文件目录，不是链接）。要减条目只能分组或合并。
