# 待办 · SkillWeave

由 `weave.py disclosure` 生成。术语见 `DISCLOSURE.md` 头部术语表。

- **待办 16 条**（机械可判 0 · 待模型 16）
- **已豁免 0 条（自动 0 · 手动 0）**（按包里 `.skillweave/waivers.txt`，共 0 条规则）

## 待办（照着做）

| # | 文档 | 问题 | 数字 | 建议动作 | 谁判 |
|---|---|---|---|---|---|
| 1 | `skills/skillweave/scripts/weavelib/__init__.py` | 到不了根 | 974 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 2 | `skills/skillweave/scripts/weavelib/analysis.py` | 到不了根 | 19835 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 3 | `skills/skillweave/scripts/weavelib/cli.py` | 到不了根 | 14089 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 4 | `skills/skillweave/scripts/weavelib/common.py` | 到不了根 | 8347 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 5 | `skills/skillweave/scripts/weavelib/deliver.py` | 到不了根 | 11423 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 6 | `skills/skillweave/scripts/weavelib/disclosure.py` | 到不了根 | 27761 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 7 | `skills/skillweave/scripts/weavelib/frontmatter.py` | 到不了根 | 6927 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 8 | `skills/skillweave/scripts/weavelib/graph.py` | 到不了根 | 27032 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 9 | `skills/skillweave/scripts/weavelib/model.py` | 到不了根 | 14540 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 10 | `skills/skillweave/scripts/weavelib/pack.py` | 到不了根 | 4184 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 11 | `skills/skillweave/scripts/weavelib/render.py` | 到不了根 | 23980 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 12 | `skills/skillweave/scripts/weavelib/selftest.py` | 到不了根 | 50873 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 13 | `skills/skillweave/scripts/weavelib/transform.py` | 到不了根 | 40494 B | 判：该被引用（加一条引用）· 该删 · 还是刻意的（免检） | 待模型 |
| 14 | `skills/skillweave/scripts/weavelib/graph.py` | 悬空 | 1 条（162: `references/x.md`） | **先判**：包内路径写错（改路径）· 还是在说包外文件（免检）→ 再动手 | 待模型 |
| 15 | `skills/skillweave/scripts/weavelib/model.py` | 悬空 | 1 条（79: `templates/README.md`） | **先判**：包内路径写错（改路径）· 还是在说包外文件（免检）→ 再动手 | 待模型 |
| 16 | `skills/skillweave/scripts/weavelib/selftest.py` | 悬空 | 10 条（36: `references/gone.md` · 36: `references/guide.md` · 37: `templates/README.md` …） | **先判**：包内路径写错（改路径）· 还是在说包外文件（免检）→ 再动手 | 待模型 |

## 已豁免 · 自动（资源目录：`templates/` · `examples/` · `tests/`）

这些文件不要求被 `SKILL.md` 显式引用，**无需**写入 `.skillweave/waivers.txt`；若确实被引用，仍验证路径正确性（悬空照报）。

| 文档 | 问题 | 数字 | 理由 |
|---|---|---|---|
| — | — | — | 没有自动豁免的资源文件 |

## 已豁免 · 手动（匹配了 waivers.txt，不动它）

| 文档 | 问题 | 数字 | 理由 |
|---|---|---|---|
| — | — | — | 没有命中豁免规则 |

## 免检表长什么样（`<pack>/.skillweave/waivers.txt`）

```
# 一行一条：<glob>  两个以上空格  理由（# 开头是注释）
# templates/ · examples/ · tests/ 下的文件已自动豁免，不必写进来；waivers.txt 只写其他特殊情况。
*/assets/*.png             给人看的图，Agent 不读
*/test-prompts.json        测试留档，本来就不该被披露
```

豁免是**包主的判断**，写在包里、工具只匹配；没写规则的按上面的建议动作办。
