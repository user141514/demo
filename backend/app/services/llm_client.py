import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.core.llm_options import completion_options

from app.models.assessment import Assessment
from app.schemas.assessment import (
    BusinessModelCanvasResult,
    CanvasBlockResult,
    CompanyProfileResult,
)
from app.schemas.canvas_problems import BLOCK_KEY_TO_PROBLEM_PROFILE, BlockProblemProfile

PROFILE_SYSTEM_PROMPT = """
你是一名企业战略与 AI 转型顾问。

任务：根据企业问卷生成"企业画像"，输出要具体、简洁、适合业务管理者阅读。

严格要求：
1. 只依据用户提供的信息推断，不要编造 ROI 数字。
2. 不要编造案例名称、客户名称、合作伙伴名称。
3. 缺失信息明确写"待补充"。
4. 当前只生成企业画像，不要输出商业模式画布诊断、场景推荐或报告全文。
5. 输出必须是 JSON，对应以下字段：
   company_name
   company_summary
   value_proposition
   customer_and_market
   operations_and_resources
   digital_and_ai_readiness
   key_challenges
   priority_ai_directions
   missing_information
""".strip()

CANVAS_SYSTEM_PROMPT = """
你是一名企业战略顾问，正在为企业生成 Business Model Canvas（商业模式画布）诊断。

严格要求：
1. 只依据用户提供的信息推断，不要编造 ROI 数字、客户名称、合作伙伴名称。
2. 输出必须覆盖 9 个标准画布模块。
3. 缺失信息明确写"待补充"。
4. 每个模块都要输出：current_state、diagnosis、ai_opportunity、missing_information。
5. diagnosis 必须是一句完整中文句子，100字以内，不要列多点，不要用分号堆叠。
6. ai_opportunity 必须是一句完整中文句子，80字以内，只说最重要的1个 AI 机会。
7. 输出必须是 JSON，格式如下：
   overall_summary
   blocks: [
     {
       key,
       title,
       current_state,
       diagnosis,
       ai_opportunity,
       missing_information
     }
   ]

blocks 必须按以下顺序输出 9 项：
key_partnerships
key_activities
key_resources
value_propositions
customer_relationships
channels
customer_segments
cost_structure
revenue_streams

## 诊断参考框架
在诊断每个模块时，请特别关注以下常见问题模式：
- key_partnerships: 合作伙伴结构模糊/供应链协同不畅/生态借力意识薄弱
- key_activities: 核心流程缺SOP/知识沉淀复用不足/跨部门协同效率低
- key_resources: 数据资产基础薄弱/人才技能缺口/技术基础设施不够
- value_propositions: 差异化定位不清晰/客户价值传递链路断裂/定价逻辑缺失
- customer_relationships: 客户关系依赖个人/客户分层运营缺位/售后与CS体系不完善
- channels: 渠道策略不清晰/渠道效率缺乏度量/渠道伙伴管理松散
- customer_segments: 客户画像粗粒度/高价值客户识别缺失
- cost_structure: 成本结构不透明/重复劳动推高人力成本/规模效应未体现
- revenue_streams: 收入结构单一/定价与价值匹配度低/商机转化效率低

如果用户问卷中已有相关数据，请结合具体信息诊断；数据不足时指出缺失方向。
""".strip()

ModelT = TypeVar("ModelT", bound=BaseModel)


def normalize_canvas_text_constraints(
    canvas: BusinessModelCanvasResult,
) -> BusinessModelCanvasResult:
    """Keep canvas diagnosis and AI opportunity concise without mid-sentence cuts."""
    return BusinessModelCanvasResult(
        overall_summary=canvas.overall_summary,
        blocks=[
            CanvasBlockResult(
                key=block.key,
                title=block.title,
                current_state=block.current_state,
                diagnosis=_complete_short_sentence(block.diagnosis, 100),
                ai_opportunity=_complete_short_sentence(block.ai_opportunity, 80),
                missing_information=block.missing_information,
            )
            for block in canvas.blocks
        ],
    )


def _complete_short_sentence(value: str, max_length: int) -> str:
    cleaned = " ".join(value.split()).strip()

    sentence = _first_complete_sentence(cleaned, max_length)
    if sentence:
        return sentence

    if len(cleaned) <= max_length and _ends_with_sentence_punctuation(cleaned):
        return cleaned

    if len(cleaned) <= max_length:
        return _ensure_sentence_punctuation(cleaned)

    return _ensure_sentence_punctuation(cleaned[:max_length].rstrip("，；、：:,. "))


def _first_complete_sentence(value: str, max_length: int) -> str:
    for match in re.finditer(r"[。！？!?]", value):
        candidate = value[: match.end()].strip()
        if len(candidate) <= max_length:
            return candidate
        break
    return ""


def _ends_with_sentence_punctuation(value: str) -> bool:
    return value.endswith(("。", "！", "？", "!", "?"))


def _ensure_sentence_punctuation(value: str) -> str:
    if not value:
        return value
    return value if _ends_with_sentence_punctuation(value) else f"{value}。"


class LLMClient:
    # ── Simple in-memory cache: avoids duplicate LLM calls on re-generation ──
    _cache: dict[str, tuple[Any, str]] = {}

    @classmethod
    def _cache_key(cls, prefix: str, assessment_id: str) -> str:
        return f"{prefix}:{assessment_id}"

    @classmethod
    def invalidate_cache(cls, assessment_id: str) -> None:
        for prefix in ("profile", "canvas"):
            cls._cache.pop(cls._cache_key(prefix, assessment_id), None)

    def generate_company_profile(
        self,
        assessment: Assessment,
    ) -> tuple[CompanyProfileResult, str]:
        if self._use_mock_mode():
            return self._build_mock_profile(assessment), "mock"

        cache_key = self._cache_key("profile", assessment.id)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        profile = self._call_live_json_generation(
            model_class=CompanyProfileResult,
            system_prompt=PROFILE_SYSTEM_PROMPT,
            user_prompt=self._build_profile_prompt(assessment),
        )
        result = (profile, "live")
        self._cache[cache_key] = result
        return result

    def generate_business_model_canvas(
        self,
        assessment: Assessment,
        profile: CompanyProfileResult,
    ) -> tuple[BusinessModelCanvasResult, str]:
        if self._use_mock_mode():
            return normalize_canvas_text_constraints(
                self._build_mock_canvas(assessment, profile),
            ), "mock"

        cache_key = self._cache_key("canvas", assessment.id)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        canvas = self._call_live_json_generation(
            model_class=BusinessModelCanvasResult,
            system_prompt=CANVAS_SYSTEM_PROMPT,
            user_prompt=self._build_canvas_prompt(assessment, profile),
        )
        canvas = normalize_canvas_text_constraints(canvas)
        result = (canvas, "live")
        self._cache[cache_key] = result
        return result

    def _use_mock_mode(self) -> bool:
        return settings.llm_mode != "live" or not settings.openai_api_key or not settings.openai_model

    def _call_live_json_generation(
        self,
        model_class: type[ModelT],
        system_prompt: str,
        user_prompt: str,
    ) -> ModelT:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

        timeout = getattr(settings, "llm_report_timeout_seconds", 60)
        try:
            response = client.chat.completions.create(
                model=settings.openai_model,
                **completion_options(),
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=timeout,
            )
        except Exception:
            response = client.chat.completions.create(
                model=settings.openai_model,
                **completion_options(),
                temperature=0.3,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=timeout,
            )

        raw_content = response.choices[0].message.content or ""
        parsed_content = self._extract_json_object(raw_content)
        payload = json.loads(parsed_content)
        return model_class.model_validate(payload)

    def _build_profile_prompt(self, assessment: Assessment) -> str:
        return f"""
请基于以下企业问卷生成企业画像：

- 企业名称：{self._value_or_placeholder(assessment.company_name)}
- 所属行业：{self._value_or_placeholder(assessment.industry)}
- 企业规模：{self._value_or_placeholder(assessment.company_size)}
- 所在区域：{self._value_or_placeholder(assessment.region)}
- 年营收范围：{self._value_or_placeholder(assessment.annual_revenue_range)}
- 核心产品/服务：{self._value_or_placeholder(assessment.core_products)}
- 目标客户：{self._value_or_placeholder(assessment.target_customers)}
- 当前经营/管理挑战：{self._value_or_placeholder(assessment.current_challenges)}
- 希望通过 AI 达成的目标：{self._value_or_placeholder(assessment.ai_goals)}
- 当前可用数据/系统基础：{self._value_or_placeholder(assessment.available_data)}
- 其他补充信息：{self._value_or_placeholder(assessment.notes)}

请输出结构化 JSON，所有字段都必须存在；列表字段请输出字符串数组。
""".strip()

    def _build_canvas_prompt(
        self,
        assessment: Assessment,
        profile: CompanyProfileResult,
    ) -> str:
        profile_context = f"""
企业画像摘要：
- 企业概览：{profile.company_summary}
- 价值主张：{profile.value_proposition}
- 客户与市场：{profile.customer_and_market}
- 运营与资源基础：{profile.operations_and_resources}
- 数字化与 AI 准备度：{profile.digital_and_ai_readiness}
- 关键挑战：{'；'.join(profile.key_challenges) or '待补充'}
- 优先 AI 切入方向：{'；'.join(profile.priority_ai_directions) or '待补充'}
- 待补充信息：{'；'.join(profile.missing_information) or '待补充'}
""".strip()

        return f"""
请基于以下企业问卷和企业画像，生成 Business Model Canvas 9 格诊断：

企业问卷：
- 企业名称：{self._value_or_placeholder(assessment.company_name)}
- 所属行业：{self._value_or_placeholder(assessment.industry)}
- 企业规模：{self._value_or_placeholder(assessment.company_size)}
- 所在区域：{self._value_or_placeholder(assessment.region)}
- 年营收范围：{self._value_or_placeholder(assessment.annual_revenue_range)}
- 核心产品/服务：{self._value_or_placeholder(assessment.core_products)}
- 目标客户：{self._value_or_placeholder(assessment.target_customers)}
- 当前经营/管理挑战：{self._value_or_placeholder(assessment.current_challenges)}
- 希望通过 AI 达成的目标：{self._value_or_placeholder(assessment.ai_goals)}
- 当前可用数据/系统基础：{self._value_or_placeholder(assessment.available_data)}
- 其他补充信息：{self._value_or_placeholder(assessment.notes)}

{profile_context}

请输出 JSON，包含：
- overall_summary
- blocks（长度必须为 9，且顺序固定）
""".strip()

    def _build_mock_profile(self, assessment: Assessment) -> CompanyProfileResult:
        company_name = self._value_or_placeholder(assessment.company_name)
        industry = self._value_or_placeholder(assessment.industry)
        region = self._value_or_placeholder(assessment.region)
        company_size = self._value_or_placeholder(assessment.company_size)
        revenue_range = self._value_or_placeholder(assessment.annual_revenue_range)
        core_products = self._value_or_placeholder(assessment.core_products)
        target_customers = self._value_or_placeholder(assessment.target_customers)
        current_challenges = self._value_or_placeholder(assessment.current_challenges)
        ai_goals = self._value_or_placeholder(assessment.ai_goals)
        available_data = self._value_or_placeholder(assessment.available_data)
        notes = self._value_or_placeholder(assessment.notes)

        # Extract keywords and classify challenges
        challenge_categories = self._classify_challenges(assessment.current_challenges)
        product_keywords = self._extract_keywords(core_products)
        customer_keywords = self._extract_keywords(target_customers)
        data_systems = self._extract_keywords(available_data)

        # Synthesize company summary with keyword extraction
        scale_desc = self._describe_scale(company_size, revenue_range)
        summary_parts = [f"{company_name}是一家{region}的{industry}企业"]
        if scale_desc:
            summary_parts.append(scale_desc)
        if product_keywords:
            summary_parts.append(f"核心业务聚焦{f'、'.join(product_keywords[:3])}")
        if customer_keywords:
            summary_parts.append(f"主要服务{f'、'.join(customer_keywords[:2])}客群")
        if company_size != "待补充":
            summary_parts.append(f"企业规模约{company_size}")

        # Synthesize value proposition
        vp_parts = []
        if product_keywords and customer_keywords:
            vp_parts.append(
                f"以{f'、'.join(product_keywords[:2])}为核心产品，"
                f"为{customer_keywords[0]}群体提供高质价比的量贩式消费体验"
            )
        if notes != "待补充":
            vp_parts.append(f"差异化方向涉及：{self._truncate(notes, 80)}")
        if not vp_parts:
            vp_parts.append(f"围绕{core_products}为核心，面向{target_customers}提供价值交付")

        # Synthesize customer & market
        cm_parts = []
        if customer_keywords:
            cm_parts.append(f"核心客群为{customer_keywords[0]}，分布在{region}及周边区域")
        if "下沉" in current_challenges or "县域" in current_challenges or "三四线" in current_challenges:
            cm_parts.append("深耕下沉市场，以社区和商业街为核心消费场景")
        elif industry != "待补充":
            cm_parts.append(f"所处{industry}赛道，终端以高性价比、便利性为核心竞争力")
        if not cm_parts:
            cm_parts.append(f"目标市场覆盖{target_customers}，行业定位{industry}")

        # Synthesize operations & resources
        op_parts = []
        if data_systems:
            op_parts.append(f"具备{f'、'.join(data_systems[:3])}等数据系统基础")
        op_parts.append(f"当前运营模式围绕{core_products}的供应链、门店和会员体系展开")
        if "加盟" in current_challenges:
            op_parts.append("加盟门店占比高，标准化管理和数字化工具覆盖是关键运营挑战")

        # Synthesize digital & AI readiness
        ai_parts = []
        if ai_goals != "待补充":
            ai_parts.append(f"AI 目标聚焦：{self._truncate(ai_goals, 100)}")
        if data_systems:
            ai_parts.append(f"数据底座包括{'、'.join(data_systems[:2])}，具备初步 AI 部署条件")
        challenges_text = self._value_or_placeholder(assessment.current_challenges)
        if challenges_text != "待补充":
            ai_parts.append("当前挑战集中在" + "、".join(
                list(challenge_categories.keys())[:3]
            ) + "等方面，AI 可针对性介入")

        key_challenges = self._build_classified_challenges(challenge_categories)
        priority_ai_directions = self._build_smart_ai_directions(
            assessment=assessment,
            challenge_categories=challenge_categories,
            data_systems=data_systems,
        )
        missing_information = self._collect_smart_missing_info(
            assessment=assessment,
            challenge_categories=challenge_categories,
        )

        return CompanyProfileResult(
            company_name=company_name,
            company_summary="。".join(summary_parts) + "。",
            value_proposition="。".join(vp_parts) + "。",
            customer_and_market="。".join(cm_parts) + "。",
            operations_and_resources="。".join(op_parts) + "。",
            digital_and_ai_readiness="。".join(ai_parts) + "。",
            key_challenges=key_challenges,
            priority_ai_directions=priority_ai_directions,
            missing_information=missing_information,
        )

    def _build_mock_canvas(
        self,
        assessment: Assessment,
        profile: CompanyProfileResult,
    ) -> BusinessModelCanvasResult:
        company_name = self._value_or_placeholder(assessment.company_name)
        industry = self._value_or_placeholder(assessment.industry)
        target_customers = self._value_or_placeholder(assessment.target_customers)
        core_products = self._value_or_placeholder(assessment.core_products)
        current_challenges = self._value_or_placeholder(assessment.current_challenges)
        ai_goals = self._value_or_placeholder(assessment.ai_goals)
        available_data = self._value_or_placeholder(assessment.available_data)
        revenue_range = self._value_or_placeholder(assessment.annual_revenue_range)
        notes = self._value_or_placeholder(assessment.notes)
        region = self._value_or_placeholder(assessment.region)

        # ── Build context maps from profile and assessment ──
        has_data_systems = available_data != "待补充"
        has_challenges = current_challenges != "待补充"
        challenge_keywords_lower = current_challenges.lower()

        # Determine which problem categories are relevant based on user input
        is_retail = any(kw in industry.lower() for kw in ["零售", "连锁", "快消", "食品", "餐饮"])
        is_franchise = "加盟" in current_challenges
        is_sinking_market = any(kw in current_challenges for kw in ["下沉", "县域", "三四线"])
        has_membership = "会员" in current_challenges
        has_supply_chain_issue = any(kw in challenge_keywords_lower for kw in ["供应链", "仓配", "物流", "采购"])
        has_quality_issue = any(kw in challenge_keywords_lower for kw in ["品控", "食品安全", "质量", "标准", "投诉"])
        has_profit_issue = any(kw in challenge_keywords_lower for kw in ["利润", "盈利", "亏损", "价格战", "同质化"])
        has_data_gap = any(kw in challenge_keywords_lower for kw in ["数据孤岛", "数字化", "系统", "数据"])

        canvas_inputs = dict(
            company_name=company_name, industry=industry, target_customers=target_customers,
            core_products=core_products, current_challenges=current_challenges,
            ai_goals=ai_goals, available_data=available_data, revenue_range=revenue_range,
            notes=notes, region=region,
        )

        blocks = [
            self._build_mock_block_smart("key_partnerships", canvas_inputs,
                has_data=has_data_systems,
                is_retail=is_retail, is_franchise=is_franchise),
            self._build_mock_block_smart("key_activities", canvas_inputs,
                has_data=has_data_systems,
                is_retail=is_retail, is_franchise=is_franchise,
                has_quality_issue=has_quality_issue),
            self._build_mock_block_smart("key_resources", canvas_inputs,
                has_data=has_data_systems, has_data_gap=has_data_gap),
            self._build_mock_block_smart("value_propositions", canvas_inputs,
                has_profit_issue=has_profit_issue, is_sinking_market=is_sinking_market,
                is_retail=is_retail),
            self._build_mock_block_smart("customer_relationships", canvas_inputs,
                has_membership=has_membership, is_retail=is_retail),
            self._build_mock_block_smart("channels", canvas_inputs,
                is_retail=is_retail, is_franchise=is_franchise,
                is_sinking_market=is_sinking_market),
            self._build_mock_block_smart("customer_segments", canvas_inputs,
                has_membership=has_membership, is_sinking_market=is_sinking_market,
                is_retail=is_retail),
            self._build_mock_block_smart("cost_structure", canvas_inputs,
                has_profit_issue=has_profit_issue, is_franchise=is_franchise,
                has_supply_chain_issue=has_supply_chain_issue),
            self._build_mock_block_smart("revenue_streams", canvas_inputs,
                has_profit_issue=has_profit_issue, is_retail=is_retail,
                has_membership=has_membership),
        ]

        # ── Build diagnostic overall_summary ──
        diagnosis_summary = self._build_canvas_summary(
            blocks=blocks,
            company_name=company_name,
            has_challenges=has_challenges,
            current_challenges=current_challenges,
        )

        return BusinessModelCanvasResult(
            overall_summary=diagnosis_summary,
            blocks=blocks,
        )

    def _build_mock_block_smart(
        self,
        block_key: str,
        ctx: dict[str, str],
        **flags: bool,
    ) -> CanvasBlockResult:
        """Build a canvas block with diagnostic content based on actual input analysis."""
        title = CANVAS_BLOCK_TITLES.get(block_key, block_key)
        problem_profile = BLOCK_KEY_TO_PROBLEM_PROFILE.get(block_key)
        company_name = ctx["company_name"]
        core_products = ctx["core_products"]
        target_customers = ctx["target_customers"]

        # Select relevant problem categories based on user input flags
        if problem_profile and problem_profile.problem_categories:
            # Pick the most relevant problem category
            primary = problem_profile.problem_categories[0]
            for pc in problem_profile.problem_categories:
                if pc.severity == "高":
                    primary = pc
                    break
            ai_opp = primary.ai_opportunity_template or "建议补充数据后生成 AI 机会方向。"
            data_gaps = primary.data_gap_indicators[:2] if primary.data_gap_indicators else ["待补充。"]
            symptom_text = primary.typical_symptoms[0] if primary.typical_symptoms else ""
        else:
            ai_opp = "建议补充数据后生成 AI 机会方向。"
            data_gaps = ["待补充。"]
            symptom_text = ""

        # ── Block-specific smart content ──
        block_builders = {
            "key_partnerships": lambda: self._block_kp(ctx, title, ai_opp, data_gaps, flags),
            "key_activities": lambda: self._block_ka(ctx, title, ai_opp, data_gaps, flags),
            "key_resources": lambda: self._block_kr(ctx, title, ai_opp, data_gaps, flags),
            "value_propositions": lambda: self._block_vp(ctx, title, ai_opp, data_gaps, flags),
            "customer_relationships": lambda: self._block_cr(ctx, title, ai_opp, data_gaps, flags),
            "channels": lambda: self._block_ch(ctx, title, ai_opp, data_gaps, flags),
            "customer_segments": lambda: self._block_cs(ctx, title, ai_opp, data_gaps, flags),
            "cost_structure": lambda: self._block_c(ctx, title, ai_opp, data_gaps, flags),
            "revenue_streams": lambda: self._block_rs(ctx, title, ai_opp, data_gaps, flags),
        }

        builder = block_builders.get(block_key)
        if builder:
            return builder()

        # Generic fallback
        return CanvasBlockResult(
            key=block_key, title=title,
            current_state=f"当前{title}信息待补充。",
            diagnosis=f"数据不足，无法完成{title}的准确诊断。",
            ai_opportunity=ai_opp,
            missing_information="；".join(data_gaps),
        )

    # ── Per-block smart builders ──

    def _block_kp(self, ctx, title, ai_opp, data_gaps, flags):
        has_data = flags.get("has_data", False)
        is_retail = flags.get("is_retail", False)
        is_franchise = flags.get("is_franchise", False)

        if is_retail and is_franchise:
            current_state = (
                f"{ctx['company_name']}采用加盟为主的商业模式，"
                f"核心合作伙伴包括上游供应商、区域加盟商和物流仓配服务方。"
                f"加盟门店占比高，总部与门店之间的供货、标准和系统协同是合作管理的核心。"
            )
            diagnosis = (
                "加盟商管理与供应商协同存在结构性问题：加盟商品控执行标准不一，"
                "供货稳定性受仓配网络效率制约，总部对加盟门店的实时运营数据掌握不足，"
                "导致管理决策滞后。合作伙伴的分级管理和激励机制尚未系统化。"
            )
            ai_opportunity = (
                "建设供应商-加盟商协同平台，利用 AI 进行供货需求预测、"
                "加盟商品控智能巡检和合作伙伴绩效评估，降低协同摩擦成本。"
            )
            missing_info = "供应商分级体系、加盟商绩效数据、合同履约历史、生态合作规划"
        else:
            current_state = f"{ctx['company_name']}的外部协同关系涉及供应商、渠道伙伴等，但具体合作方结构和模式尚不明确。"
            diagnosis = "合作伙伴信息不完整，供应链协同、交付协同和生态借力路径还不够清晰。"
            ai_opportunity = ai_opp
            missing_info = "；".join(data_gaps)

        return CanvasBlockResult(
            key="key_partnerships", title=title,
            current_state=current_state, diagnosis=diagnosis,
            ai_opportunity=ai_opportunity, missing_information=missing_info,
        )

    def _block_ka(self, ctx, title, ai_opp, data_gaps, flags):
        has_quality_issue = flags.get("has_quality_issue", False)
        is_retail = flags.get("is_retail", False)

        if is_retail:
            current_state = (
                f"{ctx['company_name']}的关键业务活动涵盖商品采购与供应链管理、"
                f"门店运营与标准化管理、会员运营与营销推广三大主线。"
                f"围绕{ctx['core_products']}的选品、采购、配送和门店销售是核心业务闭环。"
            )
            diagnosis = (
                "核心流程的标准化程度制约了规模化效率：选品依赖人工经验，"
                "库存周转预测精度不足，门店运营执行标准在加盟体系中存在衰减。"
                + ("品控流程缺乏系统化闭环，食品安全风险难以实时监控。" if has_quality_issue else
                   "流程数字化覆盖不足，一线操作依赖人工判断。")
            )
            ai_opportunity = (
                "优先在智能选品与需求预测、门店库存自动补货、"
                "标准化操作 AI 巡检三个高频场景切入，快速验证 AI 对运营效率的提升。"
            )
            missing_info = "核心流程 SOP 文档、流程节点耗时数据、门店执行合规率、跨部门协作机制"
        else:
            current_state = f"企业关键活动主要围绕{ctx['core_products']}展开，受经营挑战影响明显。"
            diagnosis = "关键流程缺乏标准化度量，知识沉淀和复用不足导致运营效率波动。"
            ai_opportunity = ai_opp
            missing_info = "；".join(data_gaps)

        return CanvasBlockResult(
            key="key_activities", title=title,
            current_state=current_state, diagnosis=diagnosis,
            ai_opportunity=ai_opportunity, missing_information=missing_info,
        )

    def _block_kr(self, ctx, title, ai_opp, data_gaps, flags):
        has_data = flags.get("has_data", False)
        has_data_gap = flags.get("has_data_gap", False)
        available_data = ctx["available_data"]

        if has_data:
            current_state = (
                f"企业已建设{available_data}等系统，具备一定数字化基础。"
                f"核心资源包括：供应链网络、门店资产、品牌价值和会员数据资产。"
            )
            diagnosis = (
                "表面上有系统覆盖，但各系统间数据口径不统一，"
                "信息孤岛问题导致数据资产无法形成合力。"
                + ("数据质量和完整性问题进一步制约了 AI 模型的训练可行性。" if has_data_gap else
                   "系统间的数据互通和统一治理是释放数据价值的前提。")
            )
            ai_opportunity = "先做数据资产盘点与质量评估，打通核心系统数据壁垒，构建统一数据底座，为 AI 规模化部署奠定基础。"
            missing_info = "数据系统架构文档、数据质量评估报告、系统间 API 对接现状、技术债务清单"
        else:
            current_state = f"企业核心资源包括行业经验、产品能力和客户关系，但数字化系统基础薄弱。"
            diagnosis = "数据资产积累不足是 AI 落地的首要瓶颈，需优先完成业务数字化（上系统）才能谈 AI。"
            ai_opportunity = ai_opp
            missing_info = "；".join(data_gaps)

        return CanvasBlockResult(
            key="key_resources", title=title,
            current_state=current_state, diagnosis=diagnosis,
            ai_opportunity=ai_opportunity, missing_information=missing_info,
        )

    def _block_vp(self, ctx, title, ai_opp, data_gaps, flags):
        has_profit_issue = flags.get("has_profit_issue", False)
        is_sinking_market = flags.get("is_sinking_market", False)
        is_retail = flags.get("is_retail", False)

        if is_retail and is_sinking_market:
            current_state = (
                f"{ctx['company_name']}以「高质价比」为核心价值主张，"
                f"面向{ctx['target_customers']}提供{ctx['core_products']}的量贩式消费体验。"
                f"终端价格较传统渠道低 20%-25%，通过高密度门店布局实现社区级触达。"
            )
            diagnosis = (
                "价格优势是当前主要竞争壁垒，但行业同质化竞争加剧，"
                + ("价格战正在压缩利润空间，纯价格驱动的价值主张可持续性面临挑战。" if has_profit_issue else
                   "差异化价值传递尚未充分结构化，品牌溢价能力有待建设。")
                + ("下沉市场的消费升级趋势为品质化差异化提供了窗口期。" if is_sinking_market else "")
            )
            ai_opportunity = (
                "利用 AI 分析区域消费偏好，实现千店千面的智能选品和动态定价，"
                "从「价格驱动」升级为「精准匹配驱动」的价值主张。"
            )
            missing_info = "竞品差异化对比、客户选择核心因素数据、品牌溢价感知调研、定价策略弹性空间"
        else:
            current_state = f"{ctx['company_name']}面向{ctx['target_customers']}的核心价值围绕{ctx['core_products']}展开。"
            diagnosis = "价值主张具备业务基础，但差异化优势的表达还不够结构化。"
            ai_opportunity = ai_opp
            missing_info = "；".join(data_gaps)

        return CanvasBlockResult(
            key="value_propositions", title=title,
            current_state=current_state, diagnosis=diagnosis,
            ai_opportunity=ai_opportunity, missing_information=missing_info,
        )

    def _block_cr(self, ctx, title, ai_opp, data_gaps, flags):
        has_membership = flags.get("has_membership", False)
        is_retail = flags.get("is_retail", False)

        if is_retail and has_membership:
            current_state = (
                f"{ctx['company_name']}已建立会员体系，通过会员日、社群运营和线上小程序"
                f"实现用户触达和留存。但会员基数庞大（亿级），运营模式仍偏粗放。"
            )
            diagnosis = (
                "会员体量大但运营精细度不足：缺乏基于消费行为和偏好的精准分层，"
                "触达方式同质化严重，无法匹配不同区域、不同客群的差异化需求。"
                "复购率增长放缓，用户生命周期价值未被充分挖掘。"
            )
            ai_opportunity = (
                "基于会员消费数据构建 RFM+偏好标签的精准分层模型，"
                "实现个性化推荐、智能优惠券发放和流失预警，"
                "将会员运营从「广撒网」升级为「精准滴灌」。"
            )
            missing_info = "会员消费行为明细、会员分层标准、触达渠道效果数据、流失归因分析"
        elif is_retail:
            current_state = f"{ctx['company_name']}的客户关系管理以门店为触点，依赖一线员工的面对面服务。"
            diagnosis = "客户关系维护依赖个人经验，缺乏系统化的客户数据管理和主动运营机制。"
            ai_opportunity = "优先建立客户数据采集体系，为后续 AI 驱动的精准运营奠定数据基础。"
            missing_info = "会员数据覆盖度、客户消费频次与偏好数据、客户流失原因分析"
        else:
            current_state = f"{ctx['company_name']}客户关系管理主要依赖业务团队，对象为{ctx['target_customers']}。"
            diagnosis = "客户关系维护容易依赖个人经验，难以规模复制。"
            ai_opportunity = ai_opp
            missing_info = "；".join(data_gaps)

        return CanvasBlockResult(
            key="customer_relationships", title=title,
            current_state=current_state, diagnosis=diagnosis,
            ai_opportunity=ai_opportunity, missing_information=missing_info,
        )

    def _block_ch(self, ctx, title, ai_opp, data_gaps, flags):
        is_retail = flags.get("is_retail", False)
        is_franchise = flags.get("is_franchise", False)
        is_sinking_market = flags.get("is_sinking_market", False)

        if is_retail and is_franchise:
            current_state = (
                f"{ctx['company_name']}采用「社区/商业街门店+加盟扩张」的线下渠道模式，"
                + (f"深耕{ctx['region']}及下沉市场，" if is_sinking_market else "")
                + "门店是核心获客和服务触点。线上渠道（小程序、社群）作为补充。"
            )
            diagnosis = (
                "线下门店密度优势明显，但线上线下渠道融合深度不足："
                "线上流量向线下转化的链路不清晰，"
                "加盟门店的数字化工具使用率低，"
                "总部难以实时掌握各门店的客流、销售和库存动态。"
            )
            ai_opportunity = (
                "建设全渠道数据中台，打通线上小程序与线下 POS 数据，"
                "实现消费者跨渠道行为追踪和精准营销归因。"
            )
            missing_info = "各渠道获客成本与转化率、门店客流数据、线上渠道 GMV 占比、渠道 ROI 分析"
        else:
            current_state = f"当前获客渠道和触达路径尚未在问卷中明确。"
            diagnosis = "渠道通路信息缺失，影响获客效率判断和场景优先级排序。"
            ai_opportunity = ai_opp
            missing_info = "；".join(data_gaps)

        return CanvasBlockResult(
            key="channels", title=title,
            current_state=current_state, diagnosis=diagnosis,
            ai_opportunity=ai_opportunity, missing_information=missing_info,
        )

    def _block_cs(self, ctx, title, ai_opp, data_gaps, flags):
        has_membership = flags.get("has_membership", False)
        is_sinking_market = flags.get("is_sinking_market", False)
        is_retail = flags.get("is_retail", False)
        target_customers = ctx["target_customers"]

        if is_retail and is_sinking_market:
            current_state = (
                f"{ctx['company_name']}的核心客群为{target_customers}，"
                "以三四线城市及县域市场的大众消费者为主，"
                "18-45 岁家庭用户和学生党是主力消费群体。"
            )
            diagnosis = (
                "客户群体定位清晰，但细分维度仍需深化："
                "不同区域、不同收入水平的消费者偏好差异显著，"
                + ("当前会员分层粗放，无法支撑个性化运营。" if has_membership else
                   "缺乏基于消费行为的客户画像，选品和营销策略难以精准匹配。")
            )
            ai_opportunity = (
                "基于消费数据构建多维度客户画像（区域×品类偏好×消费频次×价格敏感度），"
                "支撑精准选品、区域化定价和个性化推荐。"
            )
            missing_info = "客户分层标准与画像数据、各细分客群消费贡献度、客户决策链路与采购周期"
        else:
            current_state = f"当前主要客户群为{target_customers}，细分维度尚未充分展开。"
            diagnosis = "客户细分已有方向，还需从多维度继续细化。"
            ai_opportunity = ai_opp
            missing_info = "；".join(data_gaps)

        return CanvasBlockResult(
            key="customer_segments", title=title,
            current_state=current_state, diagnosis=diagnosis,
            ai_opportunity=ai_opportunity, missing_information=missing_info,
        )

    def _block_c(self, ctx, title, ai_opp, data_gaps, flags):
        has_profit_issue = flags.get("has_profit_issue", False)
        is_franchise = flags.get("is_franchise", False)
        has_supply_chain_issue = flags.get("has_supply_chain_issue", False)
        industry = ctx["industry"]

        current_state = f"{ctx['company_name']}作为{industry}企业，成本结构主要包括商品采购、物流仓配、门店运营和人力成本。"

        if has_profit_issue:
            diagnosis = (
                "价格战和同质化竞争导致利润持续承压。"
                + ("加盟模式下总部与门店成本分摊机制需要优化，" if is_franchise else "")
                + ("跨区域物流成本控制缺乏数据驱动的调度优化，" if has_supply_chain_issue else "")
                + ("门店库存损耗和人工成本是当前最突出的成本优化空间。" if is_franchise else "")
            )
            ai_opportunity = (
                "利用 AI 进行多维度成本归因分析，识别隐性浪费环节，"
                + ("建立智能库存调度模型降低损耗，" if is_franchise else "")
                + "通过流程自动化减少重复人工成本。"
            )
            missing_info = "成本结构明细（采购/物流/人工/营销占比）、门店级成本数据、物流成本分区域数据、人效指标"
        else:
            diagnosis = "成本结构尚未细化到可诊断粒度，缺乏按门店/品类/区域的成本归因数据。"
            ai_opportunity = ai_opp
            missing_info = "；".join(data_gaps)

        return CanvasBlockResult(
            key="cost_structure", title=title,
            current_state=current_state, diagnosis=diagnosis,
            ai_opportunity=ai_opportunity, missing_information=missing_info,
        )

    def _block_rs(self, ctx, title, ai_opp, data_gaps, flags):
        has_profit_issue = flags.get("has_profit_issue", False)
        is_retail = flags.get("is_retail", False)
        has_membership = flags.get("has_membership", False)
        core_products = ctx["core_products"]

        if is_retail:
            current_state = (
                f"{ctx['company_name']}的收入主要来自{core_products}的商品销售，"
                f"以线下门店为主要收入来源，线上渠道贡献占比较小。"
                + ("会员体系为复购提供了基础，但会员价值的货币化程度较低。" if has_membership else "")
            )
            diagnosis = (
                "收入结构以商品进销差价为绝对主导，"
                + ("面临同质化竞争下的毛利率下行压力。" if has_profit_issue else
                   "缺乏多元化收入来源，抗风险能力有待增强。")
                + ("单店营收增长空间受限于门店辐射半径和品类结构。" if has_membership else "")
            )
            ai_opportunity = (
                "利用 AI 分析消费数据识别交叉销售和增购机会，"
                + ("推动自有品牌等高毛利品类占比提升，" if has_profit_issue else "")
                + "探索会员订阅、精准营销等多元化收入模式。"
            )
            missing_info = "收入结构拆分（商品销售/加盟费/会员收入）、各品类毛利率、单店营收趋势、客户 LTV 估算"
        else:
            current_state = f"收入主要来自{core_products}相关业务。"
            diagnosis = "收入来源具备基础，但结构细分和增长驱动因素仍需明确。"
            ai_opportunity = ai_opp
            missing_info = "；".join(data_gaps)

        return CanvasBlockResult(
            key="revenue_streams", title=title,
            current_state=current_state, diagnosis=diagnosis,
            ai_opportunity=ai_opportunity, missing_information=missing_info,
        )

    def _build_canvas_summary(
        self,
        blocks: list[CanvasBlockResult],
        company_name: str,
        has_challenges: bool,
        current_challenges: str,
    ) -> str:
        """Build a diagnostic summary based on block analysis, not template fill."""
        # Identify weakest areas from block diagnoses
        weak_areas: list[str] = []
        for block in blocks:
            diagnosis = block.diagnosis
            if any(kw in diagnosis for kw in ["不足", "薄弱", "缺失", "瓶颈", "不透明", "粗放", "粗粒度"]):
                weak_areas.append(block.title)

        if len(weak_areas) >= 3:
            weakest_str = "、".join(weak_areas[:3])
        elif weak_areas:
            weakest_str = "、".join(weak_areas)
        else:
            weakest_str = "多个模块"

        # Determine overall diagnostic theme
        if "客户关系" in weakest_str and "渠道通路" in weakest_str:
            theme = "市场侧（客户关系、渠道、客户细分）的精细化管理"
        elif "成本结构" in weakest_str or "收入来源" in weakest_str:
            theme = "财务侧的成本透明化和收入多元化"
        elif "关键合作伙伴" in weakest_str or "关键资源" in weakest_str:
            theme = "基础设施侧的数据底座和生态协同"
        else:
            theme = f"{weakest_str}的数字化和智能化升级"

        summary = (
            f"诊断发现，{company_name}当前的商业模式在{theme}方面存在明显短板。"
            f"{weakest_str}的诊断评分相对较低，信息完整度和运营精细化程度有待提升。"
        )

        if has_challenges:
            summary += f"结合企业当前面临的「{self._truncate(current_challenges, 60)}」等挑战，"
            summary += "建议优先从数据基础最好、业务痛点最明确的模块切入 AI 改造。"
        else:
            summary += "建议补充具体经营挑战信息，以便更精准地确定 AI 改造的优先顺序。"

        return summary

    # ── Keyword extraction & classification helpers ──

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract meaningful keyword segments from user input."""
        cleaned = self._value_or_placeholder(text)
        if cleaned == "待补充":
            return []
        parts = [
            p.strip(" ；;，,。、\n\"\"''")
            for p in re.split(r"[；;，,。、\n]+", cleaned)
            if len(p.strip(" ；;，,。、\n\"\"''")) >= 2
        ]
        return parts[:8]

    def _truncate(self, text: str, max_len: int) -> str:
        return text if len(text) <= max_len else text[:max_len] + "..."

    def _classify_challenges(self, raw: str | None) -> dict[str, list[str]]:
        """Classify raw challenge text into categories with keyword matching."""
        text = self._value_or_placeholder(raw)
        categories: dict[str, list[str]] = {
            "门店运营": [],
            "供应链": [],
            "会员与用户运营": [],
            "品控与标准化": [],
            "数字化与数据": [],
            "组织与人才": [],
            "其他": [],
        }

        if text == "待补充":
            return categories

        items = [
            p.strip(" ；;，,。、\n\"\"''")
            for p in re.split(r"[；;。\n]+", text)
            if len(p.strip(" ；;，,。、\n\"\"''")) >= 4
        ]

        for item in items:
            lower = item.lower()
            if any(kw in lower for kw in ["门店", "加盟", "运营", "亏损", "回本", "销售额", "盈利", "库存", "周转", "损耗", "滞销", "缺货"]):
                categories["门店运营"].append(item)
            elif any(kw in lower for kw in ["供应链", "仓配", "物流", "库存预测", "调度", "供需", "采购"]):
                categories["供应链"].append(item)
            elif any(kw in lower for kw in ["会员", "复购", "粘性", "社群", "运营", "分层", "触达", "留存", "用户"]):
                categories["会员与用户运营"].append(item)
            elif any(kw in lower for kw in ["品控", "标准", "食品安全", "质量", "服务标准", "投诉"]):
                categories["品控与标准化"].append(item)
            elif any(kw in lower for kw in ["数字化", "数据", "系统", "信息", "工具", "数据孤岛", "IT"]):
                categories["数字化与数据"].append(item)
            elif any(kw in lower for kw in ["人才", "培训", "组织", "团队", "技能", "文化"]):
                categories["组织与人才"].append(item)
            else:
                categories["其他"].append(item)

        return {k: v for k, v in categories.items() if v}

    def _build_classified_challenges(self, categories: dict[str, list[str]]) -> list[str]:
        """Build structured challenge list from classified categories."""
        result: list[str] = []
        for category, items in categories.items():
            if category == "其他":
                result.extend(items)
            elif items:
                result.append(f"【{category}】{'; '.join(items[:2])}")
        if not result:
            return ["当前经营/管理挑战待补充"]
        return result[:6]

    def _build_smart_ai_directions(
        self,
        assessment: Assessment,
        challenge_categories: dict[str, list[str]],
        data_systems: list[str],
    ) -> list[str]:
        """Generate specific AI directions by cross-matching challenges with AI capabilities."""
        directions: list[str] = []
        ai_goals = self._value_or_placeholder(assessment.ai_goals)

        # Match known challenge categories to AI opportunity templates
        category_ai_map = {
            "门店运营": "基于门店 POS 和进销存数据，构建智能库存预测与自动补货模型，降低滞销损耗",
            "供应链": "建设供应链调度优化引擎，实现仓配网络智能调拨与异常预警",
            "会员与用户运营": "基于会员消费数据构建精准分层模型，实现个性化推荐与流失预警",
            "品控与标准化": "利用 AI 视觉识别和 NLP 技术，实现门店品控自动巡检与标准化合规检测",
            "数字化与数据": "打通各系统数据孤岛，构建统一数据底座，支撑 AI 模型训练与部署",
            "组织与人才": "建设智能培训与知识管理平台，降低一线人员上手门槛",
        }

        for category in challenge_categories:
            if category in category_ai_map and len(directions) < 4:
                directions.append(category_ai_map[category])

        # Add AI-goal-aligned direction
        if ai_goals != "待补充":
            directions.append(f'围绕「{self._truncate(ai_goals, 60)}」目标，拆分 1-2 个可量化验证的 AI 试点场景')

        # Add data foundation direction if data systems exist
        if data_systems:
            directions.append(f"基于现有{'、'.join(data_systems[:2])}系统，构建最小可行数据底座，为 AI 模型训练做准备")
        else:
            directions.append("梳理业务数据资产现状，明确 AI 落地所需的数据采集和治理路径")

        return directions[:5]

    def _collect_smart_missing_info(
        self,
        assessment: Assessment,
        challenge_categories: dict[str, list[str]],
    ) -> list[str]:
        """Identify genuinely missing information beyond field emptiness."""
        missing: list[str] = []

        # Check empty fields first
        field_checks = [
            ("企业规模", assessment.company_size),
            ("年营收范围", assessment.annual_revenue_range),
            ("核心产品/服务详情", assessment.core_products),
            ("目标客户画像", assessment.target_customers),
        ]
        for label, value in field_checks:
            if self._value_or_placeholder(value) == "待补充":
                missing.append(f"{label}待补充")

        # Check for knowledge gaps even when fields are filled
        challenges_text = self._value_or_placeholder(assessment.current_challenges)
        if challenges_text != "待补充":
            if "加盟" in challenges_text and "门店运营" in challenge_categories:
                if len(challenge_categories.get("门店运营", [])) < 3:
                    missing.append("加盟门店单店盈利模型与盈亏平衡数据待补充")
            if "供应链" in challenge_categories:
                missing.append("供应链仓配网络布局与物流成本明细待补充")

        notes = self._value_or_placeholder(assessment.notes)
        if notes == "待补充":
            missing.append("战略方向、组织架构、预算约束等补充信息待补充")

        if not missing:
            return ["建议后续补充：竞品分析、财务核心指标、组织架构与决策流程"]

        return missing

    def _describe_scale(self, size: str, revenue: str) -> str:
        """Build a natural scale description."""
        parts = []
        if size != "待补充":
            parts.append(f"{size}规模")
        if revenue != "待补充":
            parts.append(f"年营收{revenue}")
        return "，".join(parts) if parts else ""

    def _value_or_placeholder(self, value: str | None) -> str:
        if value is None:
            return "待补充"

        cleaned = value.strip()
        return cleaned or "待补充"

    def _extract_json_object(self, content: str) -> str:
        stripped = content.strip()

        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped

        fenced_match = re.search(r"```json\s*(\{.*\})\s*```", stripped, re.DOTALL)
        if fenced_match:
            return fenced_match.group(1)

        generic_match = re.search(r"(\{.*\})", stripped, re.DOTALL)
        if generic_match:
            return generic_match.group(1)

        raise ValueError("LLM response did not contain a valid JSON object.")


CANVAS_BLOCK_ORDER = [
    "key_partnerships", "key_activities", "key_resources",
    "value_propositions", "customer_relationships", "channels",
    "customer_segments", "cost_structure", "revenue_streams",
]

CANVAS_BLOCK_TITLES = {
    "key_partnerships": "关键合作伙伴",
    "key_activities": "关键业务活动",
    "key_resources": "关键资源",
    "value_propositions": "价值主张",
    "customer_relationships": "客户关系",
    "channels": "渠道通路",
    "customer_segments": "客户细分",
    "cost_structure": "成本结构",
    "revenue_streams": "收入来源",
}


def _build_mock_block(
    *,
    block_key: str,
    profile,
    company_name: str,
    target_customers: str,
    core_products: str,
    current_challenges: str,
    ai_goals: str,
    available_data: str,
    revenue_range: str,
    notes: str,
) -> CanvasBlockResult:
    title = CANVAS_BLOCK_TITLES.get(block_key, block_key)

    if profile is None or not profile.problem_categories:
        return CanvasBlockResult(
            key=block_key,
            title=title,
            current_state="信息不足，暂无法描述。",
            diagnosis="缺失关键数据，无法完成诊断。",
            ai_opportunity="建议先补充基础信息。",
            missing_information="该模块所有信息待补充。",
        )

    categories = profile.problem_categories
    primary_category = categories[0]
    secondary_category = categories[1] if len(categories) > 1 else categories[0]

    current_state_templates = {
        "key_partnerships": f"{company_name}的外部协同关系涉及供应商、渠道、实施伙伴等，但当前问卷未明确合作方分级和模式。",
        "key_activities": f'企业关键业务活动主要围绕{core_products}展开，流程标准化程度需进一步评估。受\u201c{current_challenges}\u201d影响明显。',
        "key_resources": f"核心资源包括行业经验、产品能力、客户关系及现有系统基础（{available_data}）。",
        "value_propositions": f"{company_name}面向{target_customers}的核心价值围绕{core_products}，但差异化表达有待深化。",
        "customer_relationships": f"客户关系管理主要依赖销售/交付团队，客户数据集成度和结构化程度有待确认。",
        "channels": f"当前获客以直销/渠道/介绍为主，但全渠道策略和效能评估数据尚未完整。",
        "customer_segments": f"主要客户为{target_customers}，但细分维度（行业/规模/场景/决策链）未展开。",
        "cost_structure": f"成本主要集中在人力、交付、获客和技术维护环节，但缺少按客户/项目粒度核算。",
        "revenue_streams": f"收入以{core_products}相关业务为主，年营收{revenue_range}，收入构成比例待细化。",
    }

    diagnosis_templates = {
        "key_partnerships": f"【{primary_category.category}】{primary_category.typical_symptoms[0]}。"
                             f"此外，{secondary_category.category}方面也存在改进空间。",
        "key_activities": f"【{primary_category.category}】{primary_category.typical_symptoms[0]}。"
                           f"同时，{secondary_category.category}进一步影响了整体运营效率。",
        "key_resources": f"【{primary_category.category}】{primary_category.typical_symptoms[0]}。"
                         f"建议与{secondary_category.category}问题一并列入优化计划。",
        "value_propositions": f"【{primary_category.category}】{primary_category.typical_symptoms[0]}。"
                              f"如果{secondary_category.category}未能解决，价值感知差距会进一步扩大。",
        "customer_relationships": f"【{primary_category.category}】{primary_category.typical_symptoms[0]}。"
                                  f"配合解决{secondary_category.category}，可形成更完整的客户运营闭环。",
        "channels": f"【{primary_category.category}】{primary_category.typical_symptoms[0]}。"
                    f"{secondary_category.category}问题加剧了渠道效能的波动性。",
        "customer_segments": f"【{primary_category.category}】{primary_category.typical_symptoms[0]}。"
                             f"这直接限制了{secondary_category.category}策略的推进。",
        "cost_structure": f"【{primary_category.category}】{primary_category.typical_symptoms[0]}。"
                          f"若协同不佳，{secondary_category.category}还会推高隐性支出。",
        "revenue_streams": f"【{primary_category.category}】{primary_category.typical_symptoms[0]}。"
                           f"同时关注{secondary_category.category}以提升整体收入质量。",
    }

    missing_info_templates = {
        "key_partnerships": f"供应商名录、合作模式、渠道伙伴结构、生态借力目标（当前依据：{notes or '待补充'}）",
        "key_activities": f"标准作业流程文档、流程节点记录、知识管理现状、跨部门协同机制",
        "key_resources": f"IT系统清单、数据质量评估、团队技能矩阵、技术债务情况",
        "value_propositions": f"竞品对比、客户选择核心因素、差异化卖点排序、定价策略依据",
        "customer_relationships": f"客户分层机制、SLA现状、复购/续约数据、客户流失归因",
        "channels": f"渠道来源占比、获客成本分渠道、渠道转化漏斗、线上渠道布局",
        "customer_segments": f"客户分层标准、典型画像数据、决策链分析、各细分贡献度",
        "cost_structure": f"成本构成明细、交付成本口径、人效数据、隐性成本评估",
        "revenue_streams": f"收入类型拆分、毛利结构、订阅/服务收入占比、客户LTV",
    }

    return CanvasBlockResult(
        key=block_key,
        title=title,
        current_state=current_state_templates.get(block_key, "信息待补充。"),
        diagnosis=diagnosis_templates.get(block_key, primary_category.typical_symptoms[0]),
        ai_opportunity=primary_category.ai_opportunity_template or "建议补充数据后生成 AI 机会方向。",
        missing_information=missing_info_templates.get(block_key, "待补充。"),
    )
