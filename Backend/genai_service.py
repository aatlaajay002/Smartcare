"""
Generative AI service: turns a medical report (text / PDF / DOCX) into a simple explanation using an LLM API.
Supported providers: Anthropic (Claude), Google Gemini, OpenAI. Set the key in Backend/.env.
If no key is configured (or the API call fails) an *offline rule-based* simplifier is used so the app never
crashes - the response is clearly labelled with source = "offline".
"""
import re
import requests
from config import Config

SYSTEM_PROMPT = (
    "You are a friendly medical-report explainer for patients with no medical background. "
    "Rewrite the doctor's diagnosis/prescription in very simple, easy-to-understand English, addressing the patient as 'you'. "
    "Rules: (1) Use only information present in the report - never invent diagnoses, drugs or doses. "
    "(2) Explain medical terms and abbreviations in plain words (e.g. 'twice daily', 'BD', 'HbA1c'). "
    "(3) Cover: what condition/finding the patient has, which medicines to take and how, and the lifestyle advice. "
    "(4) Keep it short: 3-6 sentences, or a short paragraph followed by at most 4 bullet points. No headings. "
    "(5) End with one short sentence reminding the patient to follow their doctor's advice."
)

DEFAULT_MODELS = {"anthropic": "claude-sonnet-4-6", "gemini": "gemini-2.0-flash", "openai": "gpt-4o-mini"}


# ------------------------------------------------------------------ input handling
def extract_text(filename: str, data: bytes) -> str:
    """Extract raw text from an uploaded report file."""
    name = filename.lower()
    if name.endswith((".txt", ".md", ".text")):
        return data.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        from io import BytesIO
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(BytesIO(data)).pages)
    if name.endswith(".docx"):
        from io import BytesIO
        import docx
        return "\n".join(p.text for p in docx.Document(BytesIO(data)).paragraphs)
    raise ValueError("Unsupported file type. Please upload .txt, .pdf or .docx")


def clean_report(text: str) -> str:
    """Extract the relevant content: normalise whitespace, drop page numbers / empty lines, limit length."""
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.splitlines()]
    lines = [l for l in lines if l and not re.fullmatch(r"(page )?\d+( of \d+)?", l.lower())]
    return "\n".join(lines)[: Config.MAX_REPORT_CHARS]


# ------------------------------------------------------------------ LLM providers
def _provider():
    p = Config.LLM_PROVIDER
    if p in DEFAULT_MODELS:
        return p
    if Config.ANTHROPIC_API_KEY: return "anthropic"
    if Config.GEMINI_API_KEY: return "gemini"
    if Config.OPENAI_API_KEY: return "openai"
    return None


def _llm(provider: str, system: str, messages: list, max_tokens: int = 500) -> str:
    """One LLM call. messages = [{"role": "user"|"assistant", "content": str}, ...]"""
    model = Config.LLM_MODEL or DEFAULT_MODELS[provider]
    if provider == "anthropic":
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=45,
                          headers={"x-api-key": Config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"},
                          json={"model": model, "max_tokens": max_tokens, "system": system, "messages": messages})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"]).strip()
    if provider == "gemini":
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                          params={"key": Config.GEMINI_API_KEY}, timeout=45,
                          json={"systemInstruction": {"parts": [{"text": system}]},
                                "contents": [{"role": "user" if m["role"] == "user" else "model",
                                              "parts": [{"text": m["content"]}]} for m in messages],
                                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3}})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if provider == "openai":
        r = requests.post("https://api.openai.com/v1/chat/completions", timeout=45,
                          headers={"Authorization": f"Bearer {Config.OPENAI_API_KEY}"},
                          json={"model": model, "max_tokens": max_tokens, "temperature": 0.3,
                                "messages": [{"role": "system", "content": system}] + messages})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    raise ValueError("Unknown provider")


def _report_prompt(report: str) -> str:
    return f"Medical report:\n\"\"\"\n{report}\n\"\"\"\n\nExplain this to the patient in simple language."


# ------------------------------------------------------------------ offline fallback
_ABBR = {r"\bbd\b|\bbid\b": "twice a day", r"\bod\b": "once a day", r"\btds\b|\btid\b": "three times a day",
         r"\bqid\b": "four times a day", r"\bhs\b": "at bedtime", r"\bsos\b": "only when needed",
         r"\bpc\b": "after food", r"\bac\b": "before food"}
_CONDITIONS = {r"type\s*2 diabetes": "Type 2 diabetes (high blood sugar)", r"type\s*1 diabetes": "Type 1 diabetes",
               r"hypertension|high blood pressure": "high blood pressure", r"asthma": "asthma (a breathing condition)",
               r"hypothyroid\w*": "an underactive thyroid", r"anemia|anaemia": "low blood iron (anemia)",
               r"gerd|acid reflux": "acid reflux", r"migraine": "migraine headaches",
               r"viral fever": "a viral fever", r"arthritis": "joint inflammation (arthritis)"}


def offline_simplify(report: str) -> str:
    """Very simple rule-based explanation, used only when no LLM key is available."""
    low = report.lower()
    found = [plain for pat, plain in _CONDITIONS.items() if re.search(pat, low)]
    text = re.sub(r"\b(tab|cap|inj|syp|syr)\.\s*", "", report, flags=re.I)          # "Tab. Metformin" -> "Metformin"
    meds, advice = [], []
    for s in [x.strip() for x in re.split(r"[.\n;]", text) if x.strip()]:
        s = re.sub(r"^\d+[.)]\s*", "", s)                                          # list numbering
        s = re.sub(r"^(rx|advice|diagnosis|treatment|plan|medicines?)\s*:\s*", "", s, flags=re.I).strip()
        sl = s.lower()
        if not s or sl.startswith(("patient:", "name:")):
            continue
        if re.search(r"\d+\s?(mg|mcg|ml|g|iu)\b|tablet|capsule|syrup|injection|inhaler", sl):
            for pat, rep in _ABBR.items():
                s = re.sub(pat, rep, s, flags=re.I)
            meds.append(s)
        elif re.match(r"(avoid|reduce|limit|stop|do not|don't|regular|daily|drink|eat|exercise|rest|follow|walk|review|do |take rest)", sl):
            advice.append(s[0].lower() + s[1:])
    parts = [("Your report mentions " + ", ".join(found) + ".") if found else "Here is a simple version of your report."]
    if meds:
        parts.append("Medicines: " + "; ".join(meds) + ". Take them exactly as prescribed.")
    if advice:
        parts.append("Your doctor's advice: " + "; ".join(advice) + ".")
    parts.append("Please follow your doctor's advice.")
    return " ".join(parts)


# ------------------------------------------------------------------ public API
def summarize_report(text: str) -> dict:
    report = clean_report(text)
    if len(report) < 8:
        raise ValueError("The report looks empty. Please provide the diagnosis / prescription text.")
    provider = _provider()
    if provider:
        try:
            return {"summary": _llm(provider, SYSTEM_PROMPT, [{"role": "user", "content": _report_prompt(report)}]), "source": "llm", "provider": provider,
                    "model": Config.LLM_MODEL or DEFAULT_MODELS[provider]}
        except Exception as e:                      # network / quota / bad key -> graceful fallback
            return {"summary": offline_simplify(report), "source": "offline", "provider": None,
                    "warning": f"LLM call failed ({type(e).__name__}); showing offline simplification."}
    return {"summary": offline_simplify(report), "source": "offline", "provider": None,
            "warning": "No LLM API key configured - showing offline simplification. Add a key in Backend/.env."}


# ------------------------------------------------------------------ AI Health Assistant (chat)
ASSISTANT_PROMPT = (
    "You are SmartCare's AI Health Assistant inside a doctor-appointment app. Answer EXACTLY what the user asked, in simple language and plain text, "
    "at most about 130 words. Choose the answer shape that fits the question (a short paragraph, numbered steps, a few bullets starting with '• ', or a short "
    "list of foods) and do not reuse the same structure every time. Never diagnose and never prescribe medicines or doses. For symptoms give a few safe "
    "self-care tips and say when to see a doctor. If the message describes red-flag symptoms (chest pain, trouble breathing, stroke signs, severe bleeding, "
    "loss of consciousness, thoughts of self-harm) tell the person to seek emergency care immediately. If a suggested specialist is given, mention that this "
    "type of doctor can be booked in the app. Politely decline questions that are not about health or using this app."
)
_RED_FLAGS = re.compile(r"chest pain|can.?t breathe|difficulty breathing|short(ness)? of breath|unconscious|faint|stroke|"
                        r"severe bleeding|heavy bleeding|seizure|suicid|kill myself|self.?harm", re.I)


def _clean_history(history):
    """Keep the last few valid turns, starting with a user turn and alternating roles."""
    out = []
    for m in (history or [])[-6:]:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str) and m["content"].strip():
            if out and out[-1]["role"] == m["role"]:
                out[-1]["content"] += "\n" + m["content"][:600]
            else:
                out.append({"role": m["role"], "content": m["content"][:600]})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


import health_kb

NOT_HEALTH = ("I can only help with health questions and with using this app. Try asking, for example:\n"
              "• \"I have a sore throat and fever for two days\"\n• \"What should I eat when I have acidity?\"\n• \"Which doctor should I see for a skin allergy?\"")


def assistant_reply(message: str, history, hint=None) -> dict:
    """hint = {'specialization', 'probability'} from the ML model (or None). Always returns a 'specialization' (or None) so doctors can be shown."""
    kb = health_kb.analyze(message, history)
    spec, offline = kb["spec"], kb["reply"]
    if offline is None:
        if hint:                                            # the ML model recognised symptoms that the knowledge base did not
            spec = hint["specialization"]
            offline = (f"What you describe is usually looked after by {health_kb._with_a(spec)}, who treats {health_kb.FOCUS.get(spec, 'this kind of problem')}.\n"
                       "To help the doctor, note when it started, what makes it better or worse, and any medicines you take. You can book one below.")
        else:
            offline = NOT_HEALTH
    provider = _provider()
    if provider:
        system = ASSISTANT_PROMPT + (f" Suggested specialist: {spec}." if spec else "")
        msgs = _clean_history(history) + [{"role": "user", "content": message}]
        while len(msgs) > 1 and msgs[0]["role"] != "user":
            msgs.pop(0)
        try:
            return {"reply": _llm(provider, system, msgs, 450), "source": "llm", "provider": provider, "specialization": spec}
        except Exception as e:
            return {"reply": offline, "source": "offline", "provider": None, "specialization": spec, "warning": f"LLM call failed ({type(e).__name__})."}
    return {"reply": offline, "source": "offline", "provider": None, "specialization": spec}
