"""Live Chrome acceptance for the DEMO feedback changes, using an isolated database.

Run from the repo root after `npm run build` in frontend:
  uv run --no-project --python 3.12 --with-requirements backend/requirements.txt \
    --with playwright python scripts/verify_demo_feedback.py

Requires local Chrome and free ports 8000/3001. Never connects to the deployed app.
LLM and payment providers run in mock mode; browser requests use the real local API.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8000"
FRONT = "http://localhost:3001"
CHROME = Path(os.environ.get("CHROME_EXECUTABLE", "C:/Program Files/Google/Chrome/Application/chrome.exe"))


def wait_ready(url: str, process: subprocess.Popen, seconds: int = 50) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited with {process.returncode}: {url}")
        try:
            if httpx.get(url, timeout=2).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise TimeoutError(f"Server not ready: {url}")


def capture_screen(page, path: Path) -> None:
    """Capture rendered Chrome pixels without waiting for optional web fonts."""
    session = page.context.new_cdp_session(page)
    try:
        metrics = session.send("Page.getLayoutMetrics")["cssContentSize"]
        image = session.send("Page.captureScreenshot", {
            "format": "png", "captureBeyondViewport": True,
            "clip": {"x": 0, "y": 0, "width": metrics["width"],
                     "height": min(metrics["height"], 16000), "scale": 1},
        })
        path.write_bytes(base64.b64decode(image["data"]))
    finally:
        session.detach()


def main() -> None:
    if not CHROME.is_file():
        raise RuntimeError("Install Chrome or set CHROME_EXECUTABLE to its executable.")
    for port in (8000, 3001):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Port {port} is in use; no existing service will be stopped.")
    if not (ROOT / "frontend/.next/BUILD_ID").exists():
        raise RuntimeError("Build the frontend before running this check.")
    output = Path(tempfile.mkdtemp(prefix="demo-feedback-evidence-"))
    results: dict = {"checks": [], "evidence_dir": str(output), "backend": API, "frontend": FRONT}
    processes = []
    handles = []
    try:
        with tempfile.TemporaryDirectory(prefix="demo-feedback-db-", ignore_cleanup_errors=True) as tmp:
            env = dict(os.environ, DATABASE_URL="sqlite:///" + (Path(tmp) / "test.db").as_posix(),
                LLM_MODE="mock", LLM_REPORT_ENABLED="false", RAG_ENABLED="false",
                LIGHTRAG_ENABLED="false", PAYMENT_PROVIDER_MODE="mock", SMTP_ENABLED="false",
                PYTHONIOENCODING="utf-8", JWT_SECRET_KEY=uuid4().hex)
            for name, cwd, argv in (
                ("backend", ROOT / "backend", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]),
                ("frontend", ROOT / "frontend", [shutil.which("node") or "node", "node_modules/next/dist/bin/next", "start", "-p", "3001"]),
            ):
                log = (output / f"{name}.log").open("w", encoding="utf-8")
                handles.append(log)
                processes.append(subprocess.Popen(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT))
            try:
                wait_ready(API + "/health", processes[0])
                wait_ready(FRONT + "/login", processes[1])
                with httpx.Client(base_url=API, timeout=120) as client:
                    def call(method: str, path: str, body=None):
                        response = client.request(method, path, json=body)
                        response.raise_for_status()
                        return response.json()

                    email = f"feedback-{uuid4().hex[:10]}@example.test"
                    password = uuid4().hex + "Aa1!"
                    user = call("POST", "/api/auth/register", {"email": email, "password": password,
                        "display_name": "反馈验收", "company_name": "反馈验收企业", "job_title": "测试负责人"})
                    client.headers["Authorization"] = "Bearer " + user["access_token"]
                    assessment = call("POST", "/api/assessments", {
                        "company_name": "反馈验收企业", "industry": "零售", "company_size": "100-499人",
                        "region": "华东", "annual_revenue_range": "5000万-1亿元", "core_products": "社区门店与会员服务",
                        "target_customers": "社区家庭及会员", "current_challenges": "复购不足与知识传递依赖个人",
                        "ai_goals": "提升经营效率", "available_data": "POS、CRM、客服记录", "notes": "隔离测试，不使用真实客户数据",
                    })
                    root = "/api/assessments/" + assessment["id"]
                    order = call("POST", root + "/payments/orders", {"provider": "wechat"})
                    call("POST", "/api/payments/wechat/notify", {"out_trade_no": order["order_no"],
                        "total_amount_cents": order["amount_cents"], "transaction_id": "test-" + order["order_no"], "trade_state": "SUCCESS"})
                    call("POST", root + "/profile")
                    call("POST", root + "/canvas")
                    keys = ["customer_segments", "value_propositions", "channels", "customer_relationships",
                        "revenue_streams", "key_resources", "key_activities", "key_partnerships", "cost_structure"]
                    scores = {"key_resources": (3.5, 5, 3), "value_propositions": (3.5, 3.5, 3),
                        "customer_segments": (3, 3.5, 3), "key_partnerships": (2.5, 4, 3)}
                    modules = [{"key": key, "pain": scores.get(key, (3, 3, 3))[0],
                        "data": scores.get(key, (3, 3, 3))[1], "feasibility": scores.get(key, (3, 3, 3))[2]} for key in keys]
                    call("POST", root + "/bmc-scoring/save", {"selected_keys": ["cost_structure"],
                        "all_module_scores": modules, "selection_mode": "manual"})
                    with sync_playwright() as pw:
                        browser = pw.chromium.launch(executable_path=str(CHROME), headless=True)
                        try:
                            context = browser.new_context(viewport={"width": 1440, "height": 1100})
                            # Even a previously built external API URL is routed to this isolated local server.
                            def local_api(route):
                                parsed = urlsplit(route.request.url)
                                response = route.fetch(url=API + parsed.path + ("?" + parsed.query if parsed.query else ""))
                                route.fulfill(response=response)
                            context.route("**/api/**", local_api)
                            page = context.new_page()
                            page.set_default_timeout(30000)
                            errors = []
                            page.on("pageerror", lambda error: errors.append(str(error)))
                            page.goto(FRONT + "/login", wait_until="domcontentloaded")
                            page.get_by_placeholder("your@email.com").fill(email)
                            page.get_by_placeholder("输入密码", exact=True).fill(password)
                            page.locator("#main-content").get_by_role("button", name="登录", exact=True).click()
                            page.wait_for_url(FRONT + "/", wait_until="domcontentloaded")
                            page.goto(FRONT + f"/assessment/{assessment['id']}/scoring", wait_until="domcontentloaded")
                            panel = page.get_by_text("🎯 Top 3 突破要素推荐", exact=True).locator("..")
                            expect(panel.get_by_text("核心资源", exact=True)).to_be_visible()
                            text = panel.inner_text()
                            assert text.index("核心资源") < text.index("价值主张") < text.index("客户细分")
                            page.get_by_role("button", name="重新调整突破要素（全部九大模块）", exact=True).click()
                            cost = panel.get_by_role("button").filter(has_text="C$ 成本结构")
                            expect(cost).to_have_attribute("aria-pressed", "true")
                            cost.click()
                            save = panel.get_by_role("button", name="保存并锁定突破要素（已选 0/3）", exact=True)
                            expect(save).to_be_disabled()
                            panel.get_by_text("核心资源", exact=True).first.click()
                            save = panel.get_by_role("button", name="保存并锁定突破要素（已选 1/3）", exact=True)
                            expect(save).to_be_enabled()
                            with page.expect_response(lambda r: r.url.endswith("/bmc-scoring/save") and r.request.method == "POST") as pending:
                                save.click()
                            assert pending.value.ok
                            page.reload(wait_until="domcontentloaded")
                            expect(page.get_by_text("已选择：KR", exact=True)).to_be_visible()
                            page.get_by_role("button", name="生成创新方向候选", exact=True).click()
                            page.wait_for_url("**/directions", wait_until="domcontentloaded")
                            results["checks"].append("Single selection: browser save, refresh, progress, next-step navigation")
                            expansion = call("GET", root + "/directions")["direction_expansion"]["elements"]
                            ids = [expansion[0]["suggestions"][0]["direction_id"]]
                            call("POST", root + "/directions/select", {"selected_direction_ids": ids})
                            scenes = call("POST", root + "/scenarios")["scenario_recommendation"]
                            all_items = scenes["all_scores"]
                            original = [x["scenario_id"] for x in scenes["top_scenarios"]]
                            replacement = next(x for x in all_items if x["scenario_id"] not in original)
                            page.goto(FRONT + f"/assessment/{assessment['id']}/scenarios", wait_until="domcontentloaded")
                            preview = page.get_by_text("实时预览", exact=True).locator("..")
                            expect(preview.get_by_text("QS = X × Y，用于体现象限位置。", exact=True)).to_be_visible()
                            expect(preview.get_by_text("LPS = [X × 0.6 + (6 - Y) × 0.4] × 行业系数 × 2，用于推荐排序。", exact=True)).to_be_visible()
                            page.get_by_role("button", name="重新选择 Top 3 应用场景", exact=True).click()
                            page.get_by_role("checkbox", name=scenes["top_scenarios"][0]["name"], exact=True).uncheck()
                            page.get_by_role("checkbox", name=replacement["name"], exact=True).check()
                            with page.expect_response(lambda r: r.url.endswith("/scenarios/top3") and r.request.method == "PUT") as pending:
                                page.get_by_role("button", name="确认新的 Top 3（已选 3/3）", exact=True).click()
                            assert pending.value.ok
                            expected_ids = original[1:] + [replacement["scenario_id"]]
                            actual = call("GET", root)["scenario_recommendation"]["top_scenarios"]
                            assert [x["scenario_id"] for x in actual] == expected_ids
                            page.reload(wait_until="domcontentloaded")
                            expect(page.get_by_text("场景三 · " + replacement["name"], exact=True)).to_be_visible()
                            capture_screen(page, output / "scenarios.png")
                            results["checks"].append("Manual Top3: real PUT, persisted ordered IDs and refreshed cards; formula placement")
                            call("POST", root + "/competitiveness/generate")
                            call("POST", root + "/endgame/generate")
                            page.goto(FRONT + f"/assessment/{assessment['id']}/endgame", wait_until="domcontentloaded")
                            expect(page.get_by_role("heading", name="反馈验收企业 核心竞争力推进策略", exact=True)).to_be_visible()
                            expect(page.get_by_text("三阶段推进策略", exact=True)).to_be_visible()
                            assert page.get_by_text("行业商业终局判断", exact=True).count() == 0
                            capture_screen(page, output / "strategy.png")
                            page.goto(FRONT + f"/assessment/{assessment['id']}/results", wait_until="domcontentloaded")
                            expect(page.get_by_text("三阶段推进策略", exact=True)).to_be_visible()
                            assert page.get_by_text("行业商业终局判断", exact=True).count() == 0
                            assert page.get_by_text("串联逻辑描述", exact=True).count() == 0
                            assert page.get_by_text("VP 交付逻辑变化", exact=True).count() == 0
                            results["checks"].append("Strategy page and results dashboard retain stages, omit removed design/redundant fields")
                            assert not errors, errors
                            results["checks"].append("No browser page errors")
                        except Exception:
                            results["last_url"] = page.url
                            results["page_errors"] = errors
                            try:
                                capture_screen(page, output / "failure.png")
                            except Exception:
                                pass
                            raise
                        finally:
                            browser.close()
            finally:
                for process in reversed(processes):
                    if process.poll() is None:
                        if os.name == "nt":
                            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
                        else:
                            process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
    finally:
        for handle in handles:
            handle.close()
        (output / "result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
