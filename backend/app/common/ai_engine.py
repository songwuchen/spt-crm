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

# Approximate pricing per 1M tokens (USD)
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "mock": {"input": 0, "output": 0},
}


def get_last_usage() -> dict:
    """Get token usage from the last LLM call."""
    return dict(_last_usage)


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
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o"])
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


def _mock_response(prompt: str) -> str:
    """Generate mock AI response for development/testing."""
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

请从技术、商务、竞争三个维度分析风险，输出JSON格式。"""

    system = "你是一位CRM销售风险分析专家。请以JSON格式输出风险评估结果。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return json.loads(result)
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

请分析客户的行业定位、决策模式、痛点和机会，输出JSON格式。"""

    system = "你是一位CRM客户分析专家。请以JSON格式输出客户画像分析。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return json.loads(result)
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

请评估赢率并给出积极/消极因素分析，输出JSON格式。"""

    system = "你是一位CRM销售预测专家。请以JSON格式输出赢率预测。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return json.loads(result)
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

请从定价合理性、利润率、付款条款等维度审核，输出JSON格式。"""

    system = "你是一位CRM报价审核专家。请以JSON格式输出审核结果，包含 review_items 列表和 overall_comment。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"raw_response": result}


async def review_contract(contract_data: dict, chat_cfg: dict | None = None) -> dict:
    """Review a contract for risk clauses."""
    prompt = f"""请对以下合同进行风险条款审核：
合同编号: {contract_data.get('contract_no', '')}
合同金额: {contract_data.get('amount_total', 0)}
版本: V{contract_data.get('version_no', 1)}
客户: {contract_data.get('customer_name', '')}

请从交付周期、违约条款、知识产权、付款条件等维度审核合同风险，输出JSON格式。"""

    system = "你是一位CRM合同审核专家。请以JSON格式输出审核结果，包含 clauses 风险列表和 overall_comment。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return json.loads(result)
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

请推荐3-5个具体行动项，输出JSON格式。"""

    system = "你是一位CRM销售教练。请以JSON格式输出行动建议。"
    result = await _call_llm(system, prompt, chat_cfg=chat_cfg)
    try:
        return json.loads(result)
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
        return json.loads(result)
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
        return json.loads(result)
    except json.JSONDecodeError:
        return {"similar_projects": [], "insights": result[:200]}
