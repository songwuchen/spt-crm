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
    },
    "qwen": {
        "label": "通义千问 (阿里云 DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-turbo", "qwen-max", "qwen-long"],
        "api": "openai",
        "needs_key": True,
    },
    "deepseek": {
        "label": "DeepSeek 深度求索",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "api": "openai",
        "needs_key": True,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "api": "openai",
        "needs_key": True,
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "base_url": "https://api.anthropic.com",
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"],
        "api": "anthropic",
        "needs_key": True,
    },
    "custom": {
        "label": "自定义(OpenAI 兼容接口)",
        "base_url": "",
        "models": [],
        "api": "openai",
        "needs_key": True,
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


def chat_provider_meta(provider: str) -> dict:
    return CHAT_PROVIDERS.get(provider) or CHAT_PROVIDERS["custom"]


def embedding_provider_meta(provider: str) -> dict:
    return EMBEDDING_PROVIDERS.get(provider) or EMBEDDING_PROVIDERS["custom"]
