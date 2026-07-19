"""深度思考(enable_thinking)开关 —— 供应商门控 + 配置往返。

不碰数据库:全部针对纯函数与请求体构造。重点守住两件已经踩过的事:
  1. enable_thinking 只能下发给支持它的供应商 —— 真 OpenAI 收到未知顶层字段会 400;
  2. _mask_ai_provider 是白名单式回显,漏了 thinking 前端就读不到,设置会静默失效。
"""

import pytest

from app.common.ai_providers import (
    CHAT_PROVIDERS, THINKING_MODES, normalize_thinking,
    provider_supports_thinking, thinking_payload,
)
from app.domains.admin.service import _mask_ai_provider, _merge_ai_provider


def test_thinking_payload_only_for_supporting_providers():
    """off 只对声明了 supports_thinking 的供应商生成参数。"""
    assert thinking_payload("off", "qwen") == {"enable_thinking": False}
    assert thinking_payload("off", "custom") == {"enable_thinking": False}
    # 这三个收到 enable_thinking 会报错或无意义,必须一个字段都不发
    for provider in ("openai", "deepseek", "anthropic", "mock"):
        assert thinking_payload("off", provider) == {}, provider


def test_thinking_payload_auto_sends_nothing():
    """auto = 完全跟随模型默认,任何供应商都不加字段。"""
    for provider in CHAT_PROVIDERS:
        assert thinking_payload("auto", provider) == {}
        assert thinking_payload(None, provider) == {}


def test_thinking_payload_unknown_provider_is_denied():
    """供应商未知时按不支持处理,宁可不生效也不要打出 400。"""
    assert thinking_payload("off", None) == {}
    assert thinking_payload("off", "") == {}
    assert thinking_payload("off", "not-a-provider") == {}


def test_no_force_on_mode():
    """'on' 在本系统没有可用链路,不应存在于合法取值里。"""
    assert THINKING_MODES == ("auto", "off")
    assert normalize_thinking("on") == "auto"


def test_normalize_thinking_rejects_junk():
    for junk in ("", "false", "disabled", "ON", None, "; drop table"):
        assert normalize_thinking(junk) == "auto"


def test_every_chat_provider_declares_thinking_support():
    """新增供应商时必须显式表态,不能靠 .get() 默认值蒙混过去。"""
    for name, meta in CHAT_PROVIDERS.items():
        assert "supports_thinking" in meta, f"{name} 缺少 supports_thinking"
        assert isinstance(meta["supports_thinking"], bool)
    assert provider_supports_thinking("qwen") is True
    assert provider_supports_thinking("openai") is False


def test_mask_ai_provider_echoes_thinking():
    """回显白名单必须带上 thinking,否则前端读不到、每次保存都被冲成 auto。"""
    masked = _mask_ai_provider({"model": "qwen3.7-plus", "api_key": "sk-x", "thinking": "off"})
    assert masked["thinking"] == "off"
    assert masked["api_key"] == "***"          # 密钥不能明文回显
    # 老配置没有该键时不硬造,前端自己回落 auto
    assert "thinking" not in _mask_ai_provider({"model": "qwen-plus"})


def test_merge_preserves_thinking_on_partial_update():
    """只改模型不应把已存的 thinking 冲掉。"""
    existing = {"model": "qwen-plus", "api_key": "sk-x", "thinking": "off"}
    merged = _merge_ai_provider(existing, {"model": "qwen3.7-plus"})
    assert merged["thinking"] == "off"
    assert merged["api_key"] == "sk-x"          # 空/*** 时保留原密钥的既有行为


def test_merge_normalizes_illegal_thinking():
    merged = _merge_ai_provider({"model": "qwen-plus"}, {"thinking": "yes-please"})
    assert merged["thinking"] == "auto"


@pytest.mark.parametrize("provider,expect_field", [("qwen", True), ("openai", False)])
async def test_request_body_gated_by_provider(monkeypatch, provider, expect_field):
    """端到端:_call_openai 真正发出的请求体里有没有 enable_thinking。"""
    import httpx
    from app.common import ai_engine

    captured = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            captured.update(json)
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _Client())
    await ai_engine._call_openai("sys", "user", 100, "https://x/v1", "k", "m",
                                 thinking="off", provider=provider)
    assert ("enable_thinking" in captured) is expect_field
