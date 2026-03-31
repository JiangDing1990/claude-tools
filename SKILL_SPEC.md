# Skill 编写规范

本文档定义了 claude-tools 仓库中 skill 的目录结构、必填字段和最佳实践。

---

## 目录结构

```
skills/<skill-name>/
├── SKILL.md                 # 必须：skill 入口文件
├── scripts/                 # 建议：辅助脚本目录
│   └── main.py              # 主脚本（命名不限）
├── references/              # 可选：补充参考文档
│   └── notes.md
├── requirements.txt         # 如有 Python 依赖则必须提供
└── .claude/
    └── settings.local.json  # 可选：该 skill 所需的权限声明
```

### 命名规范

- 目录名：全小写，单词间用连字符，例如 `weixin-article-fetcher`
- 脚本名：下划线分隔，例如 `fetch_article.py`

---

## SKILL.md 规范

`SKILL.md` 是 Claude Code 加载 skill 的入口，**必须**包含 YAML frontmatter。

### Frontmatter 字段

```yaml
---
name: skill-name          # 必须：与目录名一致
description: |            # 必须：触发说明，需包含典型触发场景和关键词
  What this skill does.
  Trigger when: user asks to X, Y, Z.
  Also trigger for: "中文触发词1"、"中文触发词2".
metadata:
  version: v1.0.0         # 可选：语义化版本号
  author: your-github-id  # 可选：作者 GitHub ID
---
```

**`description` 写作要点：**
- 第一句话说清楚 skill 做什么
- 明确列出触发场景（英文 + 中文关键词）
- 不要超过 5 行，Claude 会用它来判断是否触发该 skill

### 正文结构（推荐）

```markdown
# Skill 标题

一句话简介。

---

## How It Works（可选）

简要说明实现原理。

---

## Workflow

### Step 1: 安装依赖（如需）
### Step 2: 运行
### Step 3: 查看输出

---

## CLI Reference（如有脚本）

参数说明表格或 --help 输出。

---

## Error Handling（如有）

常见错误及处理方式。
```

---

## 依赖声明

### Python 脚本

必须提供 `requirements.txt`，格式如下：

```
requests>=2.28.0
beautifulsoup4>=4.12.0
markdownify>=0.11.0
```

在 `SKILL.md` 的 Workflow 中说明安装命令：

```bash
pip install -r requirements.txt
```

### Node.js 脚本

提供 `package.json`，锁文件（`package-lock.json` 或 `pnpm-lock.yaml`）**不**提交到仓库。

---

## 权限声明

如果 skill 需要执行特定命令，在 `.claude/settings.local.json` 中声明所需权限：

```json
{
  "permissions": {
    "allow": [
      "Bash(pip install:*)",
      "Bash(python3:*)"
    ]
  }
}
```

该文件已在 `.gitignore` 中排除，**不会**提交到仓库，仅供本地使用参考，在 SKILL.md 中说明需要哪些权限即可。

---

## README 表格条目

每个 skill 合并进仓库后，需在根目录 `README.md` 的 Skills 表格中新增一行：

```markdown
| [skill-name](skills/skill-name/) | 一句话描述 | v1.0.0 |
```

---

## 版本规范

Skill 版本遵循 `vMAJOR.MINOR.PATCH`：

| 变更类型 | 版本位 |
|----------|--------|
| 新增功能 | MINOR |
| Bug 修复 / 文档更新 | PATCH |
| 不兼容的行为变更 | MAJOR |

版本号在 `SKILL.md` frontmatter 的 `metadata.version` 字段中维护，同步更新 `README.md` 表格。

---

## 最佳实践

- **最小依赖**：能用标准库就不引入第三方包
- **错误友好**：脚本报错信息用中文，面向使用者而非开发者
- **增量安全**：批量操作要支持断点续传，避免重复执行副作用
- **幂等性**：同一输入多次执行，结果相同
- **文档优先**：先写 SKILL.md 的使用说明，再写实现代码
