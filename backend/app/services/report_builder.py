import re

from app.models.assessment import Assessment
from app.schemas.assessment import (
    CanvasDiagnosisResult,
    CaseRecommendationResult,
    CompanyProfileResult,
    ReportActionItem,
    ReportCardData,
    ReportData,
    ReportRoadmapStage,
    ReportSectionData,
    ReportTableData,
    ScenarioRecommendationResult,
)
from app.schemas.breakthrough import ELEMENT_KEY_TO_TITLE
from app.schemas.direction import DirectionSuggestion


class ReportBuilder:
    def build(
        self,
        assessment: Assessment,
        profile: CompanyProfileResult,
        canvas_diagnosis: CanvasDiagnosisResult,
        scenario_recommendation: ScenarioRecommendationResult,
        case_recommendation: CaseRecommendationResult | None,
        breakthrough_keys: list[str] | None = None,
        direction_labels: list[str] | None = None,
        selected_directions: list[DirectionSuggestion] | None = None,
        competitiveness_result = None,
        enrichment_result = None,
        endgame_result = None,
    ) -> ReportData:
        ai_readiness_score = self._calculate_ai_readiness_score(
            profile=profile,
            canvas_diagnosis=canvas_diagnosis,
            scenario_recommendation=scenario_recommendation,
        )
        breakthrough_labels = self._resolve_breakthrough_labels(breakthrough_keys or [])
        direction_labels = direction_labels or []
        selected_directions = selected_directions or []
        canvas_blocks = canvas_diagnosis.canvas.blocks

        sections = [
            self._build_canvas_section(canvas_diagnosis),
            self._build_breakthrough_section(breakthrough_labels, canvas_blocks),
            self._build_direction_section(direction_labels, selected_directions),
            self._build_priority_scenarios_section(scenario_recommendation),
            self._build_competitiveness_section(profile, canvas_diagnosis, scenario_recommendation, competitiveness_result),
            self._build_endgame_section(endgame_result, profile, canvas_diagnosis),
        ]

        return ReportData(
            title=f"{assessment.company_name} AI 商业创新建议报告",
            subtitle=f"{assessment.industry} | {assessment.region} | 模板化管理层阅读版",
            company_name=assessment.company_name,
            industry=assessment.industry,
            company_size=assessment.company_size,
            region=assessment.region,
            annual_revenue_range=assessment.annual_revenue_range,
            ai_readiness_score=ai_readiness_score,
            ai_readiness_summary=self._build_ai_readiness_summary(
                ai_readiness_score,
                profile,
                canvas_diagnosis,
            ),
            generated_with="template",
            sections=sections,
        )

    def _calculate_ai_readiness_score(
        self,
        profile: CompanyProfileResult,
        canvas_diagnosis: CanvasDiagnosisResult,
        scenario_recommendation: ScenarioRecommendationResult,
    ) -> int:
        score = canvas_diagnosis.overall_score
        score -= min(18, len(profile.missing_information) * 3)
        score += min(8, len(profile.priority_ai_directions) * 2)
        if scenario_recommendation.top_scenarios:
            score += 5
        if "待补充" in profile.digital_and_ai_readiness:
            score -= 5
        return max(35, min(95, score))

    def _build_ai_readiness_summary(
        self,
        score: int,
        profile: CompanyProfileResult,
        canvas_diagnosis: CanvasDiagnosisResult,
    ) -> str:
        weakest_blocks = self._join_or_todo(canvas_diagnosis.weakest_blocks[:2], "、")
        if score >= 75:
            return (
                "企业已经具备相对明确的试点条件，可以围绕当前高优先级场景直接推进业务试点，"
                f"同时优先修补 {weakest_blocks} 相关的管理与协同短板。"
            )
        if score >= 60:
            return (
                "企业具备初步 AI 推进基础，但仍需先统一关键数据口径、明确责任人和验收标准，"
                f"尤其要先补齐 {weakest_blocks} 对应的流程与数据基础。"
            )
        return (
            "企业当前更适合先做数据盘点、流程梳理和跨部门协同机制建设，再选择低风险、可量化的小范围试点，"
            f"优先从 {weakest_blocks} 对应问题切入。"
        )

    def _build_company_profile_section(
        self,
        profile: CompanyProfileResult,
    ) -> ReportSectionData:
        return ReportSectionData(
            key="company_profile",
            title="企业基本画像",
            content=profile.company_summary,
            cards=[
                ReportCardData(title="价值主张", content=profile.value_proposition),
                ReportCardData(title="客户与市场", content=profile.customer_and_market),
                ReportCardData(title="运营与资源", content=profile.operations_and_resources),
                ReportCardData(
                    title="数字化与 AI 准备度",
                    content=profile.digital_and_ai_readiness,
                ),
            ],
            bullets=[
                f"关键挑战：{self._join_or_todo(profile.key_challenges)}",
                f"优先 AI 方向：{self._join_or_todo(profile.priority_ai_directions)}",
            ],
        )

    def _build_canvas_section(
        self,
        canvas_diagnosis: CanvasDiagnosisResult,
    ) -> ReportSectionData:
        # Build an overview table of all 9 blocks
        overview_table = ReportTableData(
            columns=["画布模块", "当前状态摘要", "核心诊断", "AI 机会方向"],
            rows=[
                [
                    block.title,
                    self._truncate_text(block.current_state, 80),
                    self._truncate_text(block.diagnosis, 80),
                    self._truncate_text(block.ai_opportunity, 80),
                ]
                for block in canvas_diagnosis.canvas.blocks
            ],
        )

        return ReportSectionData(
            key="canvas_diagnosis",
            title="当前商业模式画布诊断",
            content=canvas_diagnosis.canvas.overall_summary,
            bullets=[
                f"薄弱模块：{self._join_or_todo(canvas_diagnosis.weakest_blocks)}",
            ],
            table=overview_table,
            note=f"建议优先动作：{'；'.join(canvas_diagnosis.recommended_focus[:3])}" if canvas_diagnosis.recommended_focus else None,
        )

    @staticmethod
    def _truncate_text(text: str, max_len: int) -> str:
        return text

    def _build_ai_readiness_section(
        self,
        score: int,
        profile: CompanyProfileResult,
        canvas_diagnosis: CanvasDiagnosisResult,
    ) -> ReportSectionData:
        # Build readiness dimension cards
        dim_cards = [
            ReportCardData(
                title="数据基础",
                subtitle="Data Foundation",
                content=f"现有系统：{self._join_or_todo([profile.operations_and_resources[:120]], '；')}",
                highlight=f"状态：{'✅ 已具备初步数据底座' if score >= 60 else '⚠️ 数据基础需要加强'}",
                bullets=[f"待补充：{self._join_or_todo(profile.missing_information[:2])}"],
            ),
            ReportCardData(
                title="组织意愿",
                subtitle="Organization Readiness",
                content=f"AI 目标方向：{self._join_or_todo(profile.priority_ai_directions[:2], '；')}",
                highlight=f"状态：{'✅ 目标明确，可推进试点' if score >= 70 else '⚠️ 建议先统一内部共识'}",
                bullets=[f"关键挑战：{self._join_or_todo(profile.key_challenges[:2])}"],
            ),
            ReportCardData(
                title="技术可行性",
                subtitle="Technical Feasibility",
                content=f"数字化与 AI 准备度：{profile.digital_and_ai_readiness}",
                highlight=f"状态：{'✅ 技术条件基本具备' if score >= 65 else '⚠️ 需先补齐基础系统'}",
                bullets=[f"画布薄弱环节：{self._join_or_todo(canvas_diagnosis.weakest_blocks[:2])}"],
            ),
            ReportCardData(
                title="综合就绪度",
                subtitle="Readiness Summary",
                content=self._build_ai_readiness_summary(score, profile, canvas_diagnosis),
                highlight="综合判断：当前可进入试点验证与组织准备并行推进阶段。",
            ),
        ]

        return ReportSectionData(
            key="ai_readiness",
            title="AI 成熟度评估",
            content=self._build_ai_readiness_summary(score, profile, canvas_diagnosis),
            cards=dim_cards,
            bullets=[
                f"数字化与 AI 准备度判断：{profile.digital_and_ai_readiness}",
                f"当前优先补齐项：{self._join_or_todo(profile.missing_information[:3])}",
                f"优先 AI 方向：{self._join_or_todo(profile.priority_ai_directions[:3])}",
            ],
            note="该评分基于画布完整度、数据基础和 AI 目标明确度综合计算，仅作为管理层判断和排序参考，不代表财务回报承诺，也不替代正式立项评审。",
        )

    def _build_priority_scenarios_section(
        self,
        scenario_recommendation: ScenarioRecommendationResult,
    ) -> ReportSectionData:
        is_four_quadrant = scenario_recommendation.scoring_method == "four_quadrant_v1"

        columns = ["推荐场景", "场景描述", "预期效果", "切入模块"]
        trimmed_summaries = [
            self._trim_scenario_summary_lead_in(item.summary)
            for item in scenario_recommendation.top_scenarios
        ]
        display_summaries = [
            self._dedupe_scenario_summary(
                trimmed_summaries[index],
                trimmed_summaries[:index],
            )
            for index, _item in enumerate(scenario_recommendation.top_scenarios)
        ]
        display_effects = [
            self._dedupe_scenario_effects(
                display_summaries[index],
                self._dedupe_scenario_effects_across_rows(
                    item.expected_effects,
                    [
                        previous.expected_effects
                        for previous in scenario_recommendation.top_scenarios[:index]
                    ],
                ),
            )
            for index, item in enumerate(scenario_recommendation.top_scenarios)
        ]
        rows = []
        for index, item in enumerate(scenario_recommendation.top_scenarios):
            row = [
                item.name,
                display_summaries[index],
                display_effects[index],
                item.canvas_elements,
            ]
            rows.append(row)

        table = ReportTableData(columns=columns, rows=rows)

        content = (
            "以下场景基于企业问卷、商业画布诊断和四象限优先级评分结果生成，"
            "适合作为当前阶段优先验证的 AI 提效切入口。"
            if is_four_quadrant
            else (
                "以下场景基于企业问卷、商业画布诊断和规则评分结果生成，"
                "适合作为当前阶段优先验证的 AI 提效切入口。"
            )
        )

        return ReportSectionData(
            key="priority_scenarios",
            title="高优先级 AI 提效场景",
            content=content,
            table=table,
        )

    @staticmethod
    def _normalize_scenario_text(value: str) -> str:
        return re.sub(r"[：:；;，,。.!！?？\s]+", "", value)

    @staticmethod
    def _strip_scenario_effect_lead_in(expected_effects: str) -> str:
        return re.sub(r"^支撑方向：.*?[；;]", "", expected_effects).strip()

    def _trim_scenario_summary_lead_in(self, summary: str) -> str:
        trimmed = summary.strip()
        if "围绕" not in trimmed or "结合" not in trimmed:
            return trimmed

        shortened = re.sub(
            r"^围绕[\s\S]+?结合[\s\S]+?(?:[，,；;。]\s*)?(?=在)",
            "",
            trimmed,
        ).strip()
        return shortened or trimmed

    def _dedupe_scenario_summary(
        self,
        summary: str,
        previous_summaries: list[str],
    ) -> str:
        if not previous_summaries:
            return summary

        normalized_previous = [
            self._normalize_scenario_text(previous)
            for previous in previous_summaries
        ]
        segments = [
            segment.strip()
            for segment in re.split(r"[；;。]", summary)
            if segment.strip()
        ]
        unique_segments = [
            segment
            for segment in segments
            if self._normalize_scenario_text(segment)
            and not any(
                previous.find(self._normalize_scenario_text(segment)) >= 0
                for previous in normalized_previous
            )
        ]

        if not unique_segments:
            return summary
        return "；".join(unique_segments) + "。"

    def _dedupe_scenario_effects(
        self,
        summary: str,
        expected_effects: str,
    ) -> str:
        normalized_summary = self._normalize_scenario_text(summary)
        cleaned_effects = self._strip_scenario_effect_lead_in(expected_effects)
        segments = [
            segment.strip()
            for segment in re.split(r"[；;。]", cleaned_effects)
            if segment.strip()
        ]
        unique_segments = [
            segment
            for segment in segments
            if self._normalize_scenario_text(segment)
            and self._normalize_scenario_text(segment) not in normalized_summary
        ]

        if not unique_segments:
            return cleaned_effects or expected_effects
        return "；".join(unique_segments) + "。"

    def _dedupe_scenario_effects_across_rows(
        self,
        expected_effects: str,
        previous_effects: list[str],
    ) -> str:
        cleaned_effects = self._strip_scenario_effect_lead_in(expected_effects)
        if not previous_effects:
            return cleaned_effects or expected_effects

        normalized_previous = [
            self._normalize_scenario_text(
                self._strip_scenario_effect_lead_in(previous),
            )
            for previous in previous_effects
        ]
        segments = [
            segment.strip()
            for segment in re.split(r"[；;。]", cleaned_effects)
            if segment.strip()
        ]
        unique_segments = [
            segment
            for segment in segments
            if self._normalize_scenario_text(segment)
            and not any(
                previous.find(self._normalize_scenario_text(segment)) >= 0
                for previous in normalized_previous
            )
        ]

        if not unique_segments:
            return cleaned_effects or expected_effects
        return "；".join(unique_segments) + "。"

    def _build_scenario_planning_section(
        self,
        scenario_recommendation: ScenarioRecommendationResult,
    ) -> ReportSectionData:
        return ReportSectionData(
            key="scenario_planning",
            title="推荐场景详细规划",
            content=(
                "建议把推荐场景拆成可验证、可复盘的单点试点，先在一个业务单元内跑通，"
                "再逐步复制到相邻流程，降低组织推进阻力。"
            ),
            cards=[
                ReportCardData(
                    title=item.name,
                    subtitle=item.category,
                    content=item.summary,
                    highlight=f"对应画布要素：{item.canvas_elements}" if item.canvas_elements else None,
                    bullets=[
                        f"预期效果：{item.expected_effects}" if item.expected_effects else None,
                        f"核心数据需求：{item.core_data_requirements}" if item.core_data_requirements else None,
                        f"推荐意见：{getattr(item, 'priority_recommendation', None)}" if getattr(item, "priority_recommendation", None) else None,
                        "试点建议：先定义成功标准、责任人、验收频次和异常兜底机制。",
                    ],
                )
                for item in scenario_recommendation.top_scenarios
            ],
        )

    def _build_competitiveness_section(
        self,
        profile: CompanyProfileResult,
        canvas_diagnosis: CanvasDiagnosisResult,
        scenario_recommendation: ScenarioRecommendationResult,
        competitiveness_result=None,
    ) -> ReportSectionData:
        if competitiveness_result is not None:
            cr = competitiveness_result
            _legacy_template_section = ReportSectionData(
                key="competitiveness",
                title="宸紓鍖栫珵浜夊姏璁捐",
                content=f"输出文档标题：《{profile.company_name}·差异化竞争力策略概要》",
                bullets=["模板摘要：围绕系统方案命名、VP 重构、差异化定位与三阶段提升路径展开。"],
                table=ReportTableData(
                    columns=["字段模块", "输出内容说明"],
                    rows=self._build_competitiveness_template_rows(
                        scenario_recommendation=scenario_recommendation,
                        competitiveness_result=cr,
                    ),
                ),
                note="该章节已按固定输出模板整理，可直接用于管理员批注、方案汇报或二次编辑。",
            )
            vp = cr.vp_reconstruction
            connections_text = "；".join(
                [f"{c.line_name}（{c.competitive_impact}）" for c in cr.connections[:3]]
            ) if cr.connections else ""
            advantages_text = "；".join(
                [f"{a.advantage_name}（壁垒{a.barrier_level}）" for a in cr.advantages[:3]]
            ) if cr.advantages else ""
            top_scenarios = [item.name for item in scenario_recommendation.top_scenarios[:3]]
            competitiveness_content = (
                cr.overall_narrative.strip()
                if getattr(cr, "overall_narrative", None)
                else ""
            )
            if not competitiveness_content:
                competitiveness_content = (
                    f"建议围绕“{vp.enhanced_vp}”组织差异化竞争力建设，优先把 "
                    f"{connections_text or '关键竞争力线'} 转化为可被客户感知的业务优势，"
                    f"并沉淀为 {advantages_text or '核心能力壁垒'}。"
                )

            cards = [
                ReportCardData(
                    title="AI 点优势串联",
                    subtitle="系统方案命名",
                    content="",
                    highlight=f"系统方案名称：{self._build_system_solution_name(cr, top_scenarios)}",
                ),
                ReportCardData(
                    title="VP 重构输出",
                    subtitle="价值主张升级",
                    content="",
                    highlights=[
                        f"旧 VP：{vp.current_vp}",
                        f"新 VP（AI 重构）：{vp.enhanced_vp}",
                    ],
                ),
                ReportCardData(
                    title="竞争优势差异化定位",
                    subtitle="市场定位",
                    content=self._build_differentiation_overview(cr),
                    highlight=f"定位语：{self._build_differentiation_positioning(cr)}",
                    bullets=[f"AI 原生竞争者应对：{self._build_ai_native_threat_response(cr)}"],
                ),
                ReportCardData(
                    title="核心竞争力提升路径",
                    subtitle="短中长期推进",
                    content="\n".join([
                        f"短期：{cr.delivery_strategy.phase_1_quick_win}",
                        f"中期：{cr.delivery_strategy.phase_2_scale}",
                        f"长期：{cr.delivery_strategy.phase_3_moat}",
                    ]),
                ),
            ]

            return ReportSectionData(
                key="competitiveness",
                title="差异化竞争力设计",
                content=competitiveness_content,
                bullets=[
                    f"系统方案名称：{self._build_system_solution_name(cr, top_scenarios)}",
                    f"增强型价值主张：{vp.enhanced_vp}",
                    f"串联竞争力线：{connections_text or '待补充'}",
                    f"核心优势：{advantages_text or '待补充'}",
                ],
                cards=cards,
                note="该章节保留卡片式展示，便于管理员批注、方案汇报和后续人工修订。",
            )

        top_scenarios = [item.name for item in scenario_recommendation.top_scenarios[:2]]
        weakest_blocks = canvas_diagnosis.weakest_blocks[:2]
        return ReportSectionData(
            key="competitiveness",
            title="差异化竞争力设计",
            content=(
                f"建议不要把 AI 仅当作内部降本工具，而要围绕“{profile.value_proposition}”重新组织客户响应速度、"
                "知识复用效率和跨部门协同能力。优先把 "
                f"{self._join_or_todo(top_scenarios)} 做成客户可感知的改进点，同时修补 "
                f"{self._join_or_todo(weakest_blocks)} 对应的商业模式薄弱环节，让 AI 成为竞争力放大器。"
            ),
            bullets=[
                "把高频重复工作转为标准化能力，缩短业务响应周期。",
                "把知识和数据沉淀为组织资产，减少对个人经验的依赖。",
                "把试点经验映射到客户价值和经营指标，形成持续扩展基础。",
            ],
        )

    def _build_competitiveness_template_rows(
        self,
        scenario_recommendation: ScenarioRecommendationResult,
        competitiveness_result,
    ) -> list[list[str]]:
        vp = competitiveness_result.vp_reconstruction
        top_scenarios = [item.name for item in scenario_recommendation.top_scenarios[:3]]

        return [
            [
                "① AI 点优势串联叙述",
                "\n".join([
                    f"将选定的 Top 3 AI 场景（{self._join_or_todo(top_scenarios, '、')}）串联为系统性方案命名：",
                    f"系统方案名称：{self._build_system_solution_name(competitiveness_result, top_scenarios)}",
                ]),
            ],
            [
                "② VP 重构输出",
                "\n".join([
                    "基于 AI 系统方案，重构价值主张（VP）：",
                    f"旧 VP：{vp.current_vp}",
                    f"新 VP（AI 重构）：{vp.enhanced_vp}",
                ]),
            ],
            [
                "③ 竞争优势差异化定位",
                "\n".join([
                    "与行业竞争对手的差异化优势描述：",
                    f"差异化优势描述：{self._build_differentiation_overview(competitiveness_result)}",
                    f"差异化定位语：{self._build_differentiation_positioning(competitiveness_result)}",
                    f"AI 原生竞争者的威胁应对策略：{self._build_ai_native_threat_response(competitiveness_result)}",
                ]),
            ],
            [
                "④ 核心竞争力提升路径",
                "\n".join([
                    "3 个阶段的竞争力提升路径（短中长期）：",
                    f"短期：{competitiveness_result.delivery_strategy.phase_1_quick_win}",
                    f"中期：{competitiveness_result.delivery_strategy.phase_2_scale}",
                    f"长期：{competitiveness_result.delivery_strategy.phase_3_moat}",
                ]),
            ],
        ]

    def _build_system_solution_name(
        self,
        competitiveness_result,
        top_scenarios: list[str],
    ) -> str:
        connections = competitiveness_result.connections[:2]
        if connections:
            primary = connections[0].line_name.replace("线", "").strip() or connections[0].line_name
            if len(connections) > 1:
                secondary = connections[1].line_name.replace("线", "").strip() or connections[1].line_name
                if secondary and secondary != primary:
                    return f"{primary}×{secondary}智能协同系统"
            return f"{primary}智能协同系统"
        if top_scenarios:
            return f"{top_scenarios[0]}智能协同系统"
        return "AI 差异化竞争力协同系统"

    def _build_solution_chain_logic(self, competitiveness_result) -> str:
        parts: list[str] = []
        for conn in competitiveness_result.connections[:3]:
            logic = conn.linkage_logic or conn.strategic_narrative or conn.competitive_impact
            if logic:
                parts.append(f"{conn.line_name}：{logic}")
        return "；".join(parts) if parts else competitiveness_result.overall_narrative

    def _build_synergy_description(self, competitiveness_result) -> str:
        parts: list[str] = []
        for conn in competitiveness_result.connections[:3]:
            point_titles = self._join_or_todo(conn.point_titles[:3], "、")
            parts.append(
                f"{point_titles}共同支撑{conn.line_name}，带来{conn.competitive_impact or '竞争力增益'}"
            )
        return "；".join(parts) if parts else competitiveness_result.overall_narrative

    def _build_differentiation_overview(self, competitiveness_result) -> str:
        if getattr(competitiveness_result, "overall_narrative", "").strip():
            return competitiveness_result.overall_narrative.strip()
        return self._build_differentiation_positioning(competitiveness_result)

    def _build_differentiation_positioning(self, competitiveness_result) -> str:
        vp = competitiveness_result.vp_reconstruction
        advantage_names = [item.advantage_name for item in competitiveness_result.advantages[:2]]
        joined_advantages = self._join_or_todo(advantage_names, "、")
        return f"围绕“{vp.enhanced_vp}”，以{joined_advantages}构建不可替代的客户价值定位。"

    def _build_ai_native_threat_response(self, competitiveness_result) -> str:
        line_names = [item.line_name for item in competitiveness_result.connections[:2]]
        joined_lines = self._join_or_todo(line_names, "、")
        return (
            f"不与 AI 原生竞争者单纯比拼模型能力，而是围绕{joined_lines}，"
            "将客户数据、业务流程与专业知识整合为可持续的组织能力。"
        )

    def _build_cases_section(
        self,
        case_recommendation: CaseRecommendationResult | None,
    ) -> ReportSectionData:
        if not case_recommendation or not case_recommendation.top_cases:
            return ReportSectionData(
                key="cases",
                title="参考案例与启示",
                content=(
                    "当前未匹配到足够贴合的匿名行业参考案例。下一阶段可以接入案例检索增强能力。"
                    "本报告在案例部分统一标记为“待补充”，避免编造真实客户名称或真实 ROI。"
                ),
                bullets=["待补充：后续可在报告生成端接入案例检索与 RAG。"],
            )

        # Build a summary table for quick comparison
        cases_table = ReportTableData(
            columns=["案例", "行业", "匹配度", "核心启示", "数据基础"],
            rows=[
                [
                    item.title,
                    item.industry,
                    f"{'★' * max(1, min(5, item.fit_score // 20))} {item.fit_score}分",
                    self._join_or_todo(item.match_reasons[:2], "；"),
                    self._join_or_todo(getattr(item, 'data_foundation', item.reference_points[:2]), "；"),
                ]
                for item in case_recommendation.top_cases
            ],
        )

        return ReportSectionData(
            key="cases",
            title="参考案例与启示",
            content=(
                "以下内容均为匿名行业参考案例，仅用于帮助管理层理解类似场景的落地方式与参考路径，"
                "不代表真实客户名称，也不构成真实 ROI 承诺。"
            ),
            table=cases_table,
            cards=[
                ReportCardData(
                    title=f"案例 {i+1}：{item.title}",
                    subtitle=f"{item.industry} · 匹配度 {'★' * max(1, min(5, item.fit_score // 20))}",
                    content=item.summary,
                    highlight=f"匹配分数：{item.fit_score} 分 —— 与当前企业画像的相似度",
                    bullets=[
                        f"匹配理由：{self._join_or_todo(item.match_reasons)}",
                        f"参考做法：{self._join_or_todo(item.reference_points)}",
                        f"注意要点：{self._join_or_todo(getattr(item, 'cautions', ['建议结合自身业务实际评估']))}",
                    ],
                )
                for i, item in enumerate(case_recommendation.top_cases)
            ],
            note="案例匹配基于行业、规模、痛点和 AI 方向四层匹配，分数越高代表与当前企业情境的相似度越高。建议优先研读高匹配度案例的落地路径和前置条件。",
        )

    def _build_roadmap_section(
        self,
        roadmap: list[ReportRoadmapStage],
    ) -> ReportSectionData:
        return ReportSectionData(
            key="roadmap",
            title="三阶段 AI 创新路线图",
            content="建议按“短期单点提效 -> 中期差异化竞争力 -> 长期生态与增长路径”的顺序推进。",
            cards=[
                ReportCardData(
                    title=stage.stage_name,
                    subtitle=stage.time_horizon,
                    content=stage.strategic_focus,
                    bullets=[
                        f"优先动作：{self._join_or_todo(stage.priority_actions)}",
                        f"阶段产出：{self._join_or_todo(stage.expected_outputs)}",
                    ],
                )
                for stage in roadmap
            ],
        )

    def _build_risk_section(
        self,
        profile: CompanyProfileResult,
        canvas_diagnosis: CanvasDiagnosisResult,
        scenario_recommendation: ScenarioRecommendationResult,
    ) -> ReportSectionData:
        bullets = [
            "如果关键业务数据口径不统一，报告中的建议难以稳定落地，需先统一口径。",
            "如果试点场景过多，组织协同成本会快速上升，建议先聚焦 1 到 2 个场景。",
            "如果没有业务负责人参与验收，AI 项目容易停留在演示层，无法进入经营闭环。",
        ]

        for item in profile.missing_information[:2]:
            bullets.append(f"信息缺口风险：{item}")

        if canvas_diagnosis.weakest_blocks:
            bullets.append(
                f"商业模式薄弱点集中在 {self._join_or_todo(canvas_diagnosis.weakest_blocks[:3])}，"
                "会直接影响推荐场景的落地速度。"
            )

        if scenario_recommendation.top_scenarios:
            top_scenario = scenario_recommendation.top_scenarios[0]
            bullets.append(
                "首选场景「" + top_scenario.name + "」核心数据需求：" + (top_scenario.core_data_requirements or "待补充") + "。"
            )

        return ReportSectionData(
            key="risks",
            title="风险与阻力",
            content="以下风险不是否定 AI 推进，而是帮助管理层提前设定边界、节奏和验收机制。",
            bullets=bullets[:7],
        )

    def _build_instructor_section(
        self,
        profile: CompanyProfileResult,
        scenario_recommendation: ScenarioRecommendationResult,
        enrichment_result=None,
    ) -> ReportSectionData:
        if enrichment_result is not None:
            ic = enrichment_result.instructor_comment
            return ReportSectionData(
                key="instructor_comments",
                title="管理员点评区",
                content=ic.overall_assessment,
                bullets=[
                    f"优势：{p}" for p in ic.strength_points[:3]
                ] + [
                    f"风险：{r}" for r in ic.risk_warnings[:3]
                ],
                note=(
                    f"推荐阅读：{'、'.join(ic.recommended_reading[:3]) or '待补充'}"
                ),
            )

        top_name = (
            scenario_recommendation.top_scenarios[0].name
            if scenario_recommendation.top_scenarios
            else "待补充"
        )
        return ReportSectionData(
            key="instructor_comments",
            title="管理员点评区",
            content=(
                "管理员点评建议：当前企业更适合采用\u201c先验证一个高频试点，再把经验复制到相邻流程\u201d的推进方式。"
                f"优先围绕 {top_name} 这类能较快体现业务价值的场景切入，同时关注 "
                f"{profile.digital_and_ai_readiness} 所暴露出的组织准备度问题。"
            ),
            note="该区域适合作为后续人工点评、管理员批注、高层会议纪要或培训反馈的补充位置。",
        )

    def _build_endgame_section(
        self,
        endgame_result,
        profile: CompanyProfileResult,
        canvas_diagnosis: CanvasDiagnosisResult,
    ) -> ReportSectionData:
        if endgame_result is None:
            return ReportSectionData(
                key="endgame",
                title="核心竞争力推进策略",
                content="该评估尚未生成核心竞争力推进策略。",
                note="建议先完成竞争力和场景分析，再生成三阶段推进计划。",
            )

        er = endgame_result
        strategy = er.three_stage_strategy
        path_cards = [
            ReportCardData(
                title=f"{path.path_name}（{path.path_type}·{path.recommendation_level}）",
                subtitle=f"推进节奏：{path.execution_rhythm}",
                content=path.expected_outcomes,
                bullets=[
                    f"能力前提：{path.capability_requirements}",
                    f"里程碑：{'；'.join(path.key_milestones[:2])}",
                    f"风险提示：{'；'.join(path.major_risks[:2])}",
                ],
            )
            for path in er.strategic_paths
        ]
        return ReportSectionData(
            key="endgame",
            title="核心竞争力推进策略",
            content="围绕核心竞争力，按以下三个阶段推进：",
            bullets=[
                f"{strategy.stage_1.title}：{strategy.stage_1.focus}；{strategy.stage_1.strategy}",
                f"{strategy.stage_2.title}：{strategy.stage_2.focus}；{strategy.stage_2.strategy}",
                f"{strategy.stage_3.title}：{strategy.stage_3.focus}；{strategy.stage_3.strategy}",
                *[f"关键风险：{risk}" for risk in strategy.key_risks],
            ],
            cards=path_cards if path_cards else None,
        )

    def _build_roadmap(
        self,
        canvas_diagnosis: CanvasDiagnosisResult,
        scenario_recommendation: ScenarioRecommendationResult,
    ) -> list[ReportRoadmapStage]:
        weakest_blocks = canvas_diagnosis.weakest_blocks or ["待补充"]
        top_names = [item.name for item in scenario_recommendation.top_scenarios]
        first = top_names[0] if top_names else "待补充"
        second = top_names[1] if len(top_names) > 1 else first
        third = top_names[2] if len(top_names) > 2 else second

        return [
            ReportRoadmapStage(
                stage_name="短期：单点提效",
                time_horizon="0-30 天",
                strategic_focus="围绕一个高频、可量化、数据基础相对明确的场景快速试点。",
                priority_actions=[
                    f"围绕 {first} 明确试点目标和验收标准。",
                    f"补齐 {weakest_blocks[0]} 对应的数据口径和流程说明。",
                    "梳理最小可用数据集和人工兜底规则。",
                ],
                expected_outputs=["试点方案", "关键数据清单", "首轮试点复盘纪要"],
            ),
            ReportRoadmapStage(
                stage_name="中期：差异化竞争力",
                time_horizon="31-90 天",
                strategic_focus="把单点试点扩展到相邻流程，形成跨部门协同和可感知业务价值。",
                priority_actions=[
                    f"把 {first} 与 {second} 串联成前后流程闭环。",
                    f"围绕 {weakest_blocks[1] if len(weakest_blocks) > 1 else weakest_blocks[0]} 建立监控与预警。",
                    "沉淀 SOP、异常处理规则和人工接管机制。",
                ],
                expected_outputs=["跨部门协同流程", "阶段经营复盘机制", "可复制场景模板"],
            ),
            ReportRoadmapStage(
                stage_name="长期：生态与增长路径",
                time_horizon="91-180 天",
                strategic_focus="把试点经验沉淀为组织能力，并逐步扩展到更多业务单元和增长场景。",
                priority_actions=[
                    f"推广 {third} 及其相邻方法模板。",
                    "建立统一的知识、数据质量和权限治理机制。",
                    "形成年度 AI 创新项目池和预算讨论机制。",
                ],
                expected_outputs=["组织级 AI 能力框架", "标准化场景资产库", "持续扩展路线图"],
            ),
        ]

    def _build_breakthrough_section(
        self,
        breakthrough_labels: list[str],
        canvas_blocks,
    ) -> ReportSectionData:
        if not breakthrough_labels:
            return ReportSectionData(
                key="breakthrough",
                title="突破要素",
                content="该评估尚未完成突破要素选择。建议先完成商业画布诊断后，围绕最薄弱的 2-3 个要素进行选择和聚焦。",
                note="突破要素选择是 V2 方法论的关键节点，建议在生成最终报告前完成。",
            )

        block_map = {block.key: block for block in canvas_blocks}
        cards: list[ReportCardData] = []
        for label in breakthrough_labels:
            for key, title in ELEMENT_KEY_TO_TITLE.items():
                if title == label:
                    block = block_map.get(key)
                    if block:
                        cards.append(
                            ReportCardData(
                                title=title,
                                subtitle="选定突破要素",
                                content=f"当前状态：{block.current_state}",
                                highlight=f"AI 机会：{block.ai_opportunity}",
                                bullets=[
                                    f"诊断发现：{block.diagnosis}",
                                    f"信息缺口提示：{block.missing_information}",
                                ],
                            )
                        )
                    else:
                        cards.append(
                            ReportCardData(
                                title=title,
                                subtitle="选定突破要素",
                                content="画布诊断中未找到该要素的详细数据。",
                            )
                        )
                    break

        joined_labels = "、".join(breakthrough_labels)
        return ReportSectionData(
            key="breakthrough",
            title="突破要素",
            content=(
                f"基于商业模式画布诊断结果，本评估选定以下 {len(breakthrough_labels)} 个要素作为"
                f"当前阶段最需要突破的方向：{joined_labels}。"
                f"建议将资源和精力优先聚焦于这些薄弱环节，以最快的速度获得结构性改善。"
            ),
            cards=cards,
            bullets=[
                f"突破方向：{joined_labels}",
                "聚焦 2-3 个关键是避免力量分散、确保落地效果的最佳策略。",
                "每个突破要素对应的 AI 机会可作为后续场景推荐的输入参考。",
            ],
        )

    def _build_direction_section(
        self,
        direction_labels: list[str],
        selected_directions: list[DirectionSuggestion],
    ) -> ReportSectionData:
        if not direction_labels:
            return ReportSectionData(
                key="direction_expansion",
                title="创新方向延展",
                content="该评估尚未完成创新方向延展。建议先完成突破要素选择后，围绕每个要素展开具体创新方向。",
                note="方向延展是 V2 方法论点阶段的重要环节，建议在生成最终报告前完成。",
            )

        joined = "、".join(direction_labels[:10])
        description_by_title = {
            item.title.strip(): item.description.strip()
            for item in selected_directions
            if item.title.strip() and item.description.strip()
        }
        return ReportSectionData(
            key="direction_expansion",
            title="创新方向延展",
            content=(
                f"基于选定的突破要素，本评估延展出 {len(direction_labels)} 个具体创新方向：{joined}。"
                f"这些方向为后续的 AI 场景推荐和差异化竞争力设计提供了明确抓手。"
            ),
            bullets=[
                f"共计延展 {len(direction_labels)} 个方向",
                "每个方向均对应具体的预期影响和数据需求",
                "后续场景推荐将优先匹配与选定方向高度相关的候选场景",
            ],
            cards=[
                ReportCardData(
                    title=label,
                    content=description_by_title.get(label.strip(), ""),
                )
                for label in direction_labels
            ],
            note="方向延展为 V2 方法论点阶段的核心产物，其产出将直接影响后续场景矩阵的生成和竞争力策略的设计。",
        )

    def _resolve_breakthrough_labels(self, breakthrough_keys: list[str]) -> list[str]:
        resolved: list[str] = []
        for key in breakthrough_keys:
            title = ELEMENT_KEY_TO_TITLE.get(key, key)
            if title and title != key:
                resolved.append(title)
            else:
                resolved.append(key)
        return resolved

    def _join_or_todo(self, values: list[str], separator: str = "；") -> str:
        cleaned = [value.strip() for value in values if value and value.strip()]
        return separator.join(cleaned) if cleaned else "待补充"
