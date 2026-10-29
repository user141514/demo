"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useIntakeStore } from "@/stores/intake-store";
import { useImportIntake, useImportIntakeFile, useIntakeSession } from "@/hooks";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { toast } from "@/hooks/use-toast";
import {
  intakeFieldDefinitions,
  sourceTypeLabels,
  buildConfirmedForm,
  buildStructuredFieldPayload,
  validateUploadFile,
  formatFileSize,
  getUploadStageLabel,
  getUploadStageButtonLabel,
  formatImportError,
  allowedUploadExtensions,
  maxUploadSizeBytes,
  emptyConfirmedForm,
} from "@/lib/intake-utils";

export function IntakeImportSection({
  onImported,
}: {
  onImported?: (importSessionId: string) => void;
}) {
  const router = useRouter();
  const store = useIntakeStore();
  const importMutation = useImportIntake();
  const importFileMutation = useImportIntakeFile();
  const sessionQuery = useIntakeSession(store.importSessionId);

  const handleSourceTypeChange = useCallback(
    (nextType: string) => {
      if (store.sourceType === "file" && nextType !== "file" && store.selectedUploadFile) {
        if (!window.confirm("切换输入类型将清除已选择的文件，是否继续？")) return;
      }
      store.setSourceType(nextType as typeof store.sourceType);
    },
    [store],
  );

  const handleFileSelect = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;
      const error = validateUploadFile(file);
      if (error) {
        store.setSelectedFile(null, null);
        store.setUploadStage("idle");
        toast({ title: "文件校验失败", description: error, variant: "destructive" });
        event.target.value = "";
        return;
      }
      store.setSelectedFile(file, file.name);
      store.setUploadStage("validating");
      event.target.value = "";
    },
    [store],
  );

  const handleImport = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      if (store.sourceType === "file" && !store.selectedUploadFile) {
        toast({ title: "请选择文件", description: "请选择一个 txt、md、pdf 或 docx 文件后再导入。", variant: "destructive" });
        return;
      }
      if (store.sourceType === "form" && Object.keys(buildStructuredFieldPayload(store.structuredFields ?? emptyConfirmedForm)).length === 0) {
        toast({ title: "请填写字段", description: "结构化表单至少需要填写 1 个字段。", variant: "destructive" });
        return;
      }

      store.setIsImporting(true);
      try {
        let result: { import_session_id: string; created_assessment_id?: string | null };
        if (store.sourceType === "file" && store.selectedUploadFile) {
          store.setUploadStage("uploading");
          result = await importFileMutation.mutateAsync(store.selectedUploadFile);
          store.setUploadStage("parsing");
        } else {
          result = await importMutation.mutateAsync({
            sourceType: store.sourceType,
            rawContent: store.sourceType === "form" ? null : store.rawContent,
            structuredFields: store.sourceType === "form" ? buildStructuredFieldPayload(store.structuredFields ?? emptyConfirmedForm) : undefined,
          });
        }
        store.setImportSessionId(result.import_session_id);
        onImported?.(result.import_session_id);
        store.setUploadStage("completed");

        // Auto-redirect if assessment was auto-created
        if (result.created_assessment_id) {
          toast({ title: "导入完成", description: "正在跳转到主流程工作台...", variant: "success" });
          router.push(`/assessment/${result.created_assessment_id}`);
          return;
        }
      } catch (error) {
        store.setUploadStage("idle");
        toast({ title: "导入失败", description: formatImportError(error), variant: "destructive" });
      } finally {
        store.setIsImporting(false);
      }
    },
    [store, importMutation, importFileMutation, onImported],
  );

  const isPending = importMutation.isPending || importFileMutation.isPending;

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="section-label">步骤一</p>
          <h2 className="section-heading">前置材料导入</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            先粘贴前置收集的文本或 Markdown，生成问卷预填建议；
            确认并补充信息后即可创建企业问卷。
          </p>
        </div>
        {!onImported ? (
          <Button variant="outline" size="sm" onClick={() => router.push("/assessment")}>
            切回快速填写
          </Button>
        ) : null}
      </div>

      <form onSubmit={handleImport} className="mt-6 space-y-6">
        <label className="flex flex-col gap-3 text-sm">
          <span className="font-medium">输入类型</span>
          <select
            value={store.sourceType}
            onChange={(e) => handleSourceTypeChange(e.target.value)}
            className="input-field"
          >
            {Object.entries(sourceTypeLabels).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </label>

        {store.sourceType === "form" ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-border bg-secondary p-6 text-sm leading-relaxed text-muted-foreground">
              可先填写已有字段，未填项会在下一步继续补充确认。
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {intakeFieldDefinitions.map(({ key, label, inputType }) => (
                <label key={key} className="flex flex-col gap-3 text-sm">
                  <span className="font-medium">{label}</span>
                  {inputType === "textarea" ? (
                    <Textarea
                      value={store.structuredFields?.[key] ?? ""}
                      onChange={(e) => store.updateStructuredField(key, e.target.value)}
                      placeholder={`请输入${label}`}
                    />
                  ) : (
                    <Input
                      value={store.structuredFields?.[key] ?? ""}
                      onChange={(e) => store.updateStructuredField(key, e.target.value)}
                      placeholder={`请输入${label}`}
                    />
                  )}
                </label>
              ))}
            </div>
          </div>
        ) : store.sourceType === "file" ? (
          <label className="flex flex-col gap-3 text-sm">
            <span className="font-medium">上传文件</span>
            <div className="flex flex-wrap items-center gap-4 rounded-xl border border-dashed border-border bg-secondary px-6 py-6">
              <label className="cursor-pointer text-xs">
                <span className="btn-secondary text-xs">
                  选择 txt / md / pdf / docx 文件
                </span>
                <input
                  type="file"
                  accept=".txt,.md,.markdown,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  className="sr-only"
                  onChange={handleFileSelect}
                />
              </label>
              <span className="text-sm text-muted-foreground">
                {store.selectedFileName ? `待上传文件：${store.selectedFileName}` : "服务端会提取文件文本后生成预填建议"}
              </span>
            </div>
            <div className="rounded-xl border border-border bg-secondary p-6 text-sm leading-relaxed text-muted-foreground">
              <p>上传限制：支持 {allowedUploadExtensions.join(" / ")}，单文件最大 {formatFileSize(maxUploadSizeBytes)}。</p>
              <p className="mt-2">
                当前状态：{getUploadStageLabel(store.uploadStage)}
                {store.sourceType === "file" && isPending ? "，请稍候" : ""}
              </p>
              {isPending && store.sourceType === "file" && (
                <Progress value={store.uploadStage === "uploading" ? 33 : store.uploadStage === "parsing" ? 66 : 0} className="mt-3" />
              )}
            </div>
          </label>
        ) : (
          <label className="flex flex-col gap-3 text-sm">
            <span className="font-medium">原始材料</span>
            <Textarea
              value={store.rawContent}
              onChange={(e) => store.setRawContent(e.target.value)}
              placeholder="请粘贴企业前置输入、会议纪要或 Markdown 摘要"
              className="min-h-[220px]"
              rows={14}
            />
          </label>
        )}

        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={isPending} loading={isPending}>
            {isPending && store.sourceType === "file"
              ? getUploadStageButtonLabel(store.uploadStage)
              : isPending
                ? "正在提交并解析..."
                : "导入并生成预填建议"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
