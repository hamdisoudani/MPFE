"""Centralized prompt builders + context trimmers. One place for prompt engineering."""
from __future__ import annotations

MAX_LESSON_CHARS_FOR_CRITIC = 6000
MAX_FINDING_CHARS = 400
MAX_FINDINGS_IN_OUTLINE = 15
MAX_DEP_LESSON_CHARS_FOR_ACTIVITY = 2500


def _trim(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + "\n…[truncated]"


def trim_findings(findings: list[str], k: int = MAX_FINDINGS_IN_OUTLINE) -> list[str]:
    return [_trim(f, MAX_FINDING_CHARS) for f in (findings or [])[-k:]]


def outline_prompt(requirements: str, prefs: dict, findings: list[str],
                   n_chapters: int, lessons_per_chapter: int,
                   activity_granularity: str, include_activities: bool) -> str:
    return (
        "You are a senior curriculum designer producing a RIGOROUS, goal-driven plan.\n\n"
        f"REQUIREMENT:\n{requirements}\n\n"
        f"TEACHER PREFERENCES:\n{prefs}\n\n"
        "WEB FINDINGS (ground real-world relevance; do not quote URLs):\n"
        + "\n---\n".join(trim_findings(findings))
        + "\n\nPRODUCE EXACTLY:\n"
        f"1) {n_chapters} chapters. Each chapter MUST have:\n"
        "   - title (short, concrete)\n"
        "   - goal: one sentence starting 'By the end of this chapter, the learner can …' "
        "(observable, testable skill — NOT a topic label)\n"
        "   - summary: 2–3 sentences describing scope\n"
        f"2) {n_chapters*lessons_per_chapter} lesson_plans ({lessons_per_chapter} per chapter, positions 1-based). Each MUST have:\n"
        "   - chapter_pos, position, title\n"
        "   - serves_chapter_goal: verbatim copy of this chapter's goal sentence (proves alignment)\n"
        "   - learning_objective: one sentence, observable ('the learner will …')\n"
        "   - must_cover: 3–6 CONCRETE, checkable bullets (phrases, structures, facts the lesson MUST contain literally)\n"
        "   - grammar_point: one specific structure (or 'none' if N/A)\n"
        "   - vocab_targets: 6–12 items the lesson MUST introduce in a vocabulary section\n"
        "3) activity_plans with scope=" f"{activity_granularity}" " "
        "(lesson => one per lesson; chapter => one per chapter consolidating ALL its lessons). "
        f"include_activities={include_activities}. Each MUST have:\n"
        "   - scope, chapter_pos, depends_on_lesson_positions (every lesson it covers)\n"
        "   - kind (quiz|roleplay|writing|listening)\n"
        "   - title, instructions\n"
        "   - requirements: 3–5 bullets describing what the activity must test/produce\n"
        "RULES: every lesson_plan.must_cover item must be something the critic can grep for in the lesson markdown. "
        "No vague items like 'be engaging'. Use concrete phrases, verbs, tenses, or vocabulary. "
        "Every lesson's serves_chapter_goal must exactly match one chapter.goal."
    )


def writer_prompt(chapter: dict, lesson_pos: int, prefs: dict, plan: dict,
                  chapter_goal: str, prior_critique: str | None, attempt_num: int) -> str:
    plan_block = ""
    if plan:
        plan_block = (
            "\n\n### PLAN CONTRACT — you MUST satisfy EVERY item below. The critic will check each.\n"
            f"- CHAPTER GOAL this lesson serves (reference it in the lesson intro): {chapter_goal}\n"
            f"- Lesson title (use or refine minimally): {plan.get('title')}\n"
            f"- Learning objective (state it literally as the first line after the H1): {plan.get('learning_objective')}\n"
            f"- must_cover — each of these EXACT items must appear, ideally as a labeled section or quoted phrase:\n"
            + "\n".join(f"    * {item}" for item in (plan.get("must_cover") or []))
            + f"\n- Grammar focus (explain with ≥2 concrete examples): {plan.get('grammar_point')}\n"
            f"- Vocabulary targets — include EVERY item in a '## Vocabulary' section with a short gloss:\n"
            + ", ".join(plan.get("vocab_targets") or [])
        )
    revision = ""
    if prior_critique:
        revision = (
            f"\n\n### REVISION #{attempt_num} — previous draft was REJECTED\n"
            f"Critic report (address every failed criterion, quote-worthy fixes required):\n{prior_critique}\n"
            "Rewrite: keep what worked, add missing must_cover items literally, add vocabulary entries that were missing."
        )
    return (
        f"Write lesson {lesson_pos} of chapter '{chapter['title']}'. Chapter scope: {chapter.get('summary','')}.\n"
        f"Approach: {prefs.get('pedagogical_approach','mixed')}. "
        f"Focus: {prefs.get('special_focus', [])}. "
        f"Audience: {prefs.get('target_audience','adult learners')}. "
        f"Language of instruction: {prefs.get('language_of_instruction','English')}.\n"
        "Required structure:\n"
        "# <Title>\n"
        "**Learning objective:** <one sentence>\n"
        "**Serves chapter goal:** <one sentence — the chapter goal>\n"
        "## Warm-up\n## Grammar / Key concept (≥2 worked examples)\n"
        "## Dialogues or Examples (3–5)\n## Vocabulary (all targets, each with a gloss)\n"
        "## Practice (≥3 exercises with answers)\n"
        + plan_block + revision
        + "\nReturn clean markdown only."
    )


def critic_prompt(lesson_markdown: str, plan: dict, chapter_goal: str, prefs: dict) -> str:
    lesson = _trim(lesson_markdown or "", MAX_LESSON_CHARS_FOR_CRITIC)
    must_cover = plan.get("must_cover") or []
    vocab = plan.get("vocab_targets") or []
    return (
        "You are an ADVERSARIAL pedagogy reviewer. Your default stance is SKEPTICAL.\n"
        "You must provide EVIDENCE for every claim. No rubber-stamping.\n\n"
        "For each criterion, either quote a SHORT verbatim snippet from the lesson that proves it, "
        "or state 'MISSING' with what was expected. A criterion without a quote counts as FAIL.\n\n"
        "CRITERIA:\n"
        "C1_objective_stated: the lesson states an explicit learning objective near the top.\n"
        f"C2_serves_chapter_goal: the lesson explicitly references/aligns with the chapter goal: {chapter_goal!r}\n"
        f"C3_must_cover_each: for EACH of the must_cover items, quote where it appears: {must_cover}\n"
        f"C4_grammar_examples: grammar point '{plan.get('grammar_point')}' is explained with ≥2 concrete examples.\n"
        f"C5_vocab_coverage: at least 80% of vocab_targets appear in a Vocabulary section. Targets: {vocab}\n"
        "C6_practice_and_constraints: there is a practice section with ≥3 exercises; must_avoid is respected.\n"
        f"   must_avoid (teacher): {prefs.get('must_avoid', [])}\n\n"
        "Return ONLY this JSON object (no prose outside):\n"
        "{\n"
        '  "per_criterion": [\n'
        '    {"id":"C1_objective_stated","pass":true|false,"evidence":"<quote or MISSING>","note":"<1 sentence>"},\n'
        '    {"id":"C2_serves_chapter_goal","pass":...,"evidence":"...","note":"..."},\n'
        '    {"id":"C3_must_cover_each","pass":...,"per_item":[{"item":"...","pass":...,"evidence":"<quote or MISSING>"}],"note":"..."},\n'
        '    {"id":"C4_grammar_examples","pass":...,"evidence":"...","note":"..."},\n'
        '    {"id":"C5_vocab_coverage","pass":...,"coverage_ratio":0.0,"missing":["..."],"note":"..."},\n'
        '    {"id":"C6_practice_and_constraints","pass":...,"evidence":"...","note":"..."}\n'
        "  ],\n"
        '  "score": <integer 0-6>,\n'
        '  "weaknesses": ["<specific shaky thing even if you pass — be honest>"],\n'
        '  "passes": <true|false>,\n'
        '  "critique": "<2-4 sentence actionable summary>"\n'
        "}\n\n"
        "HARD RULES:\n"
        "- passes=true ONLY if score>=5 AND C3_must_cover_each.pass=true (every must_cover item has a real quote, none MISSING) "
        "AND C5_vocab_coverage.coverage_ratio>=0.8.\n"
        "- If in doubt, FAIL. It is better to reject and force a rewrite than to pass a weak lesson.\n"
        "- Always list at least 1 weakness, even when passing.\n\n"
        "---LESSON MARKDOWN---\n" + lesson
    )
