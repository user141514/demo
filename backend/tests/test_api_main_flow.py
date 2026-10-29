from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import session as db_session
from app.main import create_app
from app.services.llm_client import LLMClient
from app.services.llm_enhancer import LLMEnhancer
from app.services.llm_report_writer import LLMReportWriter


TEST_DB_PATH = Path(__file__).resolve().parent / "test_main_flow.db"


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    engine = create_engine(
        f"sqlite:///{TEST_DB_PATH.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )

    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "SessionLocal", testing_session_local)
    monkeypatch.setattr(LLMClient, "_use_mock_mode", lambda self: True)
    monkeypatch.setattr(LLMEnhancer, "_is_live_mode", lambda self: False)

    db_session.Base.metadata.create_all(bind=engine)
    db_session._migrate_generated_reports_table()

    app = create_app()
    with TestClient(app) as test_client:
        register_response = test_client.post(
            "/api/auth/register",
            json={
                "email": "mainflow@test.com",
                "password": "test123456",
                "display_name": "主流程测试用户",
                "company_name": "主流程测试企业",
                "job_title": "产品负责人",
            },
        )
        assert register_response.status_code == 201
        token = register_response.json()["access_token"]
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client

    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture()
def assessment_payload() -> dict[str, str]:
    return {
        "company_name": "测试连锁零售企业",
        "industry": "零售",
        "company_size": "100-499人",
        "region": "华东",
        "annual_revenue_range": "5000万-1亿元",
        "core_products": "社区零售门店、会员运营与到家服务",
        "target_customers": "社区家庭用户、周边白领与会员客户",
        "current_challenges": "门店运营效率波动，会员复购不稳定，知识传递依赖店长经验",
        "ai_goals": "提升门店运营效率，增强会员复购，沉淀可复制的门店运营知识",
        "available_data": "POS、会员系统、商品主数据、巡店记录、客服反馈",
        "notes": "计划先从单区域试点推进",
    }


def _create_assessment(client: TestClient, payload: dict[str, str]) -> str:
    response = client.post("/api/assessments", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["company_name"] == payload["company_name"]
    assessment_id = body["id"]
    _unlock_assessment(client, assessment_id)
    return assessment_id


def _unlock_assessment(client: TestClient, assessment_id: str) -> None:
    order_response = client.post(
        f"/api/assessments/{assessment_id}/payments/orders",
        json={"provider": "wechat"},
    )
    if order_response.status_code == 409:
        return
    assert order_response.status_code == 201
    order = order_response.json()
    notify_response = client.post(
        "/api/payments/wechat/notify",
        json={
            "out_trade_no": order["order_no"],
            "total_amount_cents": order["amount_cents"],
            "transaction_id": f"test-{order['order_no']}",
            "trade_state": "SUCCESS",
        },
    )
    assert notify_response.status_code == 200


def _select_recommended_breakthroughs(client: TestClient, assessment_id: str) -> list[str]:
    breakthrough_response = client.post(
        f"/api/assessments/{assessment_id}/breakthrough/recommend"
    )
    assert breakthrough_response.status_code == 200
    recommended_keys = breakthrough_response.json()["breakthrough_recommendation"][
        "recommended_keys"
    ]
    select_response = client.post(
        f"/api/assessments/{assessment_id}/breakthrough/select",
        json={
            "selected_keys": recommended_keys[:2],
            "selection_mode": "system_recommended",
        },
    )
    assert select_response.status_code == 200
    return recommended_keys


def _expand_and_select_directions(
    client: TestClient,
    assessment_id: str,
) -> list[str]:
    expand_response = client.post(f"/api/assessments/{assessment_id}/directions/expand")
    assert expand_response.status_code == 200
    expanded = expand_response.json()["direction_expansion"]["elements"]
    selected_direction_ids = [
        expanded[0]["suggestions"][0]["direction_id"],
        expanded[1]["suggestions"][0]["direction_id"],
    ]
    select_response = client.post(
        f"/api/assessments/{assessment_id}/directions/select",
        json={"selected_direction_ids": selected_direction_ids},
    )
    assert select_response.status_code == 200
    return selected_direction_ids


def _prepare_for_scenarios(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> str:
    assessment_id = _create_assessment(client, assessment_payload)
    assert client.post(f"/api/assessments/{assessment_id}/profile").status_code == 200
    assert client.post(f"/api/assessments/{assessment_id}/canvas").status_code == 200
    _select_recommended_breakthroughs(client, assessment_id)
    _expand_and_select_directions(client, assessment_id)
    return assessment_id


def _prepare_for_report(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> str:
    assessment_id = _prepare_for_scenarios(client, assessment_payload)
    assert client.post(f"/api/assessments/{assessment_id}/scenarios").status_code == 200
    assert (
        client.post(f"/api/assessments/{assessment_id}/competitiveness/generate").status_code
        == 200
    )
    assert client.post(f"/api/assessments/{assessment_id}/endgame/generate").status_code == 200
    return assessment_id


def _live_llm_report_test_enabled() -> bool:
    return (
        os.getenv("RUN_LIVE_LLM_TESTS", "").strip().lower() == "true"
        and os.getenv("LLM_REPORT_ENABLED", "").strip().lower() == "true"
        and bool(os.getenv("OPENAI_API_KEY", "").strip())
        and bool(os.getenv("OPENAI_MODEL", "").strip())
    )


def test_single_manual_breakthrough_survives_reload_and_completes_report(
    client: TestClient, assessment_payload: dict[str, str],
) -> None:
    from app.schemas.bmc_scoring import BMC_MODULE_DEFINITIONS

    assessment_id = _prepare_for_report(client, assessment_payload)
    root = f"/api/assessments/{assessment_id}"
    assert client.post(root + "/report?mode=template").status_code == 200
    # Choose a low-ranked module outside the system Top 3.
    selected = "cost_structure"
    modules = [
        {"key": item["key"], "pain": 3, "data": 3, "feasibility": 3}
        for item in BMC_MODULE_DEFINITIONS
    ]
    response = client.post(root + "/bmc-scoring/save", json={
        "selected_keys": [selected], "all_module_scores": modules,
        "selection_mode": "manual",
    })
    assert response.status_code == 200, response.text
    assert selected not in response.json()["scoring_result"]["top_3_keys"]
    assert client.get(root + "/bmc-scoring").json()["selected_keys"] == [selected]
    detail = client.get(root).json()
    assert detail["breakthrough_selection"] == [selected]
    assert detail["progress"]["has_breakthrough"] is True
    for flag in ("has_directions", "has_scenarios", "has_competitiveness", "has_endgame", "has_report"):
        assert detail["progress"][flag] is False, flag
    saved_selection = client.get(root + "/breakthrough").json()["breakthrough_selection"]
    assert [item["key"] for item in saved_selection["selected_elements"]] == [selected]

    expansion = client.post(root + "/directions/expand")
    assert expansion.status_code == 200, expansion.text
    elements = expansion.json()["direction_expansion"]["elements"]
    ids = [item["direction_id"] for item in elements[0]["suggestions"][:1]]
    assert client.post(root + "/directions/select", json={"selected_direction_ids": ids}).status_code == 200
    for action in ("/scenarios", "/competitiveness/generate", "/endgame/generate", "/report?mode=template"):
        step = client.post(root + action)
        assert step.status_code == 200, (action, step.text)


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_report_requires_prerequisites(client: TestClient, assessment_payload: dict[str, str]) -> None:
    assessment_id = _create_assessment(client, assessment_payload)

    context_response = client.get(f"/api/assessments/{assessment_id}/report-context")
    report_response = client.post(f"/api/assessments/{assessment_id}/report?mode=template")

    assert context_response.status_code == 400
    assert "company profile" in context_response.json()["detail"]
    assert report_response.status_code == 400
    assert "company profile" in report_response.json()["detail"]


def test_main_flow_template_report_and_exports(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _create_assessment(client, assessment_payload)

    profile_response = client.post(f"/api/assessments/{assessment_id}/profile")
    assert profile_response.status_code == 200
    assert profile_response.json()["generation_mode"] in ("mock", "live")

    canvas_response = client.post(f"/api/assessments/{assessment_id}/canvas")
    assert canvas_response.status_code == 200
    canvas_body = canvas_response.json()["canvas_diagnosis"]
    assert canvas_body["generation_mode"] in ("mock", "live")
    assert len(canvas_body["canvas"]["blocks"]) == 9

    breakthrough_recommend_response = client.post(
        f"/api/assessments/{assessment_id}/breakthrough/recommend"
    )
    assert breakthrough_recommend_response.status_code == 200
    breakthrough_recommend_body = breakthrough_recommend_response.json()
    assert breakthrough_recommend_body["assessment_id"] == assessment_id
    assert breakthrough_recommend_body["breakthrough_recommendation"]["generation_mode"] == "rule_based"
    assert len(breakthrough_recommend_body["breakthrough_recommendation"]["elements"]) == 9
    assert len(breakthrough_recommend_body["breakthrough_recommendation"]["recommended_keys"]) == 3

    recommended_keys = breakthrough_recommend_body["breakthrough_recommendation"]["recommended_keys"]
    breakthrough_select_response = client.post(
        f"/api/assessments/{assessment_id}/breakthrough/select",
        json={
            "selected_keys": recommended_keys[:2],
            "selection_mode": "system_recommended",
        },
    )
    assert breakthrough_select_response.status_code == 200
    breakthrough_select_body = breakthrough_select_response.json()
    assert breakthrough_select_body["selection_mode"] == "system_recommended"
    assert len(breakthrough_select_body["selected_elements"]) == 2

    direction_ids = _expand_and_select_directions(client, assessment_id)
    assert len(direction_ids) == 2

    scenarios_response = client.post(f"/api/assessments/{assessment_id}/scenarios")
    assert scenarios_response.status_code == 200
    scenarios_body = scenarios_response.json()["scenario_recommendation"]
    assert scenarios_body["scoring_method"] == "four_quadrant_v1"
    assert len(scenarios_body["top_scenarios"]) >= 1
    # 验证每个 Top 场景都带有四象限评分字段
    for s in scenarios_body["top_scenarios"]:
        assert "priority_structuredness_x" in s
        assert "priority_complexity_y" in s
        assert "priority_qs" in s
        assert "priority_lps" in s
        assert "priority_lps_display" in s
        assert "priority_quadrant" in s
        assert s["priority_quadrant"] in ("自动化主战场", "AI优先区", "人机协作区", "人类保留区")
        assert "priority_tier" in s
        assert "priority_recommendation" in s

    cases_response = client.post(f"/api/assessments/{assessment_id}/cases")
    assert cases_response.status_code == 200
    cases_body = cases_response.json()["case_recommendation"]
    assert cases_body["scoring_method"] == "layered_v1"
    assert len(cases_body["top_cases"]) >= 1

    competitiveness_response = client.post(
        f"/api/assessments/{assessment_id}/competitiveness/generate"
    )
    assert competitiveness_response.status_code == 200

    endgame_response = client.post(f"/api/assessments/{assessment_id}/endgame/generate")
    assert endgame_response.status_code == 200

    context_response = client.get(f"/api/assessments/{assessment_id}/report-context")
    assert context_response.status_code == 200
    context_body = context_response.json()
    assert context_body["assessment_id"] == assessment_id
    assert len(context_body["top_scenarios"]) >= 1
    assert context_body["report_outline"] == [
        "当前商业模式画布诊断",
        "突破要素",
        "创新方向延展",
        "高优先级 AI 提效场景",
        "差异化竞争力设计",
        "核心竞争力推进策略",
    ]
    assert len(context_body["selected_breakthrough_elements"]) == 2

    report_response = client.post(f"/api/assessments/{assessment_id}/report?mode=template")
    assert report_response.status_code == 200
    report_body = report_response.json()
    assert report_body["assessment_id"] == assessment_id
    assert report_body["generation_mode"] == "template"
    assert report_body["used_llm"] is False
    assert report_body["content_json"]["generated_with"] == "template"
    assert len(report_body["sections"]) == 6
    assert [section["key"] for section in report_body["sections"]] == [
        "canvas_diagnosis",
        "breakthrough",
        "direction_expansion",
        "priority_scenarios",
        "competitiveness",
        "endgame",
    ]

    detail_response = client.get(f"/api/assessments/{assessment_id}")
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["progress"]["has_profile"] is True
    assert detail_body["progress"]["has_canvas"] is True
    assert detail_body["progress"]["has_breakthrough"] is True
    assert detail_body["progress"]["has_directions"] is True
    assert detail_body["progress"]["has_competitiveness"] is True
    assert detail_body["progress"]["has_endgame"] is True
    assert detail_body["progress"]["has_scenarios"] is True
    assert detail_body["progress"]["has_report"] is True
    assert detail_body["progress"]["ready_for_report"] is True
    assert detail_body["progress"].get("has_cases") is True
    assert detail_body["generated_report"]["report_id"] == report_body["report_id"]

    report_id = report_body["report_id"]

    markdown_response = client.get(f"/api/reports/{report_id}/export/markdown")
    assert markdown_response.status_code == 200
    assert "text/markdown" in markdown_response.headers["content-type"]
    assert "used_llm: false" in markdown_response.text

    docx_response = client.get(f"/api/reports/{report_id}/export/docx")
    assert docx_response.status_code == 200
    assert (
        docx_response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(docx_response.content) > 0

    print_response = client.get(f"/api/reports/{report_id}/print")
    assert print_response.status_code == 200
    assert "text/html" in print_response.headers["content-type"]
    assert "used_llm: false" in print_response.text

    report_detail_response = client.get(f"/api/reports/{report_id}")
    assert report_detail_response.status_code == 200
    assert report_detail_response.json()["report_id"] == report_id


def test_llm_mode_falls_back_to_template_when_llm_call_fails(
    client: TestClient,
    assessment_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assessment_id = _prepare_for_report(client, assessment_payload)

    def _force_llm_mode(self, requested_mode: str) -> tuple[str, list[str]]:
        return "llm", []

    def _raise_llm_error(*args, **kwargs):
        raise RuntimeError("forced llm failure")

    monkeypatch.setattr(LLMReportWriter, "_resolve_mode", _force_llm_mode)
    monkeypatch.setattr(LLMReportWriter, "_call_llm", _raise_llm_error)

    report_response = client.post(f"/api/assessments/{assessment_id}/report?mode=llm")

    assert report_response.status_code == 200
    report_body = report_response.json()
    assert report_body["generation_mode"] == "template"
    assert report_body["used_llm"] is False
    assert report_body["content_json"]["generated_with"] == "template"
    assert any("template mode" in warning for warning in report_body["warnings"])
    assert any("RuntimeError" in warning for warning in report_body["warnings"])


def test_report_generation_auto_matches_cases_when_missing(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _prepare_for_report(client, assessment_payload)

    detail_before_report = client.get(f"/api/assessments/{assessment_id}")
    assert detail_before_report.status_code == 200
    assert detail_before_report.json()["progress"].get("has_cases") is False

    report_response = client.post(f"/api/assessments/{assessment_id}/report?mode=template")

    assert report_response.status_code == 200
    report_body = report_response.json()
    assert report_body["generation_mode"] == "template"
    assert report_body["used_llm"] is False

    detail_after_report = client.get(f"/api/assessments/{assessment_id}")
    assert detail_after_report.status_code == 200
    detail_body = detail_after_report.json()
    assert detail_body["progress"].get("has_cases") is True
    assert detail_body["case_recommendation"]["scoring_method"] == "layered_v1"
    assert len(detail_body["case_recommendation"]["top_cases"]) >= 1


def test_assessment_detail_serializes_direction_selection(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _create_assessment(client, assessment_payload)

    assert client.post(f"/api/assessments/{assessment_id}/profile").status_code == 200
    assert client.post(f"/api/assessments/{assessment_id}/canvas").status_code == 200

    _select_recommended_breakthroughs(client, assessment_id)
    selected_direction_ids = _expand_and_select_directions(client, assessment_id)

    select_response = client.get(f"/api/assessments/{assessment_id}/directions")
    assert select_response.status_code == 200

    detail_response = client.get(f"/api/assessments/{assessment_id}")

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["direction_selection"] is not None
    assert {
        item["direction_id"]
        for item in detail_body["direction_selection"]["selected_directions"]
    } == set(selected_direction_ids)


def test_direction_selection_accepts_llm_enhanced_direction_ids(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _create_assessment(client, assessment_payload)

    assert client.post(f"/api/assessments/{assessment_id}/profile").status_code == 200
    assert client.post(f"/api/assessments/{assessment_id}/canvas").status_code == 200

    breakthrough_response = client.post(
        f"/api/assessments/{assessment_id}/breakthrough/recommend"
    )
    recommended_keys = breakthrough_response.json()["breakthrough_recommendation"][
        "recommended_keys"
    ]
    assert client.post(
        f"/api/assessments/{assessment_id}/breakthrough/select",
        json={
            "selected_keys": recommended_keys[:2],
            "selection_mode": "system_recommended",
        },
    ).status_code == 200

    expand_response = client.post(f"/api/assessments/{assessment_id}/directions/expand")
    assert expand_response.status_code == 200

    from sqlalchemy import select

    from app.models.direction_expansion import DirectionExpansion

    custom_ids = ["llm_direction_alpha", "llm_direction_beta"]
    enhanced_expansion = {
        "generation_mode": "llm",
        "llm_status": "completed",
        "total_suggestions": 2,
        "elements": [
            {
                "element_key": recommended_keys[0],
                "element_title": "收入来源",
                "suggestions": [
                    {
                        "direction_id": custom_ids[0],
                        "element_key": recommended_keys[0],
                        "title": "AI 驱动动态定价与个性化促销引擎",
                        "description": "根据会员行为实时调整活动策略。",
                        "expected_impact": "提升转化与复购。",
                        "data_needed": ["会员画像", "订单明细"],
                        "related_scenario_categories": ["销售增长"],
                    },
                    {
                        "direction_id": custom_ids[1],
                        "element_key": recommended_keys[0],
                        "title": "会员订阅付费计划",
                        "description": "围绕高频客户推出订阅权益。",
                        "expected_impact": "提升客单与留存。",
                        "data_needed": ["会员等级", "消费频次"],
                        "related_scenario_categories": ["销售增长"],
                    },
                ],
            }
        ],
    }

    with db_session.SessionLocal() as session:
        record = session.scalar(
            select(DirectionExpansion).where(
                DirectionExpansion.assessment_id == assessment_id
            )
        )
        assert record is not None
        record.generation_mode = "llm"
        record.llm_status = "completed"
        record.expansion_json = json.dumps(enhanced_expansion, ensure_ascii=False)
        session.add(record)
        session.commit()

    select_response = client.post(
        f"/api/assessments/{assessment_id}/directions/select",
        json={"selected_direction_ids": custom_ids},
    )

    assert select_response.status_code == 200
    assert {
        item["direction_id"] for item in select_response.json()["selected_directions"]
    } == set(custom_ids)

    detail_response = client.get(f"/api/assessments/{assessment_id}/directions")

    assert detail_response.status_code == 200
    assert {
        item["direction_id"]
        for item in detail_response.json()["direction_selection"]["selected_directions"]
    } == set(custom_ids)


def test_expand_directions_clears_existing_selection_and_downstream_outputs(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _prepare_for_report(client, assessment_payload)

    response = client.post(f"/api/assessments/{assessment_id}/directions/expand")

    assert response.status_code == 200
    body = response.json()
    assert body["direction_selection"] is None
    expansion = body["direction_expansion"]
    assert expansion["created_at"]
    assert expansion["updated_at"]

    saved_expansion = client.get(
        f"/api/assessments/{assessment_id}/directions"
    ).json()["direction_expansion"]
    assert saved_expansion["created_at"] == expansion["created_at"]
    assert saved_expansion["updated_at"] == expansion["updated_at"]

    detail_response = client.get(f"/api/assessments/{assessment_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["direction_expansion"]["updated_at"] == expansion["updated_at"]
    assert detail["direction_selection"] is None
    assert detail["scenario_recommendation"] is None
    assert detail["competitiveness"] is None
    assert detail["endgame"] is None
    assert detail["progress"]["has_directions"] is False
    assert detail["progress"]["has_scenarios"] is False
    assert detail["progress"]["has_competitiveness"] is False
    assert detail["progress"]["has_endgame"] is False


def test_get_directions_normalizes_duplicate_ids_and_total_count(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _create_assessment(client, assessment_payload)

    assert client.post(f"/api/assessments/{assessment_id}/profile").status_code == 200
    assert client.post(f"/api/assessments/{assessment_id}/canvas").status_code == 200

    breakthrough_response = client.post(
        f"/api/assessments/{assessment_id}/breakthrough/recommend"
    )
    recommended_keys = breakthrough_response.json()["breakthrough_recommendation"][
        "recommended_keys"
    ]
    assert client.post(
        f"/api/assessments/{assessment_id}/breakthrough/select",
        json={
            "selected_keys": recommended_keys[:2],
            "selection_mode": "system_recommended",
        },
    ).status_code == 200

    expand_response = client.post(f"/api/assessments/{assessment_id}/directions/expand")
    assert expand_response.status_code == 200

    from sqlalchemy import select

    from app.models.direction_expansion import DirectionExpansion

    duplicate_expansion = {
        "generation_mode": "llm",
        "llm_status": "completed",
        "total_suggestions": 7,
        "elements": [
            {
                "element_key": recommended_keys[0],
                "element_title": "收入来源",
                "suggestions": [
                    {
                        "direction_id": "direction-1",
                        "element_key": recommended_keys[0],
                        "title": "方向 1",
                        "description": "描述 1",
                        "expected_impact": "影响 1",
                        "data_needed": ["数据 1"],
                        "related_scenario_categories": ["销售增长"],
                    },
                    {
                        "direction_id": "direction-2",
                        "element_key": recommended_keys[0],
                        "title": "方向 2",
                        "description": "描述 2",
                        "expected_impact": "影响 2",
                        "data_needed": ["数据 2"],
                        "related_scenario_categories": ["销售增长"],
                    },
                    {
                        "direction_id": "direction-3",
                        "element_key": recommended_keys[0],
                        "title": "方向 3",
                        "description": "描述 3",
                        "expected_impact": "影响 3",
                        "data_needed": ["数据 3"],
                        "related_scenario_categories": ["销售增长"],
                    },
                    {
                        "direction_id": "direction-4",
                        "element_key": recommended_keys[0],
                        "title": "方向 4",
                        "description": "描述 4",
                        "expected_impact": "影响 4",
                        "data_needed": ["数据 4"],
                        "related_scenario_categories": ["销售增长"],
                    },
                ],
            },
            {
                "element_key": recommended_keys[1],
                "element_title": "客户关系",
                "suggestions": [
                    {
                        "direction_id": "direction-4",
                        "element_key": recommended_keys[1],
                        "title": "重复方向 4",
                        "description": "重复描述",
                        "expected_impact": "重复影响",
                        "data_needed": ["重复数据"],
                        "related_scenario_categories": ["客户服务"],
                    },
                    {
                        "direction_id": "direction-5",
                        "element_key": recommended_keys[1],
                        "title": "方向 5",
                        "description": "描述 5",
                        "expected_impact": "影响 5",
                        "data_needed": ["数据 5"],
                        "related_scenario_categories": ["客户服务"],
                    },
                    {
                        "direction_id": "direction-6",
                        "element_key": recommended_keys[1],
                        "title": "方向 6",
                        "description": "描述 6",
                        "expected_impact": "影响 6",
                        "data_needed": ["数据 6"],
                        "related_scenario_categories": ["客户服务"],
                    },
                ],
            },
        ],
    }

    with db_session.SessionLocal() as session:
        record = session.scalar(
            select(DirectionExpansion).where(
                DirectionExpansion.assessment_id == assessment_id
            )
        )
        assert record is not None
        record.generation_mode = "llm"
        record.llm_status = "completed"
        record.expansion_json = json.dumps(duplicate_expansion, ensure_ascii=False)
        session.add(record)
        session.commit()

    response = client.get(f"/api/assessments/{assessment_id}/directions")

    assert response.status_code == 200
    expansion = response.json()["direction_expansion"]
    all_ids = [
        suggestion["direction_id"]
        for element in expansion["elements"]
        for suggestion in element["suggestions"]
    ]
    assert expansion["total_suggestions"] == 6
    assert len(all_ids) == 6
    assert len(set(all_ids)) == 6


def test_main_flow_generates_competitiveness_endgame_and_report_without_old_labels(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    """确认主流程可生成点线面结果，并且报告中不再混入旧省略号与终局量化标签。"""
    assessment_id = _create_assessment(client, assessment_payload)

    assert client.post(f"/api/assessments/{assessment_id}/profile").status_code == 200
    assert client.post(f"/api/assessments/{assessment_id}/canvas").status_code == 200

    breakthrough_response = client.post(
        f"/api/assessments/{assessment_id}/breakthrough/recommend"
    )
    recommended_keys = breakthrough_response.json()["breakthrough_recommendation"][
        "recommended_keys"
    ]
    assert client.post(
        f"/api/assessments/{assessment_id}/breakthrough/select",
        json={
            "selected_keys": recommended_keys[:2],
            "selection_mode": "system_recommended",
        },
    ).status_code == 200

    expand_response = client.post(f"/api/assessments/{assessment_id}/directions/expand")
    assert expand_response.status_code == 200
    expanded = expand_response.json()["direction_expansion"]["elements"]
    selected_direction_ids = [
        expanded[0]["suggestions"][0]["direction_id"],
        expanded[1]["suggestions"][0]["direction_id"],
    ]
    assert client.post(
        f"/api/assessments/{assessment_id}/directions/select",
        json={"selected_direction_ids": selected_direction_ids},
    ).status_code == 200

    assert client.post(f"/api/assessments/{assessment_id}/scenarios").status_code == 200

    competitiveness_response = client.post(
        f"/api/assessments/{assessment_id}/competitiveness/generate"
    )
    assert competitiveness_response.status_code == 200
    competitiveness_payload = json.dumps(
        competitiveness_response.json(), ensure_ascii=False
    )
    assert "..." not in competitiveness_payload
    assert "…" not in competitiveness_payload

    endgame_response = client.post(f"/api/assessments/{assessment_id}/endgame/generate")
    assert endgame_response.status_code == 200
    endgame_body = endgame_response.json()["result"]
    assert endgame_body["three_stage_strategy"]["stage_1"]["focus"] == "快速验证"
    assert "execution_rhythm" in endgame_body["strategic_paths"][0]
    assert "timeline" not in endgame_body["strategic_paths"][0]

    report_response = client.post(f"/api/assessments/{assessment_id}/report?mode=template")
    assert report_response.status_code == 200
    report_payload = json.dumps(report_response.json(), ensure_ascii=False)
    assert "投资需求" not in report_payload
    assert "时间范围" not in report_payload

    detail_response = client.get(f"/api/assessments/{assessment_id}")
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["progress"]["has_directions"] is True
    assert detail_body["progress"]["has_competitiveness"] is True


def test_scenario_recommendations_alias_is_backward_compatible(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _prepare_for_scenarios(client, assessment_payload)

    alias_response = client.post(
        f"/api/assessments/{assessment_id}/scenario-recommendations"
    )
    canonical_response = client.post(f"/api/assessments/{assessment_id}/scenarios")

    assert alias_response.status_code == 200
    alias_body = alias_response.json()["scenario_recommendation"]
    assert alias_body["scoring_method"] == "four_quadrant_v1"
    assert len(alias_body["top_scenarios"]) >= 1

    assert canonical_response.status_code == 200
    canonical_body = canonical_response.json()["scenario_recommendation"]
    assert canonical_body["scoring_method"] == "four_quadrant_v1"
    assert [item["name"] for item in canonical_body["top_scenarios"]] == [
        item["name"] for item in alias_body["top_scenarios"]
    ]

    # 验证 legacy mode 仍返回 rule_based_v1
    legacy_response = client.post(
        f"/api/assessments/{assessment_id}/scenarios?mode=legacy"
    )
    assert legacy_response.status_code == 200
    legacy_body = legacy_response.json()["scenario_recommendation"]
    assert legacy_body["scoring_method"] == "rule_based_v1"
    assert len(legacy_body["top_scenarios"]) == 3
    assert legacy_body.get("all_scores") is None

    # 验证四象限模式返回 all_scores
    assert canonical_body.get("all_scores") is not None
    assert len(canonical_body["all_scores"]) >= len(canonical_body["top_scenarios"])


def test_save_calibrations_persists_xy_and_reranks_top3(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _prepare_for_scenarios(client, assessment_payload)

    scenarios_resp = client.post(f"/api/assessments/{assessment_id}/scenarios")
    assert scenarios_resp.status_code == 200
    original = scenarios_resp.json()["scenario_recommendation"]
    all_scores = original.get("all_scores") or original["top_scenarios"]

    if len(all_scores) < 1:
        return

    first = all_scores[0]
    calibrations = [
        {
            "scenario_id": first["scenario_id"],
            "priority_structuredness_x": 5.0,
            "priority_complexity_y": 1.0,
        }
    ]

    cal_resp = client.post(
        f"/api/assessments/{assessment_id}/scenarios/calibrations",
        json={"calibrations": calibrations},
    )
    assert cal_resp.status_code == 200
    cal_body = cal_resp.json()["scenario_recommendation"]

    updated = next(
        (s for s in cal_body["all_scores"] if s["scenario_id"] == first["scenario_id"]),
        None,
    )
    assert updated is not None
    assert updated["priority_structuredness_x"] == 5.0
    assert updated["priority_complexity_y"] == 1.0
    assert updated["priority_qs"] == 5.0
    assert updated["priority_quadrant"] == "自动化主战场"
    assert updated["priority_tier"] == 1
    assert updated["recommendation_level"] == "立即启动"

    # 刷新后数据应持久化
    detail_resp = client.get(f"/api/assessments/{assessment_id}")
    assert detail_resp.status_code == 200
    detail_scenarios = detail_resp.json()["scenario_recommendation"]
    assert detail_scenarios is not None
    detail_updated = next(
        (s for s in detail_scenarios["all_scores"]
         if s["scenario_id"] == first["scenario_id"]),
        None,
    )
    assert detail_updated is not None
    assert detail_updated["priority_structuredness_x"] == 5.0


def test_update_scenario_pool_persists_active_and_excluded_buckets_and_clears_downstream_outputs(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _prepare_for_report(client, assessment_payload)
    report_response = client.post(f"/api/assessments/{assessment_id}/report?mode=template")
    assert report_response.status_code == 200

    detail_before = client.get(f"/api/assessments/{assessment_id}")
    assert detail_before.status_code == 200
    original_scenarios = detail_before.json()["scenario_recommendation"]
    all_scores = original_scenarios["all_scores"]
    assert all_scores is not None
    assert len(all_scores) >= 4

    removed_id = all_scores[3]["scenario_id"]
    original_ids = [item["scenario_id"] for item in all_scores]
    next_active_ids = [scenario_id for scenario_id in original_ids if scenario_id != removed_id]

    update_response = client.put(
        f"/api/assessments/{assessment_id}/scenarios/pool",
        json={"active_scenario_ids": next_active_ids},
    )
    assert update_response.status_code == 200
    updated_scenarios = update_response.json()["scenario_recommendation"]
    assert updated_scenarios["active_count"] == len(next_active_ids)
    assert all(
        item["scenario_id"] != removed_id for item in updated_scenarios["all_scores"]
    )
    assert any(
        item["scenario_id"] == removed_id
        for item in updated_scenarios["excluded_scores"]
    )

    detail_after_update = client.get(f"/api/assessments/{assessment_id}")
    assert detail_after_update.status_code == 200
    detail_body = detail_after_update.json()
    assert detail_body["progress"]["has_competitiveness"] is False
    assert detail_body["progress"]["has_endgame"] is False
    assert detail_body["progress"]["has_report"] is False
    assert detail_body["progress"].get("has_cases") is False
    assert detail_body["scenario_recommendation"]["active_count"] == len(next_active_ids)

    restore_response = client.put(
        f"/api/assessments/{assessment_id}/scenarios/pool",
        json={"active_scenario_ids": original_ids},
    )
    assert restore_response.status_code == 200
    restored_scenarios = restore_response.json()["scenario_recommendation"]
    assert restored_scenarios["active_count"] == len(original_ids)
    assert restored_scenarios["excluded_scores"] == []


def test_scenario_regeneration_invalidates_every_dependent_output(
    client: TestClient, assessment_payload: dict[str, str],
) -> None:
    assessment_id = _prepare_for_report(client, assessment_payload)
    root = f"/api/assessments/{assessment_id}"
    assert client.post(root + "/report?mode=template").status_code == 200
    assert client.post(root + "/scenarios").status_code == 200
    progress = client.get(root).json()["progress"]
    for flag in ("has_competitiveness", "has_endgame", "has_cases", "has_report"):
        assert progress.get(flag) is False, flag


def test_manual_scenario_change_and_invalidation_are_atomic(
    client: TestClient, assessment_payload: dict[str, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.routes import assessments as routes
    assessment_id = _prepare_for_report(client, assessment_payload)
    root = f"/api/assessments/{assessment_id}"
    before = client.get(root).json()["scenario_recommendation"]
    original = [item["scenario_id"] for item in before["top_scenarios"]]
    replacement = next(item["scenario_id"] for item in before["all_scores"] if item["scenario_id"] not in original)
    requested = original[1:] + [replacement]
    def fail_invalidation(*args, **kwargs):
        raise RuntimeError("invalidation unavailable")
    monkeypatch.setattr(routes, "_clear_competitiveness_outputs", fail_invalidation)
    with pytest.raises(RuntimeError, match="invalidation unavailable"):
        client.put(root + "/scenarios/top3", json={"selected_scenario_ids": requested})
    after = client.get(root).json()
    assert [item["scenario_id"] for item in after["scenario_recommendation"]["top_scenarios"]] == original
    assert after["progress"]["has_competitiveness"] is True


def test_manual_top3_selection_persists_order_and_clears_downstream(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _prepare_for_report(client, assessment_payload)
    current = client.get(f"/api/assessments/{assessment_id}")
    assert current.status_code == 200
    active = current.json()["scenario_recommendation"]["all_scores"]
    assert active and len(active) >= 4
    requested = [
        active[3]["scenario_id"],
        active[1]["scenario_id"],
        active[0]["scenario_id"],
    ]
    endpoint = f"/api/assessments/{assessment_id}/scenarios/top3"

    assert client.put(endpoint, json={"selected_scenario_ids": requested[:2]}).status_code == 422
    assert client.put(endpoint, json={"selected_scenario_ids": [requested[0]] * 3}).status_code == 422
    assert client.put(endpoint, json={"selected_scenario_ids": ["unknown", *requested[:2]]}).status_code == 422

    selected = client.put(endpoint, json={"selected_scenario_ids": requested})
    assert selected.status_code == 200, selected.text
    assert [item["scenario_id"] for item in selected.json()["scenario_recommendation"]["top_scenarios"]] == requested

    detail = client.get(f"/api/assessments/{assessment_id}")
    assert detail.status_code == 200
    assert [item["scenario_id"] for item in detail.json()["scenario_recommendation"]["top_scenarios"]] == requested
    assert detail.json()["progress"]["has_competitiveness"] is False
    assert detail.json()["progress"]["has_endgame"] is False
    assert detail.json()["progress"]["has_report"] is False

    record = _load_scenario_record(assessment_id)
    assert [item["scenario_id"] for item in json.loads(record.scenario_json)] == requested


def test_calibration_keeps_removed_scenarios_out_of_top3(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _prepare_for_scenarios(client, assessment_payload)

    scenarios_response = client.post(f"/api/assessments/{assessment_id}/scenarios")
    assert scenarios_response.status_code == 200
    scenario_body = scenarios_response.json()["scenario_recommendation"]
    all_scores = scenario_body["all_scores"]
    assert all_scores is not None
    assert len(all_scores) >= 4

    removed = all_scores[3]
    removed_id = removed["scenario_id"]
    active_ids = [
        item["scenario_id"]
        for item in all_scores
        if item["scenario_id"] != removed_id
    ]

    pool_response = client.put(
        f"/api/assessments/{assessment_id}/scenarios/pool",
        json={"active_scenario_ids": active_ids},
    )
    assert pool_response.status_code == 200

    calibration_response = client.post(
        f"/api/assessments/{assessment_id}/scenarios/calibrations",
        json={
            "calibrations": [
                {
                    "scenario_id": removed_id,
                    "priority_structuredness_x": 5.0,
                    "priority_complexity_y": 1.0,
                }
            ]
        },
    )
    assert calibration_response.status_code == 200
    calibrated = calibration_response.json()["scenario_recommendation"]

    assert all(
        item["scenario_id"] != removed_id for item in calibrated["top_scenarios"]
    )
    removed_after = next(
        item
        for item in calibrated["excluded_scores"]
        if item["scenario_id"] == removed_id
    )
    assert removed_after["priority_structuredness_x"] == 5.0
    assert removed_after["priority_complexity_y"] == 1.0

    detail_response = client.get(f"/api/assessments/{assessment_id}")
    assert detail_response.status_code == 200
    detail_scenarios = detail_response.json()["scenario_recommendation"]
    assert detail_scenarios["active_count"] == len(active_ids)
    assert all(
        item["scenario_id"] != removed_id
        for item in detail_scenarios["top_scenarios"]
    )


def test_calibration_requires_existing_scenarios(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _create_assessment(client, assessment_payload)
    cal_resp = client.post(
        f"/api/assessments/{assessment_id}/scenarios/calibrations",
        json={"calibrations": [{"scenario_id": "test", "priority_structuredness_x": 3, "priority_complexity_y": 3}]},
    )
    assert cal_resp.status_code in (404, 400)


def _load_scenario_record(assessment_id: str):
    from app.models.scenario_recommendation import ScenarioRecommendation

    db = db_session.SessionLocal()
    try:
        record = db.scalar(
            select(ScenarioRecommendation).where(
                ScenarioRecommendation.assessment_id == assessment_id
            )
        )
        assert record is not None
        return record
    finally:
        db.close()


def _scenario_ids_from_json_list(raw_json: str) -> list[str]:
    parsed = json.loads(raw_json)
    assert isinstance(parsed, list)
    return [item["scenario_id"] for item in parsed]


def _make_legacy_scenario_item(
    scenario_id: str,
    name: str,
    summary: str,
    canvas_elements: str,
    expected_effects: str,
    core_data_requirements: str,
    x: float,
    y: float,
) -> dict:
    return {
        "scenario_id": scenario_id,
        "name": name,
        "category": "legacy-test",
        "summary": summary,
        "canvas_elements": canvas_elements,
        "expected_effects": expected_effects,
        "core_data_requirements": core_data_requirements,
        "priority_structuredness_x": x,
        "priority_complexity_y": y,
    }


def _seed_legacy_scenario_record(assessment_id: str) -> list[dict]:
    from app.models.scenario_recommendation import ScenarioRecommendation

    legacy_items = [
        _make_legacy_scenario_item(
            "legacy-1",
            "Legacy Top 1",
            "该场景聚焦高价值会员经营。战略定位是高价值会员复购增长引擎。",
            "对应突破要素：客户细分、渠道通路；对应创新方向：自动化营销；战略价值：通过聚焦高价值客户提升转化效率。",
            "预期收益：提升复购率；缩短活动反馈周期；减少人工筛客时间。",
            "资源准备：数据基础：需整合CRM会员系统数据；关键风险：会员标签口径不统一。",
            4.0,
            2.0,
        ),
        _make_legacy_scenario_item(
            "legacy-2",
            "Legacy Top 2",
            "该场景聚焦门店补货优化。战略定位是门店补货协同加速器。",
            "对应突破要素：关键业务活动、关键资源；对应创新方向：智能补货；战略价值：通过降低缺货和滞销改善经营效率。",
            "预期收益：降低缺货率；减少滞销库存；提升门店周转效率。",
            "资源准备：数据基础：需整合POS与库存数据；组织准备：补货规则需要门店和采购同步。",
            4.0,
            3.0,
        ),
        _make_legacy_scenario_item(
            "legacy-3",
            "Legacy Top 3",
            "该场景聚焦客服知识复用。战略定位是服务知识标准化中枢。",
            "对应突破要素：客户关系、关键资源；对应创新方向：知识沉淀；战略价值：通过统一知识口径提升服务响应速度。",
            "预期收益：缩短培训周期；提升首问解决率；减少重复答疑。",
            "资源准备：数据基础：需整合客服话术与工单数据；组织准备：需安排知识运营角色。",
            3.0,
            2.0,
        ),
        _make_legacy_scenario_item(
            "legacy-4",
            "Legacy Candidate 4",
            "该场景聚焦会员流失预警。战略定位是流失风险前置预警器。",
            "对应突破要素：客户关系、客户细分；对应创新方向：流失预警；战略价值：通过提前识别流失风险减少会员流失。",
            "预期收益：提升挽回成功率；减少高价值会员流失；提升留存运营效率。",
            "资源准备：数据基础：需整合交易与互动数据；关键风险：触达策略不当可能引发打扰。",
            2.0,
            5.0,
        ),
    ]

    with db_session.SessionLocal() as session:
        record = session.scalar(
            select(ScenarioRecommendation).where(
                ScenarioRecommendation.assessment_id == assessment_id
            )
        )
        if record is None:
            record = ScenarioRecommendation(
                assessment_id=assessment_id,
                scoring_method="four_quadrant_v1",
                evaluated_count=len(legacy_items),
                scenario_json="[]",
                top_scenarios="[]",
            )
        record.scoring_method = "four_quadrant_v1"
        record.evaluated_count = len(legacy_items)
        record.scenario_json = json.dumps(legacy_items[:3], ensure_ascii=False)
        record.top_scenarios = json.dumps(
            [item["name"] for item in legacy_items[:3]],
            ensure_ascii=False,
        )
        record.all_scores_json = json.dumps(legacy_items, ensure_ascii=False)
        record.active_scenario_ids_json = json.dumps(
            [item["scenario_id"] for item in legacy_items],
            ensure_ascii=False,
        )
        session.add(record)
        session.commit()

    return legacy_items


def _assert_structured_scenario_payload(item: dict) -> None:
    assert item["positioning"]
    assert item["value_text"]
    assert _not_contains_legacy_markers(item["value_text"])
    assert item["canvas_element"]
    assert item["canvas_key"]
    assert item["benefits"]
    assert all(benefit["canvas"] for benefit in item["benefits"])
    assert item["resources"]
    assert all(resource["label"] for resource in item["resources"])
    assert all(resource["type"] for resource in item["resources"])


def _not_contains_legacy_markers(value: str) -> bool:
    return "对应突破要素" not in value and "对应创新方向" not in value


def _compute_expected_top3_ids_from_items(
    items: list[dict],
    industry: str,
) -> list[str]:
    from app.schemas.scene_priority import ScenePriorityInput
    from app.services.scene_priority_scorer import ScenePriorityScorer

    candidates: list[ScenePriorityInput] = []
    for item in items:
        candidates.append(
            ScenePriorityInput(
                scene_id=item["scenario_id"],
                scene_name=item.get("name", ""),
                category=item.get("category", ""),
                summary=item.get("summary") or "",
                structuredness_x=float(item.get("priority_structuredness_x") or 3.0),
                complexity_y=float(item.get("priority_complexity_y") or 3.0),
                industry=industry or "",
                canvas_elements=item.get("canvas_elements") or "",
                expected_effects=item.get("expected_effects") or "",
                core_data_requirements=item.get("core_data_requirements") or "",
                canvas_element=item.get("canvas_element") or "",
                canvas_key=item.get("canvas_key") or "",
                positioning=item.get("positioning") or "",
                value_dimensions=item.get("value_dimensions") or [],
                value_text=item.get("value_text") or "",
                benefits=item.get("benefits") or [],
                resources=item.get("resources") or [],
            )
        )

    result = ScenePriorityScorer().recommend_top3(candidates)
    return [score.scene_id for score in result.top_3]


def test_legacy_record_detail_backfills_structured_fields(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _prepare_for_scenarios(client, assessment_payload)
    legacy_items = _seed_legacy_scenario_record(assessment_id)

    detail_response = client.get(f"/api/assessments/{assessment_id}")

    assert detail_response.status_code == 200
    scenarios = detail_response.json()["scenario_recommendation"]
    assert scenarios is not None
    assert [item["scenario_id"] for item in scenarios["top_scenarios"]] == [
        item["scenario_id"] for item in legacy_items[:3]
    ]
    for item in scenarios["top_scenarios"]:
        _assert_structured_scenario_payload(item)


def test_legacy_record_calibration_backfills_and_persists_structured_fields(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _prepare_for_scenarios(client, assessment_payload)
    _seed_legacy_scenario_record(assessment_id)

    calibration_response = client.post(
        f"/api/assessments/{assessment_id}/scenarios/calibrations",
        json={
            "calibrations": [
                {
                    "scenario_id": "legacy-4",
                    "priority_structuredness_x": 5.0,
                    "priority_complexity_y": 1.0,
                }
            ]
        },
    )

    assert calibration_response.status_code == 200
    calibrated = calibration_response.json()["scenario_recommendation"]
    assert any(item["scenario_id"] == "legacy-4" for item in calibrated["top_scenarios"])
    for item in calibrated["top_scenarios"]:
        _assert_structured_scenario_payload(item)

    detail_response = client.get(f"/api/assessments/{assessment_id}")
    assert detail_response.status_code == 200
    detail_top = detail_response.json()["scenario_recommendation"]["top_scenarios"]
    assert any(item["scenario_id"] == "legacy-4" for item in detail_top)
    for item in detail_top:
        _assert_structured_scenario_payload(item)

    record = _load_scenario_record(assessment_id)
    persisted_top = json.loads(record.scenario_json)
    persisted_all = json.loads(record.all_scores_json)
    assert any(item["scenario_id"] == "legacy-4" for item in persisted_top)
    for item in persisted_top + persisted_all:
        _assert_structured_scenario_payload(item)


def test_legacy_record_pool_update_backfills_and_persists_structured_fields(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    assessment_id = _prepare_for_scenarios(client, assessment_payload)
    legacy_items = _seed_legacy_scenario_record(assessment_id)
    removed_id = legacy_items[0]["scenario_id"]

    pool_response = client.put(
        f"/api/assessments/{assessment_id}/scenarios/pool",
        json={
            "active_scenario_ids": [
                item["scenario_id"]
                for item in legacy_items
                if item["scenario_id"] != removed_id
            ]
        },
    )

    assert pool_response.status_code == 200
    pooled = pool_response.json()["scenario_recommendation"]
    assert all(item["scenario_id"] != removed_id for item in pooled["top_scenarios"])
    assert any(item["scenario_id"] == removed_id for item in pooled["excluded_scores"])
    for item in pooled["top_scenarios"]:
        _assert_structured_scenario_payload(item)

    detail_response = client.get(f"/api/assessments/{assessment_id}")
    assert detail_response.status_code == 200
    detail_scenarios = detail_response.json()["scenario_recommendation"]
    assert all(item["scenario_id"] != removed_id for item in detail_scenarios["top_scenarios"])
    for item in detail_scenarios["top_scenarios"]:
        _assert_structured_scenario_payload(item)

    record = _load_scenario_record(assessment_id)
    persisted_top = json.loads(record.scenario_json)
    persisted_all = json.loads(record.all_scores_json)
    assert all(item["scenario_id"] != removed_id for item in persisted_top)
    assert any(item["scenario_id"] == removed_id for item in persisted_all)
    for item in persisted_top + persisted_all:
        _assert_structured_scenario_payload(item)


def _install_fake_priority_recommender(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Force a deterministic mismatch:
    - stored scenario_json (true top3) = [t-1, t-2, t-3]
    - stored all_scores_json prefix (ranked_items[:3]) = [a-1, a-2, a-3]
    Current buggy code derives top_scenarios from all_scores[:3], so API responses
    will return [a-1, a-2, a-3] instead of [t-1, t-2, t-3].
    """
    from app.schemas.assessment import ScenarioRecommendationItem, ScenarioRecommendationResult
    from app.services.scenario_recommender import ScenarioRecommender

    def _item(
        scenario_id: str,
        name: str,
        x: float,
        y: float,
    ) -> ScenarioRecommendationItem:
        return ScenarioRecommendationItem(
            scenario_id=scenario_id,
            name=name,
            category="test",
            summary=f"summary {scenario_id}",
            canvas_elements=f"canvas {scenario_id}",
            expected_effects=f"effects {scenario_id}",
            core_data_requirements=f"data {scenario_id}",
            priority_structuredness_x=x,
            priority_complexity_y=y,
            priority_qs=None,
            priority_lps=None,
            priority_lps_display=None,
            priority_quadrant=None,
            priority_tier=None,
            priority_recommendation=None,
            industry_coefficient=None,
            recommendation_level=None,
            canvas_element="",
            canvas_key="",
            positioning="",
            value_dimensions=[],
            value_text="",
            benefits=[],
            resources=[],
        )

    top_scenarios = [
        _item("t-1", "Top-1", 5.0, 1.0),
        _item("t-2", "Top-2", 4.0, 2.0),
        _item("t-3", "Top-3", 4.0, 1.5),
    ]
    all_scores = [
        _item("a-1", "Aux-1", 1.0, 5.0),
        _item("a-2", "Aux-2", 1.0, 4.5),
        _item("a-3", "Aux-3", 2.0, 5.0),
        *top_scenarios,
    ]

    def _fake_recommend_with_priority(self, *args, **kwargs) -> ScenarioRecommendationResult:
        return ScenarioRecommendationResult(
            scoring_method="four_quadrant_v1",
            evaluated_count=len(all_scores),
            top_scenarios=top_scenarios,
            all_scores=all_scores,
        )

    monkeypatch.setattr(ScenarioRecommender, "recommend_with_priority", _fake_recommend_with_priority)


def test_top3_source_after_generate_detail_matches_record_scenario_json_not_all_scores_prefix(
    client: TestClient,
    assessment_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_priority_recommender(monkeypatch)
    assessment_id = _prepare_for_scenarios(client, assessment_payload)

    gen_resp = client.post(f"/api/assessments/{assessment_id}/scenarios")
    assert gen_resp.status_code == 200

    record = _load_scenario_record(assessment_id)
    stored_top_ids = _scenario_ids_from_json_list(record.scenario_json)
    assert stored_top_ids == ["t-1", "t-2", "t-3"]
    assert record.all_scores_json is not None
    all_scores_prefix_ids = _scenario_ids_from_json_list(record.all_scores_json)[:3]
    # Ensure the fixture actually triggers the mismatch this regression test is meant to lock in.
    assert all_scores_prefix_ids != stored_top_ids

    detail_resp = client.get(f"/api/assessments/{assessment_id}")
    assert detail_resp.status_code == 200
    detail_top_ids = [
        item["scenario_id"]
        for item in detail_resp.json()["scenario_recommendation"]["top_scenarios"]
    ]
    # Contract: top_scenarios must come from the persisted true Top3 (scenario_json),
    # never derived from all_scores[:3].
    assert detail_top_ids == stored_top_ids


def test_top3_source_after_calibration_detail_matches_scorer_top3_not_all_scores_prefix(
    client: TestClient,
    assessment_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_priority_recommender(monkeypatch)
    assessment_id = _prepare_for_scenarios(client, assessment_payload)
    assert client.post(f"/api/assessments/{assessment_id}/scenarios").status_code == 200

    # Calibrate a non-prefix scenario to ensure it should become Top1 under scorer rules.
    cal_resp = client.post(
        f"/api/assessments/{assessment_id}/scenarios/calibrations",
        json={
            "calibrations": [
                {
                    "scenario_id": "t-1",
                    "priority_structuredness_x": 5.0,
                    "priority_complexity_y": 1.0,
                }
            ]
        },
    )
    assert cal_resp.status_code == 200

    record = _load_scenario_record(assessment_id)
    assert record.all_scores_json is not None
    stored_items = json.loads(record.all_scores_json)
    assert isinstance(stored_items, list)
    expected_top3_ids = _compute_expected_top3_ids_from_items(
        stored_items,
        industry=assessment_payload.get("industry", ""),
    )
    assert len(expected_top3_ids) >= 1

    stored_top_ids = _scenario_ids_from_json_list(record.scenario_json)
    detail_resp = client.get(f"/api/assessments/{assessment_id}")
    assert detail_resp.status_code == 200
    detail_top_ids = [
        item["scenario_id"]
        for item in detail_resp.json()["scenario_recommendation"]["top_scenarios"]
    ]

    # Contract: calibration re-ranking must use scorer Top3, not list slicing.
    assert stored_top_ids == expected_top3_ids
    assert detail_top_ids == expected_top3_ids


def test_top3_source_after_scenario_pool_update_detail_matches_scorer_top3_not_all_scores_prefix(
    client: TestClient,
    assessment_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_priority_recommender(monkeypatch)
    assessment_id = _prepare_for_scenarios(client, assessment_payload)
    assert client.post(f"/api/assessments/{assessment_id}/scenarios").status_code == 200

    record = _load_scenario_record(assessment_id)
    assert record.all_scores_json is not None
    ranked_items = json.loads(record.all_scores_json)
    assert isinstance(ranked_items, list)
    all_ids = [item["scenario_id"] for item in ranked_items]
    assert set(["t-1", "t-2", "t-3"]).issubset(set(all_ids))

    expected_before = _compute_expected_top3_ids_from_items(
        ranked_items,
        industry=assessment_payload.get("industry", ""),
    )
    assert len(expected_before) >= 1

    removed_id = expected_before[0]
    active_ids = [scenario_id for scenario_id in all_ids if scenario_id != removed_id]
    assert len(active_ids) >= 3

    update_resp = client.put(
        f"/api/assessments/{assessment_id}/scenarios/pool",
        json={"active_scenario_ids": active_ids},
    )
    assert update_resp.status_code == 200

    record_after = _load_scenario_record(assessment_id)
    assert record_after.all_scores_json is not None
    ranked_items_after = json.loads(record_after.all_scores_json)
    assert isinstance(ranked_items_after, list)

    active_set = set(json.loads(record_after.active_scenario_ids_json or "[]"))
    active_items_after = [
        item for item in ranked_items_after if item["scenario_id"] in active_set
    ]
    expected_after = _compute_expected_top3_ids_from_items(
        active_items_after,
        industry=assessment_payload.get("industry", ""),
    )
    assert len(expected_after) >= 1

    stored_top_ids = _scenario_ids_from_json_list(record_after.scenario_json)
    detail_resp = client.get(f"/api/assessments/{assessment_id}")
    assert detail_resp.status_code == 200
    detail_top_ids = [
        item["scenario_id"]
        for item in detail_resp.json()["scenario_recommendation"]["top_scenarios"]
    ]

    # Contract: pool updates must re-evaluate Top3 using the same scorer ordering,
    # never derived from active_ranked_items[:3].
    assert stored_top_ids == expected_after
    assert detail_top_ids == expected_after


def test_live_scenario_packaging_rewrites_top3_and_syncs_all_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.routes import assessments as assessments_routes
    from app.schemas.assessment import (
        BusinessModelCanvasResult,
        CanvasBlockResult,
        CanvasDiagnosisResult,
        ScenarioRecommendationItem,
    )

    monkeypatch.setattr(
        LLMEnhancer,
        "enhance_scenario_descriptions",
        lambda self, assessment, profile, canvas_diagnosis, breakthrough_labels, selected_directions, scenarios: [
            scenario.model_copy(
                update={
                    "summary": f"改写场景摘要 {index}",
                    "canvas_elements": f"对应突破要素：突破{index}",
                    "expected_effects": f"预期收益：收益{index}",
                    "core_data_requirements": f"资源准备：准备{index}",
                }
            )
            for index, scenario in enumerate(scenarios, start=1)
        ],
    )

    canvas = CanvasDiagnosisResult(
        generation_mode="mock",
        overall_score=70,
        weakest_blocks=["客户关系"],
        recommended_focus=["客户关系"],
        canvas=BusinessModelCanvasResult(
            overall_summary="摘要",
            blocks=[
                CanvasBlockResult(
                    key="customer_relationships",
                    title="客户关系",
                    current_state="现状",
                    diagnosis="诊断",
                    ai_opportunity="机会",
                    missing_information="",
                )
            ],
        ),
    )
    top_scenarios = [
        ScenarioRecommendationItem(
            scenario_id="s-1",
            name="场景 1",
            category="客户经营",
            summary="旧摘要 1",
            canvas_elements="旧切入 1",
            expected_effects="旧收益 1",
            core_data_requirements="旧资源 1",
            priority_quadrant="AI优先区",
        ),
        ScenarioRecommendationItem(
            scenario_id="s-2",
            name="场景 2",
            category="客户经营",
            summary="旧摘要 2",
            canvas_elements="旧切入 2",
            expected_effects="旧收益 2",
            core_data_requirements="旧资源 2",
            priority_quadrant="自动化主战场",
        ),
    ]
    all_scores = top_scenarios + [
        ScenarioRecommendationItem(
            scenario_id="s-3",
            name="场景 3",
            category="客户经营",
            summary="旧摘要 3",
            canvas_elements="旧切入 3",
            expected_effects="旧收益 3",
            core_data_requirements="旧资源 3",
            priority_quadrant="人机协作区",
        )
    ]

    merged_top, merged_all = assessments_routes._enhance_scenario_description_fields(
        assessment=SimpleNamespace(
            company_name="测试企业",
            industry="零售",
            company_size="100-499人",
            region="华东",
            annual_revenue_range="5000万-1亿元",
            core_products="门店服务",
            target_customers="会员用户",
            current_challenges="复购波动",
            ai_goals="提升复购",
            available_data="POS、会员数据",
            notes="先试点",
        ),
        profile=None,
        canvas=canvas,
        breakthrough_labels=["客户关系"],
        selected_directions=[],
        top_scenarios=top_scenarios,
        all_scores=all_scores,
    )

    assert merged_top[0].summary == "改写场景摘要 1"
    assert merged_top[1].summary == "改写场景摘要 2"
    assert merged_all is not None
    assert merged_all[0].summary == "改写场景摘要 1"
    assert merged_all[1].summary == "改写场景摘要 2"
    assert merged_all[2].summary == "旧摘要 3"


@pytest.mark.skip(reason="manual scenario calibration no longer re-runs LLM packaging")
def test_calibration_repackages_promoted_top3_when_live_packaging_enabled(
    client: TestClient,
    assessment_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assessment_id = _prepare_for_scenarios(client, assessment_payload)

    scenarios_response = client.post(f"/api/assessments/{assessment_id}/scenarios")
    assert scenarios_response.status_code == 200
    scenario_body = scenarios_response.json()["scenario_recommendation"]
    all_scores = scenario_body["all_scores"]
    assert all_scores is not None
    assert len(all_scores) >= 4

    target = scenario_body["top_scenarios"][0]
    rewrites = [
        {
            "scenario_id": item["scenario_id"],
            "summary": f"{item['name']} 的管理层改写摘要",
            "canvas_elements": f"{item['name']} 的突破要素与战略价值",
            "expected_effects": f"{item['name']} 的预期收益",
            "core_data_requirements": f"{item['name']} 的资源准备",
        }
        for item in scenario_body["top_scenarios"]
    ]

    monkeypatch.setattr(
        LLMEnhancer,
        "enhance_scenario_descriptions",
        lambda self, assessment, profile, canvas_diagnosis, breakthrough_labels, selected_directions, scenarios: [
            scenario.model_copy(
                update=next(
                    rewrite
                    for rewrite in rewrites
                    if rewrite["scenario_id"] == scenario.scenario_id
                )
            )
            if any(
                rewrite["scenario_id"] == scenario.scenario_id for rewrite in rewrites
            )
            else scenario
            for scenario in scenarios
        ],
    )

    calibration_response = client.post(
        f"/api/assessments/{assessment_id}/scenarios/calibrations",
        json={
            "calibrations": [
                {
                    "scenario_id": target["scenario_id"],
                    "priority_structuredness_x": 5.0,
                    "priority_complexity_y": 1.0,
                }
            ]
        },
    )
    assert calibration_response.status_code == 200
    calibrated = calibration_response.json()["scenario_recommendation"]

    promoted_top = next(
        (
            item
            for item in calibrated["top_scenarios"]
            if item["scenario_id"] == target["scenario_id"]
        ),
        None,
    )
    assert promoted_top is not None
    assert promoted_top["summary"] == f"{target['name']} 的管理层改写摘要"
    assert (
        promoted_top["expected_effects"]
        == f"{target['name']} 的预期收益"
    )

    promoted_all = next(
        item
        for item in calibrated["all_scores"]
        if item["scenario_id"] == target["scenario_id"]
    )
    assert promoted_all["summary"] == promoted_top["summary"]
    assert (
        promoted_all["core_data_requirements"]
        == f"{target['name']} 的资源准备"
    )


def test_calibration_keeps_text_without_repackaging(
    client: TestClient,
    assessment_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assessment_id = _prepare_for_scenarios(client, assessment_payload)

    scenarios_response = client.post(f"/api/assessments/{assessment_id}/scenarios")
    assert scenarios_response.status_code == 200
    scenario_body = scenarios_response.json()["scenario_recommendation"]
    all_scores = scenario_body["all_scores"]
    assert all_scores is not None
    assert len(all_scores) >= 4

    target = scenario_body["top_scenarios"][0]
    monkeypatch.setattr(
        LLMEnhancer,
        "enhance_scenario_descriptions",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("manual calibration should not trigger scenario repackaging")
        ),
    )

    calibration_response = client.post(
        f"/api/assessments/{assessment_id}/scenarios/calibrations",
        json={
            "calibrations": [
                {
                    "scenario_id": target["scenario_id"],
                    "priority_structuredness_x": 5.0,
                    "priority_complexity_y": 1.0,
                }
            ]
        },
    )
    assert calibration_response.status_code == 200
    calibrated = calibration_response.json()["scenario_recommendation"]

    promoted_top = next(
        (
            item
            for item in calibrated["top_scenarios"]
            if item["scenario_id"] == target["scenario_id"]
        ),
        None,
    )
    assert promoted_top is not None
    assert promoted_top["summary"] == target["summary"]
    assert promoted_top["expected_effects"] == target["expected_effects"]

    promoted_all = next(
        item
        for item in calibrated["all_scores"]
        if item["scenario_id"] == target["scenario_id"]
    )
    assert promoted_all["summary"] == promoted_top["summary"]
    assert promoted_all["core_data_requirements"] == target["core_data_requirements"]


def test_pool_update_reorders_top3_without_repackaging_text(
    client: TestClient,
    assessment_payload: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assessment_id = _prepare_for_scenarios(client, assessment_payload)

    scenarios_response = client.post(f"/api/assessments/{assessment_id}/scenarios")
    assert scenarios_response.status_code == 200
    scenario_body = scenarios_response.json()["scenario_recommendation"]
    all_scores = scenario_body["all_scores"]
    assert all_scores is not None
    assert len(all_scores) >= 4

    removed_top_id = all_scores[0]["scenario_id"]
    promoted_candidate = all_scores[3]
    monkeypatch.setattr(
        LLMEnhancer,
        "enhance_scenario_descriptions",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("scenario pool update should not trigger scenario repackaging")
        ),
    )

    next_active_ids = [
        item["scenario_id"] for item in all_scores if item["scenario_id"] != removed_top_id
    ]
    pool_response = client.put(
        f"/api/assessments/{assessment_id}/scenarios/pool",
        json={"active_scenario_ids": next_active_ids},
    )
    assert pool_response.status_code == 200
    updated = pool_response.json()["scenario_recommendation"]

    promoted_top = next(
        (
            item
            for item in updated["top_scenarios"]
            if item["scenario_id"] == promoted_candidate["scenario_id"]
        ),
        None,
    )
    assert promoted_top is not None
    assert promoted_top["summary"] == promoted_candidate["summary"]
    assert promoted_top["canvas_elements"] == promoted_candidate["canvas_elements"]


def test_enhance_scenario_descriptions_only_overrides_text_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.assessment import (
        BusinessModelCanvasResult,
        CanvasBlockResult,
        CanvasDiagnosisResult,
        CompanyProfileResult,
        ScenarioRecommendationItem,
    )
    from app.schemas.direction import DirectionSuggestion

    enhancer = LLMEnhancer()
    monkeypatch.setattr(LLMEnhancer, "_is_live_mode", lambda self: True)
    monkeypatch.setattr(
        LLMEnhancer,
        "_call_llm",
        lambda self, system_prompt, user_prompt: {
            "scenarios": [
                {
                    "scenario_id": "scenario-1",
                    "summary": "新的管理层场景描述",
                    "canvas_elements": "对应突破要素与战略价值",
                    "expected_effects": "新的预期收益",
                    "core_data_requirements": "新的资源准备",
                }
            ]
        },
    )

    assessment = SimpleNamespace(
        company_name="测试零售企业",
        industry="零售",
        company_size="100-499人",
        region="华东",
        annual_revenue_range="5000万-1亿元",
        core_products="社区零售门店",
        target_customers="会员用户",
        current_challenges="复购波动",
        ai_goals="提升复购",
        available_data="POS、会员数据",
        notes="先试点",
    )
    profile = CompanyProfileResult(
        company_name="测试零售企业",
        company_summary="企业概览",
        value_proposition="价值主张",
        customer_and_market="客户与市场",
        operations_and_resources="运营与资源",
        digital_and_ai_readiness="准备度",
        key_challenges=["复购波动"],
        priority_ai_directions=["会员经营"],
    )
    canvas = CanvasDiagnosisResult(
        generation_mode="mock",
        overall_score=68,
        weakest_blocks=["客户关系"],
        recommended_focus=["客户关系"],
        canvas=BusinessModelCanvasResult(
            overall_summary="画布总体摘要",
            blocks=[
                CanvasBlockResult(
                    key="customer_relationships",
                    title="客户关系",
                    current_state="依赖门店经验",
                    diagnosis="复购运营缺少统一机制",
                    ai_opportunity="建立客户分层与召回",
                    missing_information="",
                )
            ],
        ),
    )
    directions = [
        DirectionSuggestion(
            direction_id="dir-1",
            element_key="customer_relationships",
            title="会员经营自动化",
            description="围绕复购做分层运营",
            expected_impact="提升复购稳定性",
            data_needed=["POS", "会员标签"],
            related_scenario_categories=["客户经营"],
        )
    ]
    source = ScenarioRecommendationItem(
        scenario_id="scenario-1",
        name="AI 流失预测与自动关怀",
        category="客户经营",
        summary="旧摘要",
        canvas_elements="旧切入点",
        expected_effects="旧收益",
        core_data_requirements="旧资源",
        priority_structuredness_x=4.0,
        priority_complexity_y=2.0,
        priority_qs=4.0,
        priority_lps=7.2,
        priority_lps_display=7.0,
        priority_quadrant="AI优先区",
        priority_tier=2,
        priority_recommendation="原推荐说明",
        recommendation_level="规划推进",
    )

    result = enhancer.enhance_scenario_descriptions(
        assessment=assessment,
        profile=profile,
        canvas_diagnosis=canvas,
        breakthrough_labels=["客户关系"],
        selected_directions=directions,
        scenarios=[source],
    )

    assert result is not None
    assert result[0].summary == "新的管理层场景描述"
    assert result[0].canvas_elements == "对应突破要素与战略价值"
    assert result[0].expected_effects == "新的预期收益"
    assert result[0].core_data_requirements == "新的资源准备"
    assert result[0].priority_qs == 4.0
    assert result[0].priority_quadrant == "AI优先区"
    assert result[0].priority_recommendation == "原推荐说明"


def test_report_endpoints_return_404_for_missing_report_id(client: TestClient) -> None:
    missing_report_id = "missing-report-id"

    report_response = client.get(f"/api/reports/{missing_report_id}")
    markdown_response = client.get(
        f"/api/reports/{missing_report_id}/export/markdown"
    )
    docx_response = client.get(f"/api/reports/{missing_report_id}/export/docx")
    print_response = client.get(f"/api/reports/{missing_report_id}/print")

    for response in (
        report_response,
        markdown_response,
        docx_response,
        print_response,
    ):
        assert response.status_code == 404
        assert response.json()["detail"] == "Report not found."


def test_live_llm_report_success_path_is_opt_in(
    client: TestClient,
    assessment_payload: dict[str, str],
) -> None:
    if not _live_llm_report_test_enabled():
        pytest.skip(
            "Set RUN_LIVE_LLM_TESTS=true together with LLM_REPORT_ENABLED=true, "
            "OPENAI_API_KEY, and OPENAI_MODEL to run the live LLM report test."
        )

    assessment_id = _prepare_for_report(client, assessment_payload)

    report_response = client.post(f"/api/assessments/{assessment_id}/report?mode=llm")

    assert report_response.status_code == 200
    report_body = report_response.json()
    assert report_body["generation_mode"] == "llm"
    assert report_body["used_llm"] is True
    assert report_body["content_json"]["generated_with"] == "llm"
    assert len(report_body["sections"]) == 6
