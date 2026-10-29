import React from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Mock } from "vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ResultsDashboardPageContent } from "@/components/results-dashboard-page-content";

const useAssessmentDetailMock = vi.fn();

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/hooks", () => ({
  useAssessmentDetail: (...args: unknown[]) => useAssessmentDetailMock(...args),
}));

vi.mock("@/components/business-canvas-grid", () => ({
  BusinessCanvasGrid: () => <div>Canvas grid ready</div>,
}));

vi.mock("@/components/competitiveness-panel", () => ({
  CompetitivenessPanel: () => <div>Competitiveness ready</div>,
}));

vi.mock("@/components/endgame-panel", () => ({
  EndgamePanel: () => <div>Endgame ready</div>,
}));

vi.mock("@/components/sync-feedback-panel", () => ({
  SyncFeedbackPanel: () => null,
}));

vi.mock("@/app/assessment/[assessmentId]/results/report-export-actions", () => ({
  ReportExportActions: ({
    initialReportId,
  }: {
    initialReportId?: string | null;
  }) => <div>Export actions {initialReportId ?? "none"}</div>,
}));

function renderWithQueryClient(node: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>{node}</QueryClientProvider>,
  );
}

describe("ResultsDashboardPageContent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders point-line-surface content from assessment detail data", () => {
    (useAssessmentDetailMock as Mock).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      data: {
        assessment: {
          id: "assessment-1",
          company_name: "Test Retail",
          industry: "Retail",
        },
        company_profile: null,
        canvas_diagnosis: {
          generation_mode: "mock",
          overall_score: 85,
          weakest_blocks: [],
          recommended_focus: [],
          canvas: {
            overall_summary: "Summary",
            blocks: [],
          },
          created_at: null,
          updated_at: null,
        },
        breakthrough_selection: [
          "value_propositions",
          "customer_relationships",
          "key_resources",
        ],
        direction_expansion: null,
        direction_selection: {
          assessment_id: "assessment-1",
          generation_mode: "rule_based",
          created_at: null,
          updated_at: null,
          selected_directions: [
            {
              direction_id: "direction-1",
              element_key: "value_propositions",
              title: "Membership AI",
              description: "Personalized member experience",
              expected_impact: "Increase retention",
              data_needed: [],
              related_scenario_categories: [],
            },
            {
              direction_id: "direction-2",
              element_key: "key_resources",
              title: "Unified Data Platform",
              description: "Connect store and member data",
              expected_impact: "Improve decision speed",
              data_needed: [],
              related_scenario_categories: [],
            },
          ],
        },
        scenario_recommendation: {
          scoring_method: "rule_based_v1",
          evaluated_count: 3,
          top_scenarios: [
            {
              scenario_id: "scenario-1",
              name: "Store Copilot",
              category: "Operations",
              summary: "Assist frontline staff with fast answers",
              canvas_elements: "Key activities",
              expected_effects: "Reduce training time",
              core_data_requirements: "Docs",
            },
          ],
          created_at: null,
          updated_at: null,
        },
        competitiveness: {
          assessment_id: "assessment-1",
          result: {
            generation_mode: "rule_based",
            vp_reconstruction: {
              current_vp: "Current",
              enhanced_vp: "Enhanced",
              differentiation_points: [],
              customer_value_shift: "Shift",
            },
            connections: [],
            advantages: [],
            delivery_strategy: {
              phase_1_quick_win: "QW",
              phase_2_scale: "Scale",
              phase_3_moat: "Moat",
              key_risks: [],
            },
            overall_narrative: "Narrative",
          },
          created_at: null,
          updated_at: null,
        },
        endgame: {
          assessment_id: "assessment-1",
          result: {
            generation_mode: "rule_based",
            industry_essence: "Essence",
            private_domain: {
              current_state: "",
              target_model: "",
              key_strategies: [],
              customer_retention_loop: "",
              revenue_impact: "",
            },
            ecosystem: {
              ecosystem_positioning: "",
              key_partners_to_engage: [],
              orchestration_strategy: "",
              platform_effect: "",
            },
            opc: {
              operations_excellence: "",
              platform_capability: "",
              content_and_community: "",
              data_flywheel_effect: "",
            },
            three_stage_strategy: {
              stage_1: {
                title: "",
                focus: "",
                strategy: "",
                objective: "",
                key_actions: [],
                key_risks: [],
              },
              stage_2: {
                title: "",
                focus: "",
                strategy: "",
                objective: "",
                key_actions: [],
                key_risks: [],
              },
              stage_3: {
                title: "",
                focus: "",
                strategy: "",
                objective: "",
                key_actions: [],
                key_risks: [],
              },
              key_risks: [],
            },
            strategic_paths: [],
            overall_narrative: "Endgame",
          },
          created_at: null,
          updated_at: null,
        },
        case_recommendation: null,
        generated_report: {
          report_id: "report-1",
          assessment_id: "assessment-1",
          title: "Report",
          created_at: null,
          updated_at: null,
        },
        progress: {
          has_profile: true,
          has_canvas: true,
          has_breakthrough: true,
          has_directions: true,
          has_competitiveness: true,
          has_endgame: true,
          has_scenarios: true,
          has_report: true,
          ready_for_report: true,
        },
      },
    });

    renderWithQueryClient(
      <ResultsDashboardPageContent assessmentId="assessment-1" />,
    );

    expect(
      screen.getByRole("heading", { name: "Test Retail AI 商业创新评估" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Canvas grid ready")).toBeInTheDocument();
    expect(screen.getByText("价值主张")).toBeInTheDocument();
    expect(screen.getByText("Membership AI｜Personalized member experience")).toBeInTheDocument();
    expect(screen.getByText("Store Copilot")).toBeInTheDocument();
    expect(screen.getByText("Assist frontline staff with fast answers")).toBeInTheDocument();
    expect(screen.getByText("Reduce training time。")).toBeInTheDocument();
    expect(screen.getByText("Competitiveness ready")).toBeInTheDocument();
    expect(screen.getByText("Endgame ready")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "差异化竞争力报告" }).previousElementSibling,
    ).toHaveTextContent("线");
    expect(
      screen.getByRole("heading", { name: "核心竞争力推进策略" }).previousElementSibling,
    ).toHaveTextContent("面");
    expect(screen.getByText("Export actions report-1")).toBeInTheDocument();
    expect(screen.queryByText("无结果")).not.toBeInTheDocument();
  });

  it("removes repeated scenario summary setup text from the results dashboard", () => {
    const repeatedSetup =
      "围绕“客户数据平台与智能分群推荐引擎、基于位置的个性化触达引擎、AI驱动的供应商发现与匹配引擎”，结合“关键资源、渠道通路、关键合作伙伴”";

    (useAssessmentDetailMock as Mock).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      data: {
        assessment: {
          id: "assessment-1",
          company_name: "Test Retail",
          industry: "Retail",
        },
        company_profile: null,
        canvas_diagnosis: null,
        breakthrough_selection: [],
        direction_expansion: null,
        direction_selection: null,
        scenario_recommendation: {
          scoring_method: "rule_based_v1",
          evaluated_count: 3,
          top_scenarios: [
            {
              scenario_id: "scenario-1",
              name: "回款风险预警",
              category: "财务经营",
              summary: `${repeatedSetup}，在财务经营环节布局“回款风险预警”，对账期异常、逾期概率和重点客户回款风险进行监控与预警。`,
              canvas_elements: "关键资源",
              expected_effects: "降低逾期回款比例",
              core_data_requirements: "客户账期数据",
            },
            {
              scenario_id: "scenario-2",
              name: "销售线索优先级排序",
              category: "销售增长",
              summary: `${repeatedSetup}；在销售增长环节布局“销售线索优先级排序”，基于线索来源、跟进行为和成交历史，对销售线索进行优先级排序。`,
              canvas_elements: "渠道通路",
              expected_effects: "提升销售转化效率",
              core_data_requirements: "销售线索数据",
            },
            {
              scenario_id: "scenario-3",
              name: "门店销量预测",
              category: "零售运营",
              summary: `${repeatedSetup}。在零售运营环节布局“门店销量预测”，对门店或区域销量进行预测。`,
              canvas_elements: "关键合作伙伴",
              expected_effects: "优化库存周转",
              core_data_requirements: "门店销售数据",
            },
          ],
          created_at: null,
          updated_at: null,
        },
        competitiveness: null,
        endgame: null,
        case_recommendation: null,
        generated_report: null,
        progress: {
          has_profile: true,
          has_canvas: true,
          has_breakthrough: true,
          has_directions: true,
          has_competitiveness: false,
          has_endgame: false,
          has_scenarios: true,
          has_report: false,
          ready_for_report: false,
        },
      },
    });

    renderWithQueryClient(
      <ResultsDashboardPageContent assessmentId="assessment-1" />,
    );

    expect(
      screen.queryByText((content) => content.includes(repeatedSetup)),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "在财务经营环节布局“回款风险预警”，对账期异常、逾期概率和重点客户回款风险进行监控与预警。",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "在销售增长环节布局“销售线索优先级排序”，基于线索来源、跟进行为和成交历史，对销售线索进行优先级排序。",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("在零售运营环节布局“门店销量预测”，对门店或区域销量进行预测。"),
    ).toBeInTheDocument();
  });
});
