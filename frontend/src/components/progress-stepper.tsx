"use client";

import React, { useEffect, useRef } from "react";
import type { AssessmentProgress } from "@/lib/types";

const stepLabels = [
  "企业问卷",
  "企业画像",
  "商业画布",
  "BMC 评分",
  "方向延展",
  "场景推荐",
  "竞争力",
  "推进策略",
  "报告预览",
];

const stepSectionIds = [
  "section-assessment-form",
  "section-profile-results",
  "section-canvas-grid",
  "section-breakthrough",
  "section-directions",
  "section-scenarios",
  "section-competitiveness",
  "section-endgame",
  "section-report",
];

export function ProgressStepper({
  hasAssessment,
  progress,
  activeStep,
}: {
  hasAssessment: boolean;
  progress: AssessmentProgress;
  /** 1-indexed step number currently being generated (shows pulse animation) */
  activeStep?: number | null;
}) {
  const statuses: Array<"completed" | "active" | "pending"> = [
    hasAssessment ? "completed" : "active",
    progress.has_profile ? "completed" : hasAssessment ? "active" : "pending",
    progress.has_canvas ? "completed" : progress.has_profile ? "active" : "pending",
    progress.has_breakthrough ? "completed" : progress.has_canvas ? "active" : "pending",
    progress.has_directions ? "completed" : progress.has_breakthrough ? "active" : "pending",
    progress.has_scenarios ? "completed" : progress.has_directions ? "active" : "pending",
    progress.has_competitiveness ? "completed" : progress.has_scenarios ? "active" : "pending",
    (progress as any).has_endgame ? "completed" : progress.has_competitiveness ? "active" : "pending",
    progress.has_report ? "completed" : progress.ready_for_report ? "active" : "pending",
  ];

  // Override with explicitly active step (for generation-in-progress pulse)
  const activeIdx = activeStep != null ? activeStep - 1 : null;

  const scrollToSection = (index: number) => {
    const id = stepSectionIds[index];
    const el = document.getElementById(id);
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="flex flex-col gap-0">
      {/* Horizontal stepper on md+ */}
      <div className="hidden md:flex md:items-start md:justify-between md:gap-0">
        {stepLabels.map((label, index) => {
          const step = index + 1;
          const status = activeIdx === index ? "active" : statuses[index];
          const isClickable = status === "completed";
          const isActive = status === "active";

          return (
            <React.Fragment key={label}>
              {/* Step dot + label */}
              <button
                type="button"
                disabled={!isClickable}
                onClick={() => isClickable && scrollToSection(index)}
                className={`stepper-step flex flex-col items-center gap-2 flex-1 min-w-0 group ${
                  isClickable ? "cursor-pointer" : "cursor-default"
                }`}
              >
                {/* Dot with connecting line container */}
                <div className="stepper-dot-row">
                  <span
                    className={`stepper-dot ${
                      status === "completed"
                        ? `stepper-dot-done step-done-${step}`
                        : isActive
                          ? `stepper-dot-active step-current-${step}`
                          : "stepper-dot-pending"
                    }`}
                  >
                    {status === "completed" ? (
                      <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    ) : (
                      <span className="text-[10px] font-bold" aria-hidden="true">{step}</span>
                    )}
                  </span>
                </div>
                <span
                  className={`text-center text-xs font-medium leading-tight transition-colors ${
                    status === "completed"
                      ? `step-${step}-color`
                      : isActive
                        ? `step-${step}-color font-semibold`
                        : "text-muted-foreground"
                  }`}
                >
                  {label}
                </span>
              </button>

              {/* Connecting line between steps */}
              {index < stepLabels.length - 1 && (
                <div className="stepper-connector-wrapper">
                  <div
                    className={`stepper-connector ${
                      statuses[index] === "completed" ? "stepper-connector-done" : ""
                    }`}
                  />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Vertical stepper on small screens */}
      <div className="md:hidden flex flex-col gap-0">
        {stepLabels.map((label, index) => {
          const step = index + 1;
          const status = activeIdx === index ? "active" : statuses[index];
          const isClickable = status === "completed";
          const isActive = status === "active";
          const isLast = index === stepLabels.length - 1;

          return (
            <button
              key={label}
              type="button"
              disabled={!isClickable}
              onClick={() => isClickable && scrollToSection(index)}
              className={`stepper-vertical-row ${
                isClickable ? "cursor-pointer" : "cursor-default"
              }`}
            >
              {/* Vertical dot + line */}
              <div className="stepper-vertical-track">
                <span
                  className={`stepper-dot ${
                    status === "completed"
                      ? `stepper-dot-done step-done-${step}`
                      : isActive
                        ? `stepper-dot-active step-current-${step}`
                        : "stepper-dot-pending"
                  }`}
                >
                  {status === "completed" ? (
                    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : (
                    <span className="text-[10px] font-bold" aria-hidden="true">{step}</span>
                  )}
                </span>
                {!isLast && (
                  <div
                    className={`stepper-vertical-line ${
                      status === "completed" ? "stepper-connector-done" : ""
                    }`}
                  />
                )}
              </div>

              <div className="flex flex-col items-start py-1">
                <span
                  className={`text-sm font-medium ${
                    status === "completed"
                      ? `step-${step}-color`
                      : isActive
                        ? `step-${step}-color font-semibold`
                        : "text-muted-foreground"
                  }`}
                >
                  {label}
                </span>
                {isActive && (
                  <span className="text-xs text-muted-foreground animate-pulse">
                    进行中...
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
