"""AI 供应商预设 —— 对话模型 + 向量嵌入模型。

大多数国产/开源模型服务都提供 OpenAI 兼容接口(/chat/completions、/embeddings),
因此对话调用统一走 OpenAI 兼容路径(api="openai"),仅 Anthropic 走原生
Messages API(api="anthropic")。前端据此渲染可选模型与默认 base_url。
"""

# ---------------- 对话/分析模型 ----------------
CHAT_PROVIDERS = {
    "mock": {
        "label": "内置模拟(不调用外部,返回示例结果)",
        "base_url": "",
        "models": [],
        "api": "mock",
        "needs_key": False,
        "supports_thinking": False,
    },
    "qwen": {
        "label": "通义千问 (阿里云 DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen3.7-plus", "qwen-turbo", "qwen-max", "qwen-long"],
        "api": "openai",
        "needs_key": True,
        "supports_thinking": True,   # DashScope 私有扩展 enable_thinking
    },
    "deepseek": {
        "label": "DeepSeek 深度求索",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "api": "openai",
        "needs_key": True,
        "supports_thinking": False,  # 思考与否由模型名决定(chat vs reasoner),无此参数
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "api": "openai",
        "needs_key": True,
        "supports_thinking": False,  # 未知顶层字段会被 400 拒绝
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "base_url": "https://api.anthropic.com",
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"],
        "api": "anthropic",
        "needs_key": True,
        "supports_thinking": False,  # Claude 用 thinking:{type} 结构,机制不同
    },
    "custom": {
        "label": "自定义(OpenAI 兼容接口)",
        "base_url": "",
        "models": [],
        "api": "openai",
        "needs_key": True,
        "supports_thinking": True,   # 自建 qwen3/vLLM 常见,交由配置者自行判断
    },
}

# ---------------- 向量嵌入模型 ----------------
EMBEDDING_PROVIDERS = {
    "none": {
        "label": "不启用(知识库退化为关键词检索)",
        "base_url": "",
        "models": [],
        "default_dimensions": 0,
        "needs_key": False,
    },
    "qwen": {
        "label": "通义 text-embedding (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["text-embedding-v3", "text-embedding-v4", "text-embedding-v2"],
        "default_dimensions": 1024,
        "needs_key": True,
    },
    "openai": {
        "label": "OpenAI Embeddings",
        "base_url": "https://api.openai.com/v1",
        "models": ["text-embedding-3-small", "text-embedding-3-large"],
        "default_dimensions": 1024,  # 3-* 支持 dimensions 参数缩放到 1024
        "needs_key": True,
    },
    "custom": {
        "label": "自定义(OpenAI 兼容 /embeddings)",
        "base_url": "",
        "models": [],
        "default_dimensions": 1024,
        "needs_key": True,
    },
}

# 向量列固定维度。所有嵌入模型统一请求/规范化到该维度,保证 pgvector 列/索引稳定。
EMBEDDING_DIM = 1024

# ---------------- 深度思考(推理)开关 ----------------
# 部分模型带"思考"模式:先输出一段推理再给答案。它更慢、更贵,且会挤占 max_tokens
# 导致我们要求的 JSON 被截断,所以要能关掉。
#   auto = 不传参数,完全跟随模型默认(qwen-plus/turbo 老版本默认关,qwen3.7-plus 等新模型默认开)
#   off  = 传 enable_thinking:false 强制关闭
#
# 没有 "on":强制开启在本系统里没有可用路径 —— 分析类调用是非流式 + 要求返回 JSON,
# 思考会吃掉 max_tokens 把 JSON 截断;流式助手只透传 delta.content,思考段会被丢弃
# 表现为长时间空白。要支持开启,得先改这两条链路。
#
# enable_thinking 是 DashScope 的私有扩展,不是 OpenAI 标准参数:真 OpenAI 对未知的
# 顶层字段直接返回 400 "Unrecognized request argument"。因此能否下发这个参数取决于
# **供应商**,不是接口协议 —— OpenAI / DeepSeek / 通义 的 api 都是 "openai"。
THINKING_MODES = ("auto", "off")
DEFAULT_THINKING = "auto"


def normalize_thinking(value: str | None) -> str:
    return value if value in THINKING_MODES else DEFAULT_THINKING


def provider_supports_thinking(provider: str | None) -> bool:
    return bool((CHAT_PROVIDERS.get(provider or "") or {}).get("supports_thinking"))


def thinking_payload(mode: str | None, provider: str | None) -> dict:
    """把思考模式翻译成请求体增量。auto、或供应商不支持该参数时返回空 dict。"""
    if normalize_thinking(mode) == "off" and provider_supports_thinking(provider):
        return {"enable_thinking": False}
    return {}


def chat_provider_meta(provider: str) -> dict:
    return CHAT_PROVIDERS.get(provider) or CHAT_PROVIDERS["custom"]


def embedding_provider_meta(provider: str) -> dict:
    return EMBEDDING_PROVIDERS.get(provider) or EMBEDDING_PROVIDERS["custom"]
