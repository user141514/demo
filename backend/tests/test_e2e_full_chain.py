from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import session as db_session
from app.main import create_app
from app.services.llm_client import LLMClient
from app.services.llm_enhancer import LLMEnhancer


TEST_DB_PATH = Path(__file__).resolve().parent / "test_e2e_full_chain.db"

PAYLOAD = {
    "company_name": "智慧云链科技有限公司",
    "industry": "供应链科技",
    "company_size": "200-500人",
    "region": "华东",
    "annual_revenue_range": "1亿-10亿",
    "core_products": "智能供应链协同平台、仓储机器人调度系统、物流可视化中台",
    "target_customers": "中大型制造企业、区域物流服务商、品牌零售企业",
    "current_challenges": "订单交付波动大，跨部门协同低效，知识传递依赖核心骨干，获客成本持续上升",
    "ai_goals": "提升订单履约准确率，降低跨部门沟通成本，沉淀可复用的供应链优化知识，提升销售线索转化",
    "available_data": "ERP订单与库存、WMS仓储数据、CRM客户与商机、客服工单、设备运行日志",
    "notes": "已完成一期 ERP 和 WMS 系统上线，正推进数据中台建设，希望在二期引入 AI 能力增强供应链决策。",
}


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
                "email": "e2e@test.com",
                "password": "test123456",
                "display_name": "E2E Test User",
                "company_name": "E2E Test Company",
                "job_title": "Business Lead",
            },
        )
        assert register_response.status_code == 201
        token = register_response.json()["access_token"]
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client

    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


def _create_assessment(client: TestClient) -> str:
    response = client.post("/api/assessments", json=PAYLOAD)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["company_name"] == PAYLOAD["company_name"]
    return body["id"]


def _unlock_assessment(client: TestClient, assessment_id: str) -> None:
    response = client.post(
        f"/api/assessments/{assessment_id}/payments/orders",
        json={"provider": "wechat"},
    )
    assert response.status_code == 201, response.text
    order = response.json()
    response = client.post(
        "/api/payments/wechat/notify",
        json={
            "out_trade_no": order["order_no"],
            "total_amount_cents": order["amount_cents"],
            "transaction_id": f"e2e-{order['order_no']}",
            "trade_state": "SUCCESS",
        },
    )
    assert response.status_code == 200, response.text


def _select_breakthroughs(client: TestClient, assessment_id: str) -> list[str]:
    response = client.post(f"/api/assessments/{assessment_id}/breakthrough/recommend")
    assert response.status_code == 200, response.text
    recommended_keys = response.json()["breakthrough_recommendation"][
        "recommended_keys"
    ]
    assert len(recommended_keys) == 3

    response = client.post(
        f"/api/assessments/{assessment_id}/breakthrough/select",
        json={
            "selected_keys": recommended_keys[:2],
            "selection_mode": "system_recommended",
        },
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["selected_elements"]) == 2
    return recommended_keys[:2]


def _select_directions(client: TestClient, assessment_id: str) -> list[str]:
    response = client.post(f"/api/assessments/{assessment_id}/directions/expand")
    assert response.status_code == 200, response.text
    expansion = response.json()["direction_expansion"]
    assert expansion["generation_mode"] == "rule_based"
    assert expansion["total_suggestions"] >= 2

    direction_ids: list[str] = []
    for element in expansion["elements"]:
        for suggestion in element["suggestions"]:
            direction_ids.append(suggestion["direction_id"])

    selected_ids = direction_ids[:4]
    response = client.post(
        f"/api/assessments/{assessment_id}/directions/select",
        json={"selected_direction_ids": selected_ids},
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["selected_directions"]) == len(selected_ids)

    response = client.get(f"/api/assessments/{assessment_id}/directions")
    assert response.status_code == 200, response.text
    persisted = response.json()["direction_selection"]
    assert persisted is not None
    assert len(persisted["selected_directions"]) == len(selected_ids)
    return selected_ids


class TestFullChainE2E:
    def test_full_chain(self, client: TestClient) -> None:
        assessment_id = _create_assessment(client)

        response = client.post(f"/api/assessments/{assessment_id}/profile")
        assert response.status_code == 200, response.text
        profile_body = response.json()
        assert profile_body["generation_mode"] in ("mock", "live")
        assert profile_body["profile"]["company_name"] == PAYLOAD["company_name"]

        response = client.post(f"/api/assessments/{assessment_id}/canvas")
        assert response.status_code == 200, response.text
        canvas = response.json()["canvas_diagnosis"]
        assert canvas["generation_mode"] in ("mock", "live")
        assert len(canvas["canvas"]["blocks"]) == 9
        assert 0 <= canvas["overall_score"] <= 100

        _unlock_assessment(client, assessment_id)
        _select_breakthroughs(client, assessment_id)
        selected_direction_ids = _select_directions(client, assessment_id)
        assert len(selected_direction_ids) == 4

        response = client.post(f"/api/assessments/{assessment_id}/scenarios")
        assert response.status_code == 200, response.text
        scenarios = response.json()["scenario_recommendation"]
        assert scenarios["scoring_method"] == "four_quadrant_v1"
        assert len(scenarios["top_scenarios"]) == 3
        for item in scenarios["top_scenarios"]:
            assert "priority_quadrant" in item
            assert "priority_lps_display" in item
            assert "priority_tier" in item
            assert "priority_recommendation" in item

        response = client.post(
            f"/api/assessments/{assessment_id}/competitiveness/generate"
        )
        assert response.status_code == 200, response.text
        competitiveness = response.json()["result"]
        assert competitiveness["generation_mode"] == "rule_based"
        assert competitiveness["vp_reconstruction"]["differentiation_points"]
        assert competitiveness["connections"]
        assert competitiveness["advantages"]

        response = client.get(f"/api/assessments/{assessment_id}/competitiveness")
        assert response.status_code == 200, response.text
        assert len(response.json()["result"]["advantages"]) == len(
            competitiveness["advantages"]
        )

        response = client.post(f"/api/assessments/{assessment_id}/endgame/generate")
        assert response.status_code == 200, response.text
        endgame = response.json()["result"]
        assert endgame["generation_mode"] == "rule_based"
        assert endgame["private_domain"]["key_strategies"]
        assert len(endgame["strategic_paths"]) == 3

        response = client.get(f"/api/assessments/{assessment_id}/endgame")
        assert response.status_code == 200, response.text
        assert len(response.json()["result"]["strategic_paths"]) == 3

        response = client.post(f"/api/assessments/{assessment_id}/cases")
        assert response.status_code == 200, response.text
        cases = response.json()["case_recommendation"]
        assert cases["scoring_method"] == "layered_v1"
        assert len(cases["top_cases"]) >= 1

        response = client.get(f"/api/assessments/{assessment_id}/report-context")
        assert response.status_code == 200, response.text
        context = response.json()
        assert context["assessment_id"] == assessment_id
        assert context["report_outline"] == [
            "当前商业模式画布诊断",
            "突破要素",
            "创新方向延展",
            "高优先级 AI 提效场景",
            "差异化竞争力设计",
            "核心竞争力推进策略",
        ]
        assert len(context["selected_breakthrough_elements"]) == 2

        response = client.post(f"/api/assessments/{assessment_id}/report?mode=template")
        assert response.status_code == 200, response.text
        report = response.json()
        report_id = report["report_id"]
        assert report["generation_mode"] == "template"
        assert report["used_llm"] is False
        assert len(report["sections"]) == 6

        section_keys = {section["key"] for section in report["content_json"]["sections"]}
        assert section_keys == {
            "canvas_diagnosis",
            "breakthrough",
            "direction_expansion",
            "priority_scenarios",
            "competitiveness",
            "endgame",
        }

        response = client.get(f"/api/reports/{report_id}/export/markdown")
        assert response.status_code == 200, response.text
        assert PAYLOAD["company_name"] in response.text

        response = client.get(f"/api/reports/{report_id}/export/docx")
        assert response.status_code == 200, response.text
        assert len(response.content) > 1000

        response = client.get(f"/api/reports/{report_id}/print")
        assert response.status_code == 200, response.text
        assert PAYLOAD["company_name"] in response.text

        response = client.get(f"/api/reports/{report_id}/export/pdf")
        assert response.status_code == 200, response.text
        assert len(response.content) > 40

        response = client.get(f"/api/reports/{report_id}/enrich")
        assert response.status_code == 200, response.text
        enrichment = response.json()
        assert "executive_summary" in enrichment
        assert "industry_benchmark" in enrichment
        assert "roi_framework" in enrichment
        assert "instructor_comment" in enrichment

        response = client.get(f"/api/reports/{report_id}/quality")
        assert response.status_code == 200, response.text
        quality = response.json()
        assert 0 <= quality["overall_score"] <= 100
        assert len(quality["sections"]) == 6

        response = client.post(f"/api/reports/{report_id}/share")
        assert response.status_code == 200, response.text
        share = response.json()
        assert "share_url" in share
        assert "token" in share

        response = client.get(share["share_url"])
        assert response.status_code == 200, response.text
        assert PAYLOAD["company_name"] in response.text

        response = client.get(f"/api/assessments/{assessment_id}")
        assert response.status_code == 200, response.text
        detail = response.json()
        progress = detail["progress"]
        assert progress["has_profile"] is True
        assert progress["has_canvas"] is True
        assert progress["has_breakthrough"] is True
        assert progress["has_directions"] is True
        assert progress["has_scenarios"] is True
        assert progress["has_competitiveness"] is True
        assert progress["has_endgame"] is True
        assert progress["has_report"] is True
        assert progress["ready_for_report"] is True
        assert progress.get("has_cases") is True
        assert detail["breakthrough_selection"] is not None
        assert len(detail["breakthrough_selection"]) == 2

        response = client.get(f"/api/assessments/{assessment_id}/follow-up")
        assert response.status_code == 200, response.text
        follow_up = response.json()
        assert follow_up["assessment_id"] == assessment_id
        assert len(follow_up["tasks"]) == 6
        assert follow_up["total_count"] == 6
        assert follow_up["overall_progress_pct"] == 0

        first_task = follow_up["tasks"][0]
        response = client.patch(
            f"/api/assessments/{assessment_id}/follow-up/tasks/{first_task['task_id']}",
            json={
                "status": "in_progress",
                "progress_note": "试点范围与数据源已确认，正在组建团队。",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "in_progress"

        second_task = follow_up["tasks"][1]
        response = client.patch(
            f"/api/assessments/{assessment_id}/follow-up/tasks/{second_task['task_id']}",
            json={
                "status": "completed",
                "progress_note": "数据盘点完成，质量报告已输出。",
            },
        )
        assert response.status_code == 200, response.text

        third_task = follow_up["tasks"][2]
        response = client.patch(
            f"/api/assessments/{assessment_id}/follow-up/tasks/{third_task['task_id']}",
            json={
                "blocked": True,
                "blocker_description": "IT 资源被其他项目占用，需管理决策。",
            },
        )
        assert response.status_code == 200, response.text

        response = client.get(f"/api/assessments/{assessment_id}/follow-up")
        assert response.status_code == 200, response.text
        refreshed_plan = response.json()
        assert refreshed_plan["overall_progress_pct"] >= 16
        assert refreshed_plan["completed_count"] >= 1
        assert refreshed_plan["blocked_count"] >= 1

        response = client.post(
            f"/api/assessments/{assessment_id}/follow-up/recalibrate",
            json={
                "note": "30天复盘：第一阶段试点效果超预期，建议加速扩展。",
                "updated_tasks": [],
            },
        )
        assert response.status_code == 200, response.text
        assert "30天复盘" in response.json()["recalibration_note"]

        response = client.post(f"/api/assessments/{assessment_id}/push")
        assert response.status_code == 200, response.text
        push_cycle_one = response.json()
        assert push_cycle_one["cycle"] == 1
        assert len(push_cycle_one["pushed_cases"]) >= 1

        response = client.post(f"/api/assessments/{assessment_id}/push")
        assert response.status_code == 200, response.text
        push_cycle_two = response.json()
        assert push_cycle_two["cycle"] == 2
