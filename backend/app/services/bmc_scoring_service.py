"""BMC 三维突破要素评分 — 核心算法引擎

实现 Pain × Data × Feasibility 加权评分模型：
- 原始分 = Pain×0.40 + Data×0.35 + Feasibility×0.25 + Pain×Data×0.05
- 归一化 = (raw - 1.05) / 5.20 × 100
- 四象限矩阵映射
- 一票否决规则
- Top 3 遴选 + 互补性检验
"""

from app.schemas.assessment import CanvasDiagnosisResult
from app.schemas.bmc_scoring import (
    BMC_MODULE_DEFINITIONS,
    BMCScoringResult,
    INTERACTION_ALPHA,
    INTERNAL_EFFICIENCY_KEYS,
    MARKET_SIDE_KEYS,
    MODULE_KEY_TO_CATEGORY,
    MODULE_KEY_TO_TITLE,
    ModuleScoreInput,
    ModuleScoringResult,
    SCORE_MIN,
    SCORE_RANGE,
    WEIGHT_DATA,
    WEIGHT_FEASIBILITY,
    WEIGHT_PAIN,
)


class BMCScoringService:
    """三维评分引擎"""

    # ── 核心计算 ──

    @staticmethod
    def calculate_single(pain: float, data: float, feasibility: float) -> tuple[float, float]:
        """计算 raw_score 和 normalized_score"""
        raw = (
            pain * WEIGHT_PAIN
            + data * WEIGHT_DATA
            + feasibility * WEIGHT_FEASIBILITY
            + pain * data * INTERACTION_ALPHA
        )
        normalized = round((raw - SCORE_MIN) / SCORE_RANGE * 100, 1)
        normalized = max(0.0, min(100.0, normalized))
        return round(raw, 3), normalized

    # ── 象限判定 ──

    @staticmethod
    def get_zone(pain: float, data: float, normalized: float) -> str:
        """
        四象限判定（含一票否决前置检查）

        Returns: quickwin | strategic | longterm | hold | blocked
        """
        veto_status, _ = BMCScoringService.get_veto_status(pain, data, feasibility=None)
        if veto_status != "none":
            return "blocked"

        if pain >= 4 and data >= 4:
            return "quickwin"
        if pain >= 4 and data < 4:
            return "strategic"
        if pain < 4 and data >= 4:
            return "longterm"
        return "hold"

    # ── 一票否决 ──

    @staticmethod
    def get_veto_status(
        pain: float, data: float, feasibility: float | None
    ) -> tuple[str, str | None]:
        """
        检查一票否决规则

        Returns: (veto_status, veto_reason)
        """
        # Rule 1: Feasibility == 1 → 根本性障碍
        if feasibility is not None and feasibility <= 1:
            return (
                "blocked_feasibility",
                "存在根本性实施障碍，强行推进将浪费资源并损伤团队信心，建议 12 个月后重新评估。",
            )
        # Rule 2: Data == 1 AND Pain <= 3 → 数据空白且痛点不严重
        if data <= 1 and pain <= 3:
            return (
                "blocked_data_pain",
                "数据空白且痛点不算严重，AI 投入产出比极低，建议先完成数字化基础建设。",
            )
        # Rule 3: Pain <= 2 → 痛点不足
        if pain <= 2:
            return (
                "not_recommended",
                "痛点不明显，强行引入 AI 缺乏组织动力，项目极易烂尾，建议优先聚焦更迫切的要素。",
            )
        return ("none", None)

    # ── 推荐等级 ──

    @staticmethod
    def get_recommendation_meta(zone: str, normalized: float) -> tuple[str, str, str]:
        """
        根据象限和归一化分返回 (recommendation_level, recommendation_label, recommendation_stars)

        level: top / strategic / cultivate / none / veto
        """
        if zone == "blocked":
            return ("veto", "一票否决 · 强制暂缓", "🚫")

        if zone == "quickwin":
            if normalized >= 80:
                return ("top", "🚀 最优突破口 · 强烈推荐", "⭐⭐⭐")
            if normalized >= 70:
                return ("top", "🚀 强烈推荐 · 快赢黄金区", "⭐⭐⭐")
            return ("top", "🚀 推荐 · 快赢黄金区", "⭐⭐⭐")

        if zone == "strategic":
            if normalized >= 60:
                return ("strategic", "📋 战略布局 · 高优先级", "⭐⭐")
            return ("strategic", "📋 可考虑 · 战略攻坚区", "⭐⭐")

        if zone == "longterm":
            if normalized >= 50:
                return ("cultivate", "🌱 长期培育 · 数据已就绪", "⭐")
            return ("cultivate", "🌱 低优先级培育", "⭐")

        # hold
        return ("none", "⏸ 暂缓 · 当前条件不成熟", "—")

    # ── 单模块评估 ──

    def evaluate_module(self, inp: ModuleScoreInput) -> ModuleScoringResult:
        """对单个模块进行完整评估"""
        pain = inp.pain
        data = inp.data
        feasibility = inp.feasibility

        raw_score, normalized_score = self.calculate_single(pain, data, feasibility)
        zone = self.get_zone(pain, data, normalized_score)
        veto_status, veto_reason = self.get_veto_status(pain, data, feasibility)
        level, label, stars = self.get_recommendation_meta(zone, normalized_score)

        title = MODULE_KEY_TO_TITLE.get(inp.key, inp.key)
        category = MODULE_KEY_TO_CATEGORY.get(inp.key, "unknown")

        # 找 abbr
        abbr = inp.key
        for m in BMC_MODULE_DEFINITIONS:
            if m["key"] == inp.key:
                abbr = m["abbr"]
                break

        return ModuleScoringResult(
            key=inp.key,
            title=title,
            abbr=abbr,
            category=category,
            pain=pain,
            data=data,
            feasibility=feasibility,
            raw_score=raw_score,
            normalized_score=normalized_score,
            zone=zone,
            veto_status=veto_status,
            veto_reason=veto_reason,
            recommendation_level=level,
            recommendation_label=label,
            recommendation_stars=stars,
        )

    # ── 全模块评估 + Top 3 遴选 ──

    def evaluate_all(
        self,
        modules: list[ModuleScoreInput],
        assessment_id: str = "",
    ) -> BMCScoringResult:
        """评估全部模块，遴选 Top 3"""
        results = [self.evaluate_module(m) for m in modules]

        # Ranking is identical to the nine-module score preview.
        # Keep risk/veto labels visible; they do not silently reorder the list.
        top3 = sorted(
            results,
            key=lambda item: item.normalized_score,
            reverse=True,
        )[:3]
        top3_keys = [item.key for item in top3]

        # 互补性检验
        complementarity_warning = self.check_complementarity(top3_keys)

        return BMCScoringResult(
            assessment_id=assessment_id,
            module_results=results,
            top_3_keys=top3_keys,
            top_3_results=top3[:3],
            complementarity_warning=complementarity_warning,
        )

    # ── 互补性检验 ──

    @staticmethod
    def check_complementarity(selected_keys: list[str]) -> str | None:
        """
        若 Top 3 全部集中在内部效率类要素（KA/KR/C$），
        提示建议增加市场侧要素。
        """
        if len(selected_keys) < 3:
            return None

        if all(k in INTERNAL_EFFICIENCY_KEYS for k in selected_keys):
            return (
                "您当前选择的突破要素全部集中在内部效率优化（KA/KR/C$），"
                "建议考虑增加一个市场侧要素（CS/VP/CH/CR），"
                "以形成'内外兼修'的创新组合。"
            )
        return None

    # ── 自动推导 ──

    def auto_derive_scores(
        self,
        canvas_diagnosis: CanvasDiagnosisResult,
    ) -> list[ModuleScoreInput]:
        """
        从画布诊断文本自动推导三维初始分。

        启发式规则：
        - pain: 检测 "流失"/"投诉"/"损失"/"危机"/"下降"/"压力" 等痛点关键词
        - data: 检测 "系统"/"CRM"/"数据"/"数字化"/"记录"/"平台" 等数据关键词
        - feasibility: 检测 "意愿"/"预算"/"试点"/"支持"/"推动" 等可行性关键词
        """
        pain_positive_keywords = [
            "流失", "投诉", "损失", "危机", "下降", "压力", "紧迫", "严重",
            "不足", "缺失", "隐患", "瓶颈", "急需", "最困扰", "跟不上",
            "事先完全不知道", "突然", "慌了", "头疼",
        ]
        pain_negative_keywords = ["正常", "良好", "稳定", "没问题", "满意"]

        data_positive_keywords = [
            "系统", "CRM", "ERP", "数据", "数字化", "记录", "平台",
            "数据库", "交易流水", "日志", "报表", "统计", "自动化",
            "完整的", "结构化", "系统化",
        ]
        data_negative_keywords = [
            "Excel", "手机通讯录", "脑子", "纸质", "口头", "截图",
            "微信记录", "人工台账", "没有系统", "基本没有",
        ]

        feasibility_positive_keywords = [
            "愿意", "支持", "预算", "试点", "推动", "想", "考虑",
            "计划", "探索", "尝试", "引入", "上线",
        ]
        feasibility_negative_keywords = [
            "抵触", "反对", "顾虑", "担心", "不接受", "封闭",
            "暂时不考虑", "代价太大", "做不了",
        ]

        blocks_map = {b.key: b for b in canvas_diagnosis.canvas.blocks}

        result: list[ModuleScoreInput] = []
        for mod in BMC_MODULE_DEFINITIONS:
            key = mod["key"]
            block = blocks_map.get(key)

            pain = 3.0
            data = 3.0
            feasibility = 3.0

            if block is not None:
                combined_text = (
                    f"{block.diagnosis or ''} {block.current_state or ''} "
                    f"{block.missing_information or ''} {block.ai_opportunity or ''}"
                )

                # Pain 评分
                pain_pos = sum(1 for kw in pain_positive_keywords if kw in combined_text)
                pain_neg = sum(1 for kw in pain_negative_keywords if kw in combined_text)
                pain = 3.0 + pain_pos * 0.5 - pain_neg * 0.5
                pain = max(1.0, min(5.0, pain))

                # Data 评分
                data_pos = sum(1 for kw in data_positive_keywords if kw in combined_text)
                data_neg = sum(1 for kw in data_negative_keywords if kw in combined_text)
                data = 3.0 + data_pos * 0.5 - data_neg * 0.5
                data = max(1.0, min(5.0, data))

                # Feasibility 评分
                feas_pos = sum(1 for kw in feasibility_positive_keywords if kw in combined_text)
                feas_neg = sum(1 for kw in feasibility_negative_keywords if kw in combined_text)
                feasibility = 3.0 + feas_pos * 0.5 - feas_neg * 0.5
                feasibility = max(1.0, min(5.0, feasibility))

            result.append(
                ModuleScoreInput(
                    key=key,
                    pain=round(pain * 2) / 2,  # 四舍五入到 0.5
                    data=round(data * 2) / 2,
                    feasibility=round(feasibility * 2) / 2,
                )
            )

        return result
