"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  ApiError,
  createAssessmentFromIntake,
  getIntakeImportSession,
  importAssessmentIntake,
  importAssessmentIntakeFile,
} from "@/lib/api";
import type {
  AssessmentCreateRequest,
  IntakeSessionDetailResponse,
  IntakeSourceType,
} from "@/lib/types";

const intakeFieldDefinitions: Array<{
  key: keyof AssessmentCreateRequest;
  label: string;
  inputType: "input" | "textarea";
  required?: boolean;
}> = [
  { key: "company_name", label: "企业名称", inputType: "input", required: true },
  { key: "industry", label: "所属行业", inputType: "input", required: true },
  { key: "company_size", label: "企业规模", inputType: "input", required: true },
  { key: "region", label: "所在区域", inputType: "input", required: true },
  { key: "annual_revenue_range", label: "年营收范围", inputType: "input", required: true },
  { key: "core_products", label: "核心产品/服务", inputType: "textarea", required: true },
  { key: "target_customers", label: "目标客户", inputType: "textarea", required: true },
  { key: "current_challenges", label: "当前经营/管理挑战", inputType: "textarea", required: true },
  { key: "ai_goals", label: "希望通过 AI 达成的目标", inputType: "textarea", required: true },
  { key: "available_data", label: "当前可用数据/系统基础", inputType: "textarea", required: true },
  { key: "notes", label: "其他补充说明", inputType: "textarea" },
];

const sourceTypeLabels: Record<IntakeSourceType, string> = {
  text: "纯文本",
  markdown: "Markdown",
  form: "结构化表单",
  file: "文件上传",
};

const maxUploadSizeBytes = 10 * 1024 * 1024;
const allowedUploadExtensions = [".txt", ".md", ".markdown", ".pdf", ".docx"];

type UploadStage = "idle" | "validating" | "uploading" | "parsing" | "completed";

const emptyConfirmedForm: AssessmentCreateRequest = {
  company_name: "",
  industry: "",
  company_size: "",
  region: "",
  annual_revenue_range: "",
  core_products: "",
  target_customers: "",
  current_challenges: "",
  ai_goals: "",
  available_data: "",
  notes: "",
};

export function IntakeWorkbench() {
  const router = useRouter();
  const [sourceType, setSourceType] = useState<IntakeSourceType>("markdown");
  const [rawContent, setRawContent] = useState(`企业名称：测试连锁零售企业
所属行业：零售
企业规模：100-499人
所在区域：华东
核心产品/服务：社区零售门店、会员运营与到家服务
目标客户：社区家庭用户、周边白领与会员客户
希望通过 AI 达成的目标：提升门店运营效率，增强会员复购
当前可用数据/系统基础：POS、会员系统、商品主数据`);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [selectedUploadFile, setSelectedUploadFile] = useState<File | null>(null);
  const [sessionIdInput, setSessionIdInput] = useState("");
  const [sessionDetail, setSessionDetail] = useState<IntakeSessionDetailResponse | null>(null);
  const [confirmedForm, setConfirmedForm] = useState<AssessmentCreateRequest>(emptyConfirmedForm);
  const [structuredFields, setStructuredFields] = useState<AssessmentCreateRequest>(emptyConfirmedForm);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [isLoadingSession, setIsLoadingSession] = useState(false);
  const [isCreatingAssessment, setIsCreatingAssessment] = useState(false);
  const [uploadStage, setUploadStage] = useState<UploadStage>("idle");
  const [importSuccessMsg, setImportSuccessMsg] = useState<string | null>(null);
  const [showSessionRecall, setShowSessionRecall] = useState(false);
  const prefillRef = useRef<HTMLDivElement>(null);

  const completedCount = useMemo(() => {
    if (!sessionDetail) return 0;
    return intakeFieldDefinitions.filter(({ key }) => {
      const value = sessionDetail.assessment_prefill[key];
      return typeof value === "string" && value.trim().length > 0;
    }).length;
  }, [sessionDetail]);

  const confirmedCount = useMemo(() => {
    return intakeFieldDefinitions.filter(({ key }) => {
      const value = confirmedForm[key];
      return typeof value === "string" && value.trim().length > 0;
    }).length;
  }, [confirmedForm]);

  const modifiedCount = useMemo(() => {
    if (!sessionDetail) return 0;
    const originalPrefill = buildConfirmedForm(sessionDetail);
    return intakeFieldDefinitions.filter(({ key }) =>
      normalizeFieldValue(confirmedForm[key]) !== normalizeFieldValue(originalPrefill[key]),
    ).length;
  }, [confirmedForm, sessionDetail]);

  // 导入成功后自动滚动到预填结果区域
  useEffect(() => {
    if (sessionDetail && prefillRef.current) {
      prefillRef.current.scrollIntoView?.({ behavior: "smooth", block: "start" });
      setImportSuccessMsg(`导入完成，已识别 ${completedCount} / ${intakeFieldDefinitions.length} 个字段`);
      const timer = setTimeout(() => setImportSuccessMsg(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [sessionDetail]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadSessionDetail(importSessionId: string) {
    setLoadError(null);
    setCreateError(null);
    setIsLoadingSession(true);
    try {
      const detail = await getIntakeImportSession(importSessionId);
      setSessionDetail(detail);
      setConfirmedForm(buildConfirmedForm(detail));
      setStructuredFields({ ...emptyConfirmedForm, ...detail.structured_fields });
      setRawContent(detail.raw_content ?? "");
      setSelectedFileName(detail.source_file?.name ?? null);
      setSelectedUploadFile(null);
      setSourceType(detail.source_type);
      setSessionIdInput(detail.import_session_id);
      setUploadStage(detail.source_type === "file" ? "completed" : "idle");
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "导入会话加载失败，请稍后重试。");
    } finally {
      setIsLoadingSession(false);
    }
  }

  async function handleImport(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setImportError(null);
    setLoadError(null);
    setCreateError(null);

    if (sourceType === "file" && !selectedUploadFile) {
      setImportError("请选择一个 txt、md、pdf 或 docx 文件后再导入。");
      return;
    }
    if (sourceType === "form" && Object.keys(buildStructuredFieldPayload(structuredFields)).length === 0) {
      setImportError("结构化表单至少需要填写 1 个字段。");
      return;
    }

    setIsImporting(true);
    try {
      let imported;
      if (sourceType === "file" && selectedUploadFile) {
        setUploadStage("uploading");
        imported = await importAssessmentIntakeFile(selectedUploadFile);
        setUploadStage("parsing");
      } else {
        imported = await importAssessmentIntake({
          source_type: sourceType,
          raw_content: sourceType === "form" ? null : rawContent,
          structured_fields: sourceType === "form" ? buildStructuredFieldPayload(structuredFields) : undefined,
        });
      }
      await loadSessionDetail(imported.import_session_id);
    } catch (error) {
      setUploadStage("idle");
      setImportError(formatImportError(error));
    } finally {
      setIsImporting(false);
    }
  }

  async function handleLoadExistingSession() {
    if (!sessionIdInput.trim()) {
      setLoadError("请输入导入会话 ID。");
      return;
    }
    await loadSessionDetail(sessionIdInput.trim());
  }

  async function handleFileSelect(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const validationError = validateUploadFile(file);
    if (validationError) {
      setSelectedUploadFile(null);
      setSelectedFileName(null);
      setUploadStage("idle");
      setImportError(validationError);
      event.target.value = "";
      return;
    }
    setSelectedUploadFile(file);
    setSelectedFileName(file.name);
    setImportError(null);
    setSourceType("file");
    setUploadStage("validating");
    event.target.value = "";
  }

  function handleSourceTypeChange(nextSourceType: IntakeSourceType) {
    if (sourceType === "file" && nextSourceType !== "file" && selectedUploadFile) {
      if (!window.confirm("切换输入类型将清除已选择的文件，是否继续？")) return;
    }
    setSourceType(nextSourceType);
    setImportError(null);
    if (nextSourceType !== "file") {
      setSelectedUploadFile(null);
      setSelectedFileName(null);
      setUploadStage("idle");
    }
  }

  function updateStructuredField(key: keyof AssessmentCreateRequest, value: string) {
    setStructuredFields((current) => ({ ...current, [key]: value }));
  }

  function updateConfirmedField(key: keyof AssessmentCreateRequest, value: string) {
    setConfirmedForm((current) => ({ ...current, [key]: value }));
  }

  function handleContinueToAssessment() {
    if (!sessionDetail) return;

    if (sessionDetail.created_assessment_id) {
      router.push(`/assessment/${sessionDetail.created_assessment_id}`);
      return;
    }

    router.push(`/assessment?import_session_id=${encodeURIComponent(sessionDetail.import_session_id)}`);
  }

  async function handleCreateAssessment(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sessionDetail) {
      setCreateError("请先完成导入或加载一个导入会话。");
      return;
    }
    if (sessionDetail.created_assessment_id) {
      router.push(`/assessment/${sessionDetail.created_assessment_id}`);
      return;
    }
    setCreateError(null);
    setIsCreatingAssessment(true);
    try {
      const created = await createAssessmentFromIntake(sessionDetail.import_session_id, {
        confirmed_assessment_input: { ...confirmedForm, notes: (confirmedForm.notes ?? "").trim() || null },
      });
      setSessionDetail((current) =>
        current ? { ...current, status: created.status, created_assessment_id: created.assessment.id } : current,
      );
      router.push(`/assessment/${created.assessment.id}`);
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "创建问卷失败，请稍后重试。");
    } finally {
      setIsCreatingAssessment(false);
    }
  }

  return (
    <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
      {/* Left column */}
      <div className="flex flex-col gap-6">
        {/* Import card */}
        <div className="card">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="section-label">步骤一</p>
              <h2 className="section-heading">前置材料导入</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-warm-secondary">
                先粘贴前置收集的文本或 Markdown，生成问卷预填建议；
                确认并补充信息后即可创建企业问卷。
              </p>
            </div>
            <Link href="/assessment" className="btn-secondary text-xs">
              切回快速填写
            </Link>
          </div>

          <form onSubmit={handleImport} className="mt-6 space-y-5">
            <label className="flex flex-col gap-2 text-sm text-warm-text">
              <span className="font-medium">输入类型</span>
              <select
                value={sourceType}
                onChange={(event) => handleSourceTypeChange(event.target.value as IntakeSourceType)}
                className="input-field"
              >
                {Object.entries(sourceTypeLabels).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </label>

            {sourceType === "form" ? (
              <div className="space-y-4">
                <div className="rounded-xl border border-warm-border-light bg-warm-inset p-4 text-sm text-warm-secondary">
                  可先填写已有字段，未填项会在下一步继续补充确认。
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  {intakeFieldDefinitions.map(({ key, label, inputType }) => (
                    <label key={key} className="flex flex-col gap-2 text-sm text-warm-text">
                      <span className="font-medium">{label}</span>
                      {inputType === "textarea" ? (
                        <textarea
                          value={structuredFields[key] ?? ""}
                          onChange={(event) => updateStructuredField(key, event.target.value)}
                          className="input-field min-h-[120px]"
                          placeholder={`请输入${label}`}
                        />
                      ) : (
                        <input
                          value={structuredFields[key] ?? ""}
                          onChange={(event) => updateStructuredField(key, event.target.value)}
                          className="input-field"
                          placeholder={`请输入${label}`}
                        />
                      )}
                    </label>
                  ))}
                </div>
              </div>
            ) : sourceType === "file" ? (
              <label className="flex flex-col gap-2 text-sm text-warm-text">
                <span className="font-medium">上传文件</span>
                <div className="flex flex-wrap items-center gap-3 rounded-xl border border-dashed border-warm-border bg-warm-inset px-4 py-4">
                  <label className="btn-secondary cursor-pointer text-xs">
                    选择 txt / md / pdf / docx 文件
                    <input
                      type="file"
                      accept=".txt,.md,.markdown,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      className="sr-only"
                      onChange={handleFileSelect}
                    />
                  </label>
                  <span className="text-sm text-warm-muted">
                    {selectedFileName ? `待上传文件：${selectedFileName}` : "服务端会提取文件文本后生成预填建议"}
                  </span>
                </div>
                <div className="rounded-xl border border-warm-border-light bg-warm-surface p-4 text-sm text-warm-secondary">
                  <p>上传限制：支持 {allowedUploadExtensions.join(" / ")}，单文件最大 {formatFileSize(maxUploadSizeBytes)}。</p>
                  <p className="mt-2">
                    当前状态：{getUploadStageLabel(uploadStage)}
                    {sourceType === "file" && isImporting ? "，请稍候" : ""}
                  </p>
                </div>
              </label>
            ) : (
              <label className="flex flex-col gap-2 text-sm text-warm-text">
                <span className="font-medium">原始材料</span>
                <textarea
                  value={rawContent}
                  onChange={(event) => setRawContent(event.target.value)}
                  className="input-field min-h-[220px]"
                  rows={14}
                  placeholder="请粘贴企业前置输入、会议纪要或 Markdown 摘要"
                />
              </label>
            )}

            {importError ? <div className="rounded-xl msg-error p-4 text-sm">{importError}</div> : null}

            <div className="flex flex-wrap gap-3">
              <button type="submit" disabled={isImporting || isLoadingSession} className="btn-primary">
                {isImporting && sourceType === "file"
                  ? getUploadStageButtonLabel(uploadStage)
                  : isImporting || isLoadingSession
                    ? "正在提交并解析..."
                    : "导入并生成预填建议"}
              </button>
            </div>
          </form>
        </div>

        {/* Session recall — collapsible */}
        <div className="card-inset">
          <button
            type="button"
            onClick={() => setShowSessionRecall((prev) => !prev)}
            className="flex w-full items-center justify-between text-left"
          >
            <div>
              <p className="section-label">辅助功能</p>
              <h2 className="section-heading">回看导入会话</h2>
            </div>
            <span className="text-sm text-warm-muted transition-transform" style={{ transform: showSessionRecall ? "rotate(90deg)" : "rotate(0deg)" }}>
              ▶
            </span>
          </button>

          {showSessionRecall && (
            <div className="mt-4">
              <p className="text-sm leading-6 text-warm-secondary">
                输入 import_session_id 可重新加载导入结果和已确认表单，方便刷新后继续处理。
              </p>

              <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                <input
                  value={sessionIdInput}
                  onChange={(event) => setSessionIdInput(event.target.value)}
                  className="input-field flex-1"
                  placeholder="请输入 import_session_id"
                />
                <button
                  type="button"
                  onClick={handleLoadExistingSession}
                  disabled={isLoadingSession}
                  className="btn-secondary"
                >
                  {isLoadingSession ? "加载中..." : "加载会话"}
                </button>
              </div>

              {loadError ? <div className="mt-4 rounded-xl msg-error p-4 text-sm">{loadError}</div> : null}
              {sessionDetail ? (
                <div className="mt-5 space-y-2 text-sm text-warm-secondary">
                  <p>会话 ID：{sessionDetail.import_session_id}</p>
                  <p>状态：{sessionDetail.status}</p>
                  <p>来源类型：{sourceTypeLabels[sessionDetail.source_type]}</p>
                  {sessionDetail.source_file ? (
                    <p>源文件：{sessionDetail.source_file.name} ({sessionDetail.source_file.kind} / {formatFileSize(sessionDetail.source_file.size_bytes)})</p>
                  ) : null}
                  <p>已识别字段：{completedCount} / {intakeFieldDefinitions.length}</p>
                  {sessionDetail.created_assessment_id ? (
                    <p>
                      已创建问卷：
                      <Link href={`/assessment/${sessionDetail.created_assessment_id}`} className="ml-1 font-medium text-warm-accent underline underline-offset-4">
                        {sessionDetail.created_assessment_id}
                      </Link>
                    </p>
                  ) : null}
                </div>
              ) : (
                <p className="mt-4 text-sm text-warm-muted">尚未加载导入会话，导入完成后这里会显示持久化的回显结果。</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right column */}
      <div className="flex flex-col gap-6">
        {/* Confirm draft */}
        <div className="card-inset" ref={prefillRef}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="section-label">步骤二</p>
              <h2 className="section-heading">确认并创建问卷</h2>
              <p className="mt-2 text-sm leading-6 text-warm-secondary">
                你可以在这里修改系统预填建议。所有字段都允许手动覆盖；
                即使还没补齐，也可以先带入企业问卷继续补录，或直接保存当前部分结果。
              </p>
            </div>
            <span className="badge badge-accent">
              已确认 {confirmedCount} / {intakeFieldDefinitions.length} 项
            </span>
          </div>

          {importSuccessMsg ? (
            <div className="mt-4 rounded-xl msg-success p-3 text-sm">{importSuccessMsg}</div>
          ) : null}

          {sessionDetail ? (
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <span className="badge badge-success">已修改 {modifiedCount} 项</span>
              <span className="badge badge-muted">沿用建议 {intakeFieldDefinitions.length - modifiedCount} 项</span>
            </div>
          ) : null}

          {sessionDetail ? (
            <form onSubmit={handleCreateAssessment} className="mt-6 space-y-5">
              <div className="grid gap-5 md:grid-cols-2">
                {intakeFieldDefinitions.map(({ key, label, inputType, required }) => {
                  const value = confirmedForm[key] ?? "";
                  const meta = sessionDetail.field_meta[key];
                  const originalValue = buildConfirmedForm(sessionDetail)[key];
                  const isModified = normalizeFieldValue(value) !== normalizeFieldValue(originalValue);
                  const fieldNote = getFieldNote(meta?.status);
                  const needsUserInput = isFieldMissing(meta?.status);

                  return (
                    <label key={key} className="flex flex-col gap-2 text-sm text-warm-text">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">
                            {label}
                            {required ? <span className="ml-1 text-warm-accent">*</span> : null}
                          </span>
                          <span className={`badge ${isModified ? "badge-success" : "badge-muted"}`}>
                            {isModified ? "已修改" : "沿用建议"}
                          </span>
                          {isModified && (
                            <button
                              type="button"
                              onClick={() => updateConfirmedField(key, normalizeFieldValue(originalValue))}
                              className="text-xs text-warm-accent underline underline-offset-2 hover:text-warm-text"
                            >
                              恢复建议值
                            </button>
                          )}
                        </div>
                        <span
                          className={`text-xs ${
                            needsUserInput
                              ? "font-medium text-destructive"
                              : "text-warm-muted"
                          }`}
                        >
                          {fieldNote}
                        </span>
                      </div>
                      {inputType === "textarea" ? (
                        <textarea
                          value={value}
                          onChange={(event) => updateConfirmedField(key, event.target.value)}
                          className={`input-field min-h-[120px] ${
                            needsUserInput
                              ? "border-destructive focus:border-destructive focus:ring-[rgba(220,38,38,0.12)]"
                              : ""
                          }`}
                        />
                      ) : (
                        <input
                          value={value}
                          onChange={(event) => updateConfirmedField(key, event.target.value)}
                          className={`input-field ${
                            needsUserInput
                              ? "border-destructive focus:border-destructive focus:ring-[rgba(220,38,38,0.12)]"
                              : ""
                          }`}
                        />
                      )}
                    </label>
                  );
                })}
              </div>

              {createError ? <div className="rounded-xl msg-error p-4 text-sm">{createError}</div> : null}

              {sessionDetail.created_assessment_id ? (
                <div className="rounded-xl msg-info p-4 text-sm">
                  当前导入会话已创建问卷。
                  <Link href={`/assessment/${sessionDetail.created_assessment_id}`} className="ml-2 font-medium underline underline-offset-4">
                    进入已创建问卷
                  </Link>
                </div>
              ) : null}

              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={handleContinueToAssessment}
                  className="btn-secondary"
                >
                  {sessionDetail.created_assessment_id ? "进入已创建问卷" : "带入企业问卷继续补充"}
                </button>
                <button
                  type="submit"
                  disabled={isCreatingAssessment || Boolean(sessionDetail.created_assessment_id)}
                  className="btn-success"
                >
                  {isCreatingAssessment ? "创建中..." : "确认并创建问卷"}
                </button>
              </div>
            </form>
          ) : (
            <p className="mt-5 text-sm leading-6 text-warm-muted">
              请先完成导入或加载一个已有会话，系统会把预填结果带入这里供你修改确认。
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

/* ── Helpers (unchanged logic) ── */

function normalizeFieldValue(value: string | null | undefined): string {
  return (value ?? "").trim();
}

function buildConfirmedForm(detail: IntakeSessionDetailResponse): AssessmentCreateRequest {
  return {
    company_name: detail.assessment_prefill.company_name ?? "",
    industry: detail.assessment_prefill.industry ?? "",
    company_size: detail.assessment_prefill.company_size ?? "",
    region: detail.assessment_prefill.region ?? "",
    annual_revenue_range: detail.assessment_prefill.annual_revenue_range ?? "",
    core_products: detail.assessment_prefill.core_products ?? "",
    target_customers: detail.assessment_prefill.target_customers ?? "",
    current_challenges: detail.assessment_prefill.current_challenges ?? "",
    ai_goals: detail.assessment_prefill.ai_goals ?? "",
    available_data: detail.assessment_prefill.available_data ?? "",
    notes: detail.assessment_prefill.notes ?? "",
  };
}

function buildStructuredFieldPayload(
  fields: AssessmentCreateRequest,
): Partial<Record<keyof AssessmentCreateRequest, string>> {
  const entries = intakeFieldDefinitions.flatMap(({ key }) => {
    const value = normalizeFieldValue(fields[key]);
    return value ? [[key, value] as const] : [];
  });
  return Object.fromEntries(entries);
}

/**
 * 根据字段状态生成用户可读的提示文案。
 */
function getFieldNote(status?: string | null): string {
  if (status === "needs_user_confirmation") {
    return "系统推断，请重点确认";
  }
  if (status === "needs_user_input") {
    return "系统未识别，请手动补充";
  }
  return "已从原文识别";
}

/**
 * 判断字段是否需要红色补充提醒。
 */
function isFieldMissing(status?: string | null): boolean {
  return status === "needs_user_input";
}

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function validateUploadFile(file: File): string | null {
  const fileName = file.name.toLowerCase();
  const isAllowed = allowedUploadExtensions.some((ext) => fileName.endsWith(ext));
  if (!isAllowed) return "文件类型不支持，请选择 txt、md、markdown、pdf 或 docx 文件。";
  if (file.size === 0) return "上传文件为空，请重新选择。";
  if (file.size > maxUploadSizeBytes)
    return `文件过大，当前文件为 ${formatFileSize(file.size)}，请控制在 ${formatFileSize(maxUploadSizeBytes)} 以内。`;
  return null;
}

function getUploadStageLabel(stage: UploadStage): string {
  switch (stage) {
    case "validating": return "文件校验完成，等待上传";
    case "uploading": return "正在上传到后端";
    case "parsing": return "后端正在提取文本并解析";
    case "completed": return "解析完成";
    default: return "尚未开始";
  }
}

function getUploadStageButtonLabel(stage: UploadStage): string {
  switch (stage) {
    case "uploading": return "上传中...";
    case "parsing": return "解析中...";
    default: return "处理中...";
  }
}

function formatImportError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 413)
      return typeof error.message === "string" && error.message.trim()
        ? error.message
        : "上传文件超过大小限制，请压缩后重试。";
    if (error.status === 415) return "文件类型不支持，请上传 txt、md、markdown、pdf 或 docx 文件。";
    if (error.status === 422)
      return typeof error.message === "string" && error.message.trim()
        ? error.message
        : "文件解析失败，请确认内容清晰可读或改用文本粘贴。";
  }
  return error instanceof Error ? error.message : "导入解析失败，请稍后重试。";
}
