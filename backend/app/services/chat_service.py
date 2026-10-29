import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm_options import completion_options
from app.db.session import SessionLocal
from app.models.assessment import Assessment
from app.models.breakthrough_selection import BreakthroughSelection
from app.models.canvas_diagnosis import CanvasDiagnosis
from app.models.case_recommendation import CaseRecommendation
from app.models.competitiveness_analysis import CompetitivenessAnalysis
from app.models.direction_expansion import DirectionExpansion
from app.models.direction_selection import DirectionSelection
from app.models.endgame_analysis import EndgameAnalysis
from app.models.generated_report import GeneratedReport
from app.models.scenario_recommendation import ScenarioRecommendation
from app.models.chat import Conversation, Message

logger = logging.getLogger(__name__)
MAX_ATTACHMENT_TEXT_CHARS = 12000
DEFAULT_ATTACHMENT_PROMPT = "请先提炼我上传资料中的关键信息，并结合当前评估上下文给出建议。"

# 模块生成顺序（从早到晚）。用于按用户当前页面位置过滤 context，
# 防止 AI 提前泄露用户尚未到达的后续模块内容。
PAGE_MODULE_ORDER = [
    "profile", "canvas", "scoring", "directions",
    "scenarios", "competitiveness", "endgame", "results",
]

PAGE_LABELS: dict[str, str] = {
    "profile": "企业画像",
    "canvas": "商业画布诊断",
    "scoring": "BMC 突破要素评分",
    "directions": "创新方向延展",
    "scenarios": "AI 场景推荐",
    "competitiveness": "差异化竞争力分析",
    "endgame": "商业终局设计",
    "results": "结果仪表盘",
}


def _build_context(assessment_id: str, db: Session, current_page: str | None = None) -> str:
    """Build AI context from all generated assessment results, with progress table.

    When current_page is provided, only modules up to and including the current
    page position are exposed to the AI — future modules are hidden to prevent
    the assistant from leaking content the user hasn't reached yet.
    """
    parts: list[str] = []
    progress_rows: list[str] = []

    # Determine which modules the AI is allowed to see
    allowed_modules: set[str] = set(PAGE_MODULE_ORDER)
    if current_page and current_page in PAGE_MODULE_ORDER:
        idx = PAGE_MODULE_ORDER.index(current_page)
        allowed_modules = set(PAGE_MODULE_ORDER[:idx + 1])

    # Assessment basic info (always present)
    assessment = db.scalar(
        select(Assessment).where(Assessment.id == assessment_id)
    )
    if not assessment:
        return "暂无评估数据。"

    parts.append("## 企业基础信息")
    parts.append(f"- 公司名称：{assessment.company_name}")
    parts.append(f"- 行业：{assessment.industry}")
    parts.append(f"- 规模：{assessment.company_size}")
    parts.append(f"- 地区：{assessment.region}")
    parts.append(f"- 收入范围：{assessment.annual_revenue_range}")
    parts.append(f"- 核心产品：{assessment.core_products}")
    parts.append(f"- 目标客户：{assessment.target_customers}")
    parts.append(f"- 当前挑战：{assessment.current_challenges}")
    parts.append(f"- AI 目标：{assessment.ai_goals}")
    parts.append(f"- 可用数据：{assessment.available_data}")
    if assessment.notes:
        parts.append(f"- 备注：{assessment.notes}")

    # ── 1. Company profile ──
    has_profile = bool(assessment.profile_payload) and "profile" in allowed_modules
    progress_rows.append(f"| 企业画像 | {'✅ 已生成' if has_profile else '❌ 未生成'} |")
    if has_profile and assessment.profile_payload:
        try:
            profile_data = json.loads(assessment.profile_payload)
            if isinstance(profile_data, dict):
                parts.append("\n## 企业画像")
                for key, value in profile_data.items():
                    value_str = str(value)
                    if len(value_str) > 300:
                        value_str = value_str[:300] + "..."
                    parts.append(f"- {key}：{value_str}")
        except (json.JSONDecodeError, TypeError):
            pass

    # ── 2. Canvas diagnosis ──
    canvas = db.scalar(
        select(CanvasDiagnosis).where(CanvasDiagnosis.assessment_id == assessment_id)
    )
    has_canvas = canvas is not None and "canvas" in allowed_modules
    progress_rows.append(f"| 商业画布 | {'✅ 已生成' if has_canvas else '❌ 未生成'} |")
    if canvas:
        parts.append("\n## 商业画布 9 格诊断")
        parts.append(f"总分：{canvas.overall_score}")
        if canvas.canvas_json:
            try:
                canvas_data = json.loads(canvas.canvas_json)
                if isinstance(canvas_data, dict):
                    summary = canvas_data.get("overall_summary", "")
                    if summary:
                        parts.append(f"总结：{summary}")
            except (json.JSONDecodeError, TypeError):
                pass

    # ── 3. Breakthrough selection ──
    breakthrough = db.scalar(
        select(BreakthroughSelection).where(
            BreakthroughSelection.assessment_id == assessment_id
        )
    )
    has_breakthrough = breakthrough is not None and "scoring" in allowed_modules
    progress_rows.append(
        f"| BMC 突破要素 | {'✅ 已生成' if has_breakthrough else '❌ 未生成'} |"
    )
    if has_breakthrough:
        try:
            selected = json.loads(breakthrough.selected_elements_json)
            if isinstance(selected, list) and selected:
                parts.append(f"\n## BMC 突破要素（{len(selected)} 个）")
                for elem in selected:
                    if isinstance(elem, str):
                        parts.append(f"- {elem}")
                    elif isinstance(elem, dict):
                        parts.append(
                            f"- {elem.get('key', elem.get('title', str(elem)))}"
                        )
        except (json.JSONDecodeError, TypeError):
            pass

    # ── 4. Direction expansion & selection ──
    direction_sel = db.scalar(
        select(DirectionSelection).where(
            DirectionSelection.assessment_id == assessment_id
        )
    )
    has_directions = (
        direction_sel is not None
        and bool(getattr(direction_sel, "directions_json", None))
        and "directions" in allowed_modules
    )
    progress_rows.append(
        f"| 方向延展 | {'✅ 已生成' if has_directions else '❌ 未生成'} |"
    )
    if has_directions and direction_sel.directions_json:
        try:
            dirs = json.loads(direction_sel.directions_json)
            if isinstance(dirs, list) and dirs:
                parts.append(f"\n## 已选创新方向（{len(dirs)} 个）")
                for d in dirs:
                    if isinstance(d, dict):
                        parts.append(
                            f"- {d.get('title', '')}: {d.get('description', '')}"
                        )
        except (json.JSONDecodeError, TypeError):
            pass

    # ── 5. Competitiveness analysis ──
    competitiveness = db.scalar(
        select(CompetitivenessAnalysis).where(
            CompetitivenessAnalysis.assessment_id == assessment_id
        )
    )
    has_competitiveness = competitiveness is not None and "competitiveness" in allowed_modules
    progress_rows.append(
        f"| 竞争力分析 | {'✅ 已生成' if has_competitiveness else '❌ 未生成'} |"
    )
    if has_competitiveness:
        parts.append("\n## 竞争力分析")
        try:
            strategy = json.loads(competitiveness.strategy_json)
            if isinstance(strategy, dict):
                for key in ("summary", "core_strategy", "recommendation"):
                    if key in strategy:
                        val = str(strategy[key])
                        if len(val) > 500:
                            val = val[:500] + "..."
                        parts.append(f"- {key}：{val}")
        except (json.JSONDecodeError, TypeError):
            pass

    # ── 6. Endgame analysis ──
    endgame = db.scalar(
        select(EndgameAnalysis).where(
            EndgameAnalysis.assessment_id == assessment_id
        )
    )
    has_endgame = endgame is not None and bool(endgame.overall_narrative) and "endgame" in allowed_modules
    progress_rows.append(
        f"| 终局设计 | {'✅ 已生成' if has_endgame else '❌ 未生成'} |"
    )
    if has_endgame and endgame.overall_narrative:
        parts.append("\n## 商业终局设计")
        narrative = endgame.overall_narrative
        if len(narrative) > 800:
            narrative = narrative[:800] + "..."
        parts.append(narrative)

    # ── 7. Scenario recommendations ──
    scenarios = db.scalar(
        select(ScenarioRecommendation).where(
            ScenarioRecommendation.assessment_id == assessment_id
        )
    )
    has_scenarios = scenarios is not None and "scenarios" in allowed_modules
    progress_rows.append(
        f"| 场景推荐 | {'✅ 已生成' if has_scenarios else '❌ 未生成'} |"
    )
    if has_scenarios:
        try:
            top = json.loads(scenarios.top_scenarios)
            if isinstance(top, list) and top:
                parts.append(f"\n## 场景推荐（Top {len(top)}）")
                for s in top:
                    parts.append(f"- {s}")
        except (json.JSONDecodeError, TypeError):
            pass

        # 读取 scenario_json 以获取四象限评分详情
        if scenarios.scenario_json:
            try:
                scenario_details = json.loads(scenarios.scenario_json)
                if isinstance(scenario_details, list) and scenario_details:
                    parts.append(f"\n### 场景评分详情（{scenarios.scoring_method}）")
                    for detail in scenario_details:
                        if isinstance(detail, dict):
                            name = detail.get("name", "")
                            quadrant = detail.get("priority_quadrant", "")
                            lps = detail.get("priority_lps_display", "")
                            rec = detail.get("priority_recommendation", "")
                            parts.append(f"- {name}")
                            if quadrant:
                                parts.append(f"  象限：{quadrant}")
                            if lps is not None and lps != "":
                                parts.append(f"  综合优先级分：{lps}")
                            if rec:
                                parts.append(f"  建议：{rec}")
            except (json.JSONDecodeError, TypeError):
                pass

    # ── 8. Case recommendations ──
    cases = db.scalar(
        select(CaseRecommendation).where(
            CaseRecommendation.assessment_id == assessment_id
        )
    )
    has_cases = cases is not None and "competitiveness" in allowed_modules
    progress_rows.append(
        f"| 案例匹配 | {'✅ 已生成' if has_cases else '❌ 未生成'} |"
    )
    if has_cases:
        try:
            top = json.loads(cases.top_cases)
            if isinstance(top, list) and top:
                parts.append(f"\n## 案例匹配（Top {len(top)}）")
                for c in top:
                    parts.append(f"- {c}")
        except (json.JSONDecodeError, TypeError):
            pass

    # ── 9. Report ──
    report = db.scalar(
        select(GeneratedReport).where(
            GeneratedReport.assessment_id == assessment_id
        )
    )
    has_report = report is not None and "results" in allowed_modules
    progress_rows.append(
        f"| 报告 | {'✅ 已生成' if has_report else '❌ 未生成'} |"
    )

    # ── Build progress table, prepended to context ──
    progress_table = (
        "## 模块生成状态\n\n"
        "| 模块 | 状态 |\n"
        "|------|------|\n"
        + "\n".join(progress_rows)
        + "\n\n> 你只能基于上述 ✅ 已生成 的模块数据回答用户问题。"
        "对于未生成的模块，如果用户问到相关内容，请引导用户先去生成该模块，不要猜测或编造数据。\n"
    )

    return progress_table + "\n" + "\n".join(parts)


SYSTEM_PROMPT_TEMPLATE = """你是一个 AI 商业创新顾问，专门帮助企业分析商业模式、制定 AI 转型策略。

## 当前企业评估数据

{context}

## 对话要求

- 基于上面的评估数据回答用户问题，优先引用已生成模块中的具体信息
- 回答简洁专业，聚焦可落地的商业建议
- 用户可能在不同页面（画布、方向延展、终局设计、结果仪表盘）与你对话
- 当用户在新页面生成新结果后，你会自动获得更新后的上下文
{page_hint}
## 重要约束

- 最上方的"模块生成状态"表格列出了每个模块的生成状态
- 对于标记为"❌ 未生成"的模块，不要在回答中主动提及或讨论其内容
- 如果用户问到的内容涉及未生成模块，诚实告知该模块尚未生成，引导用户先去完成对应步骤
- 不要猜测或编造未生成模块的数据
- 不要提前讲解用户尚未到达的后续步骤的详细方案；如果用户询问后续内容，用简短方式说明"后续页面会逐步展开，现在请先完成当前步骤"

请用中文回答。"""


def build_system_prompt(assessment_id: str, db: Session, current_page: str | None = None) -> str:
    context = _build_context(assessment_id, db, current_page=current_page)
    page_hint = ""
    if current_page:
        label = PAGE_LABELS.get(current_page, current_page)
        page_hint = (
            f"- 用户当前正在查看「{label}」页面，请严格围绕该页面及之前已完成步骤的内容回答\n"
            f"- 可以讨论当前页面及之前已完成步骤的内容，但不要提前透露后续步骤的详细方案\n"
        )
    return SYSTEM_PROMPT_TEMPLATE.format(context=context, page_hint=page_hint)


def _compose_user_message(
    user_message: str,
    attachments: list[dict[str, object]] | None = None,
) -> str:
    cleaned_message = user_message.strip()
    cleaned_attachments = attachments or []
    if not cleaned_attachments:
        return cleaned_message

    parts: list[str] = [cleaned_message or DEFAULT_ATTACHMENT_PROMPT, "", "## 用户上传资料"]
    for attachment in cleaned_attachments:
        file_name = str(attachment.get("name", "未命名文件"))
        file_kind = str(attachment.get("kind", "unknown"))
        warnings = attachment.get("warnings", [])
        extracted_text = str(attachment.get("content", "")).strip()
        if len(extracted_text) > MAX_ATTACHMENT_TEXT_CHARS:
            extracted_text = (
                extracted_text[:MAX_ATTACHMENT_TEXT_CHARS].rstrip()
                + "\n\n[内容过长，已截断]"
            )

        parts.append(f"### 文件：{file_name} ({file_kind})")
        if warnings:
            parts.append("解析提示：" + "；".join(str(item) for item in warnings))
        parts.append(extracted_text or "[未提取到文本内容]")

    return "\n".join(parts).strip()


async def stream_chat(
    assessment_id: str,
    user_message: str,
    attachments: list[dict[str, object]] | None = None,
    current_page: str | None = None,
):
    """Stream AI chat response via SSE using DeepSeek API.

    Yields SSE-formatted strings:
        data: {"token": "..."}
        data: {"done": true, "message_id": "..."}
        data: {"error": "..."}

    When current_page is provided, the system prompt and context are scoped
    to only include modules up to the user's current page position,
    preventing the AI from leaking future content.
    """
    db = SessionLocal()
    conversation = None
    assistant_content = ""

    try:
        # Load or create conversation
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.assessment_id == assessment_id
            )
        )
        if conversation is None:
            conversation = Conversation(assessment_id=assessment_id)
            db.add(conversation)
            db.flush()
            db.refresh(conversation)

        # Save user message
        composed_message = _compose_user_message(user_message, attachments)

        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=composed_message,
        )
        db.add(user_msg)
        db.commit()

        # Build system prompt with latest context (scoped to current_page)
        system_prompt = build_system_prompt(assessment_id, db, current_page=current_page)

        # Load recent history (last 20 messages)
        history = db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(20)
        ).all()
        history.reverse()

        # Build messages for DeepSeek
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        # Call DeepSeek streaming
        if settings.llm_mode != "live" or not settings.openai_api_key:
            yield f"data: {json.dumps({'error': 'LLM 未启用，请在 mykey.py 中设置 llm_mode=live'})}\n\n"
            return

        from openai import OpenAI

        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

        stream = client.chat.completions.create(
            model=settings.openai_model,
            **completion_options(),
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                assistant_content += delta.content
                yield f"data: {json.dumps({'token': delta.content})}\n\n"

        # Save assistant message
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
        )
        db.add(assistant_msg)
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()

        yield f"data: {json.dumps({'done': True, 'message_id': assistant_msg.id})}\n\n"

    except Exception as exc:
        logger.warning("Chat stream error for assessment %s: %s", assessment_id, exc)
        yield f"data: {json.dumps({'error': str(exc)})}\n\n"
    finally:
        db.close()
