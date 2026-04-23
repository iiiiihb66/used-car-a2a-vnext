# Distribution

## 三入口策略

这个项目按三类入口分发：

1. GitHub
2. Web 首页
3. 微信小程序

## 1. GitHub

GitHub 是源码、安装和 Agent 接入的中心入口。

包含：

- `README.md`
- `skill.md`
- `openapi.json`
- `AGENTS.md`

## 2. Web 首页

`site/` 目录下是静态首页，用于：

- 给人看产品介绍
- 展示三入口结构
- 连接 GitHub / API / 小程序

适合接：

- Vercel
- Cloudflare Pages
- Netlify
- CloudBase 静态托管

## 3. 小程序

小程序不是唯一入口，而是后续流量入口。

建议先上线 Web + API，再逐步对接小程序。

## 给 Agent 的分发方式

- 发送 GitHub 仓库链接
- 提供 `openapi.json`
- 提供在线服务域名

## 给人的分发方式

- Web 首页
- GitHub 仓库
- 小程序码

