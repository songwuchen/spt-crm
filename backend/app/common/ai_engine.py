"""AI analysis engine — pluggable LLM backend for business intelligence.

Provides structured analysis for:
  - Project risk assessment
  - Customer profile generation
  - Deal win probability
  - Next action recommendations

Configure via environment variables:
  AI_PROVIDER=mock|openai|anthropic  (default: mock)
  AI_API_KEY=sk-...
  AI_MODEL=gpt-4o|claude-sonnet-4-20250514
"""

import json
import logging
from typing import Optional

logger = logging.getLogger("spt_crm.ai")

# Token usage tracking for the last call
_last_usage = {"token_in": 0, "token_out": 0, "cost_est": 0.0, "model": "mock"}

# Approximate pricing per 1M tokens (USD). 国产模型按人民币官方价折算(≈÷7.2)。
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    # 通义千问(DashScope)
    "qwen-plus": {"input": 0.11, "output": 0.28},
    "qwen-turbo": {"input": 0.04, "output": 0.09},
    "qwen-max": {"input": 0.33, "output": 1.33},
    "qwen-long": {"input": 0.07, "output": 0.28},
    # DeepSeek
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.14, "output": 0.55},
    "mock": {"input": 0, "output": 0},
}

# 未知模型按 0 计(避免用 gpt-4o 定价高估国产模型成本)
_ZERO_PRICE = {"input": 0.0, "output": 0.0}


def get_last_usage() -> dict:
    """Get token usage from the last LLM call."""
    return dict(_last_usage)


def _extract_json(text: str):
    """从模型输出中稳健解析 JSON：剥离 ```json 围栏、提取最外层花括号。

    解析失败时抛 json.JSONDecodeError,调用方据此回退 raw_response。
    """
    s = (text or "").strip()
    if s.startswith("```"):
        nl = s.find("\n")
        if nl >= 0:
            s = s[nl + 1:]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
        s = s.strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        i, j = s.find("{"), s.rfind("}")
        if i >= 0 and j > i:
            return json.loads(s[i:j + 1])
        raise


async def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 2000, chat_cfg: dict | None = None) -> str:
    """Call the LLM backend.

    优先级: 显式 chat_cfg(租户后台配置) > 环境变量 AI_PROVIDER > mock。
    chat_cfg = {"api": "openai"|"anthropic", "base_url", "api_key", "model"}。
    """
    if chat_cfg and chat_cfg.get("api_key"):
        api = chat_cfg.get("api", "openai")
        base_url = chat_cfg.get("base_url") or "https://api.openai.com/v1"
        api_key = chat_cfg["api_key"]
        model = chat_cfg.get("model") or ("claude-sonnet-4-20250514" if api == "anthropic" else "gpt-4o")
        if api == "anthropic":
            return await _call_anthropic(system_prompt, user_prompt, max_tokens, base_url, api_key, model)
        return await _call_openai(system_prompt, user_prompt, max_tokens, base_url, api_key, model)

    from app.config import settings
    provider = getattr(settings, "AI_PROVIDER", "mock")
    if provider == "openai":
        return await _call_openai(
            system_prompt, user_prompt, max_tokens,
            getattr(settings, "AI_BASE_URL", "https://api.openai.com/v1"),
            getattr(settings, "AI_API_KEY", ""),
            getattr(settings, "AI_MODEL", "") or "gpt-4o",
        )
    elif provider == "anthropic":
        return await _call_anthropic(
            system_prompt, user_prompt, max_tokens,
            "https://api.anthropic.com",
            getattr(settings, "AI_API_KEY", ""),
            getattr(settings, "AI_MODEL", "") or "claude-sonnet-4-20250514",
        )
    else:
        _last_usage.update({"token_in": 0, "token_out": 0, "cost_est": 0.0, "model": "mock"})
        return _mock_response(user_prompt)


async def ping_chat(chat_cfg: dict) -> tuple[bool, str | None]:
    """后台"测试连接":用极小 prompt 实际调用一次配置的对话模型。"""
    import httpx
    try:
        txt = await _call_llm("You are a health check.", "回复两个字:正常", max_tokens=16, chat_cfg=chat_cfg)
        return bool(txt is not None), None
    except httpx.HTTPStatusError as e:
        body = ""
        try:
            body = e.response.text[:200]
        except Exception:
            pass
        return False, f"HTTP {e.response.status_code}: {body}"
    except Exception as e:
        return False, str(e)


async def _call_openai(system_prompt: str, user_prompt: str, max_tokens: int,
                       base_url: str, api_key: str, model: str) -> str:
    """Call OpenAI-compatible API (OpenAI / 通义 / DeepSeek / 自定义兼容端点)。"""
    import httpx
    base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        # Track token usage
        usage = data.get("usage", {})
        token_in = usage.get("prompt_tokens", 0)
        token_out = usage.get("completion_tokens", 0)
        pricing = MODEL_PRICING.get(model, _ZERO_PRICE)
        cost = (token_in * pricing["input"] + token_out * pricing["output"]) / 1_000_000
        _last_usage.update({"token_in": token_in, "token_out": token_out, "cost_est": round(cost, 6), "model": model})
        logger.info(f"OpenAI call: model={model} tokens_in={token_in} tokens_out={token_out} cost=${cost:.4f}")
        return data["choices"][0]["message"]["content"]


async def _call_anthropic(system_prompt: str, user_prompt: str, max_tokens: int,
                          base_url: str, api_key: str, model: str) -> str:
    """Call Anthropic Claude API with structured JSON output."""
    import httpx
    base_url = (base_url or "https://api.anthropic.com").rstrip("/")

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{base_url}/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "system": system_prompt + "\n\nIMPORTANT: Always respond with valid JSON only, no markdown or extra text.",
                "messages": [{"role": "user", "content": user_prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        # Track token usage
        usage = data.get("usage", {})
        token_in = usage.get("input_tokens", 0)
        token_out = usage.get("output_tokens", 0)
        pricing = MODEL_PRICING.get(model, MODEL_PRICING.get("claude-sonnet-4-20250514", {"input": 3.0, "output": 15.0}))
        cost = (token_in * pricing["input"] + token_out * pricing["output"]) / 1_000_000
        _last_usage.update({"token_in": token_in, "token_out": token_out, "cost_est": round(cost, 6), "model": model})
        logger.info(f"Anthropic call: model={model} tokens_in={token_in} tokens_out={token_out} cost=${cost:.4f}")
        return data["content"][0]["text"]


async def stream_llm(system_prompt: str, messages: list[dict], chat_cfg: dict | None = None,
                     max_tokens: int = 1500):
    """流式对话生成器,逐段 yield 文本增量。

    messages: [{"role": "user"/"assistant", "content": ...}, ...](多轮对话)。
    chat_cfg: 同 _call_llm。未配置时回退 mock(把整段结果分片吐出)。
    """
    if chat_cfg and chat_cfg.get("api_key"):
        api = chat_cfg.get("api", "openai")
        base_url = chat_cfg.get("base_url") or "https://api.openai.com/v1"
        api_key = chat_cfg["api_key"]
        model = chat_cfg.get("model") or ("claude-sonnet-4-20250514" if api == "anthropic" else "gpt-4o")
        if api == "anthropic":
            async for d in _stream_anthropic(system_prompt, messages, max_tokens, base_url, api_key, model):
                yield d
        else:
            async for d in _stream_openai(system_prompt, messages, max_tokens, base_url, api_key, model):
                yield d
        return
    # mock: 分片吐出示例文本
    last = messages[-1]["content"] if messages else ""
    text = _mock_response(last)
    for i in range(0, len(text), 30):
        yield text[i:i + 30]


async def _stream_openai(system_prompt: str, messages: list[dict], max_tokens: int,
                         base_url: str, api_key: str, model: str):
    import httpx
    base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "max_tokens": max_tokens,
        "temperature": 0.4,
        "stream": True,
        "stream_options": {"include_usage": True},  # 末尾块携带 token 用量(OpenAI/通义兼容)
    }
    _last_usage.update({"token_in": 0, "token_out": 0, "cost_est": 0.0, "model": model})
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST", f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                usage = obj.get("usage")
                if usage:
                    ti = usage.get("prompt_tokens", 0); to = usage.get("completion_tokens", 0)
                    pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
                    cost = (ti * pricing["input"] + to * pricing["output"]) / 1_000_000
                    _last_usage.update({"token_in": ti, "token_out": to, "cost_est": round(cost, 6), "model": model})
                choices = obj.get("choices") or [{}]
                if choices:
                    delta = (choices[0].get("delta") or {}).get("content")
                    if delta:
                        yield delta


async def _stream_anthropic(system_prompt: str, messages: list[dict], max_tokens: int,
                            base_url: str, api_key: str, model: str):
    import httpx
    base_url = (base_url or "https://api.anthropic.com").rstrip("/")
    payload = {
        "model": model,
        "system": system_prompt,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.4,
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST", f"{base_url}/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                try:
                    obj = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "content_block_delta":
                    txt = (obj.get("delta") or {}).get("text")
                    if txt:
                        yield txt


def _mock_response(prompt: str) -> str:
    """Generate mock AI response for development/testing."""
    if "应收账款" in prompt or "receivable" in prompt.lower():
        return json.dumps({
            "risk_level": "M",
            "overdue_summary": "存在部分逾期应收，需重点跟进逾期账期的回款。",
            "collection_actions": [
                {"action": "电话联系客户财务确认逾期款项付款计划", "priority": "H", "deadline": "3天内"},
                {"action": "发送对账函并附逾期提醒", "priority": "M", "deadline": "1周内"},
                {"action": "评估是否启动分期或担保措施", "priority": "L", "deadline": "2周内"},
            ],
            "cash_flow_comment": "未收比例偏高会占用现金流，建议加快回款节奏。",
            "overall_comment": "整体回款风险中等，重点关注逾期部分，建议按上述动作分级催收。",
        }, ensure_ascii=False)

    if "销售话术" in prompt or "话术" in prompt or "script" in prompt.lower():
        return json.dumps({
            "opening": "您好，了解到贵司近期在推进相关项目，我们在同行业有成熟落地案例，想用几分钟同步一下可能的价值点。",
            "value_props": ["行业标杆案例可复制", "分阶段实施降低风险", "服务响应快、总拥有成本低"],
            "discovery_questions": ["当前最迫切要解决的问题是什么？", "决策与预算的时间窗口如何？", "对比方案时最看重哪些点？"],
            "objection_handling": [
                {"objection": "价格偏高", "response": "从总拥有成本和交付确定性看更划算，可提供分期方案"},
                {"objection": "已有供应商", "response": "可先小范围试点验证效果，再评估切换"},
            ],
            "closing": "如果方向合适，本周安排一次技术方案交流，会后给到正式报价，您看周几方便？",
            "tips": ["强调差异化价值而非比价", "尽快锁定下一步动作与时间点"],
        }, ensure_ascii=False)

    if "风险" in prompt or "risk" in prompt.lower():
        return json.dumps({
            "risk_level": "M",
            "risks": [
                {"category": "技术", "description": "技术方案复杂度较高，需关注集成风险", "severity": "M", "mitigation": "提前进行技术验证 POC"},
                {"category": "商务", "description": "客户预算周期可能影响签约节奏", "severity": "L", "mitigation": "与客户财务部门保持沟通"},
                {"category": "竞争", "description": "存在竞品低价竞争的可能", "severity": "M", "mitigation": "强化差异化价值展示"},
            ],
            "overall_assessment": "综合风险等级为中等，建议重点关注技术验证和竞品动态。",
        }, ensure_ascii=False)

    if "画像" in prompt or "profile" in prompt.lower():
        return json.dumps({
            "industry_position": "行业中上游企业，具有较强的区域影响力",
            "decision_pattern": "决策链较长，需经过技术评估、采购审批、管理层批准三个环节",
            "pain_points": ["信息化水平较低", "部门间数据孤岛严重", "管理效率待提升"],
            "opportunities": ["数字化转型需求迫切", "管理层重视IT投入", "预算充足"],
            "recommended_approach": "以管理效率提升为切入点，提供分阶段实施方案",
        }, ensure_ascii=False)

    if "赢率" in prompt or "probability" in prompt.lower():
        return json.dumps({
            "win_probability": 65,
            "factors": {
                "positive": ["客户需求明确", "决策人关系良好", "技术方案匹配度高"],
                "negative": ["竞品价格较低", "项目周期较长", "内部资源紧张"],
            },
            "recommendation": "建议加快报价节奏，在竞品介入前锁定客户选型意向",
        }, ensure_ascii=False)

    if "行动" in prompt or "action" in prompt.lower():
        return json.dumps({
            "next_actions": [
                {"action": "安排技术方案汇报会议", "priority": "H", "deadline": "3天内", "owner": "技术经理"},
                {"action": "提交正式报价方案", "priority": "H", "deadline": "5天内", "owner": "销售负责人"},
                {"action": "邀请客户参观标杆案例", "priority": "M", "deadline": "2周内", "owner": "客户经理"},
            ],
            "stage_suggestion": "当前阶段建议推进至方案报价(S3)，重点完成技术验证和正式报价。",
        }, ensure_ascii=False)

    if "报价" in prompt or "quote" in prompt.lower():
        return json.dumps({
            "risk_level": "L",
            "review_items": [
                {"item": "定价合理性", "status": "pass", "detail": "价格在市场合理范围内"},
                {"item": "利润率", "status": "warning", "detail": "毛利率偏低 (18%)，建议调整外协成本"},
                {"item": "付款条款", "status": "pass", "detail": "付款条款标准，风险可控"},
            ],
            "overall_comment": "报价整体合理，建议关注利润率优化空间。",
        }, ensure_ascii=False)

    if "合同" in prompt or "contract" in prompt.lower():
        return json.dumps({
            "risk_level": "M",
            "clauses": [
                {"clause": "交付周期", "risk": "M", "detail": "交付周期较紧，需评估产能"},
                {"clause": "违约条款", "risk": "L", "detail": "违约金比例在合理范围"},
                {"clause": "知识产权", "risk": "H", "detail": "IP 归属条款缺失，建议补充"},
            ],
            "overall_comment": "合同主要风险在交付周期和知识产权条款，建议在签署前补充完善。",
        }, ensure_ascii=False)

    if "汇总" in prompt or "跟进记录" in prompt or "summarize" in prompt.lower():
        return json.dumps({
            "summary": "近期跟进活跃，客户方已完成内部需求评审，正等待我方正式报价方案。",
            "key_points": [
                "客户完成内部需求评审，需求范围已确定",
                "技术方案获客户技术团队认可",
                "竞品正在低价策略抢客户",
                "客户Q2预算已到位，签约窗口期3-4月",
            ],
            "suggestion": "建议尽快提交正式报价，强调技术优势和服务价值，避免陷入价格战。",
        }, ensure_ascii=False)

    if "相似" in prompt or "similar" in prompt.lower():
        return json.dumps({
            "similar_projects": [
                {"name": "XX公司数字化转型", "similarity_score": 85, "reason": "同行业、相近金额、已赢单"},
                {"name": "YY集团MES项目", "similarity_score": 72, "reason": "相似技术栈、同阶段推进"},
                {"name": "ZZ工厂智能制造", "similarity_score": 68, "reason": "同金额区间、类似决策流程"},
            ],
            "insights": "相似赢单项目的共同特征是在S3阶段快速推进技术验证，平均签约周期45天。建议参考XX公司项目的推进策略。",
        }, ensure_ascii=False)

    return json.dumps({"message": "AI 分析完成", "result": "暂无特定分析结果"}, ensure_ascii=False)


async def _get_template_text(task_type: str, tenant_id: str | None = None) -> str | None:
    """Try to load a prompt template from DB for the given task_type.

    Returns template_text if found and active, otherwise None (fallback to hardcoded).
    """
    if not tenant_id:
        return None
    try:
        from app.database import async_session_factory
        from sqlalchemy import select
        from app.domains.ai_center.models import AiPromptTemplate
        async with async_session_factory() as db:
            t = (await db.execute(
                select(AiPromptTemplate).where(
                    AiPromptTemplate.tenant_id == tenant_id,
                    AiPromptTemplate.task_type == task_type,
                    AiPromptTemplate.is_active == True,
                ).order_by(AiPromptTemplate.created_at.desc()).limit(1)
            )).scalar_one_or_none()
            return t.template_text if t else None
    except Exception:
        return None


def _render_template(template: str, variables: dict) -> str:
    """Simple template rendering: replace {{key}} with value."""
    result = template
    for key, val in variables.items():
        result = result.replace("{{" + key + "}}", str(val or ""))
    return result


async def analyze_project_risk(project_data: dict, tenant_id: str | None = None, chat_cfg: dict | None = None) -> dict:
    """Analyze project risk based on project data."""
    # Try to use a DB template first
    template = await _get_template_text("quote_risk_analysis", tenant_id)
    if template:
        prompt = _render_template(template, project_data)
    else:
        prompt = f"""请对以下商机项目进行风险评估分析：
项目名称: {project_data.get('name', '')}
阶段: {project_data.get('stage_code', '')}
预期金额: {project_data.get('amount_expect', 0)}
客户: {project_data.get('customer_name', '')}
行业: {project_data.get('industry', '')}

请从技术、商务、竞争三个维度分析风险。
严格按以下 JSON 输出，只输出 JSON、不要 markdown 或多余文字，键名保持英文原样：
{{"risk_level":"H|M|L","risks":[{{"category":"技术/商务/竞争","description":"...","severity":"H|M|L","mitigation":"..."}}],"overall_assessment":"一段总体评估"}}"""

    system = "你是一位CRM销售风险分析专家。只输出符合要求的 JSON，键名用英文，值用中文。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return _extract_json(result)
    except json.JSONDecodeError:
        return {"raw_response": result}


async def generate_customer_profile(customer_data: dict, tenant_id: str | None = None, chat_cfg: dict | None = None) -> dict:
    """Generate AI customer profile/portrait."""
    template = await _get_template_text("customer_insight", tenant_id)
    if template:
        prompt = _render_template(template, customer_data)
    else:
        prompt = f"""请为以下客户生成智能画像分析：
客户名称: {customer_data.get('name', '')}
行业: {customer_data.get('industry', '')}
等级: {customer_data.get('level', '')}
商机数: {customer_data.get('project_count', 0)}
总金额: {customer_data.get('total_amount', 0)}

请分析客户的行业定位、决策模式、痛点和机会。
严格按以下 JSON 输出，只输出 JSON、不要多余文字，键名保持英文原样：
{{"industry_position":"...","decision_pattern":"...","pain_points":["..."],"opportunities":["..."],"recommended_approach":"..."}}"""

    system = "你是一位CRM客户分析专家。只输出符合要求的 JSON，键名用英文，值用中文。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return _extract_json(result)
    except json.JSONDecodeError:
        return {"raw_response": result}


async def predict_win_probability(project_data: dict, chat_cfg: dict | None = None) -> dict:
    """Predict win probability for a project."""
    prompt = f"""请预测以下商机的赢单概率：
项目: {project_data.get('name', '')}
阶段: {project_data.get('stage_code', '')}
金额: {project_data.get('amount_expect', 0)}
风险等级: {project_data.get('risk_level', 'M')}
创建天数: {project_data.get('days_since_created', 0)}

请评估赢率并给出积极/消极因素分析。
严格按以下 JSON 输出，只输出 JSON、不要多余文字，键名保持英文原样：
{{"win_probability":0-100的整数,"factors":{{"positive":["..."],"negative":["..."]}},"recommendation":"..."}}"""

    system = "你是一位CRM销售预测专家。只输出符合要求的 JSON，键名用英文，值用中文。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return _extract_json(result)
    except json.JSONDecodeError:
        return {"raw_response": result}


async def review_quote(quote_data: dict, chat_cfg: dict | None = None) -> dict:
    """Review a quote version for risk and pricing issues."""
    prompt = f"""请对以下报价进行审核分析：
报价编号: {quote_data.get('quote_no', '')}
版本: V{quote_data.get('version_no', 1)}
报价金额: {quote_data.get('total_amount', 0)}
成本合计: {quote_data.get('total_cost', 0)}
行项数量: {quote_data.get('line_count', 0)}
客户: {quote_data.get('customer_name', '')}

请从定价合理性、利润率、付款条款等维度审核。
严格按以下 JSON 输出，只输出 JSON、不要多余文字，键名保持英文原样：
{{"risk_level":"H|M|L","review_items":[{{"item":"...","status":"pass|warning|fail","detail":"..."}}],"overall_comment":"..."}}"""

    system = "你是一位CRM报价审核专家。只输出符合要求的 JSON，键名用英文，值用中文。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return _extract_json(result)
    except json.JSONDecodeError:
        return {"raw_response": result}


async def review_contract(contract_data: dict, chat_cfg: dict | None = None) -> dict:
    """Review a contract for risk clauses."""
    prompt = f"""请对以下合同进行风险条款审核：
合同编号: {contract_data.get('contract_no', '')}
合同金额: {contract_data.get('amount_total', 0)}
版本: V{contract_data.get('version_no', 1)}
客户: {contract_data.get('customer_name', '')}

请从交付周期、违约条款、知识产权、付款条件等维度审核合同风险。
严格按以下 JSON 输出，只输出 JSON、不要多余文字，键名保持英文原样：
{{"risk_level":"H|M|L","clauses":[{{"clause":"...","risk":"H|M|L","detail":"..."}}],"overall_comment":"..."}}"""

    system = "你是一位CRM合同审核专家。只输出符合要求的 JSON，键名用英文，值用中文。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return _extract_json(result)
    except json.JSONDecodeError:
        return {"raw_response": result}


async def suggest_next_actions(project_data: dict, tenant_id: str | None = None, chat_cfg: dict | None = None) -> dict:
    """Suggest next actions for a project."""
    template = await _get_template_text("next_action", tenant_id)
    if template:
        prompt = _render_template(template, project_data)
    else:
        prompt = f"""请为以下商机推荐下一步行动计划：
项目: {project_data.get('name', '')}
当前阶段: {project_data.get('stage_code', '')}
客户: {project_data.get('customer_name', '')}
最近动态: {project_data.get('last_activity', '暂无')}

请推荐3-5个具体行动项。
严格按以下 JSON 输出，只输出 JSON、不要多余文字，键名保持英文原样：
{{"next_actions":[{{"action":"...","priority":"H|M|L","deadline":"如3天内","owner":"角色"}}],"stage_suggestion":"..."}}"""

    system = "你是一位CRM销售教练。只输出符合要求的 JSON，键名用英文，值用中文。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return _extract_json(result)
    except json.JSONDecodeError:
        return {"raw_response": result}


async def summarize_activity(activities: list[dict], chat_cfg: dict | None = None) -> dict:
    """Summarize a list of activity records into a concise AI summary."""
    if not activities:
        return {"summary": "暂无活动记录。", "key_points": [], "suggestion": ""}

    activity_text = "\n".join([
        f"- [{a.get('activity_type', 'note')}] {a.get('subject', '')} - {a.get('content', '')[:100]} ({a.get('created_at', '')})"
        for a in activities[:30]
    ])

    prompt = f"""请对以下客户/商机的近期跟进记录进行汇总分析：

{activity_text}

请输出JSON格式，包含：
1. summary: 一段简洁的总结（100字以内）
2. key_points: 关键要点列表（3-5条）
3. suggestion: 下一步建议"""

    system = "你是一位CRM销售助理。请以JSON格式输出活动记录汇总分析。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return _extract_json(result)
    except json.JSONDecodeError:
        return {"summary": result[:200], "key_points": [], "suggestion": ""}


async def find_similar_projects(project_data: dict, candidates: list[dict], chat_cfg: dict | None = None) -> dict:
    """Find similar projects from a list of candidates based on industry/amount/stage."""
    if not candidates:
        return {"similar_projects": [], "insights": ""}

    candidates_text = "\n".join([
        f"- {c.get('name', '')} | 阶段: {c.get('stage_code', '')} | 金额: {c.get('amount_expect', 0)} | 状态: {c.get('status', '')} | 行业: {c.get('industry', '')}"
        for c in candidates[:20]
    ])

    prompt = f"""当前商机：
名称: {project_data.get('name', '')}
阶段: {project_data.get('stage_code', '')}
金额: {project_data.get('amount_expect', 0)}
行业: {project_data.get('industry', '')}

候选商机列表：
{candidates_text}

请从行业、金额、阶段等维度匹配最相似的商机（最多5个），并给出经验借鉴建议。
输出JSON格式：
{{"similar_projects": [{{"name": "...", "similarity_score": 85, "reason": "..."}}], "insights": "..."}}"""

    system = "你是一位CRM销售分析专家。请以JSON格式输出相似商机匹配结果。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return _extract_json(result)
    except json.JSONDecodeError:
        return {"similar_projects": [], "insights": result[:200]}


async def analyze_receivable(data: dict, chat_cfg: dict | None = None) -> dict:
    """合同应收账款风险分析（回款/逾期/催收建议）。"""
    prompt = f"""请对以下合同的应收账款与回款情况进行风险分析：
合同编号: {data.get('contract_no', '')}
客户: {data.get('customer_name', '')}
合同总额: {data.get('amount_total', 0)}
已回款: {data.get('collected', 0)}
未回款: {data.get('outstanding', 0)}
回款率: {data.get('collection_rate', 0)}%
逾期金额: {data.get('overdue_amount', 0)}
最长逾期天数: {data.get('overdue_days', 0)}
逾期笔数: {data.get('overdue_plan_count', 0)} / 回款计划数: {data.get('plan_count', 0)}
签约日期: {data.get('signed_date', '')}  到期日期: {data.get('end_date', '')}

请评估回款风险、说明逾期状况、给出分级催收动作与现金流影响。
严格按以下 JSON 输出，只输出 JSON、不要多余文字，键名保持英文原样：
{{"risk_level":"H|M|L","overdue_summary":"...","collection_actions":[{{"action":"...","priority":"H|M|L","deadline":"如3天内"}}],"cash_flow_comment":"...","overall_comment":"..."}}"""

    system = "你是一位企业应收账款与回款管理专家。只输出符合要求的 JSON，键名用英文，值用中文。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return _extract_json(result)
    except json.JSONDecodeError:
        return {"raw_response": result}


async def recommend_sales_script(data: dict, chat_cfg: dict | None = None) -> dict:
    """根据商机/客户上下文推荐销售话术。"""
    prompt = f"""请为以下销售场景生成实战销售话术建议：
名称: {data.get('name', '')}
客户: {data.get('customer_name', '')}
行业: {data.get('industry', '')}
所处阶段: {data.get('stage_code', '')}
预期金额: {data.get('amount_expect', 0)}
风险等级: {data.get('risk_level', '')}
近期动态: {data.get('last_activity', '暂无')}

请给出：开场白、核心价值主张、挖掘需求的提问、常见异议及应对、促成话术、实战提示。
严格按以下 JSON 输出，只输出 JSON、不要多余文字，键名保持英文原样：
{{"opening":"...","value_props":["..."],"discovery_questions":["..."],"objection_handling":[{{"objection":"...","response":"..."}}],"closing":"...","tips":["..."]}}"""

    system = "你是一位资深B2B销售教练。只输出符合要求的 JSON，键名用英文，值用中文，话术要具体可用。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return _extract_json(result)
    except json.JSONDecodeError:
        return {"raw_response": result}
