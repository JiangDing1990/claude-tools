# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).  
Each skill maintains its own version independently; changes are grouped by release date.

## [Unreleased]

## [2026-03-31]

### Added

- **r2-upload** `v1.0.0` — Cloudflare R2 文件上传 skill
  - 支持本地文件、base64/data-URL、base64 文件、远程 URL 四种输入模式
  - 按 MIME 类型自动选择存储前缀（images / videos / audios / files）
  - 返回结构化 JSON，含永久公开 URL、文件大小、Content-Type 等字段
  - 内置环境检查脚本 `check_env.py`，首次配置或排查问题时使用
  - 500 MB 上传限制，防止意外 OOM
  - 设计为其他 skill（图片生成、封面、信息图等）的通用上传模块
- **weixin-article-fetcher** `v1.0.0` — 微信公众号文章抓取 skill
  - 通过伪造 iOS WeChat User-Agent 绕过滑块验证码，无需浏览器
  - 支持单篇、多篇、批量（`--batch`）三种抓取模式
  - 自动转换为 Markdown，含封面图、标题、正文
  - 断点续传：已下载的 URL 自动跳过，结果写入 `results.json`
  - 限流处理：HTTP 429 指数退避重试（3s → 6s → 9s）
  - User-Agent 池随机化，降低指纹识别风险
- `SKILL_SPEC.md` — Skill 编写规范文档
- `CONTRIBUTING.md` — 贡献指南
- `LICENSE` — MIT 许可证
- `.github/workflows/validate-skills.yml` — CI：校验 skill 目录结构
