from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.assessment import (  # noqa: E402
    BusinessModelCanvasResult,
    CanvasBlockResult,
    CanvasDiagnosisResult,
    CompanyProfileResult,
    ScenarioRecommendationItem,
    ScenarioRecommendationResult,
)
from app.schemas.competitiveness import (  # noqa: E402
    CompetitivenessResult,
    CoreAdvantage,
    DeliveryStrategy,
    PointToLineConnection,
    VPReconstruction,
)
from app.exporters.html_exporter import HtmlExporter  # noqa: E402
from app.services.report_builder import ReportBuilder  # noqa: E402


def _assessment() -> SimpleNamespace:
    return SimpleNamespace(
        id="assessment-competitiveness-template",
        company_name="测试企业",
        industry="零售",
        company_size="100-499人",
        region="华东",
        annual_revenue_range="5000万-1亿元",
        core_products="门店运营",
        target_customers="会员客户",
        current_challenges="复购波动",
        ai_goals="提升经营效率",
        available_data="POS、会员系统",
        notes=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _profile() -> CompanyProfileResult:
    return CompanyProfileResult(
        company_name="测试企业",
        company_summary="一家正在推进数字化转型的零售企业。",
        value_proposition="帮助门店提升经营效率",
        customer_and_market="社区家庭用户与会员客户",
        operations_and_resources="已有 POS、会员系统和巡店记录",
        digital_and_ai_readiness="具备基础数字化系统，可推进业务场景试点。",
        key_challenges=["复购波动", "经验难复制"],
        priority_ai_directions=["知识沉淀复用", "客户关系深化"],
        missing_information=[],
    )


def _canvas() -> CanvasDiagnosisResult:
    return CanvasDiagnosisResult(
        generation_mode="mock",
        overall_score=80,
        weakest_blocks=["客户关系", "渠道通路"],
        recommended_focus=["优化客户分层"],
        canvas=BusinessModelCanvasResult(
            overall_summary="整体画布具备推进条件。",
            blocks=[
                CanvasBlockResult(
                    key="value_propositions",
                    title="价值主张",
                    current_state="帮助门店提升经营效率。",
                    diagnosis="价值主张需要增强。",
                    ai_opportunity="可通过 AI 串联关键环节。",
                    missing_information="内部字段。",
                )
            ],
        ),
    )


def _scenarios() -> ScenarioRecommendationResult:
    return ScenarioRecommendationResult(
        scoring_method="rule_based_v1",
        evaluated_count=3,
        top_scenarios=[
            ScenarioRecommendationItem(
                scenario_id="s1",
                name="门店知识助手",
                category="运营提效",
                summary="沉淀门店知识并支持快速调用。",
                canvas_elements="客户关系、关键资源",
                expected_effects="提升响应速度",
                core_data_requirements="POS、知识库",
                priority_recommendation="优先在高频门店流程中试点验证。",
            ),
            ScenarioRecommendationItem(
                scenario_id="s2",
                name="客户分层运营",
                category="客户增长",
                summary="提升客户识别与差异化服务能力。",
                canvas_elements="客户细分、客户关系",
                expected_effects="提升复购率",
                core_data_requirements="会员与交易数据",
                priority_recommendation="与门店知识助手联动推进。",
            ),
            ScenarioRecommendationItem(
                scenario_id="s3",
                name="巡店异常预警",
                category="交付运营",
                summary="缩短异常发现与处置周期。",
                canvas_elements="关键业务、渠道通路",
                expected_effects="提升交付稳定性",
                core_data_requirements="巡店记录",
                priority_recommendation="作为第二阶段复制场景储备。",
            ),
        ],
    )


def _competitiveness() -> CompetitivenessResult:
    return CompetitivenessResult(
        generation_mode="rule_based",
        vp_reconstruction=VPReconstruction(
            current_vp="帮助门店提升经营效率",
            enhanced_vp="围绕客户经营与知识复用构建持续增长能力",
            differentiation_points=["知识复用", "客户响应"],
            customer_value_shift="从单点提效升级为持续经营和可复制交付。",
        ),
        connections=[
            PointToLineConnection(
                line_name="客户响应速度线",
                point_ids=["d1"],
                point_titles=["门店知识助手", "客户分层运营"],
                strategic_narrative="形成从客户洞察到快速响应的协同闭环。",
                competitive_impact="缩短响应周期，提升客户满意度",
                key_metrics=["响应周期"],
                linkage_logic="AI 串联识别、决策和执行，形成端到端闭环。",
            )
        ],
        advantages=[
            CoreAdvantage(
                advantage_name="知识复用优势",
                source_elements=["客户关系"],
                description="把门店经验沉淀为组织能力。",
                barrier_level="中",
            )
        ],
        delivery_strategy=DeliveryStrategy(
            phase_1_quick_win="先围绕知识助手完成小范围试点。",
            phase_2_scale="把试点扩展到相邻门店和团队。",
            phase_3_moat="把数据、流程和知识沉淀为长期壁垒。",
            key_risks=["跨部门协同不足"],
        ),
        overall_narrative="企业应围绕增强型价值主张构建系统性竞争力。",
    )


def test_feedback_removes_redundant_fields_from_exported_competitiveness() -> None:
    report = ReportBuilder().build(
        assessment=_assessment(), profile=_profile(), canvas_diagnosis=_canvas(),
        scenario_recommendation=_scenarios(), case_recommendation=None,
        competitiveness_result=_competitiveness(),
    )
    section = next(item for item in report.sections if item.key == "competitiveness")
    payload = section.model_dump_json()
    assert "串联逻辑描述" not in payload
    assert "VP 交付逻辑变化" not in payload
    assert "先通过“" not in payload
    assert payload.count(_competitiveness().delivery_strategy.phase_1_quick_win) == 1
    assert payload.count(_competitiveness().delivery_strategy.phase_3_moat) == 1


def test_competitiveness_section_uses_card_layout() -> None:
    report = ReportBuilder().build(
        assessment=_assessment(),
        profile=_profile(),
        canvas_diagnosis=_canvas(),
        scenario_recommendation=_scenarios(),
        case_recommendation=None,
        competitiveness_result=_competitiveness(),
    )

    section = next(item for item in report.sections if item.key == "competitiveness")

    assert section.title == "差异化竞争力设计"
    assert section.content == "企业应围绕增强型价值主张构建系统性竞争力。"
    assert section.table is None
    assert section.cards is not None
    assert [card.title for card in section.cards] == [
        "AI 点优势串联",
        "VP 重构输出",
        "竞争优势差异化定位",
        "核心竞争力提升路径",
    ]
    assert section.cards[0].subtitle == "系统方案命名"
    assert section.cards[0].highlight == "系统方案名称：客户响应速度智能协同系统"
    assert section.cards[1].highlight is None
    assert section.cards[1].content == ""
    assert section.cards[1].highlights == [
        "旧 VP：帮助门店提升经营效率",
        "新 VP（AI 重构）：围绕客户经营与知识复用构建持续增长能力",
    ]
    assert section.cards[2].highlight is not None
    assert "定位语：" in section.cards[2].highlight
    assert section.cards[3].content == (
        "短期：先围绕知识助手完成小范围试点。\n"
        "中期：把试点扩展到相邻门店和团队。\n"
        "长期：把数据、流程和知识沉淀为长期壁垒。"
    )
    assert section.cards[3].highlight is None
    assert section.cards[3].bullets == []
    assert section.note == "该章节保留卡片式展示，便于管理员批注、方案汇报和后续人工修订。"


def test_competitiveness_vp_card_renders_two_highlight_rows_in_print_html() -> None:
    report = ReportBuilder().build(
        assessment=_assessment(),
        profile=_profile(),
        canvas_diagnosis=_canvas(),
        scenario_recommendation=_scenarios(),
        case_recommendation=None,
        competitiveness_result=_competitiveness(),
    )

    html = HtmlExporter().render_fragment(report)

    assert "旧 VP：帮助门店提升经营效率" in html
    assert "新 VP（AI 重构）：围绕客户经营与知识复用构建持续增长能力" in html
    assert "VP 交付逻辑变化" not in html
    assert html.count("background:#F5E6D0") >= 2
