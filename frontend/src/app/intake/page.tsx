"use client";

import Link from "next/link";

import { IntakeWorkspace } from "@/components/intake-workspace";
import { AuthGuard } from "@/components/auth-guard";

function IntakeContent() {
  return (
    <div className="min-h-screen px-6 py-10">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 stagger">
        <section className="page-header">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-4xl space-y-4">
              <Link href="/" className="btn-secondary text-xs">
                ← 返回首页
              </Link>
              <span className="badge badge-accent">
                前置输入 / 导入预填 / 人工确认
              </span>
              <h1 className="font-heading text-4xl font-bold tracking-tight text-warm-text">
                前置材料导入工作台
              </h1>
              <p className="text-base leading-7 text-warm-secondary sm:text-lg">
                通过文本或 Markdown 导入企业前置材料，系统会直接带入确认表单，供你补充并创建正式问卷。
              </p>
            </div>

            <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-6 py-4 text-sm text-amber-800">
              <p className="font-medium">当前阶段范围</p>
              <p className="mt-2 text-amber-700/90">
                当前页面用于验证导入、人工补充与确认创建问卷的完整闭环。
              </p>
            </div>
          </div>
        </section>

        <IntakeWorkspace />
      </div>
    </div>
  );
}

export default function IntakePage() {
  return (
    <AuthGuard>
      <IntakeContent />
    </AuthGuard>
  );
}
