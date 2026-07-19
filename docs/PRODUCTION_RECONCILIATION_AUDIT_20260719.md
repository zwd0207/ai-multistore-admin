# 生产与本地对齐审计（2026-07-19）

## 审计边界

- 任务：`TASK-PROD-RECONCILE-001`
- 方式：项目负责人提供的受控 SSH 账户下的只读核验，以及公网只读健康检查。
- 未执行：服务停止、部署、数据库或配置修改、备份创建、平台调用、真实写入。
- 敏感边界：未读取或记录服务器密钥、环境变量值、客户数据、订单正文或原始同步响应。

## 已验证事实

- API、Nginx、PostgreSQL 与 PostgreSQL 备份定时器均为 active；最近一次备份 service 结果为 success，24 小时 API 与备份 warning 计数均为 0。
- 公网 `https://aiglxt.xyz/api/v1/health` 返回 production healthy，所有真实平台写入、客服回复、订单/商品/库存更新与发货回填均保持关闭。
- PostgreSQL Alembic revision 为 `7e2a9c4f1b36`；两店共八个自动读取 checkpoint 均为 `success`、自动读取开启、无 retry 或 error code；近期订单、咨询和物流同步日志均为 success。
- 服务器后端工作目录没有 Git 元数据，但其 `app/` 下 129 个受控源码文件逐个 Git blob 对比后，与 `62e49ba9cfdd19a6f6b026c25d53fc3f2ad98401` 完全一致；当前本地仓库已包含该提交。
- 服务器前端 Git 工作树的受控源代码为干净状态，HEAD 为 `e5697e4b2e12e44a7ba1eeaed8c0ee7b85f98f25`，该提交同样是当前本地 HEAD 的祖先。工作树中的未跟踪内容均为历史 rollback/stage 静态构建目录，不是受控源代码改动。

## 已确认差异与处理

- 没有发现需要从服务器回流本地的后端或前端受控源代码。当前本地是已核验服务器代码的超集，应在既有主实现上继续收口，不重建服务、模型或调度器。
- 服务器前端活动 `dist` 未包含 `release-version.json`；公网请求该路径返回 SPA HTML 回退。因此活动静态产物的精确 Git SHA 仍为 X，不能仅凭前端源码仓库 HEAD 认定版本。下一次服务器业务里程碑发布必须把 `public/release-version.json` 作为静态产物部署并读回验证。
- 服务器 Nginx 当前配置的公开主机名为 `aiglxt.xyz` 和 `www.aiglxt.xyz`，且 HTTPS 健康检查通过。`aiglxt.com` 在本机、Google 与 Cloudflare 公共 DNS 查询中均为 NXDOMAIN；本审计不修改 DNS、域名绑定或 Nginx，是否启用 `.com` 由项目负责人另行决定。

## 结论与下一任务

`TASK-PROD-RECONCILE-001` 的只读验收通过：生产后端、自动同步、备份和写入门禁健康，且未发现服务器独有业务实现。下一准确起点为 `TASK-INQUIRY-READ-CONTRACT-001`：统一受保护 Naver 咨询的正式列表、统计、工作台和详情深链，继续不启用回复或任何平台写入。
