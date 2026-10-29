from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.assessment import (
    BusinessModelCanvasResult,
    CanvasBlockResult,
    CanvasDiagnosisResult,
    CompanyProfileResult,
    ScenarioRecommendationItem,
    ScenarioRecommendationResult,
)
from app.schemas.competitiveness import (
    CompetitivenessResult,
    CoreAdvantage,
    DeliveryStrategy,
    PointToLineConnection,
    VPReconstruction,
)
from app.schemas.endgame import (
    EcosystemDesign,
    EndgameResult,
    OPCDesign,
    PrivateDomainDesign,
    StrategicPath,
    ThreeStageStrategy,
    ThreeStageStrategyStage,
)
from app.services.report_builder import ReportBuilder
from app.services.llm_report_writer import LLMReportWriter


def test_llm_report_writer_validates_only_target_group_sections() -> None:
    writer = LLMReportWriter()
    payload = {
        "sections": [
            {
                "title": "当前商业模式画布诊断",
                "content": "围绕价值主张、客户关系和关键资源说明当前画布诊断。",
                "bullets": ["价值主张需要聚焦", "关键资源可进一步数字化"],
            },
            {
                "title": "突破要素",
                "content": "建议优先围绕客户触达和运营效率选择突破要素。",
                "bullets": ["客户触达", "运营效率"],
            },
        ],
        "warnings": [],
    }

    sections, warnings, fatal = writer._parse_llm_response(
        json.dumps(payload, ensure_ascii=False),
        expected_sections=[
            ("canvas_diagnosis", "当前商业模式画布诊断"),
            ("breakthrough", "突破要素"),
        ],
    )

    assert fatal is False
    assert warnings == []
    assert sections is not None
    assert [section.key for section in sections] == ["canvas_diagnosis", "breakthrough"]


def _long_text(prefix: str) -> str:
    """构造会触发旧截断逻辑的长文本样例。"""
    return prefix + "，" + "这是完整内容" * 30


def _build_assessment() -> SimpleNamespace:
    """构造用于报告生成测试的轻量评估对象。"""
    return SimpleNamespace(
        id="assessment-report-builder",
        company_name="测试零售企业",
        industry="零售",
        company_size="100-499人",
        region="华东",
        annual_revenue_range="5000万-1亿元",
        core_products="门店运营与会员服务",
        target_customers="会员用户",
        current_challenges="复购波动",
        ai_goals="提升运营效率",
        available_data="POS、会员系统",
        notes=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _build_canvas() -> CanvasDiagnosisResult:
    """构造画布诊断样例，覆盖摘要与模块明细。"""
    return CanvasDiagnosisResult(
        generation_mode="mock",
        overall_score=82,
        weakest_blocks=["客户关系", "渠道通路"],
        recommended_focus=["优化客户分层", "统一门店运营标准"],
        canvas=BusinessModelCanvasResult(
            overall_summary=_long_text("商业画布整体判断"),
            blocks=[
                CanvasBlockResult(
                    key="customer_relationships",
                    title="客户关系",
                    current_state=_long_text("当前状态"),
                    diagnosis=_long_text("核心诊断"),
                    ai_opportunity=_long_text("AI 机会"),
                    missing_information="该字段仍保留在内部数据中，但不应出现在报告中。",
                )
            ],
        ),
    )


def _build_profile() -> CompanyProfileResult:
    """构造企业画像样例，避免报告中引入待补充信息文案。"""
    return CompanyProfileResult(
        company_name="测试零售企业",
        company_summary=_long_text("企业概览"),
        value_proposition="围绕门店服务和会员运营提升复购与体验",
        customer_and_market="社区家庭用户与会员客户",
        operations_and_resources="已有 POS、会员系统和巡店记录",
        digital_and_ai_readiness="具备基础数字化系统，可推进业务场景试点",
        key_challenges=["复购波动", "门店经验难复用"],
        priority_ai_directions=["知识沉淀复用", "客户关系深化"],
        missing_information=[],
    )


def _build_scenarios() -> ScenarioRecommendationResult:
    """构造场景推荐样例，覆盖结果页与报告引用内容。"""
    return ScenarioRecommendationResult(
        scoring_method="four_quadrant_v1",
        evaluated_count=3,
        top_scenarios=[
            ScenarioRecommendationItem(
                scenario_id="scenario-1",
                name="门店知识助手",
                category="运营提效",
                summary=_long_text("场景摘要"),
                canvas_elements="客户关系、关键资源",
                expected_effects="通过门店知识助手，预期可降低培训成本、提升运营效率",
                core_data_requirements="POS 数据、知识库文档",
                priority_structuredness_x=4.0,
                priority_complexity_y=2.0,
                priority_qs=8.0,
                priority_lps=4.0,
                priority_lps_display=8.0,
                priority_quadrant="自动化主战场",
                priority_tier=1,
                priority_recommendation="强烈推荐快速启动，3个月内可见可量化效果。",
            )
        ],
    )


def _build_competitiveness() -> CompetitivenessResult:
    """构造竞争力分析样例，覆盖旧省略号文案路径。"""
    return CompetitivenessResult(
        generation_mode="rule_based",
        vp_reconstruction=VPReconstruction(
            current_vp="帮助门店提升经营效率",
            enhanced_vp=_long_text("增强型价值主张"),
            differentiation_points=["知识复用", "客户响应"],
            customer_value_shift=_long_text("客户价值转移"),
        ),
        connections=[
            PointToLineConnection(
                line_name="客户响应速度线",
                point_ids=["direction-1"],
                point_titles=["知识沉淀复用"],
                strategic_narrative=_long_text("战略叙述"),
                competitive_impact="缩短响应周期",
                key_metrics=["客户满意度"],
            )
        ],
        advantages=[
            CoreAdvantage(
                advantage_name="知识复用优势",
                source_elements=["客户关系"],
                description="将门店经验沉淀为组织能力",
                barrier_level="中",
            )
        ],
        delivery_strategy=DeliveryStrategy(
            phase_1_quick_win=_long_text("阶段一策略"),
            phase_2_scale=_long_text("阶段二策略"),
            phase_3_moat=_long_text("阶段三策略"),
            key_risks=["跨部门协同不足"],
        ),
        overall_narrative=_long_text("竞争力总体判断"),
    )


def _build_endgame() -> EndgameResult:
    """构造商业终局样例，覆盖旧截断和量化展示路径。"""
    return EndgameResult(
        generation_mode="rule_based",
        private_domain=PrivateDomainDesign(
            current_state="私域基础薄弱",
            target_model=_long_text("私域目标模型"),
            key_strategies=["统一客户视图"],
            customer_retention_loop="触点数据化 -> 分层运营 -> 价值留存",
            revenue_impact=_long_text("收入影响"),
        ),
        ecosystem=EcosystemDesign(
            ecosystem_positioning="整合线上线下流量入口",
            key_partners_to_engage=["品牌供应商", "物流配送"],
            orchestration_strategy="以消费者数据平台为底座",
            platform_effect="更多消费者吸引更多品牌",
        ),
        opc=OPCDesign(
            operations_excellence="建立统一运营体系",
            platform_capability="沉淀平台能力",
            content_and_community="构建内容与社群闭环",
            data_flywheel_effect=_long_text("数据飞轮"),
        ),
        three_stage_strategy=ThreeStageStrategy(
            stage_1=ThreeStageStrategyStage(
                title="阶段 1",
                focus="快速验证",
                strategy="选择单一场景试点，集中资源跑通闭环。",
                objective="先完成单点试点验证。",
                key_actions=["明确试点边界与KPI", "组建专职小组"],
                key_risks=["试点范围过大"],
            ),
            stage_2=ThreeStageStrategyStage(
                title="阶段 2",
                focus="规模扩展",
                strategy="将试点模式复制到相邻业务单元。",
                objective="再扩展到更多业务单元。",
                key_actions=["方法论模板化", "建立数据底座"],
                key_risks=["跨部门协同不足"],
            ),
            stage_3=ThreeStageStrategyStage(
                title="阶段 3",
                focus="壁垒构建",
                strategy="将能力沉淀为平台与组织标准。",
                objective="最终沉淀为长期平台能力。",
                key_actions=["核心能力API化", "建立人才梯队"],
                key_risks=["组织惯性导致创新衰减"],
            ),
            key_risks=["协同不足"],
        ),
        strategic_paths=[
            StrategicPath(
                path_name="稳健试点路径",
                path_type="保守",
                execution_rhythm="以试点验证为先，成熟后再复制扩展",
                key_milestones=["完成试点准备"],
                capability_requirements="优先复用现有团队与客户经营机制",
                expected_outcomes="形成可复制的私域运营能力",
                major_risks=["数据基础薄弱"],
                recommendation_level="推荐",
            )
        ],
        overall_narrative=_long_text("终局总体判断"),
    )


def test_report_builder_does_not_emit_ellipsis_or_removed_labels() -> None:
    """确认报告生成结果中不再保留省略号、整体评分和待补充信息标签。"""
    builder = ReportBuilder()
    report = builder.build(
        assessment=_build_assessment(),
        profile=_build_profile(),
        canvas_diagnosis=_build_canvas(),
        scenario_recommendation=_build_scenarios(),
        case_recommendation=None,
        breakthrough_keys=["customer_relationships"],
        direction_labels=["知识沉淀复用"],
        competitiveness_result=_build_competitiveness(),
        endgame_result=_build_endgame(),
    )

    assert [section.key for section in report.sections] == [
        "canvas_diagnosis",
        "breakthrough",
        "direction_expansion",
        "priority_scenarios",
        "competitiveness",
        "endgame",
    ]

    payload = report.model_dump_json()

    assert "..." not in payload
    assert "…" not in payload
    assert "整体评分" not in payload
    assert "待补充信息" not in payload
    assert "投资需求" not in payload
    assert "时间范围" not in payload
    assert "企业基本画像" not in payload
    assert "AI 成熟度评估" not in payload
    assert "推荐场景详细规划" not in payload
    assert "参考案例与启示" not in payload
    assert "三阶段 AI 创新路线图" not in payload
    assert "风险与阻力" not in payload
    assert "管理员点评区" not in payload

    # 验证四象限评分说明保留在章节描述中，但表格不额外追加优先级字段
    assert "四象限优先级评分" in payload
    priority_section = next(
        section for section in report.sections if section.key == "priority_scenarios"
    )
    assert priority_section.table is not None
    assert priority_section.table.columns == ["推荐场景", "场景描述", "预期效果", "切入模块"]
    assert "自动化主战场" not in payload
    assert "象限归属" not in payload
    assert "综合优先级得分" not in payload


def test_priority_scenarios_table_uses_dashboard_style_display_text() -> None:
    """报告场景表格应复用仪表盘口径，去掉跨卡片重复的场景描述和支撑方向。"""
    repeated_setup = (
        "围绕“客户数据平台与智能分群推荐引擎、基于LBS的精准推送、供应商智能推荐引擎”，"
        "结合“关键资源、渠道通路、关键合作伙伴”"
    )
    repeated_direction = "构建智能客户数据平台、基于LBS的精准推送、供应商智能推荐引擎"
    scenarios = ScenarioRecommendationResult(
        scoring_method="four_quadrant_v1",
        evaluated_count=3,
        top_scenarios=[
            ScenarioRecommendationItem(
                scenario_id="scenario-1",
                name="回款风险预警",
                category="财务经营",
                summary=f"{repeated_setup}，在财务经营环节布局“回款风险预警”。",
                canvas_elements="关键资源",
                expected_effects=(
                    f"支撑方向：{repeated_direction}；"
                    "通过回款风险预警，预期可优化回款、降低风险、经营稳健。"
                ),
                core_data_requirements="客户账期数据",
            ),
            ScenarioRecommendationItem(
                scenario_id="scenario-2",
                name="销售线索优先级排序",
                category="销售增长",
                summary=f"{repeated_setup}；在销售增长环节布局“销售线索优先级排序”。",
                canvas_elements="渠道通路",
                expected_effects=(
                    f"支撑方向：{repeated_direction}；"
                    "通过销售线索优先级排序，预期可销售转化、成交、增长。"
                ),
                core_data_requirements="销售线索数据",
            ),
            ScenarioRecommendationItem(
                scenario_id="scenario-3",
                name="门店销量预测",
                category="零售运营",
                summary=f"{repeated_setup}。在零售运营环节布局“门店销量预测”。",
                canvas_elements="关键合作伙伴",
                expected_effects=(
                    f"支撑方向：{repeated_direction}；"
                    "通过门店销量预测，预期可提升效率、优化库存、销售增长。"
                ),
                core_data_requirements="门店销售数据",
            ),
        ],
    )

    section = ReportBuilder()._build_priority_scenarios_section(scenarios)

    assert section.table is not None
    assert section.table.columns == ["推荐场景", "场景描述", "预期效果", "切入模块"]
    rows = section.table.rows
    assert rows[0][1] == "在财务经营环节布局“回款风险预警”。"
    assert rows[1][1] == "在销售增长环节布局“销售线索优先级排序”。"
    assert rows[2][1] == "在零售运营环节布局“门店销量预测”。"
    assert rows[0][2] == "通过回款风险预警，预期可优化回款、降低风险、经营稳健。"
    assert rows[1][2] == "通过销售线索优先级排序，预期可销售转化、成交、增长。"
    assert rows[2][2] == "通过门店销量预测，预期可提升效率、优化库存、销售增长。"

    payload = section.model_dump_json()
    assert repeated_setup not in payload
    assert repeated_direction not in payload
    assert "支撑方向" not in payload
