export type AssessmentCreateRequest = {
  company_name: string;
  industry: string;
  company_size: string;
  region: string;
  annual_revenue_range: string;
  core_products: string;
  target_customers: string;
  current_challenges: string;
  ai_goals: string;
  available_data: string;
  notes: string | null;
};

export type AssessmentInputSnapshot = {
  company_name: string;
  industry: string;
  company_size: string;
  region: string;
  annual_revenue_range: string;
  core_products: string;
  target_customers: string;
  current_challenges: string;
  ai_goals: string;
  available_data: string;
  notes: string | null;
};

export type AssessmentResponse = {
  id: string;
  company_name: string;
  industry: string;
  company_size: string;
  region: string;
  annual_revenue_range: string;
  core_products: string;
  target_customers: string;
  current_challenges: string;
  ai_goals: string;
  available_data: string;
  notes: string | null;
  class_group: string | null;
  instructor_comment: string | null;
  has_profile: boolean;
  profile_generation_mode: string | null;
  profile_generated_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CompanyProfileResult = {
  company_name: string;
  company_summary: string;
  value_proposition: string;
  customer_and_market: string;
  operations_and_resources: string;
  digital_and_ai_readiness: string;
  key_challenges: string[];
  priority_ai_directions: string[];
  missing_information: string[];
};

export type AssessmentProfileResponse = {
  assessment: AssessmentResponse;
  generation_mode: "mock" | "live";
  profile: CompanyProfileResult;
};

export type CanvasBlockResult = {
  key: string;
  title: string;
  current_state: string;
  diagnosis: string;
  ai_opportunity: string;
  missing_information: string;
};

export type BusinessModelCanvasResult = {
  overall_summary: string;
  blocks: CanvasBlockResult[];
};

export type CanvasDiagnosisResult = {
  generation_mode: "mock" | "live" | "manual_edit";
  overall_score: number;
  weakest_blocks: string[];
  recommended_focus: string[];
  canvas: BusinessModelCanvasResult;
  created_at: string | null;
  updated_at: string | null;
};

export type AssessmentCanvasResponse = {
  assessment: AssessmentResponse;
  canvas_diagnosis: CanvasDiagnosisResult;
};

export type ScenarioBenefit = {
  text: string;
  canvas: string;
};

export type ScenarioResource = {
  type: "data" | "org" | "invest" | "risk" | string;
  label: string;
  text: string;
};

export type ScenarioRecommendationItem = {
  scenario_id: string;
  name: string;
  category: string;
  summary: string;
  canvas_elements: string;
  expected_effects: string;
  core_data_requirements: string;
  // 新版结构化字段
  canvas_element?: string | null;
  canvas_key?: string | null;
  positioning?: string | null;
  value_dimensions?: string[] | null;
  value_text?: string | null;
  benefits?: ScenarioBenefit[] | null;
  resources?: ScenarioResource[] | null;
  // 四象限优先级评分字段（four_quadrant_v1 时填充）
  priority_structuredness_x?: number | null;
  priority_complexity_y?: number | null;
  priority_qs?: number | null;
  priority_lps?: number | null;
  priority_lps_display?: number | null;
  priority_quadrant?: string | null;
  priority_tier?: number | null;
  priority_recommendation?: string | null;
  industry_coefficient?: number | null;
  recommendation_level?: string | null;
};

export type ScenarioRecommendationResult = {
  scoring_method: "rule_based_v1" | "four_quadrant_v1";
  evaluated_count: number;
  top_scenarios: ScenarioRecommendationItem[];
  active_count?: number | null;
  excluded_scores?: ScenarioRecommendationItem[] | null;
  all_scores?: ScenarioRecommendationItem[] | null;
  created_at: string | null;
  updated_at: string | null;
};

export type ScenarioPoolUpdateRequest = {
  active_scenario_ids: string[];
};

export type ScenarioTop3SelectionRequest = {
  selected_scenario_ids: string[];
};

export type AssessmentScenarioRecommendationResponse = {
  assessment: AssessmentResponse;
  scenario_recommendation: ScenarioRecommendationResult;
};

export type CaseMatchItem = {
  case_id: string;
  title: string;
  industry: string;
  summary: string;
  fit_score: number;
  matched_pain_points: string[];
  matched_canvas_blocks: string[];
  matched_scenarios: string[];
  match_reasons: string[];
  reference_points: string[];
  data_foundation: string[];
  cautions: string[];
  retrieval_source: string;
  source_summary: string;
};

export type CaseRecommendationResult = {
  scoring_method: "rule_based_case_v1" | "layered_v1";
  evaluated_count: number;
  top_cases: CaseMatchItem[];
  created_at: string | null;
  updated_at: string | null;
};

export type AssessmentCaseResponse = {
  assessment: AssessmentResponse;
  case_recommendation: CaseRecommendationResult;
};

export type ReportTableData = {
  columns: string[];
  rows: string[][];
};

export type ReportCardData = {
  title: string;
  subtitle: string | null;
  content: string;
  bullets: string[];
  highlight: string | null;
};

export type ReportSectionData = {
  key: string;
  title: string;
  content: string;
  bullets: string[];
  table: ReportTableData | null;
  cards: ReportCardData[];
  note: string | null;
};

export type ReportData = {
  title: string;
  subtitle: string;
  company_name: string;
  industry: string;
  company_size: string;
  region: string;
  annual_revenue_range: string;
  ai_readiness_score: number;
  ai_readiness_summary: string;
  generated_with: "template" | "llm";
  sections: ReportSectionData[];
};

export type ReportSummaryResponse = {
  report_id: string;
  assessment_id: string;
  title: string;
  created_at: string | null;
  updated_at: string | null;
};

export type ReportDocumentResponse = {
  report_id: string;
  assessment_id: string;
  title: string;
  generation_mode: string;
  used_llm: boolean;
  used_rag: boolean;
  warnings: string[];
  content_markdown: string;
  content_html: string;
  content_json: ReportData;
  sections: ReportSectionData[];
  export_markdown_path: string | null;
  export_docx_path: string | null;
  export_pdf_path: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type AssessmentProgress = {
  has_profile: boolean;
  has_canvas: boolean;
  has_breakthrough: boolean;
  has_directions: boolean;
  has_competitiveness: boolean;
  has_endgame: boolean;
  has_scenarios: boolean;
  has_cases?: boolean;
  has_report: boolean;
  ready_for_report: boolean;
};

export type PaymentProvider = "wechat" | "alipay";

export type PaymentOrderStatus =
  | "pending"
  | "paid"
  | "failed"
  | "expired"
  | "canceled";

export type PaymentOrderCreateRequest = {
  provider: PaymentProvider;
};

export type PaymentOrderResponse = {
  order_id: string;
  order_no: string;
  assessment_id: string;
  provider: PaymentProvider;
  amount_cents: number;
  currency: string;
  status: PaymentOrderStatus;
  qr_code_url: string | null;
  expires_at: string;
  paid_at: string | null;
  created_at: string;
};

export type AssessmentEntitlementResponse = {
  assessment_id: string;
  is_unlocked: boolean;
  can_continue: boolean;
  locked_after_stage: "canvas";
  unlock_type: string | null;
  unlocked_at: string | null;
  latest_order: PaymentOrderResponse | null;
};

export type PaymentNotifyResponse = {
  status: PaymentOrderStatus;
  order_no: string;
  assessment_id: string;
  is_unlocked: boolean;
};

export type AssessmentDetailResponse = {
  assessment: AssessmentResponse;
  company_profile: CompanyProfileResult | null;
  canvas_diagnosis: CanvasDiagnosisResult | null;
  breakthrough_selection: string[] | null;
  direction_expansion: DirectionExpansionResult | null;
  direction_selection: DirectionSelectionResponse | null;
  scenario_recommendation: ScenarioRecommendationResult | null;
  competitiveness: CompetitivenessResponse | null;
  endgame: EndgameResponse | null;
  case_recommendation: CaseRecommendationResult | null;
  generated_report: ReportSummaryResponse | null;
  progress: AssessmentProgress;
  entitlement: AssessmentEntitlementResponse;
};

export type ReportContextResponse = {
  assessment_id: string;
  company_input: AssessmentInputSnapshot;
  company_profile: CompanyProfileResult;
  canvas_diagnosis: CanvasDiagnosisResult;
  selected_breakthrough_elements: string[];
  top_scenarios: ScenarioRecommendationItem[];
  report_outline: string[];
};

export type IntakeSourceType = "text" | "markdown" | "form" | "file";

export type IntakeUploadedFileKind = "txt" | "markdown" | "pdf" | "docx";

export type IntakeFieldSourceType = "raw" | "inferred" | "missing";

export type IntakeFieldStatus =
  | "confirmed"
  | "needs_user_confirmation"
  | "needs_user_input";

export type IntakeSessionStatus =
  | "draft"
  | "parsed"
  | "confirmed"
  | "discarded";

export type IntakeImportRequest = {
  source_type: IntakeSourceType;
  raw_content?: string | null;
  structured_fields?: Partial<Record<keyof AssessmentCreateRequest, string>>;
};

export type IntakeSourceFile = {
  name: string;
  kind: IntakeUploadedFileKind;
  size_bytes: number;
};

export type IntakeFieldMeta = {
  source_type: IntakeFieldSourceType;
  status: IntakeFieldStatus;
};

export type IntakeFieldCandidate = {
  value: string;
  source: "原文" | "推断";
  confidence: "high" | "medium";
  evidence: string;
};

export type AssessmentPrefillDraft = {
  [K in keyof AssessmentCreateRequest]: string | null;
};

export type IntakeImportResponse = {
  import_session_id: string;
  status: IntakeSessionStatus;
  source_type: IntakeSourceType;
  source_file: IntakeSourceFile | null;
  assessment_prefill: AssessmentPrefillDraft;
  field_meta: Partial<Record<keyof AssessmentCreateRequest, IntakeFieldMeta>>;
  field_candidates: Partial<
    Record<keyof AssessmentCreateRequest, IntakeFieldCandidate>
  >;
  unmapped_notes: string[];
  warnings: string[];
};

export type IntakeSessionDetailResponse = IntakeImportResponse & {
  raw_content: string | null;
  structured_fields: Partial<Record<keyof AssessmentCreateRequest, string>>;
  created_assessment_id: string | null;
  created_at: string;
  updated_at: string;
};

export type IntakeCreateAssessmentRequest = {
  confirmed_assessment_input: AssessmentCreateRequest;
};

export type IntakeCreateAssessmentResponse = {
  import_session_id: string;
  status: IntakeSessionStatus;
  assessment: AssessmentResponse;
};

export type BreakthroughElement = {
  key: string;
  title: string;
  score: number;
  reason: string;
  ai_opportunity: string;
};

export type BreakthroughRecommendationResult = {
  generation_mode: "rule_based" | "mock";
  elements: BreakthroughElement[];
  recommended_keys: string[];
  overall_suggestion: string;
};

export type BreakthroughSelectionResponse = {
  assessment_id: string;
  selection_mode: string;
  recommended_elements: BreakthroughElement[];
  selected_elements: BreakthroughElement[];
  created_at: string | null;
  updated_at: string | null;
};

export type AssessmentBreakthroughResponse = {
  assessment_id: string;
  breakthrough_recommendation: BreakthroughRecommendationResult;
  breakthrough_selection: BreakthroughSelectionResponse | null;
};

export type BreakthroughSelectionRequest = {
  selected_keys: string[];
  selection_mode: "system_recommended" | "manual";
};

export type DirectionSuggestion = {
  direction_id: string;
  element_key: string;
  title: string;
  description: string;
  expected_impact: string;
  data_needed: string[];
  related_scenario_categories: string[];
};

export type DirectionExpansionByElement = {
  element_key: string;
  element_title: string;
  suggestions: DirectionSuggestion[];
};

export type DirectionExpansionResult = {
  generation_mode: "rule_based" | "llm";
  llm_status: "pending" | "completed" | "failed";
  created_at?: string | null;
  updated_at?: string | null;
  elements: DirectionExpansionByElement[];
  total_suggestions: number;
};

export type DirectionSelectionResponse = {
  assessment_id: string;
  generation_mode: "rule_based";
  selected_directions: DirectionSuggestion[];
  created_at: string | null;
  updated_at: string | null;
};

export type AssessmentDirectionResponse = {
  assessment_id: string;
  direction_expansion: DirectionExpansionResult;
  direction_selection: DirectionSelectionResponse | null;
};

export type DirectionSelectionRequest = {
  selected_direction_ids: string[];
};

export type VPReconstruction = {
  current_vp: string;
  enhanced_vp: string;
  differentiation_points: string[];
  customer_value_shift: string;
};

export type PointToLineConnection = {
  line_name: string;
  point_ids: string[];
  point_titles: string[];
  strategic_narrative: string;
  competitive_impact: string;
  key_metrics: string[];
  linkage_logic: string;
  competitive_moat: string;
};

export type CoreAdvantage = {
  advantage_name: string;
  source_elements: string[];
  description: string;
  barrier_level: "低" | "中" | "高";
};

export type DeliveryStrategy = {
  phase_1_quick_win: string;
  phase_2_scale: string;
  phase_3_moat: string;
  key_risks: string[];
};

export type CompetitivenessResult = {
  generation_mode: "rule_based" | "llm" | "manual_edit";
  vp_reconstruction: VPReconstruction;
  connections: PointToLineConnection[];
  advantages: CoreAdvantage[];
  delivery_strategy: DeliveryStrategy;
  overall_narrative: string;
};

export type CompetitivenessResponse = {
  assessment_id: string;
  result: CompetitivenessResult;
  created_at: string | null;
  updated_at: string | null;
};

export type ExecutiveSummary = {
  headline: string;
  key_findings: string[];
  top_3_recommendations: string[];
  readiness_verdict: string;
};

export type IndustryBenchmark = {
  industry: string;
  industry_avg_score: number;
  peer_company_size: string;
  peer_avg_score: number;
  percentile_rank: number;
  key_gap: string;
  advantage: string;
};

export type RoiFramework = {
  confidence_level: string;
  low_investment_scenarios: { name: string; investment: string; expected_return: string }[];
  medium_investment_scenarios: { name: string; investment: string; expected_return: string }[];
  high_investment_scenarios: { name: string; investment: string; expected_return: string }[];
  roi_time_horizon: string;
};

export type InstructorComment = {
  comment_mode: string;
  overall_assessment: string;
  strength_points: string[];
  risk_warnings: string[];
  next_steps_advice: string;
  recommended_reading: string[];
};

export type ReportEnrichmentResult = {
  executive_summary: ExecutiveSummary;
  industry_benchmark: IndustryBenchmark;
  roi_framework: RoiFramework;
  instructor_comment: InstructorComment;
  generated_at: string | null;
};

export type PrivateDomainDesign = {
  current_state: string;
  target_model: string;
  key_strategies: string[];
  customer_retention_loop: string;
  revenue_impact: string;
};

export type EcosystemDesign = {
  ecosystem_positioning: string;
  key_partners_to_engage: string[];
  orchestration_strategy: string;
  platform_effect: string;
};

export type OPCDesign = {
  operations_excellence: string;
  platform_capability: string;
  content_and_community: string;
  data_flywheel_effect: string;
};

export type ThreeStageStrategyStage = {
  title: string;
  focus: string;
  strategy: string;
  objective: string;
  key_actions: string[];
  key_risks: string[];
};

export type ThreeStageStrategy = {
  stage_1: ThreeStageStrategyStage;
  stage_2: ThreeStageStrategyStage;
  stage_3: ThreeStageStrategyStage;
  key_risks: string[];
};

export type StrategicPath = {
  path_name: string;
  path_type: "保守" | "均衡" | "激进";
  execution_rhythm: string;
  key_milestones: string[];
  capability_requirements: string;
  expected_outcomes: string;
  major_risks: string[];
  recommendation_level: "推荐" | "可选" | "不推荐";
};

export type EndgameResult = {
  generation_mode: "rule_based" | "llm" | "manual_edit";
  industry_essence: string;
  private_domain: PrivateDomainDesign;
  ecosystem: EcosystemDesign;
  opc: OPCDesign;
  three_stage_strategy: ThreeStageStrategy;
  strategic_paths: StrategicPath[];
  overall_narrative: string;
};

export type EndgameResponse = {
  assessment_id: string;
  result: EndgameResult;
  created_at: string | null;
  updated_at: string | null;
};

export type UpdateCompetitivenessPayload = Omit<
  CompetitivenessResult,
  "generation_mode"
>;

export type UpdateEndgamePayload = Omit<
  EndgameResult,
  "generation_mode" | "industry_essence"
> & {
  industry_essence?: string;
};

export type QualityFlag = {
  code: string;
  level: "info" | "warn" | "error";
  message: string;
};

export type SectionQualityReport = {
  section_key: string;
  section_title: string;
  confidence: "高" | "中" | "低";
  source: "规则引擎" | "模板知识库" | "LLM生成" | "用户输入" | "待补充";
  flags: QualityFlag[];
  has_actionable_content: boolean;
  missing_aspects: string[];
};

export type OverallQualityReport = {
  overall_score: number;
  overall_confidence: "高" | "中" | "低";
  sections: SectionQualityReport[];
  critical_flags: QualityFlag[];
  summary: string;
  improvement_suggestions: string[];
};

export type FollowUpTaskItem = {
  task_id: string;
  period: string;
  action: string;
  owner_suggestion: string;
  deliverable: string;
  status: "pending" | "in_progress" | "completed" | "blocked";
  progress_note: string | null;
  blocked: boolean;
  blocker_description: string | null;
  sort_order: number;
  last_reviewed_at: string | null;
};

export type FollowUpPlan = {
  assessment_id: string;
  tasks: FollowUpTaskItem[];
  overall_progress_pct: number;
  completed_count: number;
  blocked_count: number;
  total_count: number;
  next_review_date: string | null;
  recalibration_note: string | null;
};

export type TaskUpdateRequest = {
  status?: "pending" | "in_progress" | "completed" | "blocked";
  progress_note?: string;
  blocked?: boolean;
  blocker_description?: string;
};

export type PushedCase = {
  case_id: string;
  title: string;
  industry: string;
  summary: string;
  fit_score: number;
  source_summary: string;
  reference_points: string[];
  data_foundation: string[];
  cautions: string[];
};

export type PushCycleResult = {
  cycle: number;
  pushed_cases: PushedCase[];
  cycle_note: string;
  pushed_at: string | null;
  previous_case_ids: string[];
  total_available: number;
};

export type RecalibratePlanRequest = {
  note: string;
  new_actions: {
    task_id?: string | null;
    period?: string | null;
    action: string;
    owner_suggestion: string;
    deliverable: string;
    status?: "pending" | "in_progress" | "completed" | "blocked";
  }[];
  update_task_ids: string[];
};

export type StudentSummary = {
  assessment_id: string;
  company_name: string;
  industry: string;
  company_size: string;
  class_group: string | null;
  instructor_comment: string | null;
  has_profile: boolean;
  has_canvas: boolean;
  has_breakthrough: boolean;
  has_directions: boolean;
  has_competitiveness: boolean;
  has_scenarios: boolean;
  has_cases: boolean;
  has_report: boolean;
  ready_for_report: boolean;
  canvas_score: number | null;
  report_id: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type InstructorDashboardResponse = {
  total_students: number;
  groups: string[];
  students: StudentSummary[];
  summary_by_group: Record<string, number>;
  overall_completion_pct: number;
};

export type BatchCommentResponse = {
  updated_count: number;
  comment: string;
};

export type CreateInstructorRequest = {
  email: string;
  password: string;
  display_name?: string | null;
};

// ── Auth ──
export type UserResponse = {
  id: string;
  email: string;
  display_name: string | null;
  company_name?: string | null;
  job_title?: string | null;
  role: "student" | "user" | "instructor";
  has_recovery: boolean;
  created_at: string;
};

export type RegisterRequest = {
  email: string;
  password: string;
  display_name: string;
  company_name: string;
  job_title: string;
  recovery_question?: string | null;
  recovery_answer?: string | null;
};

export type LoginRequest = {
  email: string;
  password: string;
};

export type ForgotPasswordQuestionRequest = {
  email: string;
};

export type ForgotPasswordQuestionResponse = {
  email: string;
  recovery_question: string;
};

export type ResetPasswordRequest = {
  email: string;
  recovery_answer: string;
  new_password: string;
};

export type ResetPasswordResponse = {
  success: boolean;
};

export type UpdateRecoveryRequest = {
  recovery_question: string;
  recovery_answer: string;
};

export type UpdateRecoveryResponse = {
  success: boolean;
};

export type SetupRecoveryRequest = {
  email: string;
  password: string;
  recovery_question: string;
  recovery_answer: string;
};

export type SetupRecoveryResponse = {
  success: boolean;
};

export type ForgotPasswordRequest = {
  email: string;
};

export type ForgotPasswordResponse = {
  success: boolean;
};

export type ResetPasswordByTokenRequest = {
  token: string;
  new_password: string;
};

export type ResetPasswordByTokenResponse = {
  success: boolean;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: UserResponse;
};

// ── History ──
export type AssessmentCardItem = {
  id: string;
  company_name: string;
  industry: string;
  company_size: string;
  has_profile: boolean;
  has_report: boolean;
  created_at: string;
  updated_at: string;
};

export type AssessmentListResponse = {
  items: AssessmentCardItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

// ── BMC 三维突破要素评分类型 ──

export const BMC_MODULES = [
  { key: "customer_segments", title: "客户细分", abbr: "CS", category: "market" },
  { key: "value_propositions", title: "价值主张", abbr: "VP", category: "market" },
  { key: "channels", title: "渠道通路", abbr: "CH", category: "market" },
  { key: "customer_relationships", title: "客户关系", abbr: "CR", category: "market" },
  { key: "revenue_streams", title: "收入来源", abbr: "R$", category: "market" },
  { key: "key_resources", title: "核心资源", abbr: "KR", category: "efficiency" },
  { key: "key_activities", title: "关键业务", abbr: "KA", category: "efficiency" },
  { key: "key_partnerships", title: "重要合作", abbr: "KP", category: "efficiency" },
  { key: "cost_structure", title: "成本结构", abbr: "C$", category: "efficiency" },
] as const;

export type BmcModuleKey = (typeof BMC_MODULES)[number]["key"];

export type ModuleScoreInput = {
  key: string;
  pain: number;
  data: number;
  feasibility: number;
};

export type BmcScoringZone = "quickwin" | "strategic" | "longterm" | "hold" | "blocked";

export type ModuleScoringResult = {
  key: string;
  title: string;
  abbr: string;
  category: string;
  pain: number;
  data: number;
  feasibility: number;
  raw_score: number;
  normalized_score: number;
  zone: BmcScoringZone;
  veto_status: string;
  veto_reason: string | null;
  recommendation_level: string;
  recommendation_label: string;
  recommendation_stars: string;
};

export type BmcScoringResult = {
  assessment_id: string;
  module_results: ModuleScoringResult[];
  top_3_keys: string[];
  top_3_results: ModuleScoringResult[];
  complementarity_warning: string | null;
};

export type BmcScoringSaveRequest = {
  selected_keys: string[];
  all_module_scores: ModuleScoreInput[];
  selection_mode: "bmc_scoring" | "manual";
};

export type BmcScoringResponse = {
  assessment_id: string;
  scoring_result: BmcScoringResult | null;
  selected_keys: string[];
  created_at: string | null;
  updated_at: string | null;
};

export type AutoDeriveResponse = {
  modules: ModuleScoreInput[];
  derived_from_canvas: boolean;
};

// Chat types
export type ChatMessageOut = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string | null;
};

export type ConversationOut = {
  id: string;
  assessment_id: string;
  title: string;
  messages: ChatMessageOut[];
  created_at: string | null;
};
