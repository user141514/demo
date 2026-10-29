import type {
  AssessmentCreateRequest,
  AssessmentDetailResponse,
  AssessmentDirectionResponse,
  AssessmentPrefillDraft,
  AssessmentProgress,
  AssessmentResponse,
  BreakthroughSelectionResponse,
  CanvasDiagnosisResult,
  CompanyProfileResult,
  CompetitivenessResponse,
  DirectionSelectionResponse,
  EndgameResponse,
  ScenarioRecommendationResult,
} from "@/lib/types";

export const initialForm: AssessmentCreateRequest = {
  company_name: "", industry: "", company_size: "", region: "",
  annual_revenue_range: "", core_products: "", target_customers: "",
  current_challenges: "", ai_goals: "", available_data: "", notes: "",
};

export function createInitialAssessmentForm({
  companyName,
  prefillSessionId,
  assessmentId,
}: {
  companyName?: string;
  prefillSessionId?: string;
  assessmentId?: string;
}): AssessmentCreateRequest {
  return {
    ...initialForm,
    company_name: assessmentId || prefillSessionId ? "" : (companyName?.trim() ?? ""),
  };
}

export const initialProgress: AssessmentProgress = {
  has_profile: false, has_canvas: false, has_breakthrough: false,
  has_directions: false, has_competitiveness: false, has_endgame: false, has_scenarios: false,
  has_report: false, ready_for_report: false,
};

export const companySizeOptions = [
  "10人以下", "10-50人", "50-200人", "200-500人", "500人以上",
];

export const revenueOptions = [
  "500万以下", "500万-3000万", "3000万-1亿", "1亿-10亿", "10亿以上",
];

export function mapAssessmentToForm(
  assessment: AssessmentResponse,
): AssessmentCreateRequest {
  return {
    company_name: assessment.company_name,
    industry: assessment.industry,
    company_size: assessment.company_size,
    region: assessment.region,
    annual_revenue_range: assessment.annual_revenue_range,
    core_products: assessment.core_products,
    target_customers: assessment.target_customers,
    current_challenges: assessment.current_challenges,
    ai_goals: assessment.ai_goals,
    available_data: assessment.available_data,
    notes: assessment.notes ?? "",
  };
}

export function mergePrefillIntoForm(
  currentForm: AssessmentCreateRequest,
  prefill: AssessmentPrefillDraft,
): AssessmentCreateRequest {
  const mergedEntries = Object.entries(prefill).map(([key, value]) => {
    const formKey = key as keyof AssessmentCreateRequest;
    const currentValue =
      typeof currentForm[formKey] === "string"
        ? (currentForm[formKey] as string)
        : (currentForm[formKey] ?? "");
    const normalizedCurrent = (currentValue as string).trim();
    const normalizedPrefill = ((value ?? "") as string).trim();

    if (normalizedCurrent || !normalizedPrefill) {
      return [formKey, currentForm[formKey]];
    }
    return [formKey, normalizedPrefill];
  });

  return {
    ...currentForm,
    ...Object.fromEntries(mergedEntries),
  };
}

export function countPrefillFields(prefill: AssessmentPrefillDraft): number {
  return Object.values(prefill).filter(
    (value) => typeof value === "string" && value.trim().length > 0,
  ).length;
}

export function computeProgress(opts: {
  hasAssessment: boolean;
  hasProfile: boolean;
  hasCanvas: boolean;
  hasBreakthrough?: boolean;
  hasDirections?: boolean;
  hasCompetitiveness?: boolean;
  hasEndgame?: boolean;
  hasScenarios: boolean;
  hasReport?: boolean;
}): AssessmentProgress {
  return {
    has_profile: opts.hasAssessment && opts.hasProfile,
    has_canvas: opts.hasAssessment && opts.hasCanvas,
    has_breakthrough: opts.hasAssessment && (opts.hasBreakthrough ?? false),
    has_directions: opts.hasAssessment && (opts.hasDirections ?? false),
    has_competitiveness: opts.hasAssessment && (opts.hasCompetitiveness ?? false),
    has_endgame: opts.hasAssessment && (opts.hasEndgame ?? false),
    has_scenarios: opts.hasAssessment && opts.hasScenarios,
    has_report: opts.hasAssessment && (opts.hasReport ?? false),
    ready_for_report:
      opts.hasAssessment &&
      opts.hasProfile &&
      opts.hasCanvas &&
      (opts.hasBreakthrough ?? false) &&
      (opts.hasDirections ?? false) &&
      opts.hasScenarios &&
      (opts.hasCompetitiveness ?? false) &&
      (opts.hasEndgame ?? false),
  };
}

export function applyAssessmentDetailToStore(
  detail: AssessmentDetailResponse,
  store: {
    setAssessment: (a: AssessmentResponse | null) => void;
    setCompanyProfile: (p: CompanyProfileResult | null) => void;
    setProfileMode: (m: "mock" | "live" | null) => void;
    setCanvasDiagnosis: (d: CanvasDiagnosisResult | null) => void;
    setBreakthroughSelection: (s: BreakthroughSelectionResponse | null) => void;
    setSelectedBreakthroughKeys: (keys: string[]) => void;
    setScenarioRecommendation: (r: ScenarioRecommendationResult | null) => void;
    setDirectionData: (d: AssessmentDirectionResponse | null) => void;
    setDirectionSelection: (s: DirectionSelectionResponse | null) => void;
    setSelectedDirectionIds: (ids: string[]) => void;
    setCompetitivenessData: (d: CompetitivenessResponse | null) => void;
    setEndgameData: (d: EndgameResponse | null) => void;
  },
) {
  store.setAssessment(detail.assessment);
  store.setCompanyProfile(detail.company_profile);
  store.setProfileMode(
    detail.company_profile
      ? ((detail.assessment.profile_generation_mode as "mock" | "live" | null) ?? "mock")
      : null,
  );
  store.setCanvasDiagnosis(detail.canvas_diagnosis);

  // Sync breakthrough selection if present
  if (detail.breakthrough_selection && detail.breakthrough_selection.length >= 1) {
    store.setSelectedBreakthroughKeys(detail.breakthrough_selection);
    // Build minimal BreakthroughSelectionResponse so the UI shows "done"
    store.setBreakthroughSelection({
      assessment_id: detail.assessment.id,
      selection_mode: "system_recommended",
      recommended_elements: [],
      selected_elements: detail.breakthrough_selection.map((key) => ({
        key,
        title: key,
        score: 0,
        reason: "",
        ai_opportunity: "",
      })),
      created_at: null,
      updated_at: null,
    });
  } else {
    store.setSelectedBreakthroughKeys([]);
    store.setBreakthroughSelection(null);
  }

  // Sync direction expansion and selection if present
  if (detail.direction_expansion) {
    store.setDirectionData({
      assessment_id: detail.assessment.id,
      direction_expansion: detail.direction_expansion,
      direction_selection: detail.direction_selection ?? null,
    });
  } else {
    store.setDirectionData(null);
  }

  if (detail.direction_selection && detail.direction_selection.selected_directions.length > 0) {
    store.setDirectionSelection(detail.direction_selection);
    store.setSelectedDirectionIds(
      detail.direction_selection.selected_directions.map((d) => d.direction_id),
    );
  } else {
    store.setDirectionSelection(null);
    store.setSelectedDirectionIds([]);
  }

  // Sync competitiveness if present
  store.setScenarioRecommendation(detail.scenario_recommendation);
  store.setCompetitivenessData(detail.competitiveness);
  store.setEndgameData(detail.endgame);
}
