import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CompetitivenessPanel } from "@/components/competitiveness-panel";
import { EndgamePanel } from "@/components/endgame-panel";

describe("EndgamePanel", () => {
  it("renders the three-stage strategy in the endgame panel", () => {
    render(
      <EndgamePanel
        data={{
          assessment_id: "assessment-1",
          result: {
            industry_essence: "行业的本质是核心业务流程的效率与客户价值创造。",
            generation_mode: "rule_based",
            private_domain: {
              current_state: "私域基础薄弱",
              target_model: "建立统一客户经营私域",
              key_strategies: ["统一客户视图"],
              customer_retention_loop: "触点数据化 -> 分层运营 -> 价值留存",
              revenue_impact: "提升留存和复购",
            },
            ecosystem: {
              ecosystem_positioning: "连接品牌与消费者",
              key_partners_to_engage: ["品牌供应商"],
              orchestration_strategy: "围绕数据平台做协同",
              platform_effect: "更多伙伴带来更强协同",
            },
            opc: {
              operations_excellence: "建立统一运营机制",
              platform_capability: "沉淀平台能力",
              content_and_community: "建设内容与社群",
              data_flywheel_effect: "数据沉淀形成正循环",
            },
            three_stage_strategy: {
              stage_1: {
                title: "阶段 1",
                focus: "快速验证",
                strategy: "选择单一场景试点，集中资源跑通最小闭环。",
                objective: "先在单一门店验证客户分层与触达闭环。",
                key_actions: ["明确试点边界与成功标准", "组建专职小组"],
                key_risks: ["试点范围过大"],
              },
              stage_2: {
                title: "阶段 2",
                focus: "规模扩展",
                strategy: "将试点验证有效的模式复制到相邻业务单元。",
                objective: "复制到区域门店并统一运营方法。",
                key_actions: ["方法论模板化", "建立统一数据底座"],
                key_risks: ["跨部门协同不足"],
              },
              stage_3: {
                title: "阶段 3",
                focus: "壁垒构建",
                strategy: "将已验证能力沉淀为组织标准与平台能力。",
                objective: "沉淀为长期平台能力和组织标准。",
                key_actions: ["核心能力 API 化", "建立人才梯队"],
                key_risks: ["组织惯性导致创新冲突"],
              },
              key_risks: ["跨团队协同不足"],
            },
            strategic_paths: [
              {
                path_name: "稳健试点路径",
                path_type: "保守",
                execution_rhythm: "以试点验证为先，成熟后再复制扩展",
                key_milestones: ["完成试点准备"],
                capability_requirements: "优先复用现有团队与客户经营机制",
                expected_outcomes: "形成可复制样板",
                major_risks: ["推进节奏不一致"],
                recommendation_level: "推荐",
              },
            ],
            overall_narrative: "终局方向清晰。",
          },
          created_at: null,
          updated_at: null,
        }}
      />,
    );

    expect(screen.queryByText("行业商业终局判断")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "核心竞争力推进策略" })).toBeInTheDocument();
    expect(screen.queryByText("第一性原理")).not.toBeInTheDocument();
    expect(screen.queryByText("总体判断")).not.toBeInTheDocument();
    expect(screen.queryByText("终局方向清晰。")).not.toBeInTheDocument();
    expect(screen.getByText("三阶段推进策略")).toBeInTheDocument();
    expect(
      screen.getByText((content) => content.includes("阶段 1") && content.includes("快速验证")),
    ).toBeInTheDocument();
    expect(screen.getByText("先在单一门店验证客户分层与触达闭环。")).toBeInTheDocument();
    expect(screen.getByText("跨团队协同不足")).toBeInTheDocument();
    expect(screen.getAllByText("策略").length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByText("目标").length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByText("关键动作").length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByText("关键风险").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("推进节奏")).toBeInTheDocument();
    expect(screen.getByText("能力前提")).toBeInTheDocument();
  });

  it("renders the competitiveness panel with the card layout", () => {
    render(
      <CompetitivenessPanel
        data={{
          assessment_id: "assessment-1",
          result: {
            generation_mode: "rule_based",
            vp_reconstruction: {
              current_vp: "帮助门店提升经营效率",
              enhanced_vp: "通过客户经营形成差异化竞争力",
              differentiation_points: ["客户经营深化"],
              customer_value_shift: "从单点提效升级为持续经营。",
            },
            connections: [
              {
                line_name: "客户关系深化线",
                point_ids: ["direction-1"],
                point_titles: ["客户分层运营"],
                strategic_narrative: "围绕客户关系深化形成系统性能力。",
                competitive_impact: "提高复购与留存",
                key_metrics: ["复购率"],
                linkage_logic: "通过 AI 将客户分层的数据和流程打通。",
                competitive_moat: "构建基于数据的系统性优势。",
              },
            ],
            advantages: [
              {
                advantage_name: "客户经营优势",
                source_elements: ["客户关系"],
                description: "形成更强的客户经营闭环。",
                barrier_level: "高",
              },
            ],
            delivery_strategy: {
              phase_1_quick_win: "先试点",
              phase_2_scale: "再复制",
              phase_3_moat: "后沉淀",
              key_risks: ["跨团队协同不足"],
            },
            overall_narrative: "竞争力已具备向终局迁移的基础。",
          },
          created_at: null,
          updated_at: null,
        }}
        companyName="测试企业"
        topScenarioNames={["客户分层运营", "门店知识助手", "巡店异常预警"]}
      />,
    );

    expect(screen.getByText("差异化竞争力策略概要")).toBeInTheDocument();
    expect(screen.getByText("卡片式输出")).toBeInTheDocument();
    expect(screen.getByText("输出文档标题")).toBeInTheDocument();
    expect(screen.getByText("① AI 点优势串联")).toBeInTheDocument();
    expect(screen.getByText("系统方案名称")).toBeInTheDocument();
    expect(screen.queryByText("各 AI 点如何协同增效")).not.toBeInTheDocument();
    expect(screen.getByText("AI 原生竞争者的威胁应对策略")).toBeInTheDocument();
    expect(screen.queryByText(/先通过.*快速验证/)).not.toBeInTheDocument();
    expect(screen.queryByText("串联逻辑描述")).not.toBeInTheDocument();
    expect(screen.queryByText("VP 交付逻辑变化")).not.toBeInTheDocument();
    expect(screen.getByText("短期")).toBeInTheDocument();
    expect(screen.queryByText("内容输出结构（Output Template）")).not.toBeInTheDocument();
  });
});
