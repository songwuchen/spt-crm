from contextvars import ContextVar

request_ip: ContextVar[str | None] = ContextVar("request_ip", default=None)
request_trace_id: ContextVar[str | None] = ContextVar("request_trace_id", default=None)
request_user_agent: ContextVar[str | None] = ContextVar("request_user_agent", default=None)
