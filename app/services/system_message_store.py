"""
Purpose: Load enterprise SystemMessage templates (100 base + optional extras) and wire them into LangChain.
Why: Centralized, testable, and version-tolerant prompt construction for production.

Inputs:
  - JSON/YAML schema produced earlier (metadata + templates dict).
  - Or fallback templates generator if file is absent.

APIs:
  - SystemMessageStore.from_file(path) / .from_fallback()
  - list_keys()
  - render_text(key, **kwargs)
  - render_system_message(key, **kwargs)
  - build_prompt_template(system_text, human="{input}", include_history=True, history_var="history")
  - build_prompt_from_key(key, human="{input}", include_history=True, **render_kwargs)

LangChain compatibility:
  - Tries `langchain_core.messages.SystemMessage` first, falls back to `langchain.schema.SystemMessage`.
"""

from __future__ import annotations
import json
import os
from datetime import date, datetime, timezone as dt_timezone
from dataclasses import dataclass, asdict, field, fields
from typing import Dict, List, Tuple, Mapping, Any, Optional
from langchain_core.messages import SystemMessage  # modern
from langchain_core.prompts import ChatPromptTemplate
import yaml
from enum import Enum
from zoneinfo import ZoneInfo  # py>=3.9
import pprint
from app.utils.date_utils import DateUtil


@dataclass(frozen=True)
class TemplateParam:
    """
    Defaults chosen to be safe and non-misleading.
    - timezone: drives 'today'; validated to a real IANA zone or 'UTC'.
    - knowledge_cutoff: conservative baseline; override in prod.
    """
    company: str
    product: str
    service: str
    jurisdiction: str
    policy_url: str
    knowledge_cutoff: str = "1970-01-01"
    today: str = field(default_factory=lambda: date.today().isoformat())
    timezone: str = "UTC"  # NEW: default to UTC

    @classmethod
    def from_partial(
            cls,
            data: Optional[Mapping[str, Any]] = None,
            **overrides: Any,
    ) -> "TemplateParam":
        """
        Merge partial values, fill defaults, normalize timezone, and compute 'today' from timezone when missing.
        """
        payload: Dict[str, Any] = {}
        if data:
            payload.update(dict(data))
        payload.update(overrides)

        # Normalize timezone early; tolerate unknown/bad values.
        tz = DateUtil.normalize_timezone(payload.get("timezone"))
        payload["timezone"] = tz

        # Coerce dates with safe fallbacks.
        kc_default = cls.__dataclass_fields__["knowledge_cutoff"].default  # type: ignore[attr-defined]
        td_default = DateUtil.now_date_iso(tz)

        payload["knowledge_cutoff"] = DateUtil.iso_date_or_default(
            payload.get("knowledge_cutoff"), default=kc_default
        )
        payload["today"] = DateUtil.iso_date_or_default(
            payload.get("today"), default=td_default
        )

        # Keep only known fields; dataclass injects remaining defaults.
        expected = {f.name for f in fields(cls)}
        init_kwargs = {k: v for k, v in payload.items() if k in expected}
        return cls(**init_kwargs)  # type: ignore[arg-type]

    def to_kwargs(self, *, extra: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """
        why: produce a dict for template rendering; allow pass-through extras if needed.
        """
        out = asdict(self)
        if extra:
            for k, v in extra.items():
                if k not in out or out[k] in (None, "", []):
                    out[k] = v
        return out


@dataclass(frozen=True)
class Template:
    key: str
    category: str
    variant: str
    description: str
    template: str


@dataclass(frozen=True)
class RoleSpec:
    title: str
    responsibility: str
    tasks_line: str

    '''
    Example: Get a system message for the `sales.no_hallucinations` role with policy enforcement
    
        store = SystemMessageStore() 
        system_msg = store.render_system_message(
            "sales.no_hallucinations",
            company=None,  # Falls back to default "Common Wealth"
            product=None,  # Optional product focus
            service="Accounts Payable", # Service focus
            knowledge_cutoff="2025-06-01", # Required cutoff date
            today="2025-11-10", # Current date
            timezone="America/Toronto", # Timezone for date calculations
            jurisdiction="SOX/PCI", # Compliance requirement
            policy_url=None # Optional policy URL
        )
    
    The rendered message will include:
    - Role identity as a sales advisor
    - Industry context for retirement finance
    - Service-specific context for Accounts Payable
    - Time boundaries
    - Compliance requirements
    - No-hallucination directive
    
    Key classes:
    - SystemMessageStore: Main prompt renderer with role/variant catalog
    - TemplateParam: Validated params with safe defaults
    - RoleSpec: Role metadata (title, responsibility, tasks)
    '''
class SystemMessageStore:
    _COMPANY_NAME = 'Common Wealth'
    _INDUSTRY = 'Retirement Fiance Service'
    _BUSINESS_AREA = (
        'Common Wealth provides a digital-first group retirement platform in Canada that unifies planning, saving, investing, annuities, and expert support for members, employers, and advisors. '
        'Members benefit from an all-in-one experience that combines multiple account types into a single dashboard, offers automated savings, life-stage-aligned investments, retirement projections, and accessible expert guidance. '
        'Employers gain a fully digital setup and administration process, while advisors receive turnkey onboarding and reporting tools to grow their client base.')

    _ROLES: Dict[str, RoleSpec] = {
        "sales": RoleSpec(
            title="Retirement Solutions Sales Advisor",
            responsibility="member and employer acquisition for retirement plans",
            tasks_line=(
                "Tasks: qualify employer groups, explain retirement plan value, run platform demos, "
                "guide prospects through pension options, respond to objections, and support onboarding coordination."
            ),
        ),
        "product_manager": RoleSpec(
            title="Retirement Product Manager",
            responsibility="retirement platform strategy and experience design",
            tasks_line=(
                "Tasks: define retirement product features, prioritize roadmap, analyze member outcomes, "
                "align with actuarial and compliance teams, and translate requirements for engineering."
            ),
        ),
        "customer_support": RoleSpec(
            title="Member Support Specialist",
            responsibility="member and employer support for retirement plans",
            tasks_line=(
                "Tasks: handle contribution inquiries, assist with account access, explain plan details, "
                "resolve benefit questions, and coordinate escalations across operations and compliance teams."
            ),
        ),
        "engineering": RoleSpec(
            title="Platform Software Engineer",
            responsibility="development and maintenance of the retirement platform",
            tasks_line=(
                "Tasks: design backend services, implement retirement calculation logic, optimize data flows, "
                "ensure platform security, review code, and collaborate with product and actuarial teams."
            ),
        ),
        "hr": RoleSpec(
            title="People Operations Assistant",
            responsibility="internal HR support within a regulated fintech environment",
            tasks_line=(
                "Tasks: support onboarding/offboarding, handle internal HR inquiries, assist with benefits, "
                "coordinate compliance training, and guide employees to documented HR policies without giving legal or tax advice."
            ),
        ),
    }

    _BASE_VARIANTS: Dict[str, str] = {
        "concise": " Keep the response concise (≤ {max_words} words).",
        "detailed": " Provide structured, actionable steps with short reasoning.",
        "tool_first": " Use tools or retrieved evidence before answering; cite the results clearly.",
        "no_hallucinations": " If uncertain or lacking information, say \"I don't know\" rather than guessing.",
        "pii_safe": " Avoid exposing personal or financial information; mask identifiers except the last four digits.",
        "tone_warm": " Use a warm, professional, member-centric tone.",
        "tone_strict": " Use a formal, compliance-aware tone appropriate for regulated fintech.",
        "escalate": " If the request touches compliance, regulatory, or financial risk, escalate using <handoff/>.",
        "cite": " When referencing documents or data, cite them as [ref:ID] with source names.",
        "multilingual": " Respond in the user's language ({locale}) when possible; otherwise default to {default_language}.",
    }

    _EXTRA_VARIANTS: Dict[str, Dict[str, str]] = {
        "sales": {
            "value_framing": (
                " Frame explanations around member and employer outcomes, emphasizing retirement readiness, cost efficiency, "
                "and the advantages of a digital-first pension platform."
            ),
            "discovery_first": (
                " Begin by understanding the prospect's workforce, benefits needs, and retirement goals before positioning {product} or {service}."
            ),
        },

        "product_manager": {
            "data_driven": (
                " Use member outcomes, contribution patterns, engagement metrics, and actuarial insights to support decisions. "
                "Avoid assumptions without validation."
            ),
            "prioritization_logic": (
                " Communicate tradeoffs clearly using reasoning grounded in member impact, employer value, regulatory requirements, "
                "and alignment with {company}'s long-term pension strategy."
            ),
        },

        "customer_support": {
            "empathy_first": (
                " Respond with empathy and clarity, especially when addressing contributions, withdrawals, employer remittances, "
                "or retirement anxiety."
            ),
            "structured_troubleshooting": (
                " Provide step-by-step troubleshooting; verify contribution timelines, account details, and plan rules before escalating."
            ),
        },

        "engineering": {
            "technical_clarity": (
                " Offer clear, accurate technical explanations—especially regarding contribution pipelines, retirement calculations, "
                "data integrity, and integrations."
            ),
            "reliability_focus": (
                " Recommend designs that prioritize reliability, accuracy of retirement projections, and maintainability of the pension platform."
            ),
        },

        "hr": {
            "neutral_tone": (
                " Maintain a supportive, neutral tone when handling internal HR questions within a regulated environment."
            ),
            "policy_guided": (
                " Base responses on documented HR processes; avoid legal, tax, or financial interpretations and direct employees to proper resources."
            ),
        },
    }

    """Dynamic SystemMessage builder with optional identity/compliance/product/service."""

    def keys(self) -> List[str]:
        keys: List[str] = []
        for c in self.roles.keys():
            for v in _all_variants_for(c).keys():
                keys.append(f"{c}.{v}")
        return keys

    def _get_role_and_variants(self, key: str) -> Tuple[str, List[str]]:
        """
        Parse key string into role and variant list.

        Args:
            key (str): String in format "[role]" or "[role].[variant]" or "[role].[variant].[variant]"
                      where variants are optional and can be multiple.

        Returns:
            Tuple[str, List[str]]: Role and list of variants.

        Raises:
            KeyError: If role is not found in allowed roles.
        """
        splits = key.split(".")
        role = splits[0]
        variants = splits[1:]

        if role not in self._ROLES:
            raise KeyError(f"Unknown category '{role}'.")

        return role, variants


    def render_content(
            self,
            key: str,
            *,
            company: str | None = None,
            industry: str | None = None,
            product: str | None = None,
            service: str | None = None,
            business_area: str | None = None,
            jurisdiction: str | None = None,
            policy_url: str | None = None,
            knowledge_cutoff: str,
            today: str | None = None,
            timezone: str = "UTC",
            locale: str = "en",
            default_language: str = "en",
            max_words: int = 120,
            **extra_fmt: Any,
    ) -> str:
        company = _value_or_default(company, self._COMPANY_NAME)
        industry = _value_or_default(industry, self._INDUSTRY)
        business_area = _value_or_default(business_area, self._BUSINESS_AREA)

        role, variants = self._get_role_and_variants(key)

        intro = _intro_line(company, role, industry=industry, company_business_area=business_area, product=product, service=service)
        tasks = self._ROLES[role].tasks_line
        time_line = _time_line(knowledge_cutoff=knowledge_cutoff, today=today if today is not None else DateUtil.now_date_iso(),
                               timezone=timezone)
        compliance = _compliance_line(jurisdiction=jurisdiction, policy_url=policy_url)

        variant_map = _all_variants_for(role)
        tails = []
        for variant in variants:
            if variant in variant_map:
                tail_template = variant_map[variant]
                try:
                    tail = tail_template.format(
                        max_words=max_words, locale=locale, default_language=default_language, **extra_fmt
                    )
                except Exception:
                    tail = tail_template  # why: never break due to missing optional placeholders
            else:
                tail = ""

        return (intro + " " + tasks + time_line + compliance + " " + tail).strip()

    def render_system_message(self, key: str, **kwargs: Any) -> SystemMessage:
        return SystemMessage(content=self.render_content(key, **kwargs))

    @staticmethod
    def build_prompt_template(
            system_text: str,
            *,
            human: str = "{input}",
            include_history: bool = True,
            history_var: str = "history",
    ) -> ChatPromptTemplate:
        msgs: List[Tuple[str, str]] = [("system", system_text)]
        if include_history:
            msgs.append(("placeholder", "{" + history_var + "}"))
        msgs.append(("human", human))
        return ChatPromptTemplate.from_messages(msgs)

    def build_prompt_from_key(
            self,
            key: str,
            *,
            human: str = "{input}",
            include_history: bool = True,
            history_var: str = "history",
            **render_kwargs: Any,
    ) -> ChatPromptTemplate:
        system_text = self.render_content(key, **render_kwargs)
        return self.build_prompt_template(system_text, human=human, include_history=include_history,
                                          history_var=history_var)
        # ---------- Loaders ----------


def build_prompt(store: SystemMessageStore, key: str, **kwargs: Any) -> ChatPromptTemplate:
    """
    Build a ChatPromptTemplate using the dynamic renderer. Missing optional fields are handled.
    Required: knowledge_cutoff, today. timezone defaults to 'UTC' unless provided.
    """
    return store.build_prompt_from_key(key, **kwargs)


def _value_or_default(value: Any, default: Any) -> Any:
    """Return value if not None, otherwise return default."""
    return value if value is not None else default


def _all_variants_for(category: str) -> Dict[str, str]:
    out = dict(SystemMessageStore._BASE_VARIANTS)
    out.update(SystemMessageStore._EXTRA_VARIANTS.get(category, {}))
    return out


def _a_or_an(phrase: str) -> str:
    """Minimal article chooser for smoother copy."""
    return "an" if phrase[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def _intro_line(company: str, role: str, *, industry: str | None, company_business_area: str | None, product: str | None,
                service: str | None) -> str:
    
    role_spec = SystemMessageStore._ROLES[role]
    parts = [f"You are {_a_or_an(role_spec.title)} {role_spec.title} at {company} in the {industry} industry, your responsibility is {role_spec.responsibility}"]

    if company_business_area:
        parts.append(f". {company_business_area}")

    if product:
        parts.append(f"Now you work with the {product} product")
    elif service:
        parts.append(f"Not you provide {service} services")


    parts.append(role_spec.tasks_line)

    return " ".join(parts)

def _time_line(*, knowledge_cutoff: str, today: str, timezone: str) -> str:
    return f" Knowledge cutoff={knowledge_cutoff}. Today={today} {timezone}."


def _compliance_line(*, jurisdiction: str | None, policy_url: str | None) -> str:
    """
    Optional compliance sentence. Removed if both are None.
    - Both present: 'Comply with {jurisdiction} policies and {policy_url}.'
    - Only jurisdiction: 'Comply with {jurisdiction} policies.'
    - Only policy_url: 'Follow internal policies: {policy_url}.'
    - None/None: ''
    """
    has_jurisdiction = bool(jurisdiction)
    has_policy_url = bool(policy_url)
    if has_jurisdiction and has_policy_url:
        return f" Comply with {jurisdiction} policies and {policy_url}."
    if has_jurisdiction:
        return f" Comply with {jurisdiction} policies."
    if has_policy_url:
        return f" Follow internal policies: {policy_url}."
    return ""


def _variant_tail(variant: str) -> str:
    return SystemMessageStore._BASE_VARIANTS[variant]


def _all_keys() -> List[str]:
    keys: List[str] = []
    for c in SystemMessageStore().roles.keys():
        for v in SystemMessageStore._BASE_VARIANTS.keys():
            keys.append(f"{c}.{v}")
    return keys


# ---------------- Example usage ----------------
if __name__ == "__main__":
    store = SystemMessageStore()


    pprint.pprint(store.render_system_message("sales.no_hallucinations",
                                              company=None,
                                              product=None,
                                              service="Accounts Payable",
                                              knowledge_cutoff="2025-06-01",
                                              today="2025-11-10",
                                              timezone="America/Toronto",
                                              jurisdiction="SOX/PCI",
                                              policy_url=None,
                                              ))

    # Example A: company omitted → industry fallback; only jurisdiction present
    prompt_a = store.build_prompt_from_key(
        "sales.no_hallucinations",
        company=None,
        product=None,
        service="Accounts Payable",
        knowledge_cutoff="2025-06-01",
        today="2025-11-10",
        timezone="America/Toronto",
        jurisdiction="SOX/PCI",
        policy_url=None,
    )
    print(prompt_a.invoke({"input": "Can we store full PAN?", "history": []}).to_string())

    # Example B: full brand + product, compliance removed (both None), extra variant
    prompt_b = store.build_prompt_from_key(
        "sales.hipaa_minimum",
        company="HealthCo",
        product="CarePortal",
        service=None,
        knowledge_cutoff="2024-06-01",
        today="2025-11-10",
        timezone="UTC",
        jurisdiction=None,
        policy_url=None,
    )
    print(prompt_b.invoke({"input": "How do you handle PHI?", "history": []}).to_string())

    # Example C: customer support with product + refund policy URL
    prompt_c = store.build_prompt_from_key(
        "sales.refund_policy_strict",
        company="Acme Corp",
        product="AcmeCloud",
        service=None,
        knowledge_cutoff="2025-06-01",
        today="2025-11-10",
        timezone="UTC",
        jurisdiction="CCPA",
        policy_url="https://intra.acme/policies/ai",
        refund_policy_url="https://intra.acme/policies/refunds",
    )
    print(prompt_c.invoke({"input": "Can I get a refund?", "history": []}).to_string())
