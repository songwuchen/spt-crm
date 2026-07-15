"""扩展平台 / 低代码模块。

在 CRM 内提供 schema 驱动的表单引擎、可视化审批流程引擎与可配置仪表盘，
复用 CRM 既有的租户隔离(TenantScopedBase)、认证、RBAC、组织架构、文件存储与通知设施。

移植来源: F:\\dev\\spt-lowcode(对标简道云)。
适配要点: 使用 CRM 的 String(36) 主键/租户列(而非原生 UUID),接 CRM 基础设施。
"""
