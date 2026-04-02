# Claude Tools

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[English](README.md) | 简体中文

一个 Claude Code 工具链仓库，包含 Skills、Hooks、自定义命令等，持续收录高质量的 Claude Code 扩展工具。

## Skills

Skills 是用于扩展 Claude Code 能力的提示词 + 脚本组合，安装后可通过 `/skill-name` 触发。

| 名称 | 说明 | 版本 |
|------|------|------|
| [weixin-article-fetcher](skills/weixin-article-fetcher/) | 抓取微信公众号文章，转换为干净的 Markdown，支持单篇和批量下载 | v1.0.1 |
| [r2-upload](skills/r2-upload/) | 上传文件/图片到 Cloudflare R2，返回永久公开 URL，支持本地路径、base64、base64 文件、远程 URL 四种��入 | v1.0.0 |

## 安装

### 方式一：远程安装（推荐）

无需克隆仓库，一行命令直接安装指定 skill：

```bash
npx skills add JiangDing1990/claude-tools --skill weixin-article-fetcher
npx skills add JiangDing1990/claude-tools --skill r2-upload
```

重启 Claude Code 即可使用。

### 方式二：手动安装

```bash
# 1. 克隆仓库
git clone https://github.com/JiangDing1990/claude-tools.git

# 2. 将 skill 目录复制到 Claude Code skills 路径
cp -r claude-tools/skills/weixin-article-fetcher ~/.claude/skills/
```

重启 Claude Code，skills 会从 `~/.claude/skills/` 自动加载，无需手动注册。

> 详细的 skill 目录结构规范见 [SKILL_SPEC.md](SKILL_SPEC.md)。

## 目录结构

```
claude-tools/
├── skills/                  # Claude Code Skills
│   └── <skill-name>/
│       ├── SKILL.md         # Skill 入口（frontmatter + 使用说明）
│       ├── requirements.txt # Python 依赖（如有）
│       ├── scripts/         # 辅助脚本
│       ├── references/      # 补充参考文档（可选）
│       └── README.md        # 可选：面向人类读者的说明文档
├── agents/                  # Claude Code Agents（预留）
├── commands/                # 自定义命令（预留）
├── hooks/                   # 工作流钩子（预留）
├── plugins/                 # Claude Code 插件（预留）
├── SKILL_SPEC.md            # Skill 编写规范
├── CONTRIBUTING.md          # 贡献指南
├── CHANGELOG.md             # 变更记录
└── LICENSE
```

## 贡献

欢迎提交新的 skill 或改进现有工具，请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

[MIT](LICENSE) © jiangding1990
