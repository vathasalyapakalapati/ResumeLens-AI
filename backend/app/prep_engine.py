"""Interview prep books: scenario questions in four categories, each with what the interviewer is
looking for, how to answer, and which resume lines to draw on.

With an AI key the questions come from the model (one call per category). Without one, or when a
call fails, templates filled from the match report are used, so a prep book is always produced.
"""

import logging
import re
from datetime import UTC, datetime

from . import ai
from .interview_engine import BEHAVIORAL
from .scoring.skills import find_skills, mentions

log = logging.getLogger(__name__)

CATEGORIES = [
    {
        "key": "technical",
        "title": "Technical",
        "description": "Scenario questions on the tools and skills this job asks for, including the ones your resume doesn't show yet.",
    },
    {
        "key": "system_design",
        "title": "System design",
        "description": "Open-ended design problems built around this job's stack. Interviewers judge structure, trade-offs and communication.",
    },
    {
        "key": "culture",
        "title": "Cultural fit",
        "description": "Questions about how you work, drawn from the values and working style the job description signals.",
    },
    {
        "key": "behavioral",
        "title": "Behavioural",
        "description": "Past-experience questions. Answer with STAR (situation, task, action, result), using real stories from your resume.",
    },
]
CATEGORY_KEYS = [c["key"] for c in CATEGORIES]
DIFFICULTIES = ("easy", "medium", "hard")
STAR = [
    "Situation: set the scene in one or two sentences.",
    "Task: what you were responsible for, and what was at stake.",
    "Action: what you did, in the first person, with specifics.",
    "Result: the measurable outcome, then what you learned.",
]


def _clean(text: object, limit: int = 600) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def _q(category: str, question: str, why: str, approach: list[str], difficulty: str,
       evidence: list[str] | None = None, focus: str | None = None, requirement: str | None = None) -> dict:
    return {
        "category": category,
        "question": question,
        "why": why,
        "approach": approach,
        "difficulty": difficulty,
        "evidence": evidence or [],
        "focus": focus,
        "requirement": requirement,
    }


# ---------- facts from the report ----------

DATA_STORES = ["PostgreSQL", "MySQL", "MongoDB", "Redis", "DynamoDB", "Cassandra", "Elasticsearch", "Snowflake", "BigQuery", "SQL Server", "Oracle", "SQL"]
QUEUES = ["Kafka", "RabbitMQ", "Message queues", "Celery"]
CLOUDS = ["AWS", "Azure", "GCP"]
APIS = ["REST", "GraphQL", "gRPC"]
SOFT = {"Communication", "Leadership", "Collaboration", "Problem solving", "Stakeholder management", "Agile",
        "Project management", "Product management", "Excel", "Jira", "Figma", "Salesforce", "SAP"}


class Facts:
    def __init__(self, report: dict, resume_lines: list[dict], jd_lines: list[dict]):
        self.report = report
        self.role = (report.get("jd") or {}).get("title") or "this role"
        self.company = (report.get("jd") or {}).get("company")
        self.resume_lines = resume_lines
        self.jd_text = "\n".join(x["text"] for x in jd_lines)
        kw = report.get("keywords") or {}
        jd_skills = find_skills(self.jd_text) or [*kw.get("matched", []), *kw.get("missing", [])]
        self.tech = [s for s in jd_skills if s not in SOFT]
        self.matched = [s for s in self.tech if s in kw.get("matched", [])]
        self.missing = [s for s in self.tech if s in kw.get("missing", [])]
        reqs = report.get("requirements", [])
        self.gaps = [r for r in reqs if r["status"] != "met"]
        self.strengths = [r for r in reqs if r["status"] == "met" and r.get("evidence")]
        self.technical_role = bool(self.tech)

    def lines_for(self, skill: str, limit: int = 2) -> list[str]:
        return [x["id"] for x in self.resume_lines if mentions(skill, x["text"])][:limit]

    def first(self, options: list[str], default: str) -> str:
        return next((s for s in options if s in self.tech), default)

    def quote(self, line_id: str) -> str:
        return next((x["text"] for x in self.resume_lines if x["id"] == line_id), "").lstrip("-•* ").strip()


# ---------- scripted questions ----------

TECH_TEMPLATES = [
    ("A {skill} component you own starts failing intermittently in production, but only at peak load. Walk me through how you'd investigate and fix it.",
     "Structured debugging under pressure: observability, forming and testing hypotheses, fixing safely and preventing a repeat.",
     ["Start with impact and a quick mitigation (rollback, feature flag, scaling).", "Use metrics, logs and traces to narrow it down; test one hypothesis at a time.",
      "Explain the root cause and the permanent fix.", "Finish with prevention: alerts, tests, a runbook."], "medium"),
    ("Tell me about a trade-off you made using {skill}. What alternatives did you consider, and why did you choose what you did?",
     "Depth of understanding and engineering judgement, not just familiarity with the tool.",
     ["Pick a real decision from your experience.", "Name two alternatives and the criteria you compared them on (cost, speed, complexity, team skills).",
      "Say what you'd do differently now."], "medium"),
    ("You join the team and find that the parts of the system built on {skill} have no tests and keep breaking. What do you do in your first month?",
     "Pragmatism: improving quality without stopping delivery, and bringing the team along.",
     ["Measure first: which areas break most often and why.", "Add tests around the riskiest paths before changing them.",
      "Agree standards with the team (CI checks, reviews) instead of rewriting alone.", "Show how you'd prove it worked (fewer incidents, faster releases)."], "medium"),
    ("A {skill}-based workflow has become ten times slower as usage grew. How would you find the bottleneck and speed it up?",
     "Performance thinking: measuring before optimising, and knowing where the usual bottlenecks are.",
     ["Reproduce and measure: profiling, query plans, timings per step.", "Fix the biggest bottleneck first (I/O, N+1 queries, missing indexes, caching, batching).",
      "Verify with numbers and guard against regressions with a benchmark or alert."], "hard"),
    ("A teammate's pull request uses {skill} in a way you think will cause problems later. How do you handle the review?",
     "Technical depth plus collaboration: giving clear, kind, evidence-based feedback.",
     ["Ask questions first; you may be missing context.", "Explain the concrete risk with an example or data.",
      "Suggest an alternative and agree on it together; escalate only if it really matters."], "easy"),
]
GAP_TEMPLATE = (
    "The team relies heavily on {skill}, which isn't on your resume. In week two, a production issue involving it lands on you. How do you handle it?",
    "Honesty about gaps, learning speed, and how related experience transfers.",
    ["Be upfront that it's new to you, then show what transfers from your experience.", "Describe how you'd learn fast: docs, the codebase, pairing with an expert.",
     "Show you'd ask for help early while still owning the outcome."], "hard",
)
GENERIC_TECH = [
    ("Walk me through the most technically difficult problem you've solved for a {role} job. What made it hard?",
     "Depth, problem-solving process and honest reflection.", STAR[:2] + ["Spend most of the time on your reasoning and the options you rejected.", "End with the result and what you'd do differently."], "medium"),
    ("How do you make sure the work you deliver as a {role} is correct and reliable before it reaches users?",
     "Quality habits: testing, reviews, monitoring, and owning outcomes.", ["Describe your actual process step by step.", "Give an example where it caught a real problem."], "easy"),
]

SD_TEMPLATES = [
    "Design a service that ingests events from many clients through {queue}, stores them in {store}, and serves aggregated results through a {api} API. It must survive 10x traffic spikes.",
    "Design a notification system (email, SMS and in-app) for millions of users on {cloud}, with retries, rate limits and user preferences.",
    "A read-heavy dashboard backed by {store} has become slow as data grew 50x. Redesign the data path so pages load in under 300 ms.",
    "Design a document upload and processing pipeline on {cloud}: users upload files, they are scanned and parsed, and results appear within a minute.",
    "Design a multi-tenant {api} API with authentication, per-tenant rate limiting and audit logs.",
    "How would you move one core feature out of a monolith into its own service with zero downtime?",
    "Design a job scheduler that runs millions of background jobs a day, with retries, priorities and visibility into failures.",
    "Design a caching strategy for a product catalogue that changes hourly but is read millions of times a day.",
    "Design search over the company's documents with filters, ranking and typo tolerance.",
    "Design a shareable-link system with expiry, access control and usage analytics.",
]
SD_APPROACH = [
    "Clarify requirements and scale first: users, requests per second, data size, latency, consistency.",
    "Sketch the main components and how data flows between them.",
    "Choose storage and justify it by access patterns and consistency needs.",
    "Handle scale and failure: caching, queues, replication, retries, idempotency.",
    "Cover monitoring, security and cost, and say which trade-offs you made.",
]
PROCESS_DESIGN = [
    "Design the end-to-end process for onboarding a new client in this {role} job, from signed contract to first success. Where would it break at 10x volume?",
    "Our team gets requests from five departments with conflicting priorities. Design an intake and prioritisation process.",
    "Design a weekly reporting process that leadership actually reads and acts on. What would you measure?",
    "A key process depends on one person's spreadsheet. Design a more reliable replacement without disrupting the business.",
    "Design how you'd measure success in your first 90 days in this role.",
]
PROCESS_APPROACH = [
    "Clarify the goal, the users and what success looks like.",
    "Map the current steps and where they fail.",
    "Propose the new flow, with owners, tools and hand-offs.",
    "Explain how you'd roll it out, measure it and keep improving it.",
]

CULTURE_CUES = [
    (r"fast[- ]paced|start-?up|ambigu|changing priorities", "Tell me about a time priorities changed suddenly. How did you adapt, and how do you work when things are ambiguous?"),
    (r"remote|distributed|async|hybrid", "How do you stay effective and connected in a remote or hybrid team? What habits do you rely on?"),
    (r"ownership|owner|autonom|self-starter|proactive", "Describe something you owned end to end without being asked. Why did you take it on?"),
    (r"customer|client|user[- ]focus|user experience", "Tell me about a time you pushed for the customer's interest when it wasn't the easy option."),
    (r"collaborat|cross[- ]functional|teamwork|team player", "Describe how you work with people outside your function, like product, design or sales. What makes that go well?"),
    (r"learn|growth|curious|curiosity", "What have you taught yourself recently, and how did you go about it?"),
    (r"diversity|inclusi|belonging|equit", "How do you make sure everyone on a team is heard, especially quieter people or people from different backgrounds?"),
    (r"quality|craft|excellence|attention to detail", "When have you had to balance speed against quality? How did you decide?"),
    (r"mentor|coach|grow others|develop others", "Tell me about someone you helped grow. What did you do, and what changed for them?"),
    (r"data[- ]driven|metrics|experiment", "Tell me about a decision you changed because of data. What did the data show?"),
]
CULTURE_GENERIC = [
    "Why this company, and why this {role} position in particular?",
    "What kind of manager and team gets the best out of you?",
    "Describe the best team you've ever worked in. What made it work?",
    "How do you handle a decision you disagree with but have to carry out?",
    "What would former teammates say is the best and the hardest thing about working with you?",
    "What does a great first year in this role look like to you?",
]
CULTURE_APPROACH = [
    "Research the company's values and mission and refer to them specifically.",
    "Answer with a real example that shows the value in action.",
    "Be honest: fit works both ways, so it's fine to say what you look for too.",
]


def scripted(category: str, f: Facts, n: int) -> list[dict]:
    out: list[dict] = []
    if category == "technical":
        pool = f.matched or f.tech
        for i, skill in enumerate(pool):
            t = TECH_TEMPLATES[i % len(TECH_TEMPLATES)]
            out.append(_q(category, t[0].format(skill=skill), t[1], t[2], t[3], f.lines_for(skill), skill))
        for skill in f.missing:  # gaps interleaved after the first strengths
            out.insert(min(len(out), 2 * (f.missing.index(skill) + 1)),
                       _q(category, GAP_TEMPLATE[0].format(skill=skill), GAP_TEMPLATE[1], GAP_TEMPLATE[2], GAP_TEMPLATE[3], [], skill))
        for t in GENERIC_TECH:
            out.append(_q(category, t[0].format(role=f.role), t[1], t[2], t[3]))
    elif category == "system_design":
        if f.technical_role:
            slots = {
                "queue": f.first(QUEUES, "a message queue"),
                "store": f.first(DATA_STORES, "a database"),
                "cloud": f.first(CLOUDS, "the cloud"),
                "api": f.first(APIS, "REST"),
            }
            for t in SD_TEMPLATES:
                q = t.format(**slots)
                out.append(_q(category, q, "Whether you can structure an open problem, make sensible trade-offs and explain them clearly.",
                              SD_APPROACH, "hard" if len(out) % 3 == 0 else "medium", focus="system design"))
        else:
            for t in PROCESS_DESIGN:
                out.append(_q(category, t.format(role=f.role), "How you structure a messy problem into a workable, measurable process.",
                              PROCESS_APPROACH, "medium", focus="process design"))
    elif category == "culture":
        text = f.jd_text.lower()
        cued = [q for pattern, q in CULTURE_CUES if re.search(pattern, text)]
        for q in cued + [g.format(role=f.role) for g in CULTURE_GENERIC]:
            why = "Whether your way of working matches what this team says it values." if q in cued else "Motivation, self-awareness and how you'd fit with the team."
            out.append(_q(category, q, why, CULTURE_APPROACH, "easy", focus="culture"))
    else:  # behavioral
        for r in f.strengths:
            quote = f.quote(r["evidence"][0])
            if quote:
                out.append(_q(category, f'Your resume says "{quote[:140]}". Tell me the story behind it: what was hardest, and what did you personally do?',
                              "Whether your resume claims hold up, and how you behave when things get difficult.", STAR, "medium", r["evidence"][:1], r["text"], r["id"]))
        for r in f.gaps[:2]:
            out.append(_q(category, f"Tell me about a time you had to deliver something with little prior experience. This job asks for {r['text'].rstrip('.')}, so pick a story that shows how you learn.",
                          "Learning ability and resilience, which matter for the gaps in your profile.", STAR, "medium", focus=r["text"], requirement=r["id"]))
        for b in BEHAVIORAL:
            out.append(_q(category, b, "Self-awareness, judgement and how you work with others.", STAR, "medium"))

    # de-duplicate (same resume line can back several requirements), keep order
    seen, unique = set(), []
    for q in out:
        if q["question"] not in seen:
            seen.add(q["question"])
            unique.append(q)
    return unique[:n]


# ---------- AI questions ----------

AI_SYSTEM = """You are a senior interviewer and career coach writing an interview prep book for this candidate and job.
Write exactly {n} {title} questions. {guide}
Questions must be scenario-based and specific to THIS job and THIS candidate's resume (mention their real tools, projects and gaps).
For each question give: why the interviewer asks it, 3-5 concrete answer talking points tailored to the candidate,
resume line ids (e.g. "L7") the candidate should draw on (only ids that exist; empty list if none), and a difficulty.
Respond with JSON only:
{{"questions": [{{"question": "...", "why": "...", "approach": ["..."], "evidence": ["L3"], "difficulty": "easy|medium|hard", "focus": "skill or theme"}}]}}"""

AI_GUIDES = {
    "technical": "Cover the job's core technologies and skills, mixing debugging, trade-offs, performance and best-practice scenarios. Include questions on skills the report marks missing or partial.",
    "system_design": "Give open-ended design problems that use this job's actual stack and domain (for non-engineering roles, design processes or solutions instead). Talking points should follow: requirements, components, data, scale and failure, trade-offs.",
    "culture": "Use the values, working style and team cues in the job description (pace, ownership, collaboration, customers, remote work...), plus motivation for this company and role.",
    "behavioral": "Past-experience questions to be answered with STAR. Tie several to specific resume lines (probe their claims) and some to the candidate's gaps.",
}


def ai_questions(category: dict, context: str, resume_ids: set[str], n: int) -> list[dict]:
    data = ai.chat_json(
        AI_SYSTEM.format(n=n, title=category["title"].lower(), guide=AI_GUIDES[category["key"]]), context, temperature=0.6
    )
    out = []
    for item in data.get("questions", []):
        if not isinstance(item, dict) or not _clean(item.get("question")):
            continue
        out.append(_q(
            category["key"],
            _clean(item.get("question"), 500),
            _clean(item.get("why"), 300),
            [_clean(a, 300) for a in (item.get("approach") or []) if _clean(a)][:5],
            item.get("difficulty") if item.get("difficulty") in DIFFICULTIES else "medium",
            [e for e in (item.get("evidence") or []) if isinstance(e, str) and e in resume_ids][:3],
            _clean(item.get("focus"), 80) or None,
        ))
    if not out:
        raise ValueError("model returned no questions")
    return out[:n]


# ---------- assemble ----------


def build(report: dict, resume_lines: list[dict], jd_lines: list[dict], per_category: int, on_step=None) -> tuple[dict, str]:
    from .interview_engine import _context  # same resume/JD/report context the interviewer uses

    f = Facts(report, resume_lines, jd_lines)
    use_ai = ai.chat_available()
    context = _context(report, resume_lines, jd_lines) if use_ai else ""
    resume_ids = {x["id"] for x in resume_lines}
    engines, sections, warnings = set(), [], []
    for cat in CATEGORIES:
        if on_step:
            on_step(cat["key"])
        questions: list[dict] = []
        if use_ai:
            try:
                questions = ai_questions(cat, context, resume_ids, per_category)
                engines.add(ai.engine_name())
            except Exception as exc:
                log.warning("prep %s via AI failed, using templates: %s", cat["key"], exc)
                warnings.append(f"{cat['title']} questions came from templates because the AI model was unavailable.")
        if len(questions) < per_category:  # top up (or fully fill) from templates
            have = {q["question"] for q in questions}
            questions += [q for q in scripted(cat["key"], f, per_category * 2) if q["question"] not in have][: per_category - len(questions)]
            engines.add("built-in")
        for i, q in enumerate(questions, start=1):
            q["id"] = f"{cat['key'][0].upper()}{i}"
        sections.append({**cat, "questions": questions})

    cited = sorted({e for s in sections for q in s["questions"] for e in q["evidence"]}, key=lambda x: int(x[1:]))
    by_id = {x["id"]: x["text"] for x in resume_lines}
    total = sum(len(s["questions"]) for s in sections)
    focus = ", ".join(g["text"] for g in f.gaps[:3]) or "none flagged"
    content = {
        "role": f.role,
        "company": f.company,
        "resume": (report.get("resume") or {}).get("title"),
        "verdict": report.get("verdict"),
        "overview": (
            f"{total} scenario questions in four categories for the {f.role} role{f' at {f.company}' if f.company else ''}, "
            f"built from your resume and the job description. Gaps to prepare for most: {focus}."
        ),
        "tips": [
            "Prepare 5-6 real stories (a success, a failure, a conflict, a leadership moment, a fast-learning moment) and reuse them across questions.",
            "Quantify results: time saved, users served, revenue, latency, cost.",
            "For system design, talk through your thinking out loud and state assumptions before designing.",
            *(f"Have an honest, specific answer ready for the gap: {g['text']}." for g in f.gaps[:2]),
            "Research the company's product, values and recent news, and prepare 2-3 thoughtful questions for them.",
        ],
        "warnings": warnings,
        "categories": sections,
        "resume_lines": {lid: by_id[lid] for lid in cited if lid in by_id},
        "generated_at": datetime.now(UTC).isoformat(),
    }
    engine = " + ".join(sorted(engines))
    return content, engine


# ---------- exports ----------


def to_markdown(c: dict) -> str:
    title = f"Interview prep: {c['role']}" + (f" at {c['company']}" if c.get("company") else "")
    out = [f"# {title}", "", f"_Resume: {c.get('resume') or '-'} · Match: {c.get('verdict') or '-'}_", "", c["overview"], "", "## Tips", ""]
    out += [f"- {t}" for t in c["tips"]]
    for s in c["categories"]:
        out += ["", f"## {s['title']}", "", f"_{s['description']}_", ""]
        for i, q in enumerate(s["questions"], start=1):
            out += [f"### {i}. {q['question']}", "", f"**Difficulty:** {q['difficulty']}" + (f" · **Focus:** {q['focus']}" if q.get("focus") else ""), ""]
            if q.get("why"):
                out += [f"**What they're looking for:** {q['why']}", ""]
            if q.get("approach"):
                out += ["**How to answer:**", ""] + [f"- {a}" for a in q["approach"]] + [""]
            if q.get("evidence"):
                out += ["**From your resume:**", ""] + [f"> {e}: {c['resume_lines'].get(e, '')}" for e in q["evidence"]] + [""]
    return "\n".join(out).rstrip() + "\n"


_LATIN = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                        "…": "...", "•": "-", " ": " ", "→": "->", "≤": "<=", "≥": ">="})


def _latin(text: str) -> str:
    """The built-in PDF fonts only cover Latin-1; map common punctuation and drop the rest."""
    return str(text).translate(_LATIN).encode("latin-1", "replace").decode("latin-1")


def to_pdf(c: dict) -> bytes:
    from fpdf import FPDF

    primary = (59, 76, 202)
    muted = (100, 110, 125)

    class Book(FPDF):
        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", size=8)
            self.set_text_color(*muted)
            self.cell(0, 6, _latin(f"ResumeLens AI · Interview prep · page {self.page_no()}"), align="C")

    pdf = Book(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(16, 16, 16)
    pdf.add_page()
    w = pdf.epw

    def text(s: str, size: float = 10, style: str = "", color=(30, 35, 45), h: float = 5.2):
        pdf.set_font("Helvetica", style=style, size=size)
        pdf.set_text_color(*color)
        pdf.multi_cell(w, h, _latin(s), align="L", new_x="LMARGIN", new_y="NEXT")

    title = f"Interview prep: {c['role']}" + (f" at {c['company']}" if c.get("company") else "")
    text(title, 20, "B", primary, 9)
    text(f"Resume: {c.get('resume') or '-'}   |   Match: {c.get('verdict') or '-'}", 9, color=muted)
    pdf.ln(3)
    text(c["overview"], 10.5)
    pdf.ln(2)
    text("Tips", 12, "B", primary, 7)
    for t in c["tips"]:
        text(f"-  {t}", 9.5)
    for s in c["categories"]:
        pdf.add_page()
        text(s["title"], 16, "B", primary, 8)
        text(s["description"], 9.5, "I", muted)
        pdf.ln(2)
        for i, q in enumerate(s["questions"], start=1):
            if pdf.get_y() > pdf.h - 60:
                pdf.add_page()
            pdf.set_draw_color(220, 224, 232)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + w, pdf.get_y())
            pdf.ln(2)
            text(f"{i}. {q['question']}", 11, "B", h=5.6)
            meta = f"Difficulty: {q['difficulty']}" + (f"   |   Focus: {q['focus']}" if q.get("focus") else "")
            text(meta, 8.5, color=muted)
            if q.get("why"):
                text(f"What they're looking for: {q['why']}", 9.5, "I", (60, 66, 80))
            if q.get("approach"):
                text("How to answer:", 9.5, "B")
                for a in q["approach"]:
                    text(f"   -  {a}", 9.5)
            if q.get("evidence"):
                text("From your resume:", 9.5, "B")
                for e in q["evidence"]:
                    text(f"   {e}: {c['resume_lines'].get(e, '')}", 9.5, color=(40, 110, 70))
            pdf.ln(3)
    return bytes(pdf.output())
