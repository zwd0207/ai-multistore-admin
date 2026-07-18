# 紫鸟集成研究资料索引

文档类型：紫鸟集成研究索引
研究日期：2026-07-13
当前状态：参考资料目录
权威性：不替代 `docs/PROJECT_CONTROL.md`

## 目录用途

本目录保存紫鸟开放平台、SkillHub、ERP-Demo、SSO、CLI、设备环境和当前系统复用关系的研究快照，供后续任务查阅。它不是当前项目状态、开发计划、接口授权或真实平台运行结果的来源。

紫鸟官方页面、接口字段、权限和 SkillHub 内容可能变化。所有实际开发、接入、真实测试或权限申请前，必须重新核对紫鸟官方平台和当前账号权限。

## 正式参考资料

- [`ziniao-api-inventory.md`](ziniao-api-inventory.md)：开放 API、账号、设备、权限、SSO、CLI 和 Webdriver 能力盘点。
- [`ziniao-capability-matrix.md`](ziniao-capability-matrix.md)：紫鸟能力与当前系统的价值和复用矩阵。
- [`ziniao-current-system-reuse-audit.md`](ziniao-current-system-reuse-audit.md)：现有模型、服务、页面和接口的复用审查。
- [`ziniao-manual-verification-checklist.md`](ziniao-manual-verification-checklist.md)：登录、应用、权限、IP 白名单、SSO、CLI 和 SkillHub 人工核对清单。
- [`ziniao-demo-review.md`](ziniao-demo-review.md)：ERP-Demo 的协议参考、风险和不可直接复用部分。
- [`ziniao-skillhub-inventory.md`](ziniao-skillhub-inventory.md)：SkillHub 能力清单和相关 Skill 盘点。
- [`ziniao-source-map.md`](ziniao-source-map.md)：官方公开入口、SkillHub、Demo 和本地审查来源地图。

## 历史归档

以下资料保留研究过程，但不是当前计划：

- [`archive/ziniao-expansion-roadmap.md`](archive/ziniao-expansion-roadmap.md)：早期接入扩展路线。
- [`archive/ziniao-final-summary.md`](archive/ziniao-final-summary.md)：早期研究总结。

正式参考资料也不具有项目状态权威性；历史归档更不能替代当前计划。项目权威顺序固定为：

1. `docs/PROJECT_CONTROL.md`
2. `docs/DECISION_LOG.md`
3. `docs/TASK_HANDOFF.md`
4. 本目录正式研究资料
5. 本目录 `archive/` 历史资料

## 当前紫鸟定位

紫鸟属于长期重要集成能力，但当前不扩大 Linux CLI 等非主线实现。后续候选方向包括 Windows 本地助手、店铺发现、设备关系、权限核对、环境打开和到期提醒；实际开发范围必须由后续正式阶段决策重新确认。

当前不把紫鸟作为 Linux 生产服务器直接调用 CLI 的依赖，也不以研究文档授权店铺后台打开、平台读取或平台写入。

## 当前冻结范围

- 不新增第二套店铺、账号、权限、同步或审计体系。
- 不把紫鸟页面操作当作 Naver/Coupang 官方 API 的替代品。
- 不启用未经人工确认的平台写入、自动回复、自动发货、库存/商品修改或 AI 自动操作。
- 不在本目录继续扩展旧路线、Mock、Demo 或未经核实的接口结论。

## 恢复紫鸟开发前必须重新核实

- 官方 API、SSO、CLI 和 SkillHub 当前版本、权限和调用合同。
- App/API 凭证申请方式、白名单、频率限制、错误码和回调行为。
- Windows 助手配对、设备密钥保护、离线状态、升级和代码签名方案。
- 店铺、员工、设备、权限和网络环境的精确关联规则。
- 手机查看与 Windows 后台打开之间的边界，以及审计和失败处理。

## 敏感信息规则

本目录禁止提交真实 App Token、Access Token、API Key、Client Secret、密码、Cookie、私钥、邮箱账号、店铺账号、代理地址、完整设备标识、原始平台响应和其他凭证。只能记录字段名称、脱敏示例、哈希、布尔状态和公开来源。发现疑似真实凭证时应停止提交并先进行安全审查。
