import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Mock } from "vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AssessmentWorkbench } from "@/components/assessment-workbench";
import {
  createAssessment,
  expandDirections,
  generateAssessmentCanvas,
  generateAssessmentProfile,
  generateCompetitiveness,
  generateEndgame,
  generateScenarioRecommendations,
  getAssessmentDetail,
  getFollowUpPlan,
  getIntakeImportSession,
  recommendBreakthrough,
  selectBreakthrough,
  selectDirections,
} from "@/lib/api";
import type { AssessmentResponse, IntakeSessionDetailResponse } from "@/lib/types";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/lib/api", () => ({
  createAssessment: vi.fn(),
  expandDirections: vi.fn(),
  generateAssessmentCanvas: vi.fn(),
  generateAssessmentProfile: vi.fn(),
  generateCompetitiveness: vi.fn(),
  generateEndgame: vi.fn(),
  generateScenarioRecommendations: vi.fn(),
  getAssessmentDetail: vi.fn(),
  getFollowUpPlan: vi.fn(),
  getIntakeImportSession: vi.fn(),
  recommendBreakthrough: vi.fn(),
  selectBreakthrough: vi.fn(),
  selectDirections: vi.fn(),
}));

function buildPrefillDetail(
  overrides: Partial<IntakeSessionDetailResponse> = {},
): IntakeSessionDetailResponse {
  return {
    import_session_id: "session-prefill",
    status: "parsed",
    source_type: "markdown",
    source_file: null,
    assessment_prefill: {
      company_name: "预填企业",
      industry: "工业软件",
      company_size: null,
      region: "华东",
      annual_revenue_range: null,
      core_products: "设备数据采集平台",
      target_customers: null,
      current_challenges: null,
      ai_goals: null,
      available_data: null,
      notes: null,
    },
    field_meta: {
      company_name: { source_type: "raw", status: "confirmed" },
      industry: { source_type: "raw", status: "confirmed" },
      company_size: { source_type: "missing", status: "needs_user_input" },
      region: { source_type: "raw", status: "confirmed" },
      annual_revenue_range: { source_type: "missing", status: "needs_user_input" },
      core_products: { source_type: "raw", status: "confirmed" },
      target_customers: { source_type: "missing", status: "needs_user_input" },
      current_challenges: { source_type: "missing", status: "needs_user_input" },
      ai_goals: { source_type: "missing", status: "needs_user_input" },
      available_data: { source_type: "missing", status: "needs_user_input" },
      notes: { source_type: "missing", status: "needs_user_input" },
    },
    field_candidates: {},
    unmapped_notes: [],
    warnings: [],
    raw_content: "## 企业名称\n预填企业",
    structured_fields: {},
    created_assessment_id: null,
    created_at: "2026-05-06T00:00:00",
    updated_at: "2026-05-06T00:00:00",
    ...overrides,
  };
}

function buildAssessmentResponse(
  overrides: Partial<AssessmentResponse> = {},
): AssessmentResponse {
  return {
    id: "assessment-prefill",
    company_name: "预填企业",
    industry: "工业软件",
    company_size: "",
    region: "华东",
    annual_revenue_range: "",
    core_products: "设备数据采集平台",
    target_customers: "",
    current_challenges: "",
    ai_goals: "",
    available_data: "",
    notes: null,
    class_group: null,
    instructor_comment: null,
    has_profile: false,
    profile_generation_mode: null,
    profile_generated_at: null,
    created_at: "2026-05-06T00:00:00",
    updated_at: "2026-05-06T00:00:00",
    ...overrides,
  };
}

describe("AssessmentWorkbench", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (createAssessment as Mock).mockReset();
    (expandDirections as Mock).mockReset();
    (generateAssessmentCanvas as Mock).mockReset();
    (generateAssessmentProfile as Mock).mockReset();
    (generateCompetitiveness as Mock).mockReset();
    (generateEndgame as Mock).mockReset();
    (generateScenarioRecommendations as Mock).mockReset();
    (getAssessmentDetail as Mock).mockReset();
    (getFollowUpPlan as Mock).mockReset();
    (getIntakeImportSession as Mock).mockReset();
    (recommendBreakthrough as Mock).mockReset();
    (selectBreakthrough as Mock).mockReset();
    (selectDirections as Mock).mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("prefills the assessment form from an intake session id", async () => {
    (getIntakeImportSession as Mock).mockResolvedValue(buildPrefillDetail());

    render(<AssessmentWorkbench prefillSessionId="session-prefill" />);

    await waitFor(() => {
      expect(getIntakeImportSession).toHaveBeenCalledWith("session-prefill");
    });

    expect(await screen.findByDisplayValue("预填企业")).toBeInTheDocument();
    expect(screen.getByDisplayValue("工业软件")).toBeInTheDocument();
    expect(screen.getByDisplayValue("华东")).toBeInTheDocument();
    expect(screen.getByDisplayValue("设备数据采集平台")).toBeInTheDocument();
    expect(screen.getByText(/已从前置材料带入 4 \/ 11 个字段/)).toBeInTheDocument();
  });

  it("submits even when imported fields are incomplete", async () => {
    (getIntakeImportSession as Mock).mockResolvedValue(buildPrefillDetail());
    (createAssessment as Mock).mockResolvedValue(buildAssessmentResponse());

    const user = userEvent.setup();
    render(<AssessmentWorkbench prefillSessionId="session-prefill" />);

    await screen.findByDisplayValue("预填企业");
    await user.click(screen.getByRole("button", { name: "提交企业问卷" }));

    await waitFor(() => {
      expect(createAssessment).toHaveBeenCalledWith({
        company_name: "预填企业",
        industry: "工业软件",
        company_size: "",
        region: "华东",
        annual_revenue_range: "",
        core_products: "设备数据采集平台",
        target_customers: "",
        current_challenges: "",
        ai_goals: "",
        available_data: "",
        notes: null,
      });
    });
    expect(pushMock).toHaveBeenCalledWith("/assessment/assessment-prefill");
  });
});
