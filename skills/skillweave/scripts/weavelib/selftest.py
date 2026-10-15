"""自检：`--self-test` 的全部断言。

从 weave.py 拆出，逻辑未改。"""
import contextlib, difflib, io, json, os, re, shutil, tempfile
from .analysis import cmd_audit, cmd_checks, cmd_judge, cmd_layers, cmd_score, cmd_self_check
from .cli import main
from .common import read_text
from .deliver import cmd_deliver
from .disclosure import cmd_disclosure, cmd_dispatch, cmd_verify
from .frontmatter import frontmatter_selfcheck, parse_frontmatter
from .graph import _findings, _pack_files, _read_waivers, _waived, dup_pairs, first_layer_entries
from .model import git, tracked_set, untracked_skill_files, walk_dir
from .pack import Pack
from .render import _doc_nodes, _rev, cmd_visualize
from .transform import cmd_apply, cmd_collapse, cmd_prepare, cmd_propose, propose_actions





def self_test():
    tmp = tempfile.mkdtemp(prefix="weave-selftest-")
    pack = os.path.join(tmp, "pack")
    skilldir = os.path.join(pack, "notes", "demo")     # pack → 类目 → skill
    try:
        os.makedirs(os.path.join(skilldir, "references"))
        os.makedirs(os.path.join(skilldir, "templates"))
        with open(os.path.join(skilldir, "templates", "README.md"), "w") as f:
            f.write("模板说明\n")
        with open(os.path.join(skilldir, "templates", "a.tex"), "w") as f:
            f.write("模板正文\n")
        with open(os.path.join(skilldir, "loose.txt"), "w") as f:
            f.write("没人点名\n")
        with open(os.path.join(skilldir, "SKILL.md"), "w") as f:
            f.write("---\nname: demo\ndescription: >-\n  做一件事时用。\n  带触发词。\n---\n\n"
                    "# Demo\n\n见 `references/guide.md`，另见 `references/gone.md`。\n"
                    "模板见 `templates/README.md`，随手写个 `run.py` 与 `fig.pdf`。\n"
                    "包外见 `../outside-repo/thing.md`。\n\n"
                    "```\n# 这是围栏里的假标题\npython `scripts/nothere.py`\n```\n\n## 小节\n")
        with open(os.path.join(skilldir, "references", "guide.md"), "w") as f:
            f.write("guide\n")
        with open(os.path.join(skilldir, "references", "unused.md"), "w") as f:
            f.write("nobody points here\n")
        out1 = os.path.join(tmp, "o1")
        out2 = os.path.join(tmp, "o2")
        assert main(["tree", pack, "--out", out1]) == 0
        assert main(["tree", pack, "--out", out2]) == 0
        t = json.load(open(os.path.join(out1, "tree.json")))

        def find(node, kind):
            if node["kind"] == kind:
                return node
            for c in node["children"]:
                r = find(c, kind)
                if r:
                    return r
            return None

        assert t["kind"] == "pack", t["kind"]
        cat = find(t, "category")
        assert cat and cat["id"] == "notes/", cat
        s = find(t, "skill")
        assert s and s["id"] == "notes/demo/", s
        assert s["name"] == "demo", s["name"]
        assert s["summary"] == "做一件事时用。 带触发词。", s["summary"]      # 折叠块被解析
        assert ">-" not in json.dumps(s), "frontmatter 折叠标记漏进产物"
        assert s["orphans"] == ["loose.txt"], s["orphans"]
        assert s["broken"] == ["references/gone.md"], s["broken"]
        ex = sorted(r["target"] for r in s["refs"] if r["kind"] == "example")
        assert ex == ["fig.pdf", "run.py", "scripts/nothere.py"], ex      # 示例 ≠ broken
        assert "templates/" in s["named_dirs"], s["named_dirs"]
        hs = [c["summary"] for c in s["children"] if c["kind"] == "heading"]
        assert "这是围栏里的假标题" not in hs and "小节" in hs, hs            # 围栏内标题不算
        assert cat["parent"] == "", cat["parent"]
        assert s["parent"] == "notes/", s["parent"]
        a = open(os.path.join(out1, "tree.json"), "rb").read()
        b = open(os.path.join(out2, "tree.json"), "rb").read()
        assert a == b, "两次运行产物不一致（不可重建）"
        # 内化检查：硬编码路径 + 内嵌密钥 必须命中（放在树断言之后，免得它进孤儿计数）
        with open(os.path.join(skilldir, "references", "leak.md"), "w") as f:
            # 假密钥**运行时拼出来**：文件里不留像真 key 的字面量 —— 否则安全扫描会把本工具
            # 自己判成「凭证泄漏」（实测撞过：scan 判 dangerous，Hermes 拒绝安装）。
            f.write("见 /Users/someone/project/x.md\nkey = " + "s" + "k-" + "A" * 24 + "\n")
        out3 = os.path.join(tmp, "o3")
        assert cmd_checks(pack, out3) == 1, "有命中就该退 1"
        ch = json.load(open(os.path.join(out3, "checks.json")))["hits"]
        assert len(ch["hardcoded_path"]) == 1, ch
        assert len(ch["embedded_secret"]) == 1, ch
        assert ch["name_mismatch"] == [], ch
        # 路由评测管线：生成判官输入 → 假判官输出 → 打分（含校正随机分）
        pf = os.path.join(tmp, "prompts.json")
        with open(pf, "w") as f:
            json.dump({"prompts": [{"id": 1, "kind": "should_trigger", "gold": "notes/demo",
                                    "text": "演示题面"}]}, f)
        out4 = os.path.join(tmp, "o4")
        assert cmd_judge(pack, pf, out4) == 0
        txt = open(os.path.join(out4, "judge-input.txt")).read()
        assert "gold" not in txt, "金标泄进判官输入"
        jf = os.path.join(tmp, "judge-A.txt")
        open(jf, "w").write("P1 notes/demo\nDONE\n")
        assert cmd_score(os.path.join(out4, "judge-key.json"), [jf], out4) == 0
        sc = json.load(open(os.path.join(out4, "score.json")))
        assert sc["groups"]["should_trigger"]["acc"] == 1.0, sc["groups"]
        # 提案器：这个 fixture 只有一个 skill、L1=1 项、正文很小 —— 正确行为是**一条都不提**（不误报）
        out5 = os.path.join(tmp, "o5")
        assert cmd_propose(pack, out5) == 0
        pr = json.load(open(os.path.join(out5, "proposals.json")))
        assert pr["count"] == 0, pr["proposals"]
        assert os.path.isfile(os.path.join(out5, "PROPOSALS.md"))
        # 跨命令口径对拍：layers 的 token 单口径必须与 audit 一致（两边不一致就是自相矛盾）
        assert cmd_layers(pack, out5) == 0 and cmd_audit(pack, out5) == 0
        l2 = json.load(open(os.path.join(out5, "layers.json")))["L2"]["over_token"]
        au = [r["id"] for r in json.load(open(os.path.join(out5, "audit.json")))["size"] if r["over_token"]]
        assert l2 == au, (l2, au)
        # 可视化：两份产物都要出，节点 = 每份文档（issue #4）
        assert cmd_visualize(pack, out5) == 0
        mdv = open(os.path.join(out5, "TREE.md"), encoding="utf-8").read()
        htv = open(os.path.join(out5, "TREE.html"), encoding="utf-8").read()
        assert "notes/demo/SKILL.md" in mdv and "notes/demo/SKILL.md" in htv, (mdv[:200], htv[:200])
        # 节点框数 == 文档数（= DISCLOSURE.md 的表行数）
        _ndocs = len(_doc_nodes(Pack.load(pack).skills, pack))
        assert htv.count('class="node"') == _ndocs, (htv.count('class="node"'), _ndocs)
        # 第二步 disclosure：层 = 披露深度；每个文档恰好出现一次；超限带「超多少」
        out8 = os.path.join(tmp, "o8")
        assert cmd_disclosure(pack, out8) == 0
        dj = json.load(open(os.path.join(out8, "disclosure.json")))
        assert len(dj["roots"]) == 1, dj["roots"]                       # fixture 只有一个 skill → 1 个根
        assert str(1) in dj["levels"] and dj["levels"]["1"] == dj["roots"], dj["levels"]
        dm = open(os.path.join(out8, "DISCLOSURE.md"), encoding="utf-8").read()
        assert "L1（1 份）" in dm and "口径：**层 = 披露深度**" in dm, dm[:200]
        assert dj["levels"].get("2"), "demo 的 references/guide.md 应该在 L2"    # guide.md 被点名
        # 口径：中文文件名要能被认作披露（实测 Loomerto 的段落文件是中文名，只认 ASCII 会误判成到不了根）
        _cjk = os.path.join(os.path.dirname(os.path.join(skilldir, "x")), "references", "中文说明.md")
        with open(_cjk, "w") as f:
            f.write("中文文件名\n")
        with open(os.path.join(skilldir, "SKILL.md"), "a") as f:
            f.write("另见 `references/中文说明.md`。\n")
        _oc = os.path.join(tmp, "o-cjk")
        assert cmd_disclosure(pack, _oc) == 0
        _dc = json.load(open(os.path.join(_oc, "disclosure.json"), encoding="utf-8"))
        assert "notes/demo/references/中文说明.md" in _dc["nodes"], "中文文件名该被认成节点"
        assert "notes/demo/references/中文说明.md" not in _dc["orphans"], "中文文件名该能被披露（不是到不了根）"
        # 口径：嵌套 skill 里写的 `references/x.md` 按**它自己的根**解析
        _n = os.path.join(skilldir, "references", "nested")
        os.makedirs(_n, exist_ok=True)
        with open(os.path.join(_n, "SKILL.md"), "w") as f:
            f.write("---\nname: nested\ndescription: 嵌套样例。\n---\n\n见 `references/leaf.md`。\n")
        os.makedirs(os.path.join(_n, "references"), exist_ok=True)
        with open(os.path.join(_n, "references", "leaf.md"), "w") as f:
            f.write("leaf\n")
        _on = os.path.join(tmp, "o-nested")
        assert cmd_disclosure(pack, _on) == 0
        _dn = json.load(open(os.path.join(_on, "disclosure.json"), encoding="utf-8"))
        _leaf = "notes/demo/references/nested/references/leaf.md"
        assert _leaf not in _dn["broken"], "嵌套 skill 里的 `references/x.md` 该按它自己的根解析，不该算悬空"
        assert _dn["edges"].get("notes/demo/references/nested/SKILL.md", {}).get(_leaf), \
            "嵌套 skill 的披露边该连到它自己目录下的文件"
        _d8 = json.load(open(os.path.join(out8, "disclosure.json"), encoding="utf-8"))
        assert _d8["external"], "fixture 里放了一条包外引用，external 不该是空的"
        # 披露过深（issue #4 的姊妹项）：SKILL.md → ref1 → ref2 → ref3（四层链）
        # —— L3+ **只警告不退出**，且每个深层文档在 TODO.md 里有一条「披露过深」待办。
        _deep = os.path.join(tmp, "deep-pack")
        _ddir = os.path.join(_deep, "skills", "deep")
        os.makedirs(os.path.join(_ddir, "references"), exist_ok=True)
        with open(os.path.join(_ddir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: deep\ndescription: 深链样例。\n---\n\n见 `references/ref1.md`。\n")
        for _i in (1, 2, 3):
            with open(os.path.join(_ddir, "references", f"ref{_i}.md"), "w", encoding="utf-8") as f:
                f.write(f"ref{_i}\n\n见 `references/ref{_i + 1}.md`。\n" if _i < 3 else f"ref{_i}\n")
        _odp = os.path.join(tmp, "o-deep")
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            _drc = cmd_disclosure(_deep, _odp)
        assert _drc == 0, "L4 只警告不退出（不许因为披露过深就拒绝分析）"
        _dout = _buf.getvalue()
        assert "⚠️ 检测到 L4 层" in _dout, _dout
        assert "披露深度：L1=1 → L2=1 → L3=1 → L4=1" in _dout, _dout
        _ddj = json.load(open(os.path.join(_odp, "disclosure.json"), encoding="utf-8"))
        assert _ddj["depth_histogram"] == {"1": 1, "2": 1, "3": 1, "4": 1}, _ddj["depth_histogram"]
        assert _ddj["nodes"]["skills/deep/references/ref3.md"]["depth"] == 4, _ddj["nodes"]
        _dt = open(os.path.join(_odp, "TODO.md"), encoding="utf-8").read()
        assert "披露过深" in _dt and "`skills/deep/references/ref3.md`" in _dt, _dt
        assert "L4（被 L3 的 skills/deep/references/ref2.md 引用）" in _dt, _dt
        todo_md = os.path.join(out8, "TODO.md")
        assert os.path.isfile(todo_md), "缺 TODO.md"
        t0 = open(todo_md, encoding="utf-8").read()
        assert "待办" in t0 and "免检表长什么样" in t0, t0[:200]
        # 包内免检表：命中就不算待办，改列「已豁免」
        os.makedirs(os.path.join(pack, ".skillweave"), exist_ok=True)
        open(os.path.join(pack, ".skillweave", "waivers.txt"), "w", encoding="utf-8").write(
            "# 一行一条\n*unused.md   没人点名是刻意的\n")
        out9 = os.path.join(tmp, "o9")
        assert cmd_disclosure(pack, out9) == 0
        t1 = open(os.path.join(out9, "TODO.md"), encoding="utf-8").read()
        assert "没人点名是刻意的" in t1, t1[:400]
        # issue #5 回归：`--out` 缺省值必须是**包内** `<pack>/.skillweave/`，不是系统临时目录。
        # 旧实现写在 tempfile.gettempdir()，重启即丢、换机器复现不了、clone 别人的包拿不到产物。
        _swout = os.path.join(pack, ".skillweave")
        for _f in ("DISCLOSURE.md", "disclosure.json", "TODO.md", "checks.json", "audit.json"):
            if os.path.exists(os.path.join(_swout, _f)):
                os.remove(os.path.join(_swout, _f))
        assert main(["disclosure", pack]) == 0, "不带 --out 的 disclosure 该成功"
        assert os.path.isfile(os.path.join(_swout, "DISCLOSURE.md")), \
            "issue #5：disclosure 缺省产物该落在包内 .skillweave/"
        assert os.path.isfile(os.path.join(_swout, "TODO.md")), "issue #5：TODO.md 也该在包内"
        assert main(["checks", pack]) == 1, "checks 有命中该退 1"
        assert os.path.isfile(os.path.join(_swout, "checks.json")), \
            "issue #5：checks 缺省产物该落在包内 .skillweave/"
        assert main(["audit", pack]) == 0
        assert os.path.isfile(os.path.join(_swout, "audit.json")), \
            "issue #5：audit 缺省产物该落在包内 .skillweave/"
        # `.skillweave/` 是非成员目录（SKIP_DIRS）→ 工具自己写下的产物不会变成「到不了根」
        _dsw = json.load(open(os.path.join(_swout, "disclosure.json"), encoding="utf-8"))
        assert not any(".skillweave" in p for p in _dsw["nodes"]), \
            f"工具产物进了文档树：{sorted(_dsw['nodes'])}"
        # prepare 的两条路：git 仓库 → worktree；非 git → copy + git init
        _repo = os.path.join(tmp, "repo-in")
        os.makedirs(os.path.join(_repo, "skills", "demo"))
        with open(os.path.join(_repo, "skills", "demo", "SKILL.md"), "w") as f:
            f.write("---\nname: demo\ndescription: 做一件事时用。\n---\n\n见 `references/x.md`。\n")
        with open(os.path.join(_repo, "README.md"), "w") as f:
            f.write("repo\n")
        git(_repo, "init", "-q")
        git(_repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        git(_repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
        _wt = os.path.join(tmp, "repo-wt")
        assert cmd_prepare(_repo, os.path.join(tmp, "o-prep-wt"), dest=_wt, shape="multi",
                           executor="manual") == 0, \
            "git 仓库输入该走 worktree"
        assert os.path.isfile(os.path.join(_wt, ".git")), "worktree 的 .git 该是个文件，不是目录"
        wl = git(_repo, "worktree", "list")
        assert _wt in (wl.stdout or ""), "主 clone 里该能看到这个 worktree"
        git(_repo, "worktree", "remove", "--force", _wt)
        # 非 git 输入：拷副本 + git init
        _plain = os.path.join(tmp, "plain-in")
        os.makedirs(os.path.join(_plain, "skills", "demo"))
        with open(os.path.join(_plain, "skills", "demo", "SKILL.md"), "w") as f:
            f.write("---\nname: demo\ndescription: 做一件事时用。\n---\n\n见 `references/x.md`。\n")
        _cp = os.path.join(tmp, "plain-copy")
        assert cmd_prepare(_plain, os.path.join(tmp, "o-prep-cp"), dest=_cp, shape="multi",
                           executor="manual") == 0, \
            "非 git 输入该走拷贝"
        assert git(_cp, "rev-parse", "--git-dir") is not None, "副本该被 git 管起来"
        assert not os.path.exists(os.path.join(_plain, ".git")), "原目录不该被 git init"

        # 派发：事实补全 + 批次 + 计数起点
        _dbuf = io.StringIO()
        with contextlib.redirect_stdout(_dbuf):
            assert cmd_dispatch(pack, out9, batch_size=10) == 0, "dispatch 该成功"
        pl = json.load(open(os.path.join(out9, "dispatch", "plan.json"), encoding="utf-8"))
        ids = [it["id"] for b in pl["batches"] for it in b["items"]]
        assert ids and len(ids) == len(set(ids)), "条目 id 必须唯一"
        pr = open(os.path.join(out9, "dispatch", "batch-1.prompt.md"), encoding="utf-8").read()
        assert "只产出提案" in pr and "不许开后台进程" in pr, pr[:200]
        assert "## 条目与事实" in pr and ("包内没有同名文件" in pr or "候选" in pr or "二级标题" in pr), \
            "prompt 里必须有事实补全段"
        assert os.path.isfile(os.path.join(out9, "dispatch", "state.json")), "缺 state.json"
        # ticket 07：没有执行者配置 → 只警告、不阻塞（退 0，prompt 里不加「执行方式」、plan.json 无 executor）
        assert "警告：未找到执行者配置" in _dbuf.getvalue(), _dbuf.getvalue()
        assert "## 执行方式" not in pr, "没有执行者配置时不该追加执行方式章节"
        assert "executor" not in pl, "没有执行者配置时 plan.json 不该有 executor 字段"

        st = os.path.join(out9, "dispatch", "state.json")
        # ── 落盘器：锚点 / 白名单 / 拆分守恒 / 单条回退 ──
        b1 = json.load(open(os.path.join(out9, "dispatch", "plan.json"), encoding="utf-8"))["batches"][0]
        broken = next(it for it in b1["items"] if it["kind"] == "悬空")
        bfull = os.path.join(pack, broken["path"])          # 用条目自己的路径，不猜
        blines = read_text(bfull).split("\n")
        bl = broken["refs"][0]["line"]
        old_line = blines[bl - 1]                       # 锚点是整行逐字比对，所以取真行
        new_line = old_line.replace("references/gone.md", "references/guide.md")
        good = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed", "reason_code": "typo-fixed",
             "edits": [{"file": broken["path"], "line": bl, "before": old_line, "after": new_line}]}]}
        gpath = os.path.join(tmp, "prop-good.json")
        with open(gpath, "w", encoding="utf-8") as f:
            json.dump(good, f, ensure_ascii=False)
        assert cmd_apply(pack, [gpath], st, os.path.join(out9, "dispatch")) == 0, "合法提案该落盘"
        assert "references/gone.md" not in read_text(bfull), "改动没落盘"
        pj = json.load(open(os.path.join(out9, "dispatch", "patches.json"), encoding="utf-8"))
        assert pj and pj[0]["files"][0]["file"], "缺逐条 patch 记录"
        assert cmd_apply(pack, [], st, os.path.join(out9, "dispatch"), revert_id=broken["id"]) == 0, "回退该成功"
        assert old_line in read_text(bfull), "回退没把整行原文还原回去"
        bad = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": broken["path"], "line": bl,
                        "before": "这句原文根本不存在", "after": "x"}]}]}
        bpath = os.path.join(tmp, "prop-bad.json")
        with open(bpath, "w", encoding="utf-8") as f:
            json.dump(bad, f, ensure_ascii=False)
        assert cmd_apply(pack, [bpath], st, os.path.join(out9, "dispatch")) == 1, "锚点对不上必须失败"
        out_of_range = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": "README.md", "line": 1, "before": "x", "after": "y"}]}]}
        rpath = os.path.join(tmp, "prop-range.json")
        with open(rpath, "w", encoding="utf-8") as f:
            json.dump(out_of_range, f, ensure_ascii=False)
        assert cmd_apply(pack, [rpath], st, os.path.join(out9, "dispatch")) == 1, "越界改动必须失败"
        # 拆分守恒：把 SKILL.md 拆成两份，第二份不守恒就该被拒
        orig = read_text(bfull)
        sp = {"batch": "B1", "results": [                      # 只给 parts、不给 edits = 整篇拆分，要守恒
            {"id": broken["id"], "verdict": "fixed",
             "parts": {os.path.join(os.path.dirname(broken["path"]) or ".", "half.md"): "少了内容"}}]}
        sppath = os.path.join(tmp, "prop-split.json")
        with open(sppath, "w", encoding="utf-8") as f:
            json.dump(sp, f, ensure_ascii=False)
        assert cmd_apply(pack, [sppath], st, os.path.join(out9, "dispatch")) == 1, "拆分不守恒必须失败"
        assert orig == read_text(bfull), "失败的提案不许留下半个改动"
        # 新形态：edits 与 parts 同时给 → 原文保留、新文件创建（把段落搬出去、留一行指针）
        mv = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": broken["path"], "line": bl, "before": old_line, "after": new_line}],
             "parts": {os.path.join(os.path.dirname(broken["path"]) or ".", "moved.md"): "搬出去的那几段\n"}}]}
        mvpath = os.path.join(tmp, "prop-move.json")
        with open(mvpath, "w", encoding="utf-8") as f:
            json.dump(mv, f, ensure_ascii=False)
        assert cmd_apply(pack, [mvpath], st, os.path.join(out9, "dispatch")) == 0, "搬段落的提案该落盘"
        assert os.path.isfile(os.path.join(pack, os.path.dirname(broken["path"]) or ".", "moved.md")), \
            "搬出的新文件该创建"
        assert os.path.isfile(bfull), "搬段落时原文不该被删"
        assert new_line in read_text(bfull), "原文该留下指针行"
        assert cmd_apply(pack, [], st, os.path.join(out9, "dispatch"), revert_id=broken["id"]) == 0, \
            "该能把这一条回退掉"
        assert not os.path.isfile(os.path.join(pack, os.path.dirname(broken["path"]) or ".", "moved.md")), \
            "回退该删掉搬出的文件"
        assert old_line in read_text(bfull), "回退该把指针行还原"

        # 删行 + 整行替换：把段落「搬出去 + 原文留一行指针」用的就是这两招
        blines2 = read_text(bfull).split("\n")
        keep_line = blines2[bl - 1]
        mv2 = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": broken["path"], "line": bl, "before": keep_line,
                        "after": "## 指针 → 见 `references/moved2.md`"},
                       {"file": broken["path"], "line": bl + 1, "before": blines2[bl], "after": None}],
             "parts": {os.path.join(os.path.dirname(broken["path"]) or ".", "moved2.md"): "搬走的正文\n"}}]}
        mv2p = os.path.join(tmp, "prop-move2.json")
        with open(mv2p, "w", encoding="utf-8") as f:
            json.dump(mv2, f, ensure_ascii=False)
        _orig_text = read_text(bfull)                  # 回退的判据用「逐字节还原」，比逐行断言更硬
        _before_n = len(read_text(bfull).split("\n"))
        assert cmd_apply(pack, [mv2p], st, os.path.join(out9, "dispatch")) == 0, "删行 + 指针替换该落盘"
        _after = read_text(bfull).split("\n")
        assert "## 指针 → 见 `references/moved2.md`" in _after, "指针行没写进去"
        assert len(_after) == _before_n - 1, "删了一行，总行数该少 1"
        assert cmd_apply(pack, [], st, os.path.join(out9, "dispatch"), revert_id=broken["id"]) == 0, \
            "该能回退（删行 + 指针替换）"
        assert read_text(bfull) == _orig_text, "回退该把文件逐字节还原：\n" + "\n".join(
            difflib.unified_diff(_orig_text.split("\n"), read_text(bfull).split("\n"), lineterm=""))

        ml = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": broken["path"], "line": bl, "before": old_line, "after": "两行\n内容"}]}]}
        mlp = os.path.join(tmp, "prop-multiline.json")
        with open(mlp, "w", encoding="utf-8") as f:
            json.dump(ml, f, ensure_ascii=False)
        assert cmd_apply(pack, [mlp], st, os.path.join(out9, "dispatch")) == 1, "多行 after 该被拒"

        # 删空行不能误删别处：空行到处一样，按内容找会删错行
        _orig_lines = read_text(bfull).split("\n")
        _blanks = [i for i, l in enumerate(_orig_lines, 1) if l.strip() == ""]
        _pick = _blanks[2] if len(_blanks) > 2 else _blanks[0]
        delp = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": broken["path"], "line": _pick, "before": "", "after": None}],
             "parts": {os.path.join(os.path.dirname(broken["path"]) or ".", "blank-test.md"): "占位\n"}}]}
        delpp = os.path.join(tmp, "prop-delblank.json")
        with open(delpp, "w", encoding="utf-8") as f:
            json.dump(delp, f, ensure_ascii=False)
        assert cmd_apply(pack, [delpp], st, os.path.join(out9, "dispatch")) == 0, "删空行该落盘"
        assert read_text(bfull).split("\n") == _orig_lines[:_pick - 1] + _orig_lines[_pick:], \
            "删空行必须只删掉那一行，别处的空行不许动"
        assert cmd_apply(pack, [], st, os.path.join(out9, "dispatch"), revert_id=broken["id"]) == 0, "该能回退"
        assert read_text(bfull).split("\n") == _orig_lines, "回退该逐行还原"

        # parts 拼起来等于原文 → 按拆分处理，原件要删掉（否则「拆了但原件还在」）
        _sp_orig = read_text(bfull)
        _half = len(_sp_orig.split("\n")) // 2
        _lns = _sp_orig.split("\n")
        sp2 = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "fixed",
             "edits": [{"file": broken["path"], "line": bl, "before": _lns[bl - 1],
                        "after": "## 指针 → 见 `references/p1.md`"}],
             "parts": {os.path.join(os.path.dirname(broken["path"]) or ".", "p1.md"): "\n".join(_lns[:_half]),
                       os.path.join(os.path.dirname(broken["path"]) or ".", "p2.md"): "\n".join(_lns[_half:])}}]}
        sp2p = os.path.join(tmp, "prop-split2.json")
        with open(sp2p, "w", encoding="utf-8") as f:
            json.dump(sp2, f, ensure_ascii=False)
        assert cmd_apply(pack, [sp2p], st, os.path.join(out9, "dispatch")) == 0, "守恒的拆分该落盘"
        assert not os.path.isfile(bfull), "拆分后原件该被删掉"
        assert os.path.isfile(os.path.join(os.path.dirname(bfull), "p1.md")), "拆出的两份该落盘"
        assert cmd_apply(pack, [], st, os.path.join(out9, "dispatch"), revert_id=broken["id"]) == 0, "该能回退"
        assert read_text(bfull) == _sp_orig, "回退该把原件整份恢复回来"
        assert not os.path.isfile(os.path.join(os.path.dirname(bfull), "p1.md")), "回退该删掉拆出的两份"

        # 只写豁免、没有 edits 的提案：要能落盘、写进 waivers、让条目离开待办
        _wp = os.path.join(pack, ".skillweave", "waivers.txt")
        _bk = read_text(_wp) if os.path.isfile(_wp) else None      # 测完要还原，否则后面的对账会漂
        wprop = {"batch": "B1", "results": [
            {"id": broken["id"], "verdict": "waived", "reason_code": "external",
             "reason": "这个引用在说包外的文件"}]}
        wpath = os.path.join(tmp, "prop-waive.json")
        with open(wpath, "w", encoding="utf-8") as f:
            json.dump(wprop, f, ensure_ascii=False)
        assert cmd_apply(pack, [wpath], st, os.path.join(out9, "dispatch")) == 0, "只写豁免的提案也该落盘"
        wf = open(os.path.join(pack, ".skillweave", "waivers.txt"), encoding="utf-8").read()
        assert broken["path"] in wf, "豁免规则没写进 waivers.txt"
        _fw = os.path.join(out9, "waive-todo")
        assert cmd_disclosure(pack, _fw) == 0
        assert broken["id"] not in open(os.path.join(_fw, "TODO.md"), encoding="utf-8").read(), \
            "豁免后该条目不该还在待办里"
        _wv = _read_waivers(pack)
        _bf = {i: f for i, f in _findings(json.load(open(os.path.join(out9, "dispatch",
              "baseline.json"), encoding="utf-8")), pack).items() if not _waived(f["path"], _wv)}
        assert broken["id"] not in _bf, "豁免的条目不该再被当成待解决"
        if _bk is None:
            os.remove(_wp)
        else:
            with open(_wp, "w", encoding="utf-8") as f:
                f.write(_bk)
        before_att = json.load(open(st, encoding="utf-8"))["attempts"]
        assert cmd_dispatch(pack, out9, batch_size=10) == 0, "重派（无尝试记录）应被允许"
        after_att = json.load(open(st, encoding="utf-8"))["attempts"]
        assert set(after_att) == set(before_att), "重派不许把条目账改掉"
        # 不许打转：某批已有尝试且 prompt 未变 → 再派必须被拒（退 3）
        stj = json.load(open(st, encoding="utf-8"))
        b1 = json.load(open(os.path.join(out9, "dispatch", "plan.json"), encoding="utf-8"))["batches"][0]
        stj["attempts"][b1["items"][0]["id"]] = 1
        with open(st, "w", encoding="utf-8") as f:
            json.dump(stj, f, ensure_ascii=False)
        assert cmd_dispatch(pack, out9, batch_size=10) == 3, "prompt 没换就重派，必须被拒（相同输入=相同输出）"
        # 验收：干净 → PASS；注入一条新悬空 → FAIL，并给梯子
        assert cmd_verify(pack, st, [], None, out9) == 0, "没改动的 pack、没声称修过任何东西 → 应 PASS"
        try:
            p2 = os.path.join(pack, "第二只", "SKILL.md")
            os.makedirs(os.path.dirname(p2), exist_ok=True)
            with open(p2, "w", encoding="utf-8") as f:
                f.write("---\nname: 第二只\ndescription: 另一只 demo，用来测新增悬空。\n---\n\n见 `references/nope.md`。\n")
            assert cmd_verify(pack, st, [], None, out9) == 1, "新增悬空必须 FAIL"
            run = open(os.path.join(out9, "RUN.md"), encoding="utf-8").read()
            assert "⛔" in run and "R1" in run, "FAIL 时要写拦截判据与下一级 R 指令"
        finally:
            shutil.rmtree(os.path.join(pack, "第二只"), ignore_errors=True)
        # 第一步 prepare：非 git 的输入 → 副本由 git 管、原目录不被碰、BASELINE.md 出两种形状的账
        out7 = os.path.join(tmp, "o7")
        dest7 = os.path.join(tmp, "ws", "pack")
        assert cmd_prepare(pack, out7, dest=dest7, executor="opencode") == 0
        assert os.path.isdir(os.path.join(dest7, ".git")), "副本没有被 git 管"
        assert git(dest7, "log", "--oneline").stdout.strip(), "副本没有起点 commit"
        assert not os.path.exists(os.path.join(pack, ".git")), "原目录被动了"
        # ticket 06：执行者配置写进副本、内容正确、并记进 BASELINE.md
        _ej = os.path.join(dest7, "dispatch", "executor.json")
        assert os.path.isfile(_ej), "prepare 该写出 dispatch/executor.json"
        _ec = json.load(open(_ej, encoding="utf-8"))
        assert _ec["type"] == "opencode" and _ec.get("model") == "deepseek-v4.1-flash", _ec
        assert "{model}" in _ec["command_template"] and "{input}" in _ec["command_template"], _ec
        base = open(os.path.join(out7, "BASELINE.md"), encoding="utf-8").read()
        assert "执行者：opencode (deepseek-v4.1-flash)" in base, base[:400]
        # ticket 07：dispatch 读副本 dispatch 目录下的 executor.json → 每个 prompt 末尾追加「## 执行方式」，
        # 占位符换成实际文件名；并把整份配置记进 plan.json
        _o_de = os.path.join(tmp, "o-dispatch-exec")
        assert cmd_dispatch(dest7, _o_de) == 0, "带执行者配置的 dispatch 该成功"
        _pe = json.load(open(os.path.join(_o_de, "dispatch", "plan.json"), encoding="utf-8"))
        assert _pe.get("executor", {}).get("type") == "opencode", _pe.get("executor")
        assert _pe["executor"].get("command_template"), "plan.json 里该带整份执行者配置"
        _pt = open(os.path.join(_o_de, "dispatch", "batch-1.prompt.md"), encoding="utf-8").read()
        assert "## 执行方式" in _pt and "**类型**: opencode" in _pt, _pt[-400:]
        assert ("opencode --model deepseek-v4.1-flash --prompt batch-1.prompt.md "
                "--output batch-1.proposal.json") in _pt, _pt[-400:]
        assert "`{input}`: 本文件路径（batch-1.prompt.md）" in _pt, _pt[-400:]
        assert "`{output}`: 提案输出文件（batch-1.proposal.json）" in _pt, _pt[-400:]
        assert "请手动执行上述 prompt" not in _pt, "opencode 不该出现 manual 专属提示"
        # 已有配置 → 沿用（不再问、不改内容）；非交互默认 manual 也不阻塞
        assert cmd_prepare(pack, out7, dest=dest7, executor="manual") == 2, "副本已存在时必须拒绝覆盖"
        assert "A 单入口" in base and "B 多入口" in base and "待用户选" in base, base[:200]
        # 单入口方案：干跑必须算出 L1=1；--apply 不给 description 必须拒绝（不许生成半成品）
        out6 = os.path.join(tmp, "o6")
        assert cmd_collapse(pack, out6) == 0
        cm = open(os.path.join(out6, "COLLAPSE.md"), encoding="utf-8").read()
        assert "L1  1 项" in cm and "notes/demo" in cm, cm[:200]
        assert cmd_collapse(pack, out6, apply_changes=True) == 2      # 缺 description → 拒绝
        # issue #2 回归：值里带 `: ` 时写出的 frontmatter 必须仍是合法 YAML（旧实现裸拼 → 真解析器炸）
        _bad = "入口: 带冒号的值"
        assert cmd_collapse(pack, out6, apply_changes=True, description=_bad) == 0
        _ent = os.path.join(pack, "skills", "pack", "SKILL.md")
        _et = read_text(_ent)
        assert not frontmatter_selfcheck(_et), frontmatter_selfcheck(_et)
        assert _et.split("\n")[2] == 'description: "入口: 带冒号的值"', _et.split("\n")[:4]
        assert parse_frontmatter(_et)[0].get("description") == _bad, "回读的 description 必须与写出的逐字一致"
        # 有真 YAML 解析器就用它复核（契约 §6：不引依赖，所以只在装了的时候当额外证据）
        try:
            import yaml as _yaml
            assert _yaml.safe_load(_et.split("---")[1])["description"] == _bad, "真 YAML 解析器读不一致"
        except ImportError:
            pass
        # issue #1 回归：collapse 之后 TREE.html 的节点框数必须 == 文档数（issue #4 改成文档口径）
        # （旧实现 walk_dir 遇 SKILL.md 就 return，岛内 skill 一个框都不画 → 永远 1 个）
        _nskill = sum(1 for _dp, _dn, _fn in os.walk(pack) for _f in _fn if _f == "SKILL.md")
        assert _nskill >= 2, f"fixture 该有多个 SKILL.md 才测得出丢节点，实得 {_nskill}"
        _ov = os.path.join(tmp, "o-vis")
        assert cmd_visualize(pack, _ov) == 0
        _hv = open(os.path.join(_ov, "TREE.html"), encoding="utf-8").read()
        _nrect = _hv.count('class="node"')
        _ndocs = len(_doc_nodes(Pack.load(pack).skills, pack))
        assert _nrect == _ndocs, f"节点框 {_nrect} != 文档数 {_ndocs}（丢节点）"
        _mv = open(os.path.join(_ov, "TREE.md"), encoding="utf-8").read()
        assert f"文档 {_ndocs} 个" in _mv, _mv[:300]
        # 入口层仍必须是 1 项（单入口形状），而 skill 数 > 1 —— 这两条一起才是正确形状
        _tv_skills = []
        _tv = walk_dir(pack, pack, "", tracked_set(pack), [], _tv_skills)
        assert len(first_layer_entries(_tv)) == 1, first_layer_entries(_tv)
        # issue #1 根因 2 回归：工作区有未跟踪的 SKILL.md → visualize 必须报错退出（不许静默空树）
        # 必须用**真 git 仓库**：非 git 目录下「未跟踪」无从谈起（tracked_set 返回 None，全部算成员）
        _gr = os.path.join(tmp, "git-pack")
        os.makedirs(os.path.join(_gr, "skills", "committed"), exist_ok=True)
        with open(os.path.join(_gr, "skills", "committed", "SKILL.md"), "w") as f:
            f.write("---\nname: committed\ndescription: 已 commit 的入口。\n---\n\n# c\n")
        git(_gr, "init", "-q")
        git(_gr, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        git(_gr, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
        _og = os.path.join(tmp, "o-git")
        assert cmd_visualize(_gr, _og) == 0, "全是已跟踪文件时该正常出树"
        assert untracked_skill_files(_gr) == [], untracked_skill_files(_gr)
        _un = os.path.join(_gr, "skills", "untracked-entry")
        os.makedirs(_un, exist_ok=True)
        with open(os.path.join(_un, "SKILL.md"), "w") as f:
            f.write("---\nname: untracked-entry\ndescription: 还没 commit。\n---\n\n# u\n")
        assert untracked_skill_files(_gr) == ["skills/untracked-entry/SKILL.md"], untracked_skill_files(_gr)
        _ou = os.path.join(tmp, "o-un")
        assert cmd_visualize(_gr, _ou) == 1, "有未跟踪 SKILL.md 时 visualize 该报错退出，不该静默出空树"
        assert not os.path.isfile(os.path.join(_ou, "TREE.html")), "报错时不该产出空树"
        shutil.rmtree(_un, ignore_errors=True)
        # 工具目录 `.skillweave/` **不是 pack 成员**：包主的免检表 + 历次度量 + 按 subject 搬回这份包的
        # 历史轮次档案都住这里（口径 docs/contract.md §9）。它若进了度量，工具自己写下的产物
        # （`DISCLOSURE.md`、别人那 2.5 MB 档案）会变成下一次运行量出来的「到不了根」——
        # 同一个包跑两遍给出两个数。
        _sw = os.path.join(_gr, ".skillweave", "reports", "skillweave-2026-10-11")
        os.makedirs(_sw, exist_ok=True)
        with open(os.path.join(_sw, "LAYERS.md"), "w") as f:
            f.write("# 历史轮次的层读数（真实档案长这样）\n")
        with open(os.path.join(_sw, "layers.json"), "w") as f:
            f.write('{"轮次": "2026-10-11"}\n')
        with open(os.path.join(_gr, ".skillweave", "waivers.txt"), "w") as f:
            f.write("*/assets/*.png        给人看的图，Agent 不读\n")
        _psw = Pack.load(_gr)
        assert _psw is not None, "多了一个 .skillweave/，pack 就认不出来了"
        assert [s["id"] for s in _psw.skills] == ["skills/committed/"], [s["id"] for s in _psw.skills]
        assert not any(".skillweave" in c["id"] for c in _psw.tree["children"]), \
            "工具目录进了文档树 —— 同一份 pack 跑两遍会给出两个数"
        assert not any(".skillweave" in f["path"] for s in _psw.skills for f in s["files"]), \
            "工具目录进了 skill 的文件清单"
        assert not any(".skillweave" in f for f in _pack_files(_gr)), ".skillweave 必须被 _pack_files 排除"
        assert [w[0] for w in _read_waivers(_gr)] == ["*/assets/*.png"], "免检表仍要读得到"
        _osw = os.path.join(tmp, "o-sw")
        assert cmd_disclosure(_gr, _osw) == 0
        _dj = json.load(open(os.path.join(_osw, "disclosure.json"), encoding="utf-8"))
        assert len(_dj["nodes"]) == 1 and not any(".skillweave" in p for p in _dj["nodes"]), \
            f"工具目录变成了文档节点：{sorted(_dj['nodes'])}"
        # ticket 02：templates/ · examples/ · tests/ 下的文件**自动豁免**（不算「到不了根」、不进待办），
        # 但确实被引用时路径仍要存在（悬空照报）。waivers.txt 不必手写这三个目录。
        _awd = os.path.join(tmp, "auto-waive-pack")
        _asd = os.path.join(_awd, "skills", "aw")
        os.makedirs(os.path.join(_asd, "templates"))
        os.makedirs(os.path.join(_asd, "examples"))
        os.makedirs(os.path.join(_asd, "tests"))
        open(os.path.join(_asd, "templates", "schema.json"), "w").write('{"a": 1}\n')   # 未被引用 → 自动豁免
        open(os.path.join(_asd, "examples", "demo.md"), "w").write("示例\n")             # 未被引用 → 自动豁免
        open(os.path.join(_asd, "templates", "used.json"), "w").write('{"b": 2}\n')     # 被正确引用 → 进披露链
        # 路径**运行时拼出来**：本文件（selftest.py）自己也在 pack 里被 disclosure 扫，
        # 留完整反引号路径会让工具把 fixture 的假引用算成自己的悬空。
        _used_ref, _gone_ref = "templates/" + "used.json", "templates/" + "gone.json"
        open(os.path.join(_asd, "SKILL.md"), "w").write(
            "---\nname: aw\ndescription: 自动豁免样例。\n---\n\n# aw\n\n"
            f"正确引用：`{_used_ref}`\n路径写错：`{_gone_ref}`\n")
        _oaw = os.path.join(tmp, "o-auto-waive")
        assert cmd_disclosure(_awd, _oaw) == 0, "自动豁免 fixture 该能跑通"
        _daw = json.load(open(os.path.join(_oaw, "disclosure.json"), encoding="utf-8"))
        _schema, _demo = "skills/aw/templates/schema.json", "skills/aw/examples/demo.md"
        assert _schema in _daw["nodes"] and _demo in _daw["nodes"], sorted(_daw["nodes"])
        assert _schema not in _daw["orphans"] and _demo not in _daw["orphans"], \
            f"资源目录下的文件不该算到不了根：{_daw['orphans']}"
        assert _schema in _daw["auto_waived"] and _demo in _daw["auto_waived"], _daw["auto_waived"]
        assert "skills/aw/templates/used.json" not in _daw["orphans"], "被正确引用的资源文件不该算到不了根"
        assert any(b[1] == "templates/gone.json" for b in _daw["broken"]), \
            f"资源目录里写错的路径仍要报悬空：{_daw['broken']}"
        _taw = open(os.path.join(_oaw, "TODO.md"), encoding="utf-8").read()
        assert "已豁免 2 条（自动 2 · 手动 0）" in _taw, _taw[:400]
        assert _schema not in _taw.split("## 已豁免", 1)[0], "自动豁免的文件不该在待办表"
        assert _demo not in _taw.split("## 已豁免", 1)[0], "自动豁免的文件不该在待办表"
        assert _schema in _taw.split("## 已豁免 · 自动", 1)[1], "自动豁免该单列一栏"
        # ticket 05：脚本类文档**不做悬空检查**（脚本里的路径字面量多是 fixture 与注释里的举例，
        # 与「脚本不计字节」同源），但 markdown 里的悬空**照报** —— 一条反向闸不可少。
        _sb = os.path.join(tmp, "script-broken-pack")
        _sbd = os.path.join(_sb, "skills", "sb")
        os.makedirs(os.path.join(_sbd, "references"))
        os.makedirs(os.path.join(_sbd, "scripts"))
        _lit = "references/" + "missing.md"           # 运行时拼：免得本文件自己带上这串字面量
        open(os.path.join(_sbd, "SKILL.md"), "w").write(
            "---\nname: sb\ndescription: 脚本不做悬空检查。\n---\n\n# sb\n\n"
            "见 `references/keep.md`，脚本见 `scripts/tool.py`。\n")
        open(os.path.join(_sbd, "references", "keep.md"), "w").write("# keep\n")
        open(os.path.join(_sbd, "references", "has-bad.md"), "w").write(
            f"# markdown 悬空\n\n另见 `{_lit}`。\n")                    # markdown：照报
        open(os.path.join(_sbd, "scripts", "tool.py"), "w").write(
            f"# 脚本里的路径字面量\nNOTE = \"见 `{_lit}` 就懂了\"\n")     # 脚本：不报
        _osb = os.path.join(tmp, "o-script-broken")
        assert cmd_disclosure(_sb, _osb) == 0
        _dsb = json.load(open(os.path.join(_osb, "disclosure.json"), encoding="utf-8"))
        assert any(b[0] == "skills/sb/references/has-bad.md" and b[1] == _lit for b in _dsb["broken"]), \
            f"markdown 里的悬空必须照报：{_dsb['broken']}"
        assert not any(b[0].endswith("tool.py") for b in _dsb["broken"]), \
            f"脚本类文档不该做悬空检查：{_dsb['broken']}"

        # ticket 05：根文档按**目录**点名（`scripts/weavelib/`）→ 整目录不算「到不了根」（契约 §3）。
        _dpk = os.path.join(tmp, "dir-named-pack")
        _dpd = os.path.join(_dpk, "skills", "dn")
        os.makedirs(os.path.join(_dpd, "scripts", "weavelib"))
        for _f in ("a.py", "b.py"):
            open(os.path.join(_dpd, "scripts", "weavelib", _f), "w").write("# x\n")
        _dirref = "scripts/" + "weavelib/"
        open(os.path.join(_dpd, "SKILL.md"), "w").write(
            "---\nname: dn\ndescription: 目录级点名。\n---\n\n# dn\n\n"
            f"实现在 `{_dirref}`。\n")
        _odn = os.path.join(tmp, "o-dir-named")
        assert cmd_disclosure(_dpk, _odn) == 0
        _ddn = json.load(open(os.path.join(_odn, "disclosure.json"), encoding="utf-8"))
        assert not _ddn["orphans"], f"目录级点名该覆盖整目录：{_ddn['orphans']}"
        assert "skills/dn/scripts/weavelib/a.py" in _ddn["levels"].get("2", []), _ddn["levels"]

        # ticket 05：self-check —— 对包自身跑 disclosure，未豁免条目为空才退 0，否则退 1。
        _scp = os.path.join(tmp, "selfcheck-pack")
        os.makedirs(os.path.join(_scp, "skills", "ok"), exist_ok=True)
        open(os.path.join(_scp, "skills", "ok", "SKILL.md"), "w").write(
            "---\nname: ok\ndescription: 干净包。\n---\n\n# ok\n")
        _scbuf = io.StringIO()
        with contextlib.redirect_stdout(_scbuf):
            assert cmd_self_check(_scp) == 0, "干净包该自举 PASS"
            open(os.path.join(_scp, "skills", "ok", "SKILL.md"), "a").write(
                "见 `references/gone.md`。\n")
            assert cmd_self_check(_scp) == 1, "有未豁免悬空该自举 FAIL"
        assert "PASS" in _scbuf.getvalue() and "FAIL" in _scbuf.getvalue(), _scbuf.getvalue()

        # 非 skill pack 的目录：audit 该报 FAIL 退 1，不该 IndexError（实测 312 个目录里 246 个命中）
        _plain = os.path.join(tmp, "not-a-pack")
        os.makedirs(_plain, exist_ok=True)
        with open(os.path.join(_plain, "readme.txt"), "w") as f:
            f.write("就是个普通目录\n")
        assert cmd_audit(_plain, os.path.join(tmp, "o-np")) == 1, "没有 SKILL.md 的目录该 FAIL 退 1"
        # 架构回归：`walk_dir(root, root, ...)`（装包样板）全**包**只许出现在两处 ——
        # `Pack.load`（唯一该定义它的地方）和 `cmd_collapse` 落盘后的重读（它必须重扫盘看自己的改动）。
        # 谁再在命令里手抄第三遍，这里就红 —— issue #1 那个 IndexError 正是长在这种抄写里。
        # （2026-10-12 拆包后：扫 weavelib/*.py + 入口 weave.py，不再只看单文件。）
        _pkgdir = os.path.dirname(os.path.abspath(__file__))
        _scan = [os.path.join(_pkgdir, f) for f in sorted(os.listdir(_pkgdir))
                 if f.endswith(".py")]
        _scan.append(os.path.join(_pkgdir, os.pardir, "weave.py"))
        _dup = []
        for _p in _scan:
            for _i, _l in enumerate(read_text(_p).split("\n"), 1):
                if re.search(r"^\s*tree\d? = walk_dir\(\s*(root|dest)\s*,\s*(root|dest)\s*,", _l):
                    _dup.append(f"{os.path.basename(_p)}:{_i}")
        assert len(_dup) == 2, \
            f"装包样板（walk_dir(root, root, ...)）全包该只有 2 处（Pack.load + cmd_collapse 重读），" \
            f"实得 {len(_dup)} 处：{_dup} —— 命令里出现的就是手抄，改用 Pack.load(root)"
        # issue #3 回归：单入口形状下，两个**岛**里的 skill 是同一件事（正文不同语言、字面分贴近 0），
        # 但 related_skills 逐字相同 → dup 必须比到（入口层口径），propose 必须给出候选。
        # 旧实现只比同一父目录的兄弟：1 skill/岛 → 0 对，跨岛同题永远进不了候选集。
        _up = os.path.join(tmp, "dup-pack")
        for _isl, _nm, _desc in (
                ("island-a", "alpha", "Use when vetting an external skill before adopting it."),
                ("island-b", "beta", "当有人推荐一个第三方 skill、要先核实它装不装得上时用。")):
            _d = os.path.join(_up, "skills", "entry", "references", _isl, _nm)
            os.makedirs(_d, exist_ok=True)
            with open(os.path.join(_d, "SKILL.md"), "w") as f:
                f.write(f'---\nname: {_nm}\ndescription: "{_desc}"\nmetadata:\n  hermes:\n'
                        f'    related_skills: [shared-one, shared-two, shared-three]\n---\n\n# {_nm}\n')
        with open(os.path.join(_up, "skills", "entry", "SKILL.md"), "w") as f:
            f.write('---\nname: entry\ndescription: 入口。\n---\n\n# entry\n')
        _dupp = [r for r in dup_pairs(Pack.load(_up))
                 if {os.path.basename(r["a"].rstrip("/")), os.path.basename(r["b"].rstrip("/"))}
                 == {"alpha", "beta"}]
        assert _dupp, "issue #3：单入口形状下跨岛的同题对必须被比到（旧实现 0 对）"
        assert "entry" in _dupp[0]["scopes"] and "related_skills" in _dupp[0]["signals"], \
            ("该对必须来自入口层口径、靠 related_skills 命中，实得 "
             f"{_dupp[0]['scopes']} / {list(_dupp[0]['signals'])}")
        assert any("alpha" in p["where"] and "beta" in p["where"]
                   for p in propose_actions(_up)), "issue #3：propose 必须为跨岛同题给出 rewrite/merge 候选"
        # deliver（F 交付）：工作副本改完 → **默认**合回真包 main + push + 清 worktree/分支。
        # 旧口径是「真包只读、要一句『进入 production 模式』才动」——交付是流程的最后一步，不是等人点头的动作。
        _dp = os.path.join(tmp, "deliver-pack")
        os.makedirs(os.path.join(_dp, "skills", "d"), exist_ok=True)
        with open(os.path.join(_dp, "skills", "d", "SKILL.md"), "w") as f:
            f.write("---\nname: d\ndescription: 交付自检用。\n---\n\n# d\n")
        _bare = os.path.join(tmp, "deliver-remote.git")
        assert git(_dp, "init", "-q", "-b", "main") is not None, "自检需要 git"
        git(_dp, "init", "--bare", "-q", _bare)
        git(_dp, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        git(_dp, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
        git(_dp, "remote", "add", "origin", _bare)
        git(_dp, "push", "-q", "origin", "main")
        _wt = os.path.join(tmp, "deliver-ws")
        _od = os.path.join(tmp, "o-deliver")
        assert cmd_prepare(_dp, _od, dest=_wt, shape="single", executor="manual") == 0
        _dp_before = _rev(_dp)
        with open(os.path.join(_wt, "skills", "d", "SKILL.md"), "a") as f:
            f.write("\n改一行。\n")
        git(_wt, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
        git(_wt, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "改一行")
        assert cmd_deliver(_wt, _od) == 0, "交付该成功"
        _dp_after = _rev(_dp)
        assert _dp_after != _dp_before, "交付后真包 main 必须前进"
        _ls = (git(_dp, "ls-remote", "origin", "refs/heads/main").stdout or "").split()
        _full = git(_dp, "rev-parse", "HEAD").stdout.strip()
        assert _ls and _ls[0] == _full, f"远端 main {(_ls or [''])[0][:9]} != 本地 {_full[:9]}（push 没回读一致）"
        assert not os.path.isdir(_wt), "交付该把 worktree 删掉"
        _brs = (git(_dp, "branch", "--list", "skillweave/deliver-pack").stdout or "").strip()
        assert _brs == "", f"交付该把分支删掉，实得 {_brs!r}"
        assert cmd_deliver(_dp, _od) == 1, "对主 clone 本身跑 deliver 该拒（没有可合回的分支）"
        # CLI 参数错误消息（issue #08）：统一格式 = [命令] 错误 / 用法 / 说明；缺命令给简要帮助。
        def _cli(*argv):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(list(argv))
            return rc, buf.getvalue()

        rc, o = _cli("judge", pack)
        assert rc == 2 and "[judge] 错误" in o and "--prompts" in o \
            and "用法: weave.py judge" in o and "说明:" in o, o
        rc, o = _cli("score")
        assert rc == 2 and "[score] 错误" in o and "--key" in o and "--judge" in o, o
        rc, o = _cli("apply", pack)
        assert rc == 2 and "--proposals" in o and "--revert" in o, o
        rc, o = _cli("verify", pack)
        assert rc == 2 and "--state" in o, o
        rc, o = _cli("verify", pack, "--state", "state.json")
        assert rc == 2 and "--expect-fixed" in o, o
        rc, o = _cli("collapse", pack, "--apply")
        assert rc == 2 and "--description" in o, o
        rc, o = _cli("disclosure")
        assert rc == 2 and "缺少 <pack>" in o and "用法: weave.py disclosure" in o, o
        rc, o = _cli()
        assert rc == 2 and "常用命令" in o and "disclosure" in o, o
        rc, o = _cli("--help")
        assert rc == 0 and "常用命令" in o, o
        rc, o = _cli("disclosure", "--help")
        assert rc == 0 and "用法: weave.py disclosure" in o, o
        print("[self-test] ✅ 层（pack→类目→skill）/ 折叠 description / 孤儿 / 悬空 / "
              "围栏内标题 / 两次一致 / 硬编码路径 / 内嵌密钥 / 提案器四类动作 / "
              "layers↔audit 口径对拍 / 派发划批 / 验收（集合级回归拦截 + 梯子）/ "
              "交付 deliver（默认合回真包 main + push 回读 + 清 worktree/分支） / "
              "issue #1（未跟踪闸）/ issue #2（冒号值仍是合法 YAML）/ "
              "issue #3（跨岛同题必须被比到）/ issue #4（节点框数 == 文档数）/ "
              "issue #5（产物默认落包内 .skillweave/）/ "
              "ticket 02（templates/examples/tests 资源目录自动豁免） / "
              "ticket 04（披露深度 L3+ 只警告不退出） / "
              "ticket 05（脚本不做悬空检查 / 目录级点名 / self-check） / "
              "ticket 06（执行者配置：prepare 询问并持久化） / "
              "ticket 07（dispatch 读执行者配置 → prompt 末尾输出执行说明） / "
              "issue #08（子命令参数错误统一格式 + 简要帮助）/ "
              "工具目录 .skillweave/ 非成员（免检表读得到、档案不进度量）"
              "—— 全过")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
