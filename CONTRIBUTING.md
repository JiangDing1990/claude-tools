# 贡献指南

感谢你对 claude-tools 的关注！欢迎提交新 skill、修复 bug 或改进文档。

## 贡献方式

### 报告问题

在 [Issues](https://github.com/JiangDing1990/claude-tools/issues) 中提交，请尽量包含：
- 使用的 Claude Code 版本
- 复现步骤
- 期望行为 vs 实际行为

### 提交代码

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feat/your-skill-name`
3. 按照 [SKILL_SPEC.md](SKILL_SPEC.md) 规范开发
4. 提交 PR，描述清楚改动内容和测试方式

## 贡献新 Skill

### 目录结构

每个 skill 放在 `skills/<skill-name>/` 目录下，最简结构如下：

```
skills/your-skill/
├── SKILL.md          # 必须：skill 入口文件（含 frontmatter）
├── requirements.txt  # 如有 Python 依赖则必须
├── scripts/          # 建议：辅助脚本
│   └── main.py
└── references/       # 可选：补充文档
    └── notes.md
```

完整规范见 [SKILL_SPEC.md](SKILL_SPEC.md)。

### SKILL.md frontmatter 必填字段

```yaml
---
name: your-skill-name
description: 一句话描述（同时作为 Claude Code 的触发说明，要包含触发场景）
metadata:
  version: v1.0.0
  author: your-github-id
---
```

### PR Checklist

提交 PR 前请确认：

- [ ] `SKILL.md` 包含完整的 frontmatter（`name`、`description`）
- [ ] 有清晰的使用示例
- [ ] 脚本中的依赖已在 `requirements.txt` 或 `SKILL.md` 中声明
- [ ] 本地测试通过
- [ ] 已在根目录 `README.md` 的 Skills 表格中添加条目
- [ ] 已在 `CHANGELOG.md` 中记录变更

## 代码规范

- Python 脚本遵循 PEP 8
- 优先使用标准库，尽量减少外部依赖
- 错误信息使用中文（面向中文用户的工具）

## 提问

有任何问题欢迎在 [Discussions](https://github.com/JiangDing1990/claude-tools/discussions) 中发起讨论。
