import type { AssessmentProgress } from "@/lib/types";

export type AssessmentWorkflowKey =
  | "profile"
  | "canvas"
  | "breakthrough"
  | "directions"
  | "scenarios"
  | "competitiveness"
  | "endgame";

export type WorkflowDisplayState =
  | "done"
  | "available"
  | "locked"
  | "pending-review";

export type WorkflowActionState = {
  key: AssessmentWorkflowKey;
  label: string;
  state: WorkflowDisplayState;
  disabled: boolean;
  hasResult: boolean;
};

export type WorkflowResultState = {
  key: AssessmentWorkflowKey;
  label: string;
  state: WorkflowDisplayState;
  statusLabel: string;
  done: boolean;
  isNavigable: boolean;
};

type WorkflowStateInput = {
  assessmentId?: string;
  hasAssessment: boolean;
  hasProfile: boolean;
  hasCanvas: boolean;
  hasBreakthroughSelection: boolean;
  hasDirectionDraft: boolean;
  hasDirectionSelection: boolean;
  hasScenarios: boolean;
  scenarioCount: number;
  hasCompetitiveness: boolean;
  hasEndgame: boolean;
  progress: AssessmentProgress;
  profileMode: "mock" | "live" | null;
};

/**
 * 统一推导工作台操作区与结果区的链路状态，避免两处各自计算而出现不同步。
 */
export function buildAssessmentWorkflowState(
  input: WorkflowStateInput,
): {
  actionModules: WorkflowActionState[];
  resultCards: WorkflowResultState[];
} {
  const labels: Record<AssessmentWorkflowKey, string> = {
    profile: "企业画像",
    canvas: "商业画布 9 格",
    breakthrough: "BMC 突破要素评分",
    directions: "创新方向延展",
    scenarios: "Top 3 AI 场景推荐",
    competitiveness: "差异化竞争力分析",
    endgame: "核心竞争力推进策略",
  };

  const profileDone =
    input.hasAssessment && (input.progress.has_profile || input.hasProfile);
  const canvasDone =
    profileDone && (input.progress.has_canvas || input.hasCanvas);
  const breakthroughDone =
    canvasDone &&
    (input.progress.has_breakthrough || input.hasBreakthroughSelection);
  const directionsDone =
    breakthroughDone &&
    (input.progress.has_directions || input.hasDirectionSelection);
  const directionsPendingReview =
    breakthroughDone && !directionsDone && input.hasDirectionDraft;
  const scenariosDone =
    directionsDone && (input.progress.has_scenarios || input.hasScenarios);
  const competitivenessDone =
    scenariosDone &&
    (input.progress.has_competitiveness || input.hasCompetitiveness);
  const endgameDone = competitivenessDone && input.hasEndgame;

  const states: Record<AssessmentWorkflowKey, WorkflowResultState> = {
    profile: {
      key: "profile",
      label: labels.profile,
      state: profileDone ? "done" : input.hasAssessment ? "available" : "locked",
      statusLabel: profileDone
        ? input.profileMode === "live"
          ? "真实生成"
          : "已生成"
        : "待生成",
      done: profileDone,
      isNavigable: profileDone,
    },
    canvas: {
      key: "canvas",
      label: labels.canvas,
      state: canvasDone ? "done" : profileDone ? "available" : "locked",
      statusLabel: canvasDone ? "已生成" : "待生成",
      done: canvasDone,
      isNavigable: canvasDone,
    },
    breakthrough: {
      key: "breakthrough",
      label: labels.breakthrough,
      state: breakthroughDone ? "done" : canvasDone ? "available" : "locked",
      statusLabel: breakthroughDone ? "已确认" : canvasDone ? "待确认" : "待生成",
      done: breakthroughDone,
      isNavigable: canvasDone,
    },
    directions: {
      key: "directions",
      label: labels.directions,
      state: directionsDone
        ? "done"
        : directionsPendingReview
          ? "pending-review"
          : breakthroughDone
            ? "available"
            : "locked",
      statusLabel: directionsDone
        ? "已生成"
        : directionsPendingReview
          ? "待确认"
          : breakthroughDone
            ? "待生成"
            : "待生成",
      done: directionsDone,
      isNavigable: directionsDone || directionsPendingReview,
    },
    scenarios: {
      key: "scenarios",
      label: labels.scenarios,
      state: scenariosDone ? "done" : directionsDone ? "available" : "locked",
      statusLabel: scenariosDone
        ? `Top ${input.scenarioCount || 3}`
        : "待生成",
      done: scenariosDone,
      isNavigable: scenariosDone,
    },
    competitiveness: {
      key: "competitiveness",
      label: labels.competitiveness,
      state: competitivenessDone
        ? "done"
        : scenariosDone
          ? "available"
          : "locked",
      statusLabel: competitivenessDone ? "已生成" : "待生成",
      done: competitivenessDone,
      isNavigable: competitivenessDone,
    },
    endgame: {
      key: "endgame",
      label: labels.endgame,
      state: endgameDone ? "done" : competitivenessDone ? "available" : "locked",
      statusLabel: endgameDone ? "已生成" : "待生成",
      done: endgameDone,
      isNavigable: endgameDone,
    },
  };

  const orderedKeys: AssessmentWorkflowKey[] = [
    "profile",
    "canvas",
    "breakthrough",
    "directions",
    "scenarios",
    "competitiveness",
    "endgame",
  ];

  return {
    actionModules: orderedKeys.map((key) => ({
      key,
      label: labels[key],
      state: states[key].state,
      disabled: states[key].state === "locked",
      hasResult: states[key].done,
    })),
    resultCards: orderedKeys.map((key) => states[key]),
  };
}
