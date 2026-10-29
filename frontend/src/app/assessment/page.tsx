"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { AssessmentWorkspace } from "@/components/assessment-workspace";
import { AuthGuard } from "@/components/auth-guard";
import { InstructorDashboard } from "@/components/instructor-dashboard";
import { useAuth } from "@/providers/auth-provider";

function AssessmentPageContent() {
  const { isInstructor } = useAuth();
  const [tab, setTab] = useState<"student" | "instructor">("student");
  const searchParams = useSearchParams();
  const prefillSessionId =
    searchParams.get("import_session_id")?.trim() || undefined;
  const companyName = searchParams.get("company_name")?.trim() || undefined;

  useEffect(() => {
    if (!isInstructor && tab !== "student") {
      setTab("student");
    }
  }, [isInstructor, tab]);

  const activeTab = isInstructor ? tab : "student";

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 stagger">
        <section className="page-header">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-4xl space-y-4">
              <Link href="/" className="btn-secondary text-xs">
                返回首页
              </Link>
              <span className="badge badge-accent">
                主流程工作台 / 企业画像 / 商业画布 / AI 场景 / 报告
              </span>
              <h1 className="font-heading text-4xl font-bold tracking-tight text-warm-text">
                {activeTab === "student" ? "主流程工作台" : "管理员工作台"}
              </h1>
              <p className="text-base leading-7 text-warm-secondary sm:text-lg">
                {activeTab === "student"
                  ? "导入前置材料或直接填写企业问卷，确认后继续生成企业画像、商业画布、场景推荐和报告。"
                  : "管理员账户可查看全体学员进展，按班级筛选，并批量提交管理员点评。"}
              </p>
              {activeTab === "student" ? (
                <p className="text-sm text-warm-muted">
                  前置材料导入功能已集成在工作台中，展开即可使用。
                </p>
              ) : null}
            </div>

            {isInstructor ? (
              <div className="flex items-center gap-1 rounded-full border border-warm-border bg-warm-inset p-1">
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === "student"}
                  aria-current={tab === "student" ? "page" : undefined}
                  onClick={() => setTab("student")}
                  className={`rounded-full px-6 py-2 text-sm font-medium transition ${
                    tab === "student"
                      ? "bg-warm-accent text-white shadow-sm"
                      : "text-warm-muted hover:text-warm-text"
                  }`}
                >
                  学员视角
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={tab === "instructor"}
                  aria-current={tab === "instructor" ? "page" : undefined}
                  onClick={() => setTab("instructor")}
                  className={`rounded-full px-6 py-2 text-sm font-medium transition ${
                    tab === "instructor"
                      ? "bg-warm-accent text-white shadow-sm"
                      : "text-warm-muted hover:text-warm-text"
                  }`}
                >
                  管理员视角
                </button>
              </div>
            ) : null}
          </div>
        </section>

        {activeTab === "student" ? (
          <AssessmentWorkspace
            key={`${prefillSessionId ?? ""}:${companyName ?? ""}`}
            prefillSessionId={prefillSessionId}
            companyName={companyName}
          />
        ) : (
          <InstructorDashboard />
        )}
      </div>
    </main>
  );
}

function AssessmentPageFallback() {
  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 stagger">
        <section className="page-header">
          <div className="max-w-4xl space-y-4">
            <Link href="/" className="btn-secondary text-xs">
              返回首页
            </Link>
            <span className="badge badge-accent">
              主流程工作台 / 企业画像 / 商业画布 / AI 场景 / 报告
            </span>
            <h1 className="font-heading text-4xl font-bold tracking-tight text-warm-text">
              主流程工作台
            </h1>
            <p className="text-base leading-7 text-warm-secondary sm:text-lg">
              正在加载主流程工作台与前置材料预填信息...
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}

export default function AssessmentPage() {
  return (
    <AuthGuard>
      <Suspense fallback={<AssessmentPageFallback />}>
        <AssessmentPageContent />
      </Suspense>
    </AuthGuard>
  );
}
