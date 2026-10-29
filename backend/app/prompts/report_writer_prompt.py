"""Prompt templates for LLM-based report generation."""
from typing import Any


class ReportWriterPrompt:
    """Prompt builder for AI Innovation Report deep writing mode."""

    REPORT_OUTLINE = [
        "当前商业模式画布诊断",
        "突破要素",
        "创新方向延展",
        "高优先级 AI 提效场景",
        "差异化竞争力设计",
        "核心竞争力推进策略",
    ]

    @staticmethod
    def build_system_prompt() -> str:
        """Build the system prompt for report generation."""
        return """你是一位专业的AI创新顾问，负责为企业撰写AI创新转型报告。

## 核心原则（必须严格遵守）
1. **忠实于输入数据**：只能基于提供的企业画像、画布诊断、突破要素、场景推荐、案例匹配数据进行扩写润色，绝对不能改变任何业务决策结果
2. **禁止编造事实**：
   - 不能编造真实企业名称（使用"某企业"、"贵司"等代称）
   - 不能编造具体的ROI数字（可用"预计提升"、"有望改善"等定性表述）
   - 不能编造不存在的数据来源或案例
3. **保持专业客观**：使用咨询行业规范用语，避免过度营销化表述
4. **保留结果仪表盘章节**：必须完整输出指定章节，不得删减或合并

## 写作风格
- 结构清晰，每个章节有明确的小标题
- 使用表格、列表等形式呈现关键信息
- 语言精炼专业，避免冗余
- 适当使用数据可视化描述（文字描述图表）

## 输出格式
必须使用JSON格式输出，结构如下：
```json
{
  "sections": [
    {
      "key": "section_key",
      "title": "章节标题",
      "content": "章节主要内容",
      "bullets": ["要点1", "要点2"],
      "table": {"columns": ["列1", "列2"], "rows": [["数据1", "数据2"]]},
      "note": "补充说明（可选）"
    }
  ],
  "warnings": ["警告信息（如有）"]
}
```

## 禁止事项
- 禁止编造具体企业名称（如"华为"、"阿里巴巴"等真实企业名）
- 禁止编造具体ROI数字（如"提升23.5%"）
- 禁止编造不存在的案例或数据来源
- 禁止改变评分结果、推荐场景顺序等业务决策
"""

    @staticmethod
    def build_user_prompt(
        company_input: dict[str, Any],
        company_profile: dict[str, Any],
        canvas_diagnosis: dict[str, Any],
        top_scenarios: list[dict[str, Any]],
        case_recommendation: dict[str, Any] | None = None,
        breakthrough_elements: list[str] | None = None,
    ) -> str:
        """Build the user prompt with all context data."""
        sections = []

        sections.append("## 企业原始输入信息")
        sections.append(ReportWriterPrompt._format_input(company_input))

        sections.append("\n## 企业画像分析结果")
        sections.append(ReportWriterPrompt._format_profile(company_profile))

        sections.append("\n## 商业模式画布诊断")
        sections.append(ReportWriterPrompt._format_canvas(canvas_diagnosis))

        if breakthrough_elements:
            sections.append("\n## 选定突破要素")
            sections.append(ReportWriterPrompt._format_breakthrough(breakthrough_elements))

        sections.append("\n## 推荐AI场景")
        sections.append(ReportWriterPrompt._format_scenarios(top_scenarios))

        sections.append("\n## 输出要求")
        sections.append(f"请基于以上输入，撰写完整的AI创新转型报告，包含以下{len(ReportWriterPrompt.REPORT_OUTLINE)}个章节：")
        for i, title in enumerate(ReportWriterPrompt.REPORT_OUTLINE, 1):
            sections.append(f"{i}. {title}")
        sections.append("\n请以JSON格式输出，结构必须符合系统提示中定义的格式。")

        return "\n".join(sections)

    @staticmethod
    def _format_input(data: dict[str, Any]) -> str:
        """Format company input snapshot."""
        lines = []
        if data.get("company_name"):
            lines.append(f"- 企业名称: {data['company_name']}")
        if data.get("industry"):
            lines.append(f"- 所属行业: {data['industry']}")
        if data.get("company_size"):
            lines.append(f"- 企业规模: {data['company_size']}")
        if data.get("region"):
            lines.append(f"- 所在地区: {data['region']}")
        if data.get("annual_revenue_range"):
            lines.append(f"- 年营收范围: {data['annual_revenue_range']}")
        if data.get("core_products"):
            lines.append(f"- 核心产品/服务: {data['core_products']}")
        if data.get("target_customers"):
            lines.append(f"- 目标客户: {data['target_customers']}")
        if data.get("current_challenges"):
            lines.append(f"- 当前挑战: {data['current_challenges']}")
        if data.get("ai_goals"):
            lines.append(f"- AI目标: {data['ai_goals']}")
        if data.get("available_data"):
            lines.append(f"- 可用数据: {data['available_data']}")
        return "\n".join(lines) if lines else "暂无信息"

    @staticmethod
    def _format_profile(data: dict[str, Any]) -> str:
        """Format company profile."""
        lines = []
        if data.get("industry_position"):
            lines.append(f"- 行业定位: {data['industry_position']}")
        if data.get("business_model"):
            lines.append(f"- 商业模式: {data['business_model']}")
        if data.get("pain_points"):
            lines.append(f"- 痛点分析: {data['pain_points']}")
        if data.get("data_readiness"):
            lines.append(f"- 数据准备度: {data['data_readiness']}")
        if data.get("ai_opportunities"):
            lines.append(f"- AI机会点: {data['ai_opportunities']}")
        return "\n".join(lines) if lines else "暂无画像信息"

    @staticmethod
    def _format_canvas(data: dict[str, Any]) -> str:
        """Format canvas diagnosis."""
        lines = []
        if data.get("overall_score") is not None:
            lines.append(f"- 整体评分: {data['overall_score']}分")
        if data.get("weakest_blocks"):
            lines.append(f"- 薄弱环节: {', '.join(data['weakest_blocks'])}")
        if data.get("recommended_focus"):
            lines.append(f"- 建议聚焦: {', '.join(data['recommended_focus'])}")
        if data.get("canvas"):
            lines.append("\n画布详情:")
            canvas = data["canvas"]
            for key, value in canvas.items():
                if value and key != "model_config":
                    lines.append(f"  - {key}: {value}")
        return "\n".join(lines) if lines else "暂无画布诊断信息"

    @staticmethod
    def _format_scenarios(scenarios: list[dict[str, Any]]) -> str:
        """Format scenario recommendations."""
        if not scenarios:
            return "暂无推荐场景"

        lines = []
        for i, scenario in enumerate(scenarios, 1):
            lines.append(f"\n### 场景{i}: {scenario.get('name', '未命名')}")
            lines.append(f"- 类别: {scenario.get('category', '未分类')}")
            lines.append(f"- 评分: {scenario.get('score', 0)}分")
            lines.append(f"- 摘要: {scenario.get('summary', '暂无')}")
            if scenario.get("reasons"):
                lines.append(f"- 推荐理由: {', '.join(scenario['reasons'])}")
            if scenario.get("data_requirements"):
                lines.append(f"- 数据需求: {', '.join(scenario['data_requirements'])}")
        return "\n".join(lines)

    @staticmethod
    def _format_cases(data: dict[str, Any]) -> str:
        """Format case recommendations."""
        if not data or not data.get("top_cases"):
            return "暂无参考案例"

        lines = []
        for i, case in enumerate(data.get("top_cases", []), 1):
            lines.append(f"\n### 案例{i}: {case.get('title', '未命名')}")
            lines.append(f"- 行业: {case.get('industry', '未知')}")
            lines.append(f"- 匹配度: {case.get('fit_score', 0)}分")
            lines.append(f"- 摘要: {case.get('summary', '暂无')}")
            if case.get("match_reasons"):
                lines.append(f"- 匹配原因: {', '.join(case['match_reasons'])}")
            if case.get("cautions"):
                lines.append(f"- 注意事项: {', '.join(case['cautions'])}")
        return "\n".join(lines)

    @staticmethod
    def _format_breakthrough(elements: list[str]) -> str:
        if not elements:
            return "暂未选择突破要素。"
        joined = "、".join(elements)
        return f"管理层选定的 {len(elements)} 个突破要素：{joined}。建议在报告中围绕这些要素展开分析，并在差异化竞争力设计和路线图中重点体现。"
