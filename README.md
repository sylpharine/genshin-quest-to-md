# genshhin quest to markdown

把任务剧情 JSON 转为 Markdown 的小脚本。
> 请自行前往[安柏网](https://ambr.top/chs/archive/quest)获取剧情的JSON格式文件

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
```

## 输出格式示例
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
后续公共对白...
```
