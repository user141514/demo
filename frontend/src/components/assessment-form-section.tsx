"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useCreateAssessment } from "@/hooks";
import { toast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type {
  AssessmentCreateRequest,
  AssessmentResponse,
  IntakeFieldMeta,
} from "@/lib/types";
import {
  initialForm,
  companySizeOptions,
  revenueOptions,
} from "@/lib/assessment-utils";
import { getIntakeFieldNote } from "@/lib/intake-utils";

/**
 * 渲染正式问卷表单，并在导入缺失字段上显示补充提醒。
 */
export function AssessmentFormSection({
  assessmentId,
  prefillSummary,
  prefillError,
  prefillFieldMeta,
  form: externalForm,
  onFormChange,
  assessment,
  onReset,
}: {
  assessmentId?: string;
  prefillSummary?: { importSessionId: string; mappedCount: number } | null;
  prefillError?: string | null;
  prefillFieldMeta?: Partial<Record<keyof AssessmentCreateRequest, IntakeFieldMeta>> | null;
  form: AssessmentCreateRequest;
  onFormChange: (key: keyof AssessmentCreateRequest, value: string) => void;
  assessment: AssessmentResponse | null;
  onReset: () => void;
}) {
  const router = useRouter();
  const createAssessment = useCreateAssessment();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const missingFieldNote = "系统未识别，请手动补充";

  const answeredCount = Object.values(externalForm).filter(
    (value) => typeof value === "string" && value.trim().length > 0,
  ).length;

  const hasUnsavedChanges = !assessmentId && answeredCount > 0;

  /**
   * 读取导入字段的提醒状态，供表单项统一使用。
   */
  function getFieldPresentation(
    key: keyof AssessmentCreateRequest,
    value: string | null | undefined,
    required = false,
  ) {
    const meta = prefillFieldMeta?.[key];
    const isEmptyValue = (value ?? "").trim().length === 0;
    const needsUserInput = required && isEmptyValue;
    return {
      note: needsUserInput
        ? missingFieldNote
        : meta
          ? getIntakeFieldNote(meta.status)
          : null,
      needsUserInput,
      fieldClassName: needsUserInput
        ? "border-destructive focus:border-destructive focus:ring-[rgba(220,38,38,0.12)]"
        : undefined,
    };
  }

  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [hasUnsavedChanges]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);

    // Client-side validation
    const formEl = event.currentTarget;
    if (!formEl.checkValidity()) {
      formEl.reportValidity();
      return;
    }

    try {
      const result = await createAssessment.mutateAsync({
        ...externalForm,
        notes: (externalForm.notes ?? "").trim() || null,
      });
      toast({ title: "问卷已创建", description: `ID: ${result.id}`, variant: "success" });
      router.push(`/assessment/${result.id}`);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "问卷提交失败，请稍后重试。");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="section-label">问卷录入</p>
          <h2 className="section-heading">企业问卷录入</h2>
          {assessment ? (
            <p className="mt-2 text-sm text-muted-foreground">
              当前 Assessment ID：{assessment.id}
            </p>
          ) : null}
        </div>
        <Badge variant="accent">已填写 {answeredCount} / 11 项</Badge>
      </div>

      {prefillSummary ? (
        <div className="mt-4 rounded-xl msg-info p-4 text-sm">
          已从前置材料带入 {prefillSummary.mappedCount} / 11 个字段。
          缺失项可以继续在当前问卷补充，不会阻塞提交。
        </div>
      ) : null}

      {prefillError ? (
        <div className="mt-4 rounded-xl msg-error p-4 text-sm">{prefillError}</div>
      ) : null}

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <Field label="企业名称" required note={getFieldPresentation("company_name", externalForm.company_name, true).note} noteDanger={getFieldPresentation("company_name", externalForm.company_name, true).needsUserInput}>
          <input
            required
            value={externalForm.company_name}
            onChange={(e) => onFormChange("company_name", e.target.value)}
            className={`input-field ${getFieldPresentation("company_name", externalForm.company_name, true).fieldClassName ?? ""}`}
            placeholder="例如：某某制造科技有限公司"
          />
        </Field>
        <Field label="所属行业" required note={getFieldPresentation("industry", externalForm.industry, true).note} noteDanger={getFieldPresentation("industry", externalForm.industry, true).needsUserInput}>
          <input
            required
            value={externalForm.industry}
            onChange={(e) => onFormChange("industry", e.target.value)}
            className={`input-field ${getFieldPresentation("industry", externalForm.industry, true).fieldClassName ?? ""}`}
            placeholder="例如：装备制造 / 医疗器械 / 连锁零售"
          />
        </Field>
        <Field label="企业规模" required note={getFieldPresentation("company_size", externalForm.company_size, true).note} noteDanger={getFieldPresentation("company_size", externalForm.company_size, true).needsUserInput}>
          <select
            required
            value={externalForm.company_size}
            onChange={(e) => onFormChange("company_size", e.target.value)}
            className={`input-field ${getFieldPresentation("company_size", externalForm.company_size, true).fieldClassName ?? ""}`}
          >
            <option value="">请选择企业规模</option>
            {companySizeOptions.map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
        </Field>
        <Field label="所在区域" required note={getFieldPresentation("region", externalForm.region, true).note} noteDanger={getFieldPresentation("region", externalForm.region, true).needsUserInput}>
          <input
            required
            value={externalForm.region}
            onChange={(e) => onFormChange("region", e.target.value)}
            className={`input-field ${getFieldPresentation("region", externalForm.region, true).fieldClassName ?? ""}`}
            placeholder="例如：上海 / 苏州 / 深圳"
          />
        </Field>
        <Field label="年营收范围" required note={getFieldPresentation("annual_revenue_range", externalForm.annual_revenue_range, true).note} noteDanger={getFieldPresentation("annual_revenue_range", externalForm.annual_revenue_range, true).needsUserInput}>
          <select
            required
            value={externalForm.annual_revenue_range}
            onChange={(e) => onFormChange("annual_revenue_range", e.target.value)}
            className={`input-field ${getFieldPresentation("annual_revenue_range", externalForm.annual_revenue_range, true).fieldClassName ?? ""}`}
          >
            <option value="">请选择年营收范围</option>
            {revenueOptions.map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
        </Field>
        <Field label="可用数据/系统基础" required note={getFieldPresentation("available_data", externalForm.available_data, true).note} noteDanger={getFieldPresentation("available_data", externalForm.available_data, true).needsUserInput}>
          <textarea
            required
            value={externalForm.available_data}
            onChange={(e) => onFormChange("available_data", e.target.value)}
            className={`input-field ${getFieldPresentation("available_data", externalForm.available_data, true).fieldClassName ?? ""}`}
            placeholder="例如：ERP、CRM、生产报工、客服记录、Excel 台账等"
          />
        </Field>
      </div>

      <div className="mt-6 grid gap-6">
        <Field label="核心产品/服务" required note={getFieldPresentation("core_products", externalForm.core_products, true).note} noteDanger={getFieldPresentation("core_products", externalForm.core_products, true).needsUserInput}>
          <textarea
            required
            value={externalForm.core_products}
            onChange={(e) => onFormChange("core_products", e.target.value)}
            className={`input-field ${getFieldPresentation("core_products", externalForm.core_products, true).fieldClassName ?? ""}`}
            placeholder="请描述当前主要产品、服务或解决方案"
          />
        </Field>
        <Field label="目标客户" required note={getFieldPresentation("target_customers", externalForm.target_customers, true).note} noteDanger={getFieldPresentation("target_customers", externalForm.target_customers, true).needsUserInput}>
          <textarea
            required
            value={externalForm.target_customers}
            onChange={(e) => onFormChange("target_customers", e.target.value)}
            className={`input-field ${getFieldPresentation("target_customers", externalForm.target_customers, true).fieldClassName ?? ""}`}
            placeholder="例如：大型制造企业、连锁门店总部、区域经销商等"
          />
        </Field>
        <Field label="当前经营/管理挑战" required note={getFieldPresentation("current_challenges", externalForm.current_challenges, true).note} noteDanger={getFieldPresentation("current_challenges", externalForm.current_challenges, true).needsUserInput}>
          <textarea
            required
            value={externalForm.current_challenges}
            onChange={(e) => onFormChange("current_challenges", e.target.value)}
            className={`input-field ${getFieldPresentation("current_challenges", externalForm.current_challenges, true).fieldClassName ?? ""}`}
            placeholder="例如：销售线索跟进低效、订单交付波动、客服响应慢、数据分散"
          />
        </Field>
        <Field label="希望通过 AI 达成的目标" required note={getFieldPresentation("ai_goals", externalForm.ai_goals, true).note} noteDanger={getFieldPresentation("ai_goals", externalForm.ai_goals, true).needsUserInput}>
          <textarea
            required
            value={externalForm.ai_goals}
            onChange={(e) => onFormChange("ai_goals", e.target.value)}
            className={`input-field ${getFieldPresentation("ai_goals", externalForm.ai_goals, true).fieldClassName ?? ""}`}
            placeholder="例如：提升销售转化、优化排产、减少客服重复劳动、沉淀知识库"
          />
        </Field>
        <Field label="补充说明" note={getFieldPresentation("notes", externalForm.notes ?? "").note} noteDanger={false}>
          <textarea
            value={externalForm.notes ?? ""}
            onChange={(e) => onFormChange("notes", e.target.value)}
            className="input-field"
            placeholder="选填：补充战略方向、组织现状、预算约束、负责人等"
          />
        </Field>
      </div>

      {submitError ? (
        <div className="mt-6 rounded-xl msg-error p-4 text-sm">{submitError}</div>
      ) : null}

      <div className="mt-6 flex flex-wrap gap-3">
        <Button type="submit" disabled={createAssessment.isPending} loading={createAssessment.isPending}>
          {createAssessment.isPending
            ? "提交中..."
            : assessmentId
              ? "另存为新问卷"
              : "提交企业问卷"}
        </Button>
        <Button type="button" variant="outline" onClick={onReset}>
          {assessmentId ? "新建空白问卷" : "清空问卷"}
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  required,
  note,
  noteDanger,
  children,
}: {
  label: string;
  required?: boolean;
  note?: string | null;
  noteDanger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-2 text-sm">
      <span className="flex flex-wrap items-center gap-2 font-medium">
        <span>
          {label}
          {required ? <span className="ml-1 text-destructive">*</span> : null}
        </span>
        {note ? (
          <span className={noteDanger ? "text-destructive text-xs" : "text-muted-foreground text-xs"}>
            {note}
          </span>
        ) : null}
      </span>
      {children}
    </label>
  );
}
