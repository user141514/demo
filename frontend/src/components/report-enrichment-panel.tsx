"use client";

import type { ReportEnrichmentResult } from "@/lib/types";

export function ReportEnrichmentPanel({
  data,
}: {
  data: ReportEnrichmentResult;
}) {
  const { executive_summary, industry_benchmark, roi_framework, instructor_comment } = data;

  return (
    <div className="rounded-[28px] border border-white/10 bg-white/5 p-6 backdrop-blur">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.22em] text-slate-400">
            Report Enrichment
          </p>
          <h2 className="mt-3 text-2xl font-semibold text-white">
            报告增值内容
          </h2>
        </div>
      </div>

      {/* Executive Summary */}
      <div className="mt-6 rounded-3xl border border-cyan-300/20 bg-cyan-300/5 p-6">
        <p className="text-xs uppercase tracking-[0.18em] text-cyan-100">
          执行摘要
        </p>
        <p className="mt-3 text-lg font-semibold text-white">
          {executive_summary.headline}
        </p>
        <div className="mt-3 space-y-2">
          {executive_summary.key_findings.map((f, i) => (
            <p key={i} className="text-sm leading-6 text-slate-300">
              &bull; {f}
            </p>
          ))}
        </div>
        <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/50 p-4">
          <p className="text-xs font-semibold text-amber-100">Top 3 建议</p>
          <ul className="mt-2 space-y-1.5">
            {executive_summary.top_3_recommendations.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                <span className="mt-0.5 flex-shrink-0 text-cyan-300">{i + 1}.</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
        <span className="mt-3 inline-flex rounded-full bg-cyan-300/15 px-3 py-1 text-xs text-cyan-100">
          就绪度评定：{executive_summary.readiness_verdict}
        </span>
      </div>

      {/* Industry Benchmark */}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-3xl border border-white/8 bg-slate-950/55 p-6">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
            行业对标
          </p>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <MetricBox
              label="行业"
              value={industry_benchmark.industry}
            />
            <MetricBox
              label="行业均值"
              value={`${industry_benchmark.industry_avg_score}分`}
            />
            <MetricBox
              label="同规模均值"
              value={`${industry_benchmark.peer_avg_score}分`}
            />
            <MetricBox
              label="百分位排名"
              value={`前${100 - industry_benchmark.percentile_rank}%`}
            />
          </div>
        </div>
        <div className="rounded-3xl border border-white/8 bg-slate-950/55 p-6">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-400">
            对标分析
          </p>
          <div className="mt-3 space-y-3">
            <div>
              <p className="text-[11px] text-rose-200">差距</p>
              <p className="mt-1 text-sm leading-6 text-slate-400">
                {industry_benchmark.key_gap}
              </p>
            </div>
            <div>
              <p className="text-[11px] text-emerald-200">优势</p>
              <p className="mt-1 text-sm leading-6 text-slate-400">
                {industry_benchmark.advantage}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ROI Framework */}
      <div className="mt-4 rounded-3xl border border-white/8 bg-slate-950/55 p-6">
        <p className="text-xs uppercase tracking-[0.18em] text-emerald-100">
          ROI 框架
        </p>
        <p className="mt-1 text-xs text-slate-400">
          置信度: {roi_framework.confidence_level} | 时间范围: {roi_framework.roi_time_horizon}
        </p>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <RoiCard
            tier="低投入"
            tierClass="text-emerald-200 border-emerald-300/20 bg-emerald-300/5"
            items={roi_framework.low_investment_scenarios}
          />
          <RoiCard
            tier="中投入"
            tierClass="text-amber-200 border-amber-300/20 bg-amber-300/5"
            items={roi_framework.medium_investment_scenarios}
          />
          <RoiCard
            tier="高投入"
            tierClass="text-rose-200 border-rose-300/20 bg-rose-300/5"
            items={roi_framework.high_investment_scenarios}
          />
        </div>
      </div>

      {/* Instructor Comment */}
      <div className="mt-4 rounded-3xl border border-violet-300/20 bg-violet-300/5 p-6">
        <p className="text-xs uppercase tracking-[0.18em] text-violet-100">
          管理员点评 ({instructor_comment.comment_mode})
        </p>
        <p className="mt-3 text-sm leading-7 text-slate-200">
          {instructor_comment.overall_assessment}
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {instructor_comment.strength_points.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-emerald-100">优势</p>
              <ul className="mt-1.5 space-y-1">
                {instructor_comment.strength_points.map((p, i) => (
                  <li key={i} className="text-xs leading-5 text-slate-400">
                    &bull; {p}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {instructor_comment.risk_warnings.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-rose-100">风险提示</p>
              <ul className="mt-1.5 space-y-1">
                {instructor_comment.risk_warnings.map((r, i) => (
                  <li key={i} className="text-xs leading-5 text-slate-400">
                    &bull; {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        {instructor_comment.next_steps_advice && (
          <div className="mt-4">
            <p className="text-xs font-semibold text-amber-100">下一步建议</p>
            <p className="mt-1 text-sm leading-6 text-slate-300">
              {instructor_comment.next_steps_advice}
            </p>
          </div>
        )}
        {instructor_comment.recommended_reading.length > 0 && (
          <div className="mt-3">
            <p className="text-[11px] text-slate-500">推荐阅读</p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {instructor_comment.recommended_reading.map((r, i) => (
                <span
                  key={i}
                  className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] text-slate-400"
                >
                  {r}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-center">
      <p className="text-[10px] uppercase tracking-[0.15em] text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function RoiCard({
  tier,
  tierClass,
  items,
}: {
  tier: string;
  tierClass: string;
  items: { name: string; investment: string; expected_return: string }[];
}) {
  return (
    <div className={`rounded-2xl border p-4 ${tierClass}`}>
      <p className="text-xs font-semibold">{tier}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-xs text-slate-500">暂无场景</p>
      ) : (
        <ul className="mt-2 space-y-3">
          {items.map((item, i) => (
            <li key={i}>
              <p className="text-sm font-medium text-white">{item.name}</p>
              <p className="mt-1 text-xs leading-4 text-slate-400">{item.investment}</p>
              <p className="mt-1 text-xs leading-4 text-slate-300">{item.expected_return}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
