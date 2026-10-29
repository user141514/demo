import type {
  AssessmentBreakthroughResponse,
  AssessmentCanvasResponse,
  AssessmentCaseResponse,
  AssessmentCreateRequest,
  AssessmentDetailResponse,
  AssessmentDirectionResponse,
  AssessmentProfileResponse,
  AssessmentResponse,
  AssessmentScenarioRecommendationResponse,
  ScenarioPoolUpdateRequest,
  BreakthroughSelectionRequest,
  BreakthroughSelectionResponse,
  CompetitivenessResponse,
  UpdateCompetitivenessPayload,
  DirectionSelectionRequest,
  DirectionSelectionResponse,
  IntakeCreateAssessmentRequest,
  IntakeCreateAssessmentResponse,
  IntakeImportRequest,
  IntakeImportResponse,
  IntakeSessionDetailResponse,
  ReportContextResponse,
  ReportDocumentResponse,
  ReportEnrichmentResult,
  EndgameResponse,
  UpdateEndgamePayload,
  OverallQualityReport,
  FollowUpPlan,
  FollowUpTaskItem,
  TaskUpdateRequest,
  PushCycleResult,
  RecalibratePlanRequest,
  InstructorDashboardResponse,
  BatchCommentResponse,
  TokenResponse,
  RegisterRequest,
  LoginRequest,
  ForgotPasswordQuestionRequest,
  ForgotPasswordQuestionResponse,
  ResetPasswordRequest,
  ResetPasswordResponse,
  ForgotPasswordRequest,
  ForgotPasswordResponse,
  ResetPasswordByTokenRequest,
  ResetPasswordByTokenResponse,
  SetupRecoveryRequest,
  SetupRecoveryResponse,
  UpdateRecoveryRequest,
  UpdateRecoveryResponse,
  UserResponse,
  AssessmentListResponse,
  CreateInstructorRequest,
  AssessmentEntitlementResponse,
  PaymentNotifyResponse,
  PaymentOrderCreateRequest,
  PaymentOrderResponse,
} from "@/lib/types";

export function resolveApiBaseUrl(value: string | undefined): string {
  const normalized = (value ?? "").trim();
  return normalized.replace(/\/+$/, "");
}

export const apiBaseUrl = resolveApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);

function getAuthHeaders(): Record<string, string> {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("auth_token");
    if (token) return { Authorization: `Bearer ${token}` };
  }
  return {};
}

export async function postChatMessage(
  assessmentId: string,
  payload: { message: string; files?: File[]; current_page?: string },
  init?: { signal?: AbortSignal },
): Promise<Response> {
  const hasFiles = Boolean(payload.files && payload.files.length > 0);
  const headers: Record<string, string> = {
    "ngrok-skip-browser-warning": "true",
    ...getAuthHeaders(),
  };

  let body: BodyInit;
  if (hasFiles) {
    const formData = new FormData();
    formData.append("message", payload.message);
    if (payload.current_page) {
      formData.append("current_page", payload.current_page);
    }
    for (const file of payload.files ?? []) {
      formData.append("files", file);
    }
    body = formData;
  } else {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify({ message: payload.message, current_page: payload.current_page });
  }

  const response = await fetch(`${apiBaseUrl}/api/assessments/${assessmentId}/chat`, {
    method: "POST",
    cache: "no-store",
    headers,
    body,
    signal: init?.signal,
  });

  if (!response.ok) {
    const text = await response.text();
    let detail: unknown = text;
    let message = text || `HTTP ${response.status}`;

    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      detail = parsed.detail ?? parsed;
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        message = parsed.detail;
      }
    } catch {
      // keep raw response body
    }

    throw new ApiError(message, response.status, detail);
  }

  return response;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseErrorResponse(response: Response): Promise<ApiError> {
  const text = await response.text();
  let detail: unknown = text;
  let message = text || `HTTP ${response.status}`;

  try {
    const payload = JSON.parse(text) as { detail?: unknown };
    detail = payload.detail ?? payload;
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      message = payload.detail;
    } else if (
      payload.detail &&
      typeof payload.detail === "object" &&
      "message" in payload.detail &&
      typeof (payload.detail as { message?: unknown }).message === "string"
    ) {
      message = (payload.detail as { message: string }).message;
    }
  } catch {
    // Keep raw text when response is not JSON.
  }

  return new ApiError(message, response.status, detail);
}

export async function request<T>(
  path: string,
  init?: RequestInit & { signal?: AbortSignal },
  maxRetries = 2,
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const isFormData = init?.body instanceof FormData;
      const response = await fetch(`${apiBaseUrl}${path}`, {
        cache: "no-store",
        ...init,
        headers: {
          ...(isFormData ? {} : { "Content-Type": "application/json" }),
          "ngrok-skip-browser-warning": "true",
          ...getAuthHeaders(),
          ...(init?.headers ?? {}),
        },
      });

      if (!response.ok) {
        const apiError = await parseErrorResponse(response);

        if (response.status >= 500 && attempt < maxRetries) {
          lastError = apiError;
          await new Promise((r) => setTimeout(r, (attempt + 1) * 800));
          continue;
        }

        throw apiError;
      }

      if (response.status === 204) {
        return undefined as T;
      }

      const raw = await response.text();
      if (!raw.trim()) {
        return undefined as T;
      }

      return JSON.parse(raw) as T;
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      if (attempt < maxRetries) {
        lastError = error;
        await new Promise((r) => setTimeout(r, (attempt + 1) * 800));
        continue;
      }
      throw new ApiError(
        error instanceof TypeError ? "网络连接失败，请检查后端服务是否启动。" : String(error),
        0,
      );
    }
  }

  throw lastError;
}

async function requestBlob(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "ngrok-skip-browser-warning": "true",
      ...getAuthHeaders(),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw await parseErrorResponse(response);
  }

  return response;
}

export function createAssessment(
  payload: AssessmentCreateRequest,
): Promise<AssessmentResponse> {
  return request<AssessmentResponse>("/api/assessments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function importAssessmentIntake(
  payload: IntakeImportRequest,
): Promise<IntakeImportResponse> {
  return request<IntakeImportResponse>("/api/intake/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function importAssessmentIntakeFile(
  file: File,
): Promise<IntakeImportResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return request<IntakeImportResponse>("/api/intake/import/file", {
    method: "POST",
    body: formData,
  });
}

export function getIntakeImportSession(
  importSessionId: string,
): Promise<IntakeSessionDetailResponse> {
  return request<IntakeSessionDetailResponse>(
    `/api/intake/import/${importSessionId}`,
  );
}

export function createAssessmentFromIntake(
  importSessionId: string,
  payload: IntakeCreateAssessmentRequest,
): Promise<IntakeCreateAssessmentResponse> {
  return request<IntakeCreateAssessmentResponse>(
    `/api/intake/import/${importSessionId}/assessment`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function getAssessmentDetail(
  assessmentId: string,
): Promise<AssessmentDetailResponse> {
  return request<AssessmentDetailResponse>(`/api/assessments/${assessmentId}`);
}

export function getAssessmentEntitlement(
  assessmentId: string,
): Promise<AssessmentEntitlementResponse> {
  return request<AssessmentEntitlementResponse>(
    `/api/assessments/${assessmentId}/entitlement`,
  );
}

export function createPaymentOrder(
  assessmentId: string,
  payload: PaymentOrderCreateRequest,
): Promise<PaymentOrderResponse> {
  return request<PaymentOrderResponse>(
    `/api/assessments/${assessmentId}/payments/orders`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function getPaymentOrder(orderId: string): Promise<PaymentOrderResponse> {
  return request<PaymentOrderResponse>(`/api/payments/orders/${orderId}`);
}

export function completeMockPaymentOrder(
  order: PaymentOrderResponse,
): Promise<PaymentNotifyResponse> {
  if (order.provider === "wechat") {
    return request<PaymentNotifyResponse>("/api/payments/wechat/notify", {
      method: "POST",
      body: JSON.stringify({
        out_trade_no: order.order_no,
        transaction_id: `mock-${order.order_no}`,
        trade_state: "SUCCESS",
        total_amount_cents: order.amount_cents,
      }),
    });
  }

  return request<PaymentNotifyResponse>("/api/payments/alipay/notify", {
    method: "POST",
    body: JSON.stringify({
      out_trade_no: order.order_no,
      trade_no: `mock-${order.order_no}`,
      trade_status: "TRADE_SUCCESS",
      total_amount_cents: order.amount_cents,
    }),
  });
}

export function getReportContext(
  assessmentId: string,
): Promise<ReportContextResponse> {
  return request<ReportContextResponse>(
    `/api/assessments/${assessmentId}/report-context`,
  );
}

export function generateAssessmentProfile(
  assessmentId: string,
): Promise<AssessmentProfileResponse> {
  return request<AssessmentProfileResponse>(
    `/api/assessments/${assessmentId}/profile`,
    { method: "POST" },
  );
}

export function generateAssessmentCanvas(
  assessmentId: string,
): Promise<AssessmentCanvasResponse> {
  return request<AssessmentCanvasResponse>(
    `/api/assessments/${assessmentId}/canvas`,
    { method: "POST" },
  );
}

export type UpdateCanvasPayload = {
  overall_summary: string;
  blocks: {
    key: string;
    title: string;
    current_state: string;
    diagnosis: string;
    ai_opportunity: string;
  }[];
};

export function updateAssessmentCanvas(
  assessmentId: string,
  payload: UpdateCanvasPayload,
): Promise<AssessmentCanvasResponse> {
  return request<AssessmentCanvasResponse>(
    `/api/assessments/${assessmentId}/canvas`,
    { method: "PUT", body: JSON.stringify(payload) },
  );
}

export function generateScenarioRecommendations(
  assessmentId: string,
): Promise<AssessmentScenarioRecommendationResponse> {
  return request<AssessmentScenarioRecommendationResponse>(
    `/api/assessments/${assessmentId}/scenarios`,
    { method: "POST" },
  );
}

export function updateScenarioPool(
  assessmentId: string,
  payload: ScenarioPoolUpdateRequest,
): Promise<AssessmentScenarioRecommendationResponse> {
  return request<AssessmentScenarioRecommendationResponse>(
    `/api/assessments/${assessmentId}/scenarios/pool`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

export function saveTop3Scenarios(
  assessmentId: string,
  selectedScenarioIds: string[],
): Promise<AssessmentScenarioRecommendationResponse> {
  return request<AssessmentScenarioRecommendationResponse>(
    `/api/assessments/${assessmentId}/scenarios/top3`,
    {
      method: "PUT",
      body: JSON.stringify({ selected_scenario_ids: selectedScenarioIds }),
    },
  );
}

export function generateCaseRecommendations(
  assessmentId: string,
): Promise<AssessmentCaseResponse> {
  return request<AssessmentCaseResponse>(
    `/api/assessments/${assessmentId}/cases`,
    { method: "POST" },
  );
}

export function generateAssessmentReport(
  assessmentId: string,
  mode: "template" | "llm" = "template",
): Promise<ReportDocumentResponse> {
  return request<ReportDocumentResponse>(
    `/api/assessments/${assessmentId}/report?mode=${mode}`,
    { method: "POST" },
  );
}

export function getReport(reportId: string): Promise<ReportDocumentResponse> {
  return request<ReportDocumentResponse>(`/api/reports/${reportId}`);
}

export function getReportMarkdownExportUrl(reportId: string): string {
  return `${apiBaseUrl}/api/reports/${reportId}/export/markdown`;
}

export function getReportDocxExportUrl(reportId: string): string {
  return `${apiBaseUrl}/api/reports/${reportId}/export/docx`;
}

export function getReportPrintUrl(reportId: string): string {
  return `${apiBaseUrl}/api/reports/${reportId}/print`;
}

export function recommendBreakthrough(
  assessmentId: string,
): Promise<AssessmentBreakthroughResponse> {
  return request<AssessmentBreakthroughResponse>(
    `/api/assessments/${assessmentId}/breakthrough/recommend`,
    { method: "POST" },
  );
}

export function selectBreakthrough(
  assessmentId: string,
  payload: BreakthroughSelectionRequest,
): Promise<BreakthroughSelectionResponse> {
  return request<BreakthroughSelectionResponse>(
    `/api/assessments/${assessmentId}/breakthrough/select`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function getBreakthrough(
  assessmentId: string,
): Promise<AssessmentBreakthroughResponse> {
  return request<AssessmentBreakthroughResponse>(
    `/api/assessments/${assessmentId}/breakthrough`,
  );
}

// ── BMC 三维评分 ──

export function calculateBMCScoring(
  assessmentId: string,
  payload: { modules: import("@/lib/types").ModuleScoreInput[] },
): Promise<import("@/lib/types").BmcScoringResult> {
  return request<import("@/lib/types").BmcScoringResult>(
    `/api/assessments/${assessmentId}/bmc-scoring/calculate`,
    { method: "POST", body: JSON.stringify({ ...payload, assessment_id: assessmentId }) },
  );
}

export function saveBMCScoring(
  assessmentId: string,
  payload: import("@/lib/types").BmcScoringSaveRequest,
): Promise<import("@/lib/types").BmcScoringResponse> {
  return request<import("@/lib/types").BmcScoringResponse>(
    `/api/assessments/${assessmentId}/bmc-scoring/save`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function getBMCScoring(
  assessmentId: string,
): Promise<import("@/lib/types").BmcScoringResponse> {
  return request<import("@/lib/types").BmcScoringResponse>(
    `/api/assessments/${assessmentId}/bmc-scoring`,
  );
}

export function autoDeriveBMCScoring(
  assessmentId: string,
): Promise<import("@/lib/types").AutoDeriveResponse> {
  return request<import("@/lib/types").AutoDeriveResponse>(
    `/api/assessments/${assessmentId}/bmc-scoring/auto-derive`,
    { method: "POST" },
  );
}

export function expandDirections(
  assessmentId: string,
): Promise<AssessmentDirectionResponse> {
  return request<AssessmentDirectionResponse>(
    `/api/assessments/${assessmentId}/directions/expand`,
    { method: "POST" },
  );
}

export function selectDirections(
  assessmentId: string,
  payload: DirectionSelectionRequest,
): Promise<DirectionSelectionResponse> {
  return request<DirectionSelectionResponse>(
    `/api/assessments/${assessmentId}/directions/select`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function getDirections(
  assessmentId: string,
  init?: { signal?: AbortSignal },
): Promise<AssessmentDirectionResponse> {
  return request<AssessmentDirectionResponse>(
    `/api/assessments/${assessmentId}/directions`,
    { ...init },
  );
}

export function generateCompetitiveness(
  assessmentId: string,
): Promise<CompetitivenessResponse> {
  return request<CompetitivenessResponse>(
    `/api/assessments/${assessmentId}/competitiveness/generate`,
    { method: "POST" },
  );
}

export function getCompetitiveness(
  assessmentId: string,
): Promise<CompetitivenessResponse> {
  return request<CompetitivenessResponse>(
    `/api/assessments/${assessmentId}/competitiveness`,
  );
}

export function updateCompetitiveness(
  assessmentId: string,
  payload: UpdateCompetitivenessPayload,
): Promise<CompetitivenessResponse> {
  return request<CompetitivenessResponse>(
    `/api/assessments/${assessmentId}/competitiveness`,
    { method: "PUT", body: JSON.stringify(payload) },
  );
}

export function getReportEnrichment(
  reportId: string,
): Promise<ReportEnrichmentResult> {
  return request<ReportEnrichmentResult>(
    `/api/reports/${reportId}/enrich`,
  );
}

export function createShareLink(
  reportId: string,
): Promise<{ share_url: string; token: string }> {
  return request<{ share_url: string; token: string }>(
    `/api/reports/${reportId}/share`,
    { method: "POST" },
  );
}

export function getReportPdfUrl(reportId: string): string {
  return `${apiBaseUrl}/api/reports/${reportId}/export/pdf`;
}

export type ReportExportFormat = "markdown" | "docx" | "pdf";

export function getReportExportPath(
  reportId: string,
  format: ReportExportFormat,
): string {
  return `/api/reports/${reportId}/export/${format}`;
}

function fallbackReportFilename(reportId: string, format: ReportExportFormat): string {
  const extension = format === "markdown" ? "md" : format;
  return `report-${reportId}.${extension}`;
}

function filenameFromContentDisposition(
  value: string | null,
  fallback: string,
): string {
  if (!value) return fallback;
  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1]);
  const asciiMatch = value.match(/filename="?([^";]+)"?/i);
  return asciiMatch?.[1] ?? fallback;
}

export async function downloadReportExport(
  reportId: string,
  format: ReportExportFormat,
): Promise<void> {
  const response = await requestBlob(getReportExportPath(reportId, format));
  const blob = await response.blob();
  const filename = filenameFromContentDisposition(
    response.headers.get("content-disposition"),
    fallbackReportFilename(reportId, format),
  );
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function openReportPrintPage(reportId: string): Promise<void> {
  const response = await requestBlob(`/api/reports/${reportId}/print`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener,noreferrer");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function generateEndgame(
  assessmentId: string,
): Promise<EndgameResponse> {
  return request<EndgameResponse>(
    `/api/assessments/${assessmentId}/endgame/generate`,
    { method: "POST" },
  );
}

export function getEndgame(
  assessmentId: string,
): Promise<EndgameResponse> {
  return request<EndgameResponse>(
    `/api/assessments/${assessmentId}/endgame`,
  );
}

export function updateEndgame(
  assessmentId: string,
  payload: UpdateEndgamePayload,
): Promise<EndgameResponse> {
  return request<EndgameResponse>(
    `/api/assessments/${assessmentId}/endgame`,
    { method: "PUT", body: JSON.stringify(payload) },
  );
}

export function getReportQuality(
  reportId: string,
): Promise<OverallQualityReport> {
  return request<OverallQualityReport>(
    `/api/reports/${reportId}/quality`,
  );
}

export function getFollowUpPlan(
  assessmentId: string,
): Promise<FollowUpPlan> {
  return request<FollowUpPlan>(
    `/api/assessments/${assessmentId}/follow-up`,
  );
}

export function updateFollowUpTask(
  assessmentId: string,
  taskId: string,
  payload: TaskUpdateRequest,
): Promise<FollowUpTaskItem> {
  return request<FollowUpTaskItem>(
    `/api/assessments/${assessmentId}/follow-up/tasks/${taskId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export function recalibrateFollowUp(
  assessmentId: string,
  payload: { note: string; updated_tasks: Partial<FollowUpTaskItem>[] },
): Promise<FollowUpPlan> {
  return request<FollowUpPlan>(
    `/api/assessments/${assessmentId}/follow-up/recalibrate`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function triggerCasePush(
  assessmentId: string,
): Promise<PushCycleResult> {
  return request<PushCycleResult>(
    `/api/assessments/${assessmentId}/push`,
    { method: "POST" },
  );
}

export function getPushHistory(
  assessmentId: string,
): Promise<PushCycleResult[]> {
  return request<PushCycleResult[]>(
    `/api/assessments/${assessmentId}/push/history`,
  );
}

export function recalibratePlan(
  assessmentId: string,
  payload: RecalibratePlanRequest,
): Promise<{ status: string; note: string; completed_tasks: number; new_actions: number }> {
  return request(
    `/api/assessments/${assessmentId}/recalibrate`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function getInstructorDashboard(): Promise<InstructorDashboardResponse> {
  return request<InstructorDashboardResponse>("/api/instructor/dashboard");
}

export function batchComment(
  payload: { assessment_ids: string[]; comment: string },
): Promise<BatchCommentResponse> {
  return request<BatchCommentResponse>("/api/instructor/batch-comment", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function instructorExportCsv(): Promise<{ export_format: string; content: string; student_count: number }> {
  return request("/api/instructor/export?format=csv");
}

export function createInstructor(payload: CreateInstructorRequest): Promise<UserResponse> {
  return request<UserResponse>("/api/instructor/create-instructor", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** 将 API 错误转为用户可读的中文消息，供 toast 使用 */
export function formatMutationError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return error.message;
    if (error.status === 402) {
      return error.message || "商业画布诊断免费，继续生成完整 AI 创新方案前请先解锁当前评估。";
    }
    if (error.status >= 500) return `${fallback}时后端服务异常（${error.status}），请稍后重试。`;
    if (error.status === 400) return error.message || `${fallback}失败：请求参数不合法。`;
    if (error.status === 404) return error.message || `${fallback}失败：未找到目标资源。`;
    return error.message || `${fallback}失败。`;
  }
  if (error instanceof Error) {
    if (error.message.toLowerCase().includes("timeout")) return `${fallback}超时，请稍后重试。`;
    if (error.message.toLowerCase().includes("failed to fetch") || error.message.toLowerCase().includes("network")) {
      return "网络连接失败，请检查后端服务是否启动。";
    }
    return error.message;
  }
  return fallback;
}

// ── Auth API ──
export function registerUser(payload: RegisterRequest): Promise<TokenResponse> {
  return request<TokenResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function loginUser(payload: LoginRequest): Promise<TokenResponse> {
  return request<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getForgotPasswordQuestion(
  payload: ForgotPasswordQuestionRequest,
): Promise<ForgotPasswordQuestionResponse> {
  return request<ForgotPasswordQuestionResponse>("/api/auth/forgot-password/question", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function resetPassword(
  payload: ResetPasswordRequest,
): Promise<ResetPasswordResponse> {
  return request<ResetPasswordResponse>("/api/auth/forgot-password/reset", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCurrentUser(): Promise<UserResponse> {
  return request<UserResponse>("/api/auth/me");
}

export function updateRecovery(
  payload: UpdateRecoveryRequest,
): Promise<UpdateRecoveryResponse> {
  return request<UpdateRecoveryResponse>("/api/auth/me/recovery", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function setupRecovery(
  payload: SetupRecoveryRequest,
): Promise<SetupRecoveryResponse> {
  return request<SetupRecoveryResponse>("/api/auth/setup-recovery", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function requestPasswordReset(
  payload: ForgotPasswordRequest,
): Promise<ForgotPasswordResponse> {
  return request<ForgotPasswordResponse>("/api/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function resetPasswordByToken(
  payload: ResetPasswordByTokenRequest,
): Promise<ResetPasswordByTokenResponse> {
  return request<ResetPasswordByTokenResponse>("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── History API ──
export function listMyAssessments(params?: {
  search?: string;
  date_from?: string;
  date_to?: string;
  industry?: string;
  page?: number;
  page_size?: number;
}): Promise<AssessmentListResponse> {
  const sp = new URLSearchParams();
  if (params?.search) sp.set("search", params.search);
  if (params?.date_from) sp.set("date_from", params.date_from);
  if (params?.date_to) sp.set("date_to", params.date_to);
  if (params?.industry) sp.set("industry", params.industry);
  if (params?.page) sp.set("page", String(params.page));
  if (params?.page_size) sp.set("page_size", String(params.page_size));
  const qs = sp.toString();
  return request<AssessmentListResponse>(`/api/assessments${qs ? `?${qs}` : ""}`);
}

// Chat
export async function getConversation(
  assessmentId: string,
  init?: { signal?: AbortSignal },
): Promise<import("@/lib/types").ConversationOut> {
  return request<import("@/lib/types").ConversationOut>(
    `/api/assessments/${assessmentId}/chat`,
    { ...init },
  );
}

export function clearConversation(assessmentId: string): Promise<void> {
  return request<void>(`/api/assessments/${assessmentId}/chat`, {
    method: "DELETE",
  });
}

export function deleteAssessment(assessmentId: string): Promise<void> {
  return request<void>(`/api/assessments/${assessmentId}`, {
    method: "DELETE",
  });
}
