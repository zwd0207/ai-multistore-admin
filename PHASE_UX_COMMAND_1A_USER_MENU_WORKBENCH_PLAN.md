# Phase UX-Command-1A: User Menu And Home Workbench Plan

## Goal

Turn the first screen from a technical admin console into a daily operations workbench for ordinary cross-border sellers.

The user should not need to understand API, token, JSON, webhook, payload, dry-run, or debug concepts to know what to do next.

## Completed In This Phase

- Renamed the visible home entry to `首页工作台`.
- Added `/workbench` as the default user-facing entry.
- Kept `/dashboard` as a compatibility route for old links.
- Reworked the main menu into seller-facing labels:
  - 首页工作台
  - 发货辅助
  - 订单管理
  - 商品与库存
  - 店铺管理
  - 平台消息
  - 申诉中心
  - 邮箱中心
  - 数据报表
  - 系统设置
- Removed developer-facing entries from the ordinary main menu:
  - API 能力确认
  - 操作日志
  - 设备管理
  - 环境管理
  - 账号管理
- Updated the top bar wording from a technical system label to `多平台电商运营工作台`.

## Product Boundary

This phase hides technical modules from the ordinary user's main navigation. It does not delete the routes or backend features.

Admin and troubleshooting features can remain available later under `系统设置` or an administrator-only advanced area.

## Home Workbench Definition

The home page should answer:

- 今天有哪些订单要处理?
- 哪些订单需要发货?
- 哪些商品库存不足?
- 哪些店铺连接异常?
- 哪些平台消息需要处理?
- 哪些申诉或审核资料需要提交?
- 用户下一步应该点哪里?

## UX Acceptance Standard

Every future page must be checked against:

- Does a non-technical seller understand the page title?
- Does the page explain what problem it solves?
- Is there a clear next action?
- Are mock/demo data visually identified?
- Are empty states actionable?
- Are technical words hidden or translated?
- Are errors shown as business guidance?
- Are unfinished or invalid buttons hidden?

## Deferred

- Dedicated inventory page. Current first pass uses `商品与库存` because stock alerts are already inside product views.
- Advanced settings area for API status and operation logs.
- Role-based menu visibility.
- Mobile layout cleanup.

## Recommended Next Phase

`Phase UX-Command-1B: Home workbench task hierarchy cleanup`

Purpose: reorder the first screen so orders, pending shipment, abnormal orders, inventory alerts, platform messages, appeals, and store connection issues appear before financial/reporting or technical sections.
