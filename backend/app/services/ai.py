"""Civic AI assistant: Groq when configured, deterministic facts otherwise.

All numbers in a prompt come from the database. The model is asked to write a
short explanation only; it never supplies data that is persisted or used for
authorization. When GROQ_API_KEY is absent, or the request fails, the API still
returns a useful, explicitly-labelled deterministic summary.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import Settings
from app.models import Incident, IncidentCategory, IncidentSeverity

LIMITATIONS = (
    "AI text is advisory only and may be wrong. It is not a safety decision, "
    "an official assessment, or a substitute for field verification. "
    "Counts come from incidents visible to your account."
)

_CATEGORY_KEYWORDS: dict[IncidentCategory, tuple[str, ...]] = {
    IncidentCategory.ROADS: ("pothole", "road", "street", "traffic", "bridge"),
    IncidentCategory.DRAINAGE: ("drain", "flood", "waterlog", "sewer", "gutter"),
    IncidentCategory.SANITATION: ("garbage", "waste", "trash", "sanitation", "toilet"),
    IncidentCategory.UTILITIES: ("power", "electric", "water supply", "gas", "outage"),
    IncidentCategory.PUBLIC_SAFETY: (
        "accident",
        "crime",
        "fire",
        "unsafe",
        "hazard",
        "security",
    ),
    IncidentCategory.HEALTH: ("clinic", "hospital", "medical", "disease", "health"),
    IncidentCategory.ENVIRONMENT: ("pollution", "smoke", "tree", "air quality", "noise"),
}

_CRITICAL_KEYWORDS = ("flood", "fire", "collapse", "explosion", "injured", "critical")
_HIGH_KEYWORDS = ("accident", "severe", "blocked", "outage", "unsafe", "major")


def ai_available(settings: Settings) -> bool:
    return settings.groq_api_key is not None


def summarize_incidents(incidents: list[Incident]) -> dict[str, Any]:
    by_category = Counter(incident.category.value for incident in incidents)
    by_severity = Counter(incident.severity.value for incident in incidents)
    by_status = Counter(incident.status.value for incident in incidents)
    highlights: list[str] = []
    if by_severity.get("CRITICAL", 0):
        highlights.append(
            f"{by_severity['CRITICAL']} critical incident(s) in your visible scope"
        )
    if by_status.get("OPEN", 0):
        highlights.append(f"{by_status['OPEN']} report(s) still open")
    if by_category:
        top_category, top_count = by_category.most_common(1)[0]
        highlights.append(f"Most reports are {top_category.lower()} ({top_count})")
    if not highlights:
        highlights.append("No incidents are visible in your scope yet")
    return {
        "incident_count": len(incidents),
        "by_category": dict(by_category),
        "by_severity": dict(by_severity),
        "by_status": dict(by_status),
        "highlights": highlights,
    }


def _deterministic_summary(facts: dict[str, Any]) -> str:
    count = facts["incident_count"]
    if count == 0:
        return (
            "No incidents are visible for your account yet. Reports you submit "
            "will appear here once they are recorded."
        )
    lead = facts["highlights"][0]
    return (
        f"{count} incident(s) are visible in your scope. {lead}. "
        "This summary is computed directly from the live incident list."
    )


def _ask_groq(settings: Settings, system: str, user: str) -> str | None:
    if not ai_available(settings):
        return None
    key = settings.groq_api_key
    assert key is not None
    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 220,
    }
    headers = {
        "Authorization": f"Bearer {key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(settings.groq_timeout_s)) as client:
            response = client.post(
                f"{settings.groq_base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
        if response.status_code != 200:
            return None
        body = response.json()
        choices = body.get("choices") if isinstance(body, dict) else None
        if not isinstance(choices, list) or not choices:
            return None
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return content.strip()
    except (httpx.HTTPError, ValueError, TypeError):
        return None
    return None


def local_insights(incidents: list[Incident], settings: Settings) -> dict[str, Any]:
    facts = summarize_incidents(incidents)
    system = (
        "You write brief neighbourhood safety summaries for a civic app. "
        "Use only the supplied counts. Never invent numbers, places, weather, "
        "or events. Do not give emergency advice. Two sentences maximum."
    )
    narrative = _ask_groq(settings, system, json.dumps(facts, ensure_ascii=False))
    return {
        "available": narrative is not None,
        "source": "groq" if narrative is not None else "deterministic",
        "summary": narrative or _deterministic_summary(facts),
        "highlights": facts["highlights"],
        "limitations": LIMITATIONS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "incident_count": facts["incident_count"],
        "model": settings.groq_model if narrative is not None else None,
    }


def suggest_triage(
    title: str, description: str, settings: Settings
) -> dict[str, Any]:
    text = f"{title} {description}".lower()
    suggested_category: IncidentCategory | None = None
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            suggested_category = category
            break
    if any(keyword in text for keyword in _CRITICAL_KEYWORDS):
        severity = IncidentSeverity.CRITICAL
    elif any(keyword in text for keyword in _HIGH_KEYWORDS):
        severity = IncidentSeverity.HIGH
    else:
        severity = IncidentSeverity.MEDIUM

    facts = {
        "title": title[:200],
        "description": description[:1000],
        "category_hint": suggested_category.value if suggested_category else None,
        "severity_hint": severity.value,
    }
    system = (
        "You help citizens categorize a civic incident report. Reply with one "
        "short sentence explaining the suggested category and severity. Use "
        "only the supplied text and hints. Never invent facts. Do not assign "
        "official status."
    )
    narrative = _ask_groq(settings, system, json.dumps(facts, ensure_ascii=False))
    rationale = narrative or (
        f"Suggestion derived from keywords in your text: "
        f"{suggested_category.value if suggested_category else 'category unclear'}, "
        f"{severity.value}."
    )
    return {
        "available": narrative is not None,
        "source": "groq" if narrative is not None else "deterministic",
        "suggested_category": suggested_category,
        "suggested_severity": severity,
        "rationale": rationale,
        "limitations": LIMITATIONS,
        "model": settings.groq_model if narrative is not None else None,
    }
