"""The AI interviewer: plans questions from the match report, reacts to answers, writes feedback.

With an AI key (LLM_PROVIDER=groq|gemini) the questions, follow-ups and feedback come from the
model. Without one, or if a call fails, a scripted interviewer built from the same report takes
over, so an interview never breaks halfway.
"""

import logging
import re
from dataclasses import dataclass

from . import ai

log = logging.getLogger(__name__)

MAX_FOLLOW_UPS = 1  # per question, keeps an interview to roughly question_count + a few turns


@dataclass(frozen=True)
class Persona:
    key: str
    name: str
    title: str


PERSONAS = {
    "maya": Persona("maya", "Maya", "Senior Recruiter"),
    "james": Persona("james", "James", "Engineering Manager"),
}


# ---------- context passed to the model ----------


def _context(report: dict, resume_lines: list[dict], jd_lines: list[dict]) -> str:
    reqs = "\n".join(
        f"- {r['id']} [{r['importance']}, {r['status']}] {r['text']}"
        + (f" (evidence {', '.join(r['evidence'])})" if r.get("evidence") else "")
        for r in report.get("requirements", [])
    )
    resume = "\n".join(f"{x['id']}: {x['text']}" for x in resume_lines)
    jd = "\n".join(f"{x['id']}: {x['text']}" for x in jd_lines)
    return (
        f"JOB: {report.get('jd', {}).get('title') or 'the role'} at {report.get('jd', {}).get('company') or 'the company'}\n\n"
        f"MATCH REPORT ({report.get('verdict')}):\n{reqs}\n\nRESUME\n{resume}\n\nJOB DESCRIPTION\n{jd}"
    )


def _clean(text: object, limit: int = 600) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


# ---------- 1. plan ----------

PLAN_SYSTEM = """You are an experienced interviewer preparing a realistic mock interview for this candidate and job.
Write exactly {n} questions, spoken aloud, one or two sentences each, in a natural conversational tone.
Order: 1 warm-up about their background for this role; then mix (a) the job's must-have requirements that the
report marks missing or partial, asked fairly (related experience, how they would ramp up), (b) probing their
strongest claims, quoting or paraphrasing a specific resume line, (c) technical depth for the role,
(d) 2-3 behavioural questions (STAR style); finish with one closing question such as why this role.
Never invent facts about the candidate. Do not number the questions.
Respond with JSON only: {{"questions": [{{"text": "...", "focus": "warmup|gap|strength|technical|behavioral|closing", "requirement": "R3 or null"}}]}}"""

BEHAVIORAL = [
    "Tell me about a time you disagreed with a teammate or stakeholder. How did you handle it, and what happened?",
    "Describe a project that didn't go to plan. What went wrong, and what did you learn from it?",
    "Tell me about a time you had to learn something new quickly to deliver a result.",
    "How do you prioritise when you have several urgent tasks and limited time? Give me a real example.",
    "What's the piece of work you're proudest of, and why?",
    "Tell me about a time you took ownership of a problem nobody else was handling.",
]

GENERAL = [
    "Walk me through the most technically challenging problem you've solved recently. How did you approach it?",
    "How do you make sure the work you deliver is high quality? Talk me through your process.",
    "Tell me about a time you received critical feedback. What did you change afterwards?",
    "How do you keep your skills current, and what have you learned in the last few months?",
    "Describe how you'd spend your first 90 days in this role.",
    "Tell me about a time you had to explain something complex to a non-technical person.",
    "What kind of team environment helps you do your best work?",
    "Tell me about a decision you made with incomplete information. How did it turn out?",
]


def scripted_plan(report: dict, n: int) -> list[dict]:
    """A fixed-shape plan: warm-up, report-driven questions (strengths and gaps, alternating),
    at least two behavioural ones, general questions to fill, and a closing question."""
    title = report.get("jd", {}).get("title") or "this role"
    reqs = report.get("requirements", [])
    lines = report.get("resume_lines", {})
    gaps = [r for r in reqs if r["status"] != "met" and r["importance"] == "must"]
    gaps += [r for r in reqs if r["status"] != "met" and r["importance"] == "nice"]
    strengths, quoted = [], set()
    for r in reqs:  # one question per resume line, even when it proves several requirements
        if r["status"] == "met" and r.get("evidence") and r["evidence"][0] not in quoted:
            quoted.add(r["evidence"][0])
            strengths.append(r)

    middle: list[dict] = []
    for i in range(max(len(gaps), len(strengths))):
        if i < len(strengths):
            r = strengths[i]
            quote = lines.get(r["evidence"][0], "").lstrip("-•* ").strip()
            middle.append({
                "text": f'Your resume mentions "{quote[:140]}". Can you walk me through it: what was your role, '
                "what was difficult, and what was the result?" if quote else
                f"The role needs {r['text'].rstrip('.')}. Tell me about your strongest experience with that.",
                "focus": "strength",
                "requirement": r["id"],
            })
        if i < len(gaps):
            r = gaps[i]
            verb = "doesn't clearly show" if r["status"] == "missing" else "only partly shows"
            middle.append({
                "text": f"The job asks for {r['text'].rstrip('.')}, and your resume {verb} it. What related "
                "experience do you have, and how would you get up to speed?",
                "focus": "gap",
                "requirement": r["id"],
            })

    warmup = {"text": f"To start, could you walk me through your background and what draws you to the {title} role?",
              "focus": "warmup", "requirement": None}
    closing = {"text": f"Finally, why do you think you'd be a strong fit for this {title} role?",
               "focus": "closing", "requirement": None}
    behavioral = [{"text": t, "focus": "behavioral", "requirement": None} for t in BEHAVIORAL]
    general = [{"text": t, "focus": "technical", "requirement": None} for t in GENERAL]

    slots = n - 2
    n_behavioral = 2 if slots >= 4 else 0
    body = middle[: slots - n_behavioral] + behavioral[:n_behavioral]
    for extra in behavioral[n_behavioral:] + general:  # fill any remaining slots, never repeating
        if len(body) >= slots:
            break
        body.append(extra)
    return [warmup, *body[:slots], closing]


def make_plan(report: dict, resume_lines: list[dict], jd_lines: list[dict], n: int) -> tuple[list[dict], str]:
    if ai.chat_available():
        try:
            data = ai.chat_json(PLAN_SYSTEM.format(n=n), _context(report, resume_lines, jd_lines), temperature=0.5)
            req_ids = {r["id"] for r in report.get("requirements", [])}
            plan = [
                {
                    "text": _clean(q.get("text"), 400),
                    "focus": q.get("focus") if q.get("focus") in ("warmup", "gap", "strength", "technical", "behavioral", "closing") else "technical",
                    "requirement": q.get("requirement") if q.get("requirement") in req_ids else None,
                }
                for q in data.get("questions", [])
                if isinstance(q, dict) and _clean(q.get("text"))
            ][:n]
            if len(plan) < n:  # top up from the scripted plan rather than fail
                extra = [q for q in scripted_plan(report, 15) if q["text"] not in {p["text"] for p in plan}]
                plan = plan[:-1] + extra[: n - len(plan)] + plan[-1:] if plan else extra[:n]
            return plan[:n], ai.engine_name()
        except Exception as exc:
            log.warning("interview plan via AI failed, using scripted plan: %s", exc)
    return scripted_plan(report, n), "scripted"


def opening(persona: Persona, candidate: str | None, report: dict, n: int, first_question: str) -> str:
    jd = report.get("jd", {})
    role = jd.get("title") or "this role"
    company = f" at {jd['company']}" if jd.get("company") else ""
    hello = f"Hi {candidate}!" if candidate else "Hi there!"
    return (
        f"{hello} I'm {persona.name}, {persona.title}. Thanks for joining. Today we'll do a mock interview for "
        f"the {role} position{company}. I have {n} questions, and I may ask a follow-up here and there. "
        f"Take your time with each answer. Let's begin. {first_question}"
    )


# ---------- 2. react to an answer ----------

TURN_SYSTEM = """You are {name}, a friendly but rigorous interviewer, in a live spoken mock interview.
Given the current question and the candidate's answer, decide whether ONE short follow-up would get a much
better signal (vague answer, missing result/impact, an interesting claim worth probing). Follow-ups allowed
for this question: {remaining}.
Respond with JSON only: {{"acknowledgement": "a brief natural reaction to the answer, max 12 words, no praise inflation, no question",
"follow_up": "one spoken follow-up question, or null"}}"""

ACKS = ["Thank you.", "Okay, thanks for that.", "Got it, thank you.", "Thanks, that's helpful.", "Alright, thank you."]


def react(persona: Persona, question: str, exchange: list[dict], follow_ups_used: int) -> tuple[str, str | None]:
    """(acknowledgement, follow-up question or None)."""
    remaining = MAX_FOLLOW_UPS - follow_ups_used
    if ai.chat_available():
        try:
            convo = "\n".join(f"{t['role'].upper()}: {t['text']}" for t in exchange)
            data = ai.chat_json(
                TURN_SYSTEM.format(name=persona.name, remaining=max(remaining, 0)),
                f"CURRENT QUESTION: {question}\n\nEXCHANGE SO FAR:\n{convo}",
                temperature=0.6,
            )
            ack = _clean(data.get("acknowledgement"), 120) or ACKS[0]
            follow = _clean(data.get("follow_up"), 300) if remaining > 0 else ""
            return ack, (follow if follow and follow.lower() != "null" else None)
        except Exception as exc:
            log.warning("interview turn via AI failed, continuing scripted: %s", exc)
    q = exchange[0].get("q", 0) if exchange else 0
    return ACKS[(q + len(exchange)) % len(ACKS)], None  # vary the wording between questions


def closing() -> str:
    return (
        "That's all the questions I have. Thank you for your time today, it was great talking with you. "
        "End the interview whenever you're ready to see your feedback. Good luck!"
    )


# ---------- 3. feedback ----------

FEEDBACK_SYSTEM = """You are an expert interview coach. Review this mock interview transcript for the job below and
give honest, specific, encouraging feedback. Judge only what the candidate actually said.
Respond with JSON only:
{"overall_score": 0-100, "summary": "3-4 sentences", "strengths": ["..."], "improvements": ["..."],
 "questions": [{"number": 1, "rating": 1-5, "comment": "1-2 sentences: what was good, what to add (e.g. a concrete result)"}]}"""

FILLERS = re.compile(r"\b(um+|uh+|erm|like|you know|basically|actually|sort of|kind of)\b", re.I)


def _qa_pairs(turns: list[dict], plan: list[dict]) -> list[dict]:
    """Per planned question: its wording, any follow-ups asked, and every answer given."""
    pairs: dict[int, dict] = {}
    for t in turns:
        q = t.get("q") or 0
        if not 1 <= q <= len(plan):
            continue
        p = pairs.setdefault(q, {"number": q, "question": plan[q - 1]["text"], "follow_ups": [], "answers": []})
        if t["role"] == "interviewer" and t.get("kind") == "follow_up":
            p["follow_ups"].append(t["text"])
        elif t["role"] == "candidate":
            p["answers"].append(t["text"])
    return [pairs[k] for k in sorted(pairs)]


def basic_feedback(turns: list[dict], plan: list[dict]) -> dict:
    pairs = _qa_pairs(turns, plan)
    answered = [p for p in pairs if any(a.strip() for a in p["answers"])]
    words = [len(" ".join(p["answers"]).split()) for p in answered]
    fillers = sum(len(FILLERS.findall(" ".join(p["answers"]))) for p in pairs)
    short = [p["number"] for p, w in zip(answered, words, strict=True) if w < 40]
    tips = []
    if short:
        tips.append(f"Answers to question(s) {', '.join(map(str, short))} were brief. Aim for 1-2 minutes using STAR: situation, task, action, result.")
    if fillers > 8:
        tips.append(f"You used filler words about {fillers} times. Short pauses sound more confident than 'um' or 'like'.")
    if len(answered) < len(pairs):
        tips.append(f"{len(pairs) - len(answered)} question(s) went unanswered. Even a partial answer beats silence.")
    tips.append("Back each claim with a number or an outcome (time saved, users served, cost reduced).")
    return {
        "overall_score": None,
        "summary": (
            f"You answered {len(answered)} of {len(pairs)} questions, averaging {round(sum(words) / len(words)) if words else 0} "
            "words per answer. Detailed AI feedback needs an AI key (set LLM_PROVIDER=groq and GROQ_API_KEY)."
        ),
        "strengths": [f"Answered {len(answered)} questions"] if answered else [],
        "improvements": tips,
        "questions": [
            {"number": p["number"], "rating": None,
             "comment": f"{len(' '.join(p['answers']).split())} words." if any(a.strip() for a in p["answers"]) else "No answer."}
            for p in pairs
        ],
        "engine": "basic",
    }


def make_feedback(report: dict, turns: list[dict], plan: list[dict]) -> dict:
    pairs = _qa_pairs(turns, plan)
    if not any(any(a.strip() for a in p["answers"]) for p in pairs):
        fb = basic_feedback(turns, plan)
        fb["summary"] = "No answers were recorded in this interview, so there is nothing to give feedback on yet."
        return fb
    if ai.chat_available():
        try:
            transcript = "\n\n".join(
                f"Q{p['number']}: {p['question']}\n"
                + "".join(f"FOLLOW-UP: {f}\n" for f in p["follow_ups"])
                + f"ANSWERS: {' / '.join(a for a in p['answers'] if a.strip()) or '(no answer)'}"
                for p in pairs
            )
            jd = report.get("jd", {})
            data = ai.chat_json(FEEDBACK_SYSTEM, f"JOB: {jd.get('title')} at {jd.get('company') or 'the company'}\n\n{transcript}")
            numbers = {p["number"] for p in pairs}
            score = data.get("overall_score")
            return {
                "overall_score": max(0, min(100, int(score))) if isinstance(score, (int, float)) else None,
                "summary": _clean(data.get("summary"), 1200),
                "strengths": [_clean(s, 300) for s in data.get("strengths", []) if _clean(s)][:6],
                "improvements": [_clean(s, 300) for s in data.get("improvements", []) if _clean(s)][:6],
                "questions": [
                    {
                        "number": q["number"],
                        "rating": max(1, min(5, int(q["rating"]))) if isinstance(q.get("rating"), (int, float)) else None,
                        "comment": _clean(q.get("comment"), 400),
                    }
                    for q in data.get("questions", [])
                    if isinstance(q, dict) and q.get("number") in numbers
                ],
                "engine": ai.engine_name(),
            }
        except Exception as exc:
            log.warning("interview feedback via AI failed, using basic feedback: %s", exc)
    return basic_feedback(turns, plan)


# ---------- transcript export ----------


def _clock(seconds: float) -> str:
    seconds = max(int(seconds), 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def transcript_text(meta: dict, turns: list[dict], persona: Persona, candidate: str, markdown: bool) -> str:
    title = f"Mock interview: {meta['role']}" + (f" at {meta['company']}" if meta.get("company") else "")
    out = [f"# {title}" if markdown else title, ""]
    out.append(f"Date: {meta['date']}  |  Interviewer: {persona.name} ({persona.title})  |  Candidate: {candidate}")
    out.append(f"Resume: {meta['resume']}  |  Questions: {meta['questions']}")
    out.append("")
    for t in turns:
        who = persona.name if t["role"] == "interviewer" else candidate
        label = f"Q{t['q']}" if t["role"] == "interviewer" and t.get("kind") == "question" else ""
        stamp = _clock(t.get("t", 0))
        text = t["text"] or "(no answer)"
        if markdown:
            out.append(f"**[{stamp}] {who}**{f' ({label})' if label else ''}: {text}\n")
        else:
            out.append(f"[{stamp}] {who}{f' ({label})' if label else ''}: {text}\n")
    fb = meta.get("feedback")
    if fb:
        out.append("## Feedback" if markdown else "FEEDBACK")
        if fb.get("overall_score") is not None:
            out.append(f"Overall: {fb['overall_score']}/100")
        out.append(fb.get("summary", ""))
        for head, key in (("Strengths", "strengths"), ("To improve", "improvements")):
            if fb.get(key):
                out.append(f"\n{'### ' if markdown else ''}{head}")
                out.extend(f"- {s}" for s in fb[key])
    return "\n".join(out).rstrip() + "\n"
