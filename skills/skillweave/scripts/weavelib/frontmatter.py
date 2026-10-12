"""frontmatter 的解析与**安全写出**（YAML 子集，见契约 §7.1）。

从 weave.py 拆出，逻辑未改。"""
import re




def parse_frontmatter(text):
    """返回 (meta, body, body 起始行号)。只为 frontmatter 子集写的最小 YAML：
    支持 `key: value`、`key: >-` / `|` 折叠块、引号、续行。

    **注意**：这是手写的宽松子集，比真 YAML 解析器宽 —— 它能吃下 `description: a: b` 这种
    真解析器会报错的写法。所以「工具自己读得通」不能当成文件合法（issue #2 就是这么被掩盖的）；
    要判合法性得用 `frontmatter_selfcheck`（写盘自检）或真 YAML 解析器（外部消费者）。"""
    if not text.startswith("---"):
        return {}, text, 1
    lines = text.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end = i
            break
    if end is None:
        return {}, text, 1
    parts, key = {}, None
    for ln in lines[1:end]:
        m = re.match(r"^([A-Za-z_][\w.-]*)\s*:\s*(.*)$", ln)
        if m:
            key = m.group(1)
            parts[key] = [m.group(2)]
        elif key is not None:
            parts[key].append(ln.strip())
    meta = {}
    for k, vs in parts.items():
        head, rest = vs[0].strip(), [v for v in vs[1:] if v and not v.startswith("#")]
        if head in (">-", ">", "|-", "|", "|+", ">+"):
            val = " ".join(rest) if head.startswith(">") else "\n".join(rest)
        elif head == "" and rest:
            val = " ".join(rest)
        else:
            val = " ".join([head] + rest)
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            quoted = val[0]
            val = val[1:-1]
            if quoted == '"':                    # 双引号风格要解转义，否则工具读回的值与真解析器不一致
                val = _yaml_unescape_double(val)
        meta[k] = val
    return meta, "\n".join(lines[end + 1:]), end + 2




# 未加引号的安全标量：首字符不能是 YAML 指示符，其余不许出现 `:` `#` 引号反斜杠与空白控制符
_PLAIN_SAFE = re.compile(r"^[^\s\-?:,\[\]{}#&*!|>'\"%@`][^:\"'\\#\n\r\t]*$")


_YAML_RESERVED = {"true", "false", "null", "yes", "no", "on", "off", "~", ""}




def _yaml_unescape_double(s):
    """双引号标量里那几个转义（与 `yaml_scalar` 写出的集合对称）。纯 stdlib。"""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "n":
                out.append("\n")
            elif n == "t":
                out.append("\t")
            elif n == "r":
                out.append("\r")
            elif n == '"':
                out.append('"')
            elif n == "\\":
                out.append("\\")
            elif n == "x" and i + 3 < len(s):
                try:
                    out.append(chr(int(s[i + 2:i + 4], 16)))
                    i += 4
                    continue
                except ValueError:
                    out.append(c)
                    i += 1
                    continue
            else:
                out.append(n)
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)




def yaml_scalar(value):
    """把一个**任意字符串**写成合法 YAML 标量（纯 stdlib，不引 PyYAML —— 契约 §6）。

    安全的值原样写（保持可读），其余整体加双引号并转义。这样 `: `、` #`、块指示符 `>-`/`|`、
    前导 `-`、引号、换行一律不再有歧义 —— 以前是裸拼（`description: %s`），值里带 `: ` 就写出
    非法 YAML（issue #2：63 个 pack 里 35 个入口 frontmatter 解析失败）。"""
    if value and _PLAIN_SAFE.match(value) and value.lower() not in _YAML_RESERVED:
        return value
    body = (value.replace("\\", "\\\\").replace('"', '\\"')
            .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t"))
    return '"' + body + '"'




def frontmatter_selfcheck(text):
    """最小 YAML 合法性检查（不引 PyYAML）：返回错误列表，空 = 通过。

    盯的就是 issue #2 那类坏文件：未加引号的标量里出现 `: `（真 YAML 会读成嵌套映射）、
    引号没闭合、空标量。块标量（`>-` / `|`）本身合法，只要求它后面有缩进的内容行。"""
    errs = []
    if not text.startswith("---"):
        return ["frontmatter 不以 `---` 开头"]
    lines = text.split("\n")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")), None)
    if end is None:
        return ["frontmatter 没有收尾的 `---`"]
    for i, ln in enumerate(lines[1:end], start=2):
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w.-]*)\s*:\s*(.*)$", ln)
        if not m:
            errs.append(f"第 {i} 行不是 `key: value`：{ln!r}")
            continue
        v = m.group(2).strip()
        if v == "":
            errs.append(f"第 {i} 行 `{m.group(1)}` 是空标量")
        elif v[0] in "\"'":
            if len(v) < 2 or v[-1] != v[0]:
                errs.append(f"第 {i} 行引号没闭合：{ln!r}")
        elif re.match(r"^[|>][-+]?$", v):
            if i >= end or not lines[i].startswith((" ", "\t")):
                errs.append(f"第 {i} 行是块指示符 `{v}`，但后面没有缩进的内容行")
        elif ": " in v or v.endswith(":"):
            errs.append(f"第 {i} 行未加引号的标量里有 `: `（真 YAML 会读成嵌套映射）：{ln!r}")
    return errs
