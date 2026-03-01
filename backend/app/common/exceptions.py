from app.common.error_codes import BUSINESS_ERROR


class BusinessException(Exception):
    def __init__(self, code: int = BUSINESS_ERROR, message: str = "业务异常", detail: dict | None = None):
        self.code = code
        self.message = message
        self.detail = detail
