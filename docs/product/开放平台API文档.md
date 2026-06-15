# SPT-CRM 开放平台 API 文档（对接方版）

> 版本：v1 ｜ 适用：外部系统 / ERP / WMS / 数据中台 与 SPT-CRM 的对接
>
> 本文面向**对接开发方**。SPT-CRM 通过开放平台对外提供受控的**只读查询接口**与**业务事件**（事件拉取 + Webhook 推送）。内部 `/api/v1` 接口（JWT 登录态）不在本文范围内，且不保证对外稳定。

---

## 1. 概述

| 项 | 值 |
|---|---|
| 接口基址 | `https://<your-host>/openapi/v1`（生产示例：`https://192.168.0.42:8410/openapi/v1`） |
| 协议 | HTTPS |
| 数据格式 | JSON（UTF-8） |
| 认证 | API Key（`X-API-Key`）或 HMAC 签名（`X-App-Id` + `X-Signature`），由应用配置决定 |
| 关联 ID | 每个响应回写 `X-Trace-Id`，响应体亦含 `traceId`，排障时请一并提供 |
| 首版能力 | 客户 / 联系人 / 商机项目 / 合同 的只读查询 + 业务事件拉取 + Webhook |

### 接入流程
1. 联系 SPT-CRM 管理员，在「系统 → 开放平台 → 应用与密钥」中为你创建一个**应用**，选择认证方式（API Key 或 HMAC）并授予所需 **Scope**。
2. 创建成功后系统会**一次性**展示 `App ID` 与 `Secret`，请立即保存（关闭后无法再查看，只能重置）。
3. 用拿到的凭据调用 `GET /openapi/v1/ping` 验证连通性。
4. 按需调用查询接口；如需实时性，登记 Webhook 回调地址订阅事件。

---

## 2. 认证

应用在创建时被指定为 `apikey` 或 `hmac` 之一，只能用对应方式调用。

### 2.1 方式一：API Key（简单，推荐内部/受信系统）
在请求头携带 Secret 即可：
```
X-API-Key: sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 2.2 方式二：HMAC 签名（推荐 ERP/WMS/设备网关等高安全场景）
请求头：
```
X-App-Id:    app_xxxxxxxxxxxx      # 应用公开标识
X-Timestamp: 1780714200           # 当前 Unix 时间（秒）
X-Signature: sha256=<hex>         # 见下方签名算法
```

**签名串（canonical，注意是 5 行、用 `\n` 连接）：**
```
METHOD\nPATH\nQUERY\nTIMESTAMP\nSHA256_HEX(BODY)
```
- `METHOD`：大写 HTTP 方法，如 `GET`
- `PATH`：请求路径，如 `/openapi/v1/customers`（不含域名、不含查询串）
- `QUERY`：原始查询串，如 `status=active&page=1`；无则为空字符串
- `TIMESTAMP`：与 `X-Timestamp` 完全一致
- `SHA256_HEX(BODY)`：请求体的 SHA-256 十六进制；GET 等空体为**空串的 SHA-256**

**签名：** `HMAC-SHA256(Secret, canonical)` 的十六进制，放入 `X-Signature: sha256=<hex>`。

**安全校验：** 服务端要求 `X-Timestamp` 与服务器时间偏差 ≤ **5 分钟**（防重放）。
> 说明：基于 nonce 的严格防重复依赖 Redis，当前部署未启用，故以时间窗口为准——请确保各客户端时钟同步（NTP）。

Python 签名示例：
```python
import time, hmac, hashlib, requests

APP_ID = "app_xxxxxxxxxxxx"
SECRET = "sk_xxxxxxxxxxxxxxxxxxxxxxxx"
BASE   = "https://192.168.0.42:8410"

def call(method, path, query="", body=b""):
    ts = str(int(time.time()))
    body_hash = hashlib.sha256(body or b"").hexdigest()
    canonical = "\n".join([method, path, query, ts, body_hash])
    sig = hmac.new(SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    headers = {"X-App-Id": APP_ID, "X-Timestamp": ts, "X-Signature": "sha256=" + sig}
    url = f"{BASE}{path}" + (f"?{query}" if query else "")
    return requests.get(url, headers=headers, verify=False)

print(call("GET", "/openapi/v1/customers", "status=active&page=1").json())
```

---

## 3. 统一响应与分页

### 成功
```json
{
  "code": 0,
  "message": "success",
  "traceId": "f1c2...",
  "data": {
    "items": [ /* ... */ ],
    "total": 128,
    "page": 1,
    "page_size": 20
  }
}
```
- 列表接口 `data` 为 `{items, total, page, page_size}`（**offset 分页**，参数 `page`/`page_size`，`page_size` ≤ 200）。
- 详情接口 `data` 为单个对象。
- 事件接口 `data` 为 `{items, limit, next_cursor}`（**游标分页**）。

### 错误
```json
{
  "code": 1,
  "error_code": "CRM_FORBIDDEN_SCOPE",
  "message": "应用缺少所需权限范围: crm.contract.read",
  "traceId": "f1c2...",
  "details": { "required_scope": "crm.contract.read" }
}
```
请基于稳定字符串 **`error_code`** 判断错误类型，不要解析 `message`（文案可能调整）。

### 错误码表
| HTTP | error_code | 含义 |
|---|---|---|
| 401 | `CRM_UNAUTHORIZED` | 缺少/无效凭据，或应用认证方式不匹配 |
| 401 | `CRM_INVALID_SIGNATURE` | HMAC 签名或时间戳无效/过期 |
| 403 | `CRM_APP_DISABLED` | 应用已被停用 |
| 403 | `CRM_IP_NOT_ALLOWED` | 来源 IP 不在白名单 |
| 403 | `CRM_FORBIDDEN_SCOPE` | 应用未被授予该接口所需 Scope |
| 429 | `CRM_RATE_LIMITED` | 触发限流（详见第 7 节） |
| 404 | `CRM_NOT_FOUND` | 资源不存在 |
| 400 | `CRM_VALIDATION_ERROR` | 查询/路径参数不合法 |
| 500 | `CRM_INTERNAL_ERROR` | 服务端异常，可凭 traceId 反馈 |

---

## 4. 权限范围（Scope）

每个接口绑定一个 Scope，应用须被授予方可访问。首版均为只读：

| Scope | 说明 |
|---|---|
| `crm.customer.read` | 读取客户 |
| `crm.contact.read` | 读取联系人 |
| `crm.project.read` | 读取商机项目 |
| `crm.contract.read` | 读取合同 |
| `crm.event.read` | 拉取业务事件 |

---

## 5. 接口

> 所有路径前缀 `/openapi/v1`。示例省略认证头。时间字段均为 ISO 8601 字符串。

### 5.0 连通性自检
`GET /ping` — 任意已认证应用可调用。
```json
{ "code": 0, "data": { "app_key": "app_xxx", "scopes": ["crm.customer.read"], "tenant_id": "..." } }
```

### 5.1 客户

`GET /customers` — Scope `crm.customer.read`

| 参数 | 类型 | 说明 |
|---|---|---|
| `keyword` | string | 按名称 / 客户编码模糊搜索 |
| `status` | string | `active` / `inactive` |
| `customer_code` | string | 精确匹配客户编码 |
| `updated_since` | string(ISO) | 仅返回该时间后更新的记录（增量同步用） |
| `page` / `page_size` | int | 默认 1 / 20，`page_size` ≤ 200 |

`GET /customers/{id}` — 客户详情。
`GET /customers/{id}/contacts` — 该客户下联系人列表（Scope `crm.contact.read`）。

**客户对象字段：**
| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 客户唯一 ID（对接主键） |
| `customer_code` | string | 客户编码（可对应 ERP 编码） |
| `name` / `short_name` | string | 名称 / 简称 |
| `industry` / `region` | string | 行业 / 区域 |
| `address` / `website` | string | 地址 / 官网 |
| `level` | string | 客户等级 A/B/C/D |
| `source` | string | 来源 |
| `status` | string | `active` / `inactive` |
| `owner_name` | string | 负责人姓名 |
| `tags` | array | 标签 |
| `created_at` / `updated_at` | string(ISO) | 创建/更新时间 |

示例：
```bash
curl -H "X-API-Key: $KEY" \
  "https://192.168.0.42:8410/openapi/v1/customers?status=active&page=1&page_size=20"
```
```json
{
  "code": 0, "message": "success", "traceId": "...",
  "data": { "items": [
    { "id": "a1b2...", "customer_code": "C00012", "name": "示例制造有限公司",
      "industry": "矿山机械", "region": "山东", "level": "A", "status": "active",
      "owner_name": "张三", "tags": ["重点"], "created_at": "2026-03-01T08:00:00+00:00",
      "updated_at": "2026-06-10T03:21:00+00:00" }
  ], "total": 1, "page": 1, "page_size": 20 }
}
```

### 5.2 联系人
`GET /contacts?customer_id=<id>` — Scope `crm.contact.read`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` / `customer_id` | string | 联系人 ID / 所属客户 ID |
| `name` / `title` | string | 姓名 / 职务 |
| `role_type` | string | `decision_maker`/`influencer`/`user`/`finance`/`procurement` |
| `phone` / `mobile` / `email` | string | 联系方式 |
| `is_primary` | bool | 是否主联系人 |
| `created_at` / `updated_at` | string(ISO) | 时间 |

### 5.3 商机项目
`GET /projects` — Scope `crm.project.read`，过滤：`customer_id` / `stage_code` / `status` + 分页。
`GET /projects/{id}` — 详情。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` / `project_code` | string | 商机 ID / 编号 |
| `customer_id` | string | 所属客户 |
| `name` | string | 商机名称 |
| `stage_code` | string | 阶段 `S1`…`S6` |
| `status` | string | `active`/`won`/`lost`/`suspended` |
| `amount_expect` | number | 预期金额 |
| `probability` | int | 赢单概率 % |
| `close_date_expect` | string(date) | 预计成交日 |
| `risk_level` | string | `L`/`M`/`H` |
| `owner_name` | string | 负责人 |
| `created_at` / `updated_at` | string(ISO) | 时间 |

### 5.4 合同
`GET /contracts` — Scope `crm.contract.read`，过滤：`project_id` / `status` + 分页。
`GET /contracts/{id}` — 详情。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` / `contract_no` | string | 合同 ID / 编号 |
| `project_id` | string | 所属商机 |
| `status` | string | `draft`/`signed`/`terminated` |
| `amount_total` | number | 合同总额 |
| `current_version_no` | int | 当前版本号 |
| `signed_date` / `end_date` | string(date) | 签署日 / 结束日 |
| `created_at` / `updated_at` | string(ISO) | 时间 |

### 5.5 事件拉取（对账）
`GET /events` — Scope `crm.event.read`

| 参数 | 类型 | 说明 |
|---|---|---|
| `event_type` | string | 按事件类型过滤（见第 6 节） |
| `after_event_id` | string | **游标**：返回该事件之后（更新）的事件 |
| `occurred_from` / `occurred_to` | string(ISO) | 时间范围 |
| `limit` | int | 默认 50，≤ 200 |

返回 `data = { items, limit, next_cursor }`；翻页时把上次的 `next_cursor` 作为下次的 `after_event_id`，直到 `items` 为空。

`GET /events/{event_id}` — 单事件详情。

---

## 6. 事件中心

业务动作发生时，CRM 在**同一数据库事务**内写入事件（保证“业务成功即事件不丢”）。事件可通过 `GET /events` 拉取，或通过 Webhook 推送（第 7 节）。

### 事件目录
| event_type | 触发时机 |
|---|---|
| `crm.customer.created` | 新建客户 |
| `crm.project.stage_advanced` | 商机阶段推进 |
| `crm.project.won` | 商机赢单 |
| `crm.project.lost` | 商机丢单 |
| `crm.contract.signed` | 合同签署 |
| `crm.payment.received` | 回款到账 |

> 不提供 `*.updated` 这类无业务语义的事件。事件带 `event_version`，破坏性变更会升版本。

### 事件格式
```json
{
  "event_id": "evt-uuid",
  "event_type": "crm.contract.signed",
  "event_version": "1.0",
  "occurred_at": "2026-06-12T09:30:00+00:00",
  "source_system": "spt-crm",
  "aggregate_type": "contract",
  "aggregate_id": "<contract id>",
  "data": {
    "contract_id": "...", "contract_no": "HT2026060001",
    "project_id": "...", "amount_total": 1280000.0, "signed_date": "2026-06-12"
  }
}
```

各事件 `data` 关键字段：
| 事件 | data 字段 |
|---|---|
| `crm.customer.created` | `customer_id`, `customer_code`, `name` |
| `crm.project.stage_advanced` | `project_id`, `project_code`, `from_stage`, `to_stage` |
| `crm.project.won` / `lost` | `project_id`, `project_code`, `name`, `status`, `amount_expect` |
| `crm.contract.signed` | `contract_id`, `contract_no`, `project_id`, `amount_total`, `signed_date` |
| `crm.payment.received` | `payment_record_id`, `project_id`, `amount` |

---

## 7. Webhook 推送

由 CRM 管理员在「开放平台 → Webhook 订阅」登记回调地址、订阅的事件类型与签名 `Secret`。事件产生后，CRM 会向回调地址发起 `POST`：

**请求头：**
```
Content-Type: application/json
X-Webhook-Signature: sha256=<HMAC-SHA256(webhook_secret, raw_body)>
```
**请求体：**
```json
{
  "event_id": "evt-uuid",
  "event_type": "crm.payment.received",
  "aggregate_type": "payment",
  "aggregate_id": "...",
  "tenant_id": "...",
  "timestamp": "2026-06-12T09:31:00+00:00",
  "data": { "payment_record_id": "...", "project_id": "...", "amount": 200000.0 }
}
```

**接收端校验签名（Python）：**
```python
import hmac, hashlib

def verify(raw_body: bytes, header_sig: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = header_sig.split("=", 1)[1] if header_sig.startswith("sha256=") else header_sig
    return hmac.compare_digest(expected, provided)
```

**投递与重试：** 回调返回 2xx 视为成功；失败按退避重试，多次失败后置为失败并停止。**Webhook 非 100% 可靠**——务必周期性调用 `GET /openapi/v1/events`（按 `after_event_id` 游标）做对账补偿，确保不漏单。接收端需对 `event_id` **幂等**处理（同一事件可能重复送达）。

---

## 8. 限流与最佳实践
- 每个应用有独立的**每分钟限流**（默认 600，可由管理员调整）。超限返回 `429 CRM_RATE_LIMITED`，请退避后重试。
  > 当前限流为单进程内计数；多实例部署下为各实例独立窗口。
- **增量同步**优先用 `updated_since`（查询）或事件游标，避免全量轮询。
- 请缓存并复用连接；为请求设置合理超时与重试（对 5xx/429 退避重试，对 4xx 不重试）。
- 妥善保管 Secret；如泄露，请管理员**重置密钥**（旧密钥立即失效）。
- 排障时提供响应中的 `traceId`。

## 9. 兼容性约定
- 响应**新增字段**不视为破坏性变更，客户端应忽略未知字段。
- 删除/改名/改语义属破坏性变更，会通过新版本路径 `/openapi/v2` 发布；事件破坏性变更升 `event_version`。
- 当前所有接口为**只读**；写入类接口将在后续版本提供（届时启用 `Idempotency-Key`）。
