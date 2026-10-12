"""`Pack` 门面：一次装好一个 pack 的全部事实，派生量惰性算。

从 weave.py 拆出，逻辑未改。"""
import os
from .common import est_tokens
from .graph import cross_skill_edges, entry_items, islands_of, nested_skill_nodes
from .model import add_mentions, top_level_skills, tracked_set, walk_dir




class Pack:
    """**一个 pack 目录量出来的全部事实**，只装一次、处处复用。

    为什么是这一层：8 个命令（`layers` `checks` `audit` `propose` `judge` `visualize` `disclosure`
    `collapse`）各自重复同一段「`tracked_set` → `walk_dir` → 空判 → `skipped`」样板，而
    **`audit` 少写了空判的后半句 `or not skills`** 就 IndexError（312 个目录里 246 个命中，
    合约 https://github.com/flmaximwang/SkillWeave/issues/1）。一个 bug 的变体只可能长在
    「同一段逻辑抄了 8 遍」的地方 —— 收进一个类，这条路就封了。

    派生量（`edges` / `islands` / `entry` / `resident_tokens`）按需算并缓存：它们都要扫正文，
    不该在只想看 `skills` 的命令里白付一次。

    `load()` 返回 None = 这个目录里没有任何 skill（不是 pack），调用方照旧 `return 1`。
    """

    def __init__(self, root, tree, skills, skipped, tracked):
        self.root = root
        self.tree = tree
        self.skills = skills
        self.skipped = skipped            # 未跟踪的 skill 形目录
        self.tracked = tracked            # git 跟踪清单；None = 非 git 目录，全部算成员
        self._cache = {}

    @classmethod
    def load(cls, root):
        root = os.path.abspath(root.rstrip("/"))
        skills, skipped = [], []
        tracked = tracked_set(root)
        tree = walk_dir(root, root, "", tracked, skipped, skills)
        if tree is None or not skills:
            return None                    # 目录里有文件但一份 SKILL.md 都没有 = 不是 pack
        tree["pack"] = {"name": os.path.basename(root),
                        "member_mode": "git-tracked" if tracked is not None else "all"}
        return cls(root, tree, skills, skipped, tracked)

    # ── 派生量：惰性 + 缓存 ───────────────────────────────────────────────
    def edges(self):
        """互指边（A→B：A 的文本文件里点到 B 的目录名）。口径见 `cross_skill_edges` 的 docstring。"""
        if "edges" not in self._cache:
            add_mentions(self.root, self.skills)
            self._cache["edges"] = cross_skill_edges(self.root, self.skills)
        return self._cache["edges"]

    def islands(self):
        """互指图的连通分量 —— 数据给的分层，不是人分的类。"""
        if "islands" not in self._cache:
            self._cache["islands"] = islands_of(self.skills, self.edges())
        return self._cache["islands"]

    def entry(self):
        """入口层摆出的项 → `[(kind, id, member_skill_ids)]`（契约 §0）。"""
        if "entry" not in self._cache:
            self._cache["entry"] = entry_items(self.tree)
        return self._cache["entry"]

    def by_id(self):
        """skill id → 节点。造伞体与各岛 INDEX.md 时到处都要，别再每次重算。"""
        if "by_id" not in self._cache:
            self._cache["by_id"] = {s["id"]: s for s in self.skills}
        return self._cache["by_id"]

    def top(self):
        """顶层 skill（不在别的 skill 目录之下）—— `collapse` 的输入单位。"""
        return top_level_skills(self.root, self.skills)

    def resident_tokens(self):
        """L1 常驻成本：全部 skill 的 description 拼起来的估算 token（多入口口径）。"""
        return est_tokens("\n".join(s["description"] for s in self.skills))

    def nested_skill_nodes(self):
        """id → 其下的嵌套 skill 节点（给 `TREE.md` / `TREE.html` 画岛内 skill 用）。"""
        if "nested" not in self._cache:
            self._cache["nested"] = {s["id"]: nested_skill_nodes(s) for s in self.skills}
        return self._cache["nested"]
