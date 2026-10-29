import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AssessmentWorkspace } from "@/components/assessment-workspace";
import { useAssessmentStore } from "@/stores/assessment-store";
import { initialProgress } from "@/lib/assessment-utils";
import type { AssessmentDetailResponse, AssessmentResponse, EndgameResponse } from "@/lib/types";

const controls = vi.hoisted(() => ({
  pendingKey: "profile" as string | null,
  detail: undefined as AssessmentDetailResponse | undefined,
  generateProfile: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/components/assessment-form-section", () => ({ AssessmentFormSection: () => null }));
vi.mock("@/hooks", async () => {
  const actual = await vi.importActual<typeof import("@/hooks")>("@/hooks");
  const mutation = (key: string) => ({ mutateAsync: vi.fn(), isPending: controls.pendingKey === key });
  return {
    ...actual,
    useAssessmentDetail: () => ({ data: controls.detail, isLoading: false }),
    useIntakeSession: () => ({ data: undefined }),
    useGenerateProfile: () => ({ mutateAsync: controls.generateProfile, isPending: controls.pendingKey === "profile" }),
    useGenerateCanvas: () => mutation("canvas"),
    useExpandDirections: () => mutation("directions"),
    useSelectDirections: () => mutation("selection"),
    useGenerateScenarios: () => mutation("scenarios"),
    useGenerateCompetitiveness: () => mutation("competitiveness"),
    useGenerateEndgame: () => mutation("endgame"),
  };
});

const assessment: AssessmentResponse = {
  id: "assessment-1", company_name: "测试企业", industry: "制造业",
  company_size: "", region: "", annual_revenue_range: "", core_products: "",
  target_customers: "", current_challenges: "", ai_goals: "", available_data: "",
  notes: null, class_group: null, instructor_comment: null, has_profile: false,
  profile_generation_mode: null, profile_generated_at: null,
  created_at: "2026-10-26T08:00:00Z", updated_at: "2026-10-26T08:00:00Z",
};

const profile = {
  company_name: "测试企业", company_summary: "", value_proposition: "",
  customer_and_market: "", operations_and_resources: "", digital_and_ai_readiness: "",
  key_challenges: [], priority_ai_directions: [], missing_information: [],
};

const stage = { title: "", focus: "", strategy: "", objective: "", key_actions: [], key_risks: [] };
const endgame: EndgameResponse = {
  assessment_id: assessment.id, created_at: null, updated_at: null,
  result: {
    generation_mode: "rule_based", industry_essence: "", overall_narrative: "",
    private_domain: { current_state: "", target_model: "", key_strategies: [], customer_retention_loop: "", revenue_impact: "" },
    ecosystem: { ecosystem_positioning: "", key_partners_to_engage: [], orchestration_strategy: "", platform_effect: "" },
    opc: { operations_excellence: "", platform_capability: "", content_and_community: "", data_flywheel_effect: "" },
    three_stage_strategy: { stage_1: stage, stage_2: stage, stage_3: stage, key_risks: [] },
    strategic_paths: [],
  },
};

function restoredDetail(complete = false): AssessmentDetailResponse {
  return {
    assessment, company_profile: profile, canvas_diagnosis: null,
    breakthrough_selection: null, direction_expansion: null, direction_selection: null,
    scenario_recommendation: null, competitiveness: null, endgame: complete ? endgame : null,
    case_recommendation: null, generated_report: null,
    progress: {
      ...initialProgress, has_profile: true, has_canvas: complete, has_breakthrough: complete,
      has_directions: complete, has_scenarios: complete, has_competitiveness: complete,
      has_endgame: complete,
    },
    entitlement: {
      assessment_id: assessment.id, is_unlocked: true, can_continue: true,
      locked_after_stage: "canvas", unlock_type: null, unlocked_at: null, latest_order: null,
    },
  };
}

function renderWorkspace() {
  const client = new QueryClient();
  return render(<QueryClientProvider client={client}><AssessmentWorkspace assessmentId={assessment.id} /></QueryClientProvider>);
}

describe("assessment workspace generation", () => {
  beforeEach(() => {
    controls.pendingKey = "profile";
    controls.detail = undefined;
    controls.generateProfile.mockReset();
    useAssessmentStore.getState().resetAll();
    useAssessmentStore.getState().setAssessment(assessment);
  });

  afterEach(() => {
    cleanup();
    useAssessmentStore.getState().resetAll();
  });

  it("keeps an estimated wait visible while a full profile is generating", () => {
    renderWorkspace();
    expect(screen.getByRole("status")).toHaveTextContent("正在生成企业画像");
    expect(screen.getByRole("status")).toHaveTextContent("预计 1–2 分钟");
  });

  it("does not count a pending generation or the dashboard as a completed result", () => {
    renderWorkspace();
    const progress = screen.getByRole("progressbar", { name: "生成进度" });
    expect(progress).toHaveAttribute("aria-valuenow", "0");
    expect(progress).toHaveAttribute("aria-valuemax", "7");
    expect(screen.getByText("已完成 0 / 7 项")).toBeInTheDocument();
    expect(screen.getByText("正在生成企业画像", { selector: "p" })).toBeInTheDocument();
  });

  it("restores completed progress from the saved assessment", () => {
    controls.pendingKey = null;
    controls.detail = restoredDetail();
    renderWorkspace();
    expect(screen.getByRole("progressbar", { name: "生成进度" })).toHaveAttribute("aria-valuenow", "1");
    expect(screen.getByText("已完成 1 / 7 项")).toBeInTheDocument();
  });

  it("shows the active module name while another result is generating", () => {
    controls.pendingKey = "canvas";
    controls.detail = restoredDetail();
    renderWorkspace();
    expect(screen.getByText("正在生成商业画布 9 格", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "生成进度" })).toHaveAttribute("aria-valuenow", "1");
  });

  it("keeps existing completion visible during regeneration and recalculates after upstream invalidation", async () => {
    controls.pendingKey = "profile";
    controls.detail = restoredDetail(true);
    const view = renderWorkspace();
    expect(screen.getByRole("progressbar", { name: "生成进度" })).toHaveAttribute("aria-valuenow", "7");
    expect(screen.getByText("正在重新生成企业画像", { selector: "p" })).toBeInTheDocument();

    controls.pendingKey = null;
    controls.generateProfile.mockResolvedValue({ assessment, profile, generation_mode: "mock" });
    view.rerender(<QueryClientProvider client={new QueryClient()}><AssessmentWorkspace assessmentId={assessment.id} /></QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: /企业画像/ }));
    await waitFor(() => expect(screen.getByRole("progressbar", { name: "生成进度" })).toHaveAttribute("aria-valuenow", "1"));
    expect(screen.getByText("已完成 1 / 7 项")).toBeInTheDocument();
  });

  it("does not advance completion after a failed regeneration", async () => {
    controls.pendingKey = null;
    controls.detail = restoredDetail();
    controls.generateProfile.mockRejectedValue(new Error("生成失败"));
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: /企业画像/ }));
    await waitFor(() => expect(controls.generateProfile).toHaveBeenCalled());
    expect(screen.getByRole("progressbar", { name: "生成进度" })).toHaveAttribute("aria-valuenow", "1");
  });

  it("removes the old progress when the assessment is reset", () => {
    controls.pendingKey = null;
    controls.detail = restoredDetail(true);
    renderWorkspace();
    expect(screen.getByRole("progressbar", { name: "生成进度" })).toHaveAttribute("aria-valuenow", "7");
    act(() => useAssessmentStore.getState().resetAll());
    expect(screen.queryByRole("progressbar", { name: "生成进度" })).not.toBeInTheDocument();
  });
});
