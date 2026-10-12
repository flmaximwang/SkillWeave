"""基础工具与全局常量：读文件 / token 估算 / 摘要 / 文本解析（无内部依赖）。

从 weave.py 拆出，逻辑未改。"""
import hashlib, json, os, re



FENCE = ("```", "~~~")


# 路径字符集含非 ASCII：包里的文件名可能是中文（实测 Loomerto 的段落文件），
# 只认 ASCII 会让这些文件被判成「到不了根」——那是工具的盲点，不是包的问题。
PATH_RE = re.compile(
    r"(?:[A-Za-z0-9_./-]|[\u0080-\uffff])+\.(?:md|markdown|py|sh|bash|js|ts|json|ya?ml|txt|csv|tsv|toml|ini|cfg|png|jpe?g|svg|gif|html|pdf)\b")


SCRIPT_EXT = {".py", ".sh", ".bash", ".js", ".ts", ".rb", ".pl"}


ASSET_EXT = {".png", ".jpg", ".jpeg", ".svg", ".gif", ".pdf", ".zip", ".ico", ".woff", ".ttf"}





def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""




def est_tokens(text):
    """契约口径：CJK 字符 ×1 + 其它字符 ×0.25（估算，报告里必须写明）。"""
    cjk = sum(1 for ch in text if 0x2E80 <= ord(ch) <= 0x9FFF
              or 0x3000 <= ord(ch) <= 0x303F or 0xFF00 <= ord(ch) <= 0xFFEF)
    return int(round(cjk + (len(text) - cjk) * 0.25))




def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()




DIGEST_IGNORE = {"version", "updated", "date", "modified"}   # 改这些不算内容变化（内化自 asa 的 digest 口径）




def content_digest(meta, body):
    """内容指纹：忽略版本类键的 frontmatter + 正文。用来判「可 diff」——同一内容必得同一指纹。"""
    keep = {k: v for k, v in meta.items() if k not in DIGEST_IGNORE}
    return hashlib.sha256(
        (json.dumps(keep, sort_keys=True, ensure_ascii=False) + "\n" + body).encode("utf-8")).hexdigest()




def body_counts(body, sections):
    """「该拆」的可量信号（内化自 claude-skills-cli 的告警口径）。
    ponytail: 段落切分按空行 + 排除以 # / 围栏 / 表格 / 标签开头的块；围栏内的段落仍可能被计入，够用。"""
    blocks = body.count("```") // 2
    paras = [p for p in re.split(r"\n\s*\n", body)
             if p.strip() and not p.lstrip().startswith(("#", "```", "~~~", "|", "<"))]
    return {"code_blocks": blocks, "sections": sections,
            "long_paragraphs": sum(1 for p in paras if len(p.split()) > 100),
            "todos": len(re.findall(r"\b(?:TODO|FIXME)\b", body))}




def description_health(desc):
    """`--description` 的体检（issue #2 的建议 3）：返回警告列表。
    值本身照写（`yaml_scalar` 保证合法），但下面这些征兆要让调用方看见 ——
    它们多半意味着上游把 YAML 折叠块或标题原样拼进了值里。"""
    warns = []
    if ": " in desc:
        warns.append("值里有裸 `: ` —— 不加引号的标量会被真 YAML 读成嵌套映射（本工具已改成加引号，仍提醒）")
    frags = re.findall(r"(?:^|\s)([|>][-+]?)(?=\s|$)", desc)
    if frags:
        warns.append(f"值里有 {len(frags)} 处裸块指示符片段（{', '.join(sorted(set(frags)))}）"
                     "—— 多半是上游把 `>-` / `|` 折叠块原样拼了进来")
    if desc != desc.strip():
        warns.append("值首尾有空白，已 strip")
    return warns




def fence_lines(body):
    """处于代码围栏内的**行号集合**（1-based，相对 body）。围栏里的路径是示例，不是本 skill 的引用。"""
    inside, f = set(), False
    for i, ln in enumerate(body.split("\n"), start=1):
        if ln.strip().startswith(FENCE):
            f = not f
            inside.add(i)
            continue
        if f:
            inside.add(i)
    return inside




def headings(body, body_start_line):
    """正文标题；代码围栏内的 `#` 不算（逐行维护围栏状态）。"""
    out, fence = [], None
    for i, ln in enumerate(body.split("\n")):
        s = ln.strip()
        if s.startswith(FENCE):
            fence = None if fence else s[:3]
            continue
        if fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            out.append({"line": body_start_line + i, "level": len(m.group(1)),
                        "title": m.group(2).strip()})
    return out




def first_sentence(body, body_start_line):
    """正文首个非标题、非围栏、非空段落的首句（摘要回退源）。"""
    fence = False
    for i, ln in enumerate(body.split("\n")):
        s = ln.strip()
        if s.startswith(FENCE):
            fence = not fence
            continue
        if fence or not s or s.startswith("#") or s.startswith("<!--"):
            continue
        sent = re.split(r"(?<=[。！？.!?])\s", s)[0]
        return sent[:200], body_start_line + i
    return None, None




def kind_of_file(rel):
    name = os.path.basename(rel)
    up = name.upper()
    if name == "SKILL.md":
        return "instructions"
    if up.startswith("README"):
        return "readme"
    if up.startswith(("LICENSE", "COPYING")):
        return "license"
    head = rel.split("/")[0]
    if head == "references":
        return "reference"
    if head == "scripts":
        return "script"
    if head == "assets":
        return "asset"
    ext = os.path.splitext(name)[1].lower()
    if ext in SCRIPT_EXT:
        return "script"
    if ext in ASSET_EXT:
        return "asset"
    return "other"




def extract_declared_refs(body, skill_rel):
    """正文里**真实出现**的相对路径引用：反引号片段 + markdown / wiki 链接。"""
    cands = [(m.group(1), m.start()) for m in re.finditer(r"`([^`\n]{1,200})`", body)]
    cands += [(m.group(1), m.start()) for m in re.finditer(r"\]\(([^)\s]{1,200})\)", body)]
    out, seen = [], set()
    for c, off in cands:
        if "://" in c:                       # URL 不是本 skill 的相对引用（否则 www.x/a/b.md 会被当成路径）
            continue
        for mm in PATH_RE.finditer(c):
            target = mm.group(0)
            if target in seen or "://" in target:
                continue
            seen.add(target)
            line = body[:off + mm.start()].count("\n") + 1
            out.append((target, line))
    return out




def strip_private(node):
    node.pop("_kinds", None)
    node.pop("has_skill", None)
    for c in node["children"]:
        strip_private(c)




def count(node):
    return 1 + sum(count(c) for c in node["children"])
