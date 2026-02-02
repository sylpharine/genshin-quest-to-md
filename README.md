# Genshin Impact Quest JSON to Markdown

把任务剧情 JSON 转为 Markdown 的小脚本。
> 请自行前往[安柏网](https://ambr.top/chs/archive/quest)获取剧情文本的 JSON 格式文件

## 功能
- 输出章节标题与描述
- 输出任务标题与描述
- 输出对话（角色：文本）
- 保留分支对话并在后续合并重复剧情
- 可替换旅行者名字（默认：旅行者）
- 可指定空角色名占位（默认：Unknown）

## 环境
- Python 3.8+

## 使用
```bash
python3 json2md.py "在岩间.json" -o "在岩间.md"
```

使用 uv 脚本入口：
```bash
uv run json2md "在岩间.json" -o "在岩间.md"
```

## 参数
- `-o, --output`：输出 Markdown 文件路径（不传则输出到 stdout）
- `--encoding`：输入文件编码，默认 `utf-8`
- `--unknown-role`：空角色名占位，默认 `Unknown`
- `--traveler-name`：替换 `#{NICKNAME}` / `Traveler` / `Traveller` / `玩家`，默认 `旅行者`
- `--traveler-gender`：替换 `{M#}{F#}` 形式的性别占位，`M` 或 `F`，默认 `F`
- `--wanderer-name`：替换 `#{REALNAME[...]}` 占位，默认 `流浪者`
- `--hide-branches`：隐藏分支，只选择一条路径（默认展示所有分支）
- `--branch-choice`：指定分支选择，如 `402231309-player=2`（可重复、可用逗号分隔）
- `--branch-default`：隐藏分支时默认选择第几条，默认 `1`
- `--format-file`：格式配置文件（JSON），支持模板或自定义渲染器
- `--filter-role`：仅输出指定角色的对话（可重复）
- `--exclude-role`：排除指定角色的对话（可重复）
- `--filter-keyword`：仅输出包含关键词的对话（可重复）
- `--exclude-keyword`：排除包含关键词的对话（可重复）
- `--filter-task`：仅输出任务标题包含关键词的任务（可重复）
- `--filter-id`：仅输出匹配指定 ID 前缀的内容（可重复）
- `--stream`：流式解析大 JSON（仅模板渲染）

流式模式说明：
- 仅支持模板渲染（`renderer` 插件不支持）
- 适合超大 JSON，减少内存占用

## 示例
```bash
# 自定义旅行者名
python3 json2md.py "在岩间.json" -o "在岩间.md" --traveler-name "荧"

# 自定义未知角色占位
python3 json2md.py "在岩间.json" -o "在岩间.md" --unknown-role "未知"

# 自定义旅行者性别
python3 json2md.py "在岩间.json" -o "在岩间.md" --traveler-gender "M"

# 自定义流浪者名
python3 json2md.py "在岩间.json" -o "在岩间.md" --wanderer-name "流浪者"

# 隐藏分支并选择特定分支
python3 json2md.py "在岩间.json" -o "在岩间.md" --hide-branches --branch-choice "402231309-player=2"

# 使用模板配置文件
python3 json2md.py "在岩间.json" -o "在岩间.md" --format-file "format_examples/templates.default.json"

# 使用自定义渲染器
python3 json2md.py "在岩间.json" -o "在岩间.md" --format-file "format_examples/renderer.novel.json"

# 过滤示例：仅输出角色「钟离」且包含“月亮”的对话
python3 json2md.py "在云间.json" -o "在云间.md" --filter-role "钟离" --filter-keyword "月亮"

# 过滤示例：仅输出任务标题包含“前往”的任务
python3 json2md.py "在云间.json" -o "在云间.md" --filter-task "前往"
```

## 自定义输出格式
### 模板模式（templates）
`format_examples/templates.default.json` 是完整示例，你可以修改其中模板：
- `chapter_title` / `chapter_desc`
- `task_title` / `task_desc`
- `dialog_line` / `dialog_cont`
- `branch_label`
- `black_screen`

模板可用变量示例：`{chapter_num}`, `{chapter_title}`, `{task_title}`, `{role}`, `{text}`, `{index}`。
ID 模板可用变量：`{story_id}`, `{task_id}`, `{dialog_id}`。
你可以通过 `options.skip_fields` 禁用指定字段渲染，或将模板值设为空字符串。
你也可以在 `options` 中配置过滤器：`filter_roles` / `exclude_roles` / `filter_keywords` / `exclude_keywords` / `filter_tasks` / `filter_ids`。

ID 相关说明：
- `story_id`（如 40223）、`task_id`（如 4022302）、`dialog_id`（如 402230201）
- 默认在 `skip_fields` 中不渲染
- `filter_ids` 支持前缀匹配与范围匹配（如 `402220201-402220230`）
- 范围匹配会按范围端点的位数对目标 ID 前缀进行比较（例如 `40223-40224` 会匹配 `4022301`）

### 渲染器模式（renderer）
`format_examples/renderer.novel.json` 指定了一个 Python 渲染器：
- `renderer`: `path/to/file.py:function`
- `options`: 传给渲染器的参数

渲染器函数签名：
```python
def render(doc, options) -> str:
    ...
```

`doc` 结构包含：
- `chapter_num`, `chapter_title`, `chapter_desc`
- `tasks`: `[{title, desc, nodes}]`
- `nodes` 支持 `dialog` 和 `branch`
  - `dialog`: `{type, role, text, is_black_screen}`
  - `branch`: `{type, id, options}`，`options` 是多个节点列表

渲染器示例已更新以匹配当前项目字段：
- 支持 `story_id` / `task_id` / `dialog_id`
- 支持 `skip_fields`（与模板一致）

## 项目结构
```text
src/genshhin_json_to_md/
  cli.py            # CLI 入口与参数解析
  config.py         # 全局配置与默认模板
  placeholders.py   # 占位符与性别替换
  parser.py         # JSON -> IR 结构（含分支合并）
  filters.py        # 过滤器（角色/关键词/任务/ID）
  stream.py         # 流式解析与渲染
  renderers/
    templates.py    # 模板渲染器
    plugin.py       # 渲染器插件加载
```

## 架构图
```text
           +-----------------+
           |      CLI        |
           +--------+--------+
                    |
                    v
        +-----------+------------+
        |   Placeholders/Config  |
        +-----------+------------+
                    |
                    v
             +------+------+
             |   Parser    |-----> IR (doc)
             +------+------+
                    |
                    v
             +------+------+
             |  Filters    |
             +------+------+
                    |
        +-----------+-----------+
        |                       |
        v                       v
 +--------------+       +---------------+
 | Templates    |       | Renderer Plug |
 +------+-------+       +-------+-------+
        |                       |
        +-----------+-----------+
                    v
               Markdown

流式模式：
CLI -> stream.py -> filters.py -> templates.py -> Markdown
```

## 默认输出格式示例
```md
# 奔霄颂玉轮 第二幕 《在岩间》
章节描述...

## 任务标题
任务描述
角色：对白
角色：对白

【分支1】
  角色：对白
【分支2】
  角色：对白
...
```
