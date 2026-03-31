# Claude Tools

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
English | [简体中文](README.zh-CN.md)

A curated collection of Claude Code extensions — Skills, Hooks, custom commands, and more.

## Skills

Skills are prompt + script bundles that extend Claude Code's capabilities. Once installed, they are triggered automatically when Claude recognizes a matching request.

| Name | Description | Version |
|------|-------------|---------|
| [weixin-article-fetcher](skills/weixin-article-fetcher/) | Fetch WeChat public account articles and convert them to clean Markdown. Supports single and batch downloads. | v1.0.0 |
| [r2-upload](skills/r2-upload/) | Upload files or images to Cloudflare R2 and get back a permanent public URL. Supports local path, base64 string, base64 file, and remote URL. | v1.0.0 |

## Installation

### Install a Skill

Copy the skill directory into Claude Code's skills folder and register it in `~/.claude/settings.json`.

Using `weixin-article-fetcher` as an example:

```bash
# 1. Clone the repository
git clone https://github.com/JiangDing1990/claude-tools.git

# 2. Copy the skill directory into Claude Code's skills path
cp -r claude-tools/skills/weixin-article-fetcher ~/.claude/skills/
```

Restart Claude Code — skills are auto-loaded from `~/.claude/skills/`.

> For the full skill directory spec, see [SKILL_SPEC.md](SKILL_SPEC.md).

## Repository Structure

```
claude-tools/
├── skills/                  # Claude Code Skills
│   └── <skill-name>/
│       ├── SKILL.md         # Skill entry point (frontmatter + instructions)
│       ├── requirements.txt # Python dependencies (if any)
│       ├── scripts/         # Helper scripts
│       ├── references/      # Supplementary reference docs (optional)
│       └── README.md        # Optional: human-facing documentation
├── agents/                  # Claude Code Agents (reserved)
├── commands/                # Custom commands (reserved)
├── hooks/                   # Workflow hooks (reserved)
├── plugins/                 # Claude Code plugins (reserved)
├── SKILL_SPEC.md            # Skill authoring specification
├── CONTRIBUTING.md          # Contribution guide
├── CHANGELOG.md             # Change log
└── LICENSE
```

## Contributing

Contributions are welcome — new skills, bug fixes, or documentation improvements. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a PR.

## License

[MIT](LICENSE) © jiangding1990
