# Authentication
UNAUTHORIZED = 40100          # 未认证
TOKEN_EXPIRED = 40101         # Token 过期
TOKEN_INVALID = 40102         # Token 无效

# Authorization
FORBIDDEN = 40300             # 无权限

# Validation
VALIDATION_ERROR = 42200      # 参数校验失败
DUPLICATE_ENTRY = 42201       # 重复记录

# Not Found
NOT_FOUND = 40400             # 资源不存在

# Business
BUSINESS_ERROR = 50000        # 通用业务错误
LEAD_ALREADY_QUALIFIED = 50001
LEAD_ALREADY_DISCARDED = 50002
TENANT_DISABLED = 50003
STAGE_INVALID = 50004
CONTRACT_ALREADY_SIGNED = 50005
