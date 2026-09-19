import html
import json
import os
import re
from collections.abc import Iterator
from datetime import date as date_cls

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
REQUEST_TIMEOUT = 120

DOC_LABEL_RE = re.compile(r"^(.*?)-\d{4}-\d{2}-\d{2}$")

# Design tokens and component styles, lifted from the designer's mockup (design.html):
# the "Ask" empty state and the "Answer — with citations" state.
FONTS_HREF = (
    "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600"
    "&family=Space+Grotesk:wght@500;600&display=swap"
)

STYLE = """
<style>
@import url("__FONTS_HREF__");
:root{
  --bg:#fafafa; --surface:#ffffff; --text:#131c26; --text-muted:#5b6572; --text-faint:#8a93a0;
  --border:#e4e8ec; --border-strong:#d3d9e0; --accent:#1668a5; --accent-hover:#0f5488;
  --accent-soft:#e4eef7; --navy:#0b3049; --chip-bg:#f1f3f5;
}
html, body, .stApp{background:var(--bg) !important;color:var(--text);
  font-family:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif;}
#MainMenu, header[data-testid="stHeader"], footer,
[data-testid="stDecoration"], [data-testid="collapsedControl"]{display:none !important;}
.block-container{padding:0 !important;max-width:100% !important;}
/* Streamlit's own vertical-block gap beats a plain class selector on specificity;
   !important on every section override below is what actually wins. */
div[data-testid="stVerticalBlock"]{gap:0;}
button p{margin:0;}

/* header bar */
.st-key-header{background:var(--surface);border-bottom:1px solid var(--border);}
.st-key-header [data-testid="stHorizontalBlock"]{align-items:center !important;
  padding:16px 32px !important;justify-content:space-between !important;}
.st-key-header [data-testid="stHorizontalBlock"] > div{
  flex:0 0 auto !important;width:auto !important;}
.sc-brand{display:flex;align-items:center;gap:10px;}
.sc-logo{width:32px;height:32px;border-radius:9px 9px 9px 2px;background:var(--navy);
  display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.sc-logo span{font-family:'Space Grotesk',sans-serif;font-size:18px;font-weight:600;
  color:#fff;line-height:1;}
.sc-wordmark{font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:600;
  letter-spacing:-0.01em;}
.sc-wordmark .dark{color:var(--text);}
.sc-wordmark .accent{color:var(--accent);}
.st-key-header button{height:36px;padding:0 16px;border-radius:10px;
  border:1px solid var(--border-strong) !important;background:var(--surface) !important;
  font-weight:600;letter-spacing:0.01em;}
.st-key-header button:hover{border-color:var(--text-faint) !important;}
.st-key-header button p{color:var(--text-muted) !important;font-family:'IBM Plex Sans',sans-serif;
  font-size:13px !important;}
.st-key-header button:hover p{color:var(--text) !important;}

/* hero / ask state */
.st-key-hero{min-height:calc(100vh - 73px);display:flex !important;flex-direction:column !important;
  align-items:center !important;justify-content:center !important;gap:32px !important;
  max-width:640px;margin:0 auto;padding:32px;}
.sc-hero-title{margin:0;text-align:center;font-family:'Space Grotesk',sans-serif;
  font-size:32px;line-height:40px;font-weight:600;color:var(--text);}
.sc-hero-sub{margin:12px auto 0;text-align:center;max-width:520px;
  font-family:'IBM Plex Sans',sans-serif;font-size:15px;line-height:22px;color:var(--text-muted);}

.st-key-ask_form{width:100%;background:var(--surface);border:1px solid var(--border-strong);
  border-radius:24px;box-shadow:0 1px 2px rgba(9,20,31,0.08);padding:6px 6px 6px 20px;}
.st-key-ask_form [data-testid="stForm"]{border:none !important;padding:0 !important;}
.st-key-ask_form [data-testid="stHorizontalBlock"]{align-items:center !important;
  gap:8px !important;}
.st-key-ask_form input{border:none !important;background:transparent !important;
  box-shadow:none !important;font-family:'IBM Plex Sans',sans-serif;font-size:17px;
  color:var(--text) !important;padding:8px 0 !important;}
.st-key-ask_form button{width:44px;height:44px;border-radius:999px !important;
  border:none !important;background:var(--navy) !important;padding:0 !important;}
.st-key-ask_form button:hover{background:var(--accent-hover) !important;}
.st-key-ask_form button p{color:#fff !important;font-size:18px !important;line-height:1;}
.sc-hint{margin-top:8px;text-align:center;font-family:'IBM Plex Sans',sans-serif;
  font-size:13px;color:var(--text-faint);}

/* answer state */
.st-key-answer_page{max-width:880px;margin:0 auto;padding:32px 32px 64px;
  display:flex !important;flex-direction:column !important;gap:24px !important;}
.st-key-sources_list{display:flex !important;flex-direction:column !important;gap:10px !important;}
.sc-asked-label{font-family:'IBM Plex Sans',sans-serif;font-size:13px;font-weight:600;
  letter-spacing:0.01em;color:var(--text-muted);}
.sc-question{margin:4px 0 0;font-family:'Space Grotesk',sans-serif;font-size:20px;
  line-height:28px;font-weight:600;color:var(--text);}

.sc-card, .st-key-live_card{background:var(--surface);border:1px solid var(--border);
  border-radius:16px;padding:24px;box-shadow:0 1px 2px rgba(9,20,31,0.08);}
.sc-card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;}
.sc-card-title{display:flex;align-items:center;gap:8px;font-family:'Space Grotesk',sans-serif;
  font-size:16px;line-height:24px;font-weight:600;color:var(--text);}
.sc-logo-sm{width:24px;height:24px;border-radius:7px 7px 7px 2px;background:var(--navy);
  display:inline-flex;align-items:center;justify-content:center;}
.sc-logo-sm span{font-family:'Space Grotesk',sans-serif;font-size:13px;font-weight:600;color:#fff;}
.sc-meta{font-family:'IBM Plex Sans',sans-serif;font-size:13px;line-height:20px;
  color:var(--text-muted);}
.sc-answer-text{margin:0;font-family:'IBM Plex Sans',sans-serif;font-size:17px;
  line-height:27px;color:var(--text);}
.sc-badge-inline{display:inline-flex;align-items:center;justify-content:center;min-width:17px;
  height:17px;padding:0 4px;margin:0 1px;border-radius:6px;background:var(--accent-soft);
  color:var(--accent);font-family:'IBM Plex Sans',sans-serif;font-size:12px;font-weight:500;
  line-height:16px;vertical-align:2px;}
.sc-empty-note{font-family:'IBM Plex Sans',sans-serif;font-size:13px;color:var(--text-faint);
  margin-top:12px;}

.sc-error{background:#fdf1f1;border:1px solid #e8b4b4;border-radius:16px;padding:20px 24px;
  color:#8a2c2c;font-family:'IBM Plex Sans',sans-serif;font-size:14px;line-height:22px;}

.sc-sources-header{display:flex;align-items:baseline;justify-content:space-between;}
.sc-sources-header h2{margin:0;font-family:'Space Grotesk',sans-serif;font-size:16px;
  line-height:24px;font-weight:600;color:var(--text);}

[class*="st-key-source_"]{border:1px solid var(--border-strong);border-radius:10px;
  padding:12px 16px;background:var(--surface);display:flex !important;
  flex-direction:column !important;gap:8px !important;}
[class*="st-key-source_active_"]{border-color:var(--accent);}
.sc-source-row{display:flex;align-items:center;gap:12px;}
.sc-source-badge{display:inline-flex;align-items:center;justify-content:center;min-width:20px;
  height:20px;padding:0 5px;border-radius:6px;background:var(--accent-soft);color:var(--accent);
  font-family:'IBM Plex Sans',sans-serif;font-size:12px;font-weight:500;line-height:16px;
  flex-shrink:0;}
.sc-source-meta{display:flex;flex-direction:column;gap:2px;flex-grow:1;min-width:0;}
.sc-source-name{font-family:'IBM Plex Sans',sans-serif;font-size:13px;line-height:20px;
  font-weight:600;color:var(--text);}
.sc-source-doc{font-family:'IBM Plex Sans',sans-serif;font-size:12px;line-height:16px;
  font-weight:500;color:var(--text-muted);}
.sc-pill{flex-shrink:0;display:inline-flex;align-items:center;padding:2px 10px;
  border-radius:999px;background:var(--chip-bg);border:1px solid var(--border);
  color:var(--text-muted);font-family:'IBM Plex Sans',sans-serif;font-size:12px;
  font-weight:500;line-height:16px;}
/* status pills: a pill is a warning, so a statement the record does not flag gets none */
.sc-pill-stale{background:#fdf3e1;border-color:#e8cf9f;color:#8a5a12;}
.sc-pill-never-true{background:#fdf1f1;border-color:#e8b4b4;color:#8a2c2c;}
.sc-pill-disputed{background:#f3eefb;border-color:#d3c4ec;color:#5b3a94;}
.sc-pill-unresolved{background:var(--accent-soft);border-color:#c3d8ea;color:var(--accent);}
.sc-quote{background:var(--chip-bg);border-radius:8px;padding:12px 14px;
  font-family:'IBM Plex Sans',sans-serif;font-size:13px;line-height:20px;color:var(--text);}
.sc-agreed, .sc-receipt{display:block;font-family:'IBM Plex Sans',sans-serif;font-size:12px;
  line-height:16px;color:var(--text-muted);}

[class*="st-key-toggle_"] button{background:transparent !important;border:none !important;
  box-shadow:none !important;padding:0 !important;height:auto !important;
  min-height:auto !important;}
[class*="st-key-toggle_"] button p{color:var(--text-faint) !important;
  font-family:'IBM Plex Sans',sans-serif !important;font-size:12px !important;
  font-weight:500 !important;}
[class*="st-key-toggle_"] button:hover p{color:var(--accent) !important;}
[class*="st-key-toggle_"]{align-self:flex-end !important;}
</style>
""".replace("__FONTS_HREF__", FONTS_HREF)

BRAND_HTML = (
    '<div class="sc-brand">'
    '<div class="sc-logo"><span>s</span></div>'
    '<span class="sc-wordmark"><span class="dark">scand</span><span class="accent">AI</span></span>'
    "</div>"
)


def document_label(document_id: str) -> str:
    match = DOC_LABEL_RE.match(document_id)
    stem = match.group(1) if match else document_id
    return stem.replace("-", " ").replace("_", " ").strip().capitalize()


def location_label(location: dict) -> str:
    page = location.get("page")
    start = location.get("line_start")
    end = location.get("line_end")
    line_part = f"Line {start}" if start == end else f"Lines {start}–{end}"
    label = f"Page {page}, {line_part}" if page else line_part
    # D14's genre-specific pointer: the utterance offset for a transcript, or "message N of
    # M" for an email thread or report — the actual "position in the conversation".
    position = location.get("position")
    return f"{label} · {position}" if position else label


# status -> (pill label, css class). "current" has no entry on purpose: a pill is a warning, and
# everything the record does not flag is current. The status and the ids behind it are worked out
# by the backend (D31); this only shows them.
STATUS_PILLS = {
    "stale": ("Superseded", "sc-pill-stale"),
    "never-true": ("Never true", "sc-pill-never-true"),
    "disputed": ("Disputed", "sc-pill-disputed"),
    "unresolved": ("Never answered", "sc-pill-unresolved"),
}


def status_pill(status: str) -> str:
    if status not in STATUS_PILLS:
        return ""
    label, css_class = STATUS_PILLS[status]
    return f'<span class="sc-pill {css_class}">{label}</span>'


def date_label(iso_date: str) -> str:
    try:
        parsed = date_cls.fromisoformat(iso_date)
    except ValueError:
        return iso_date
    return parsed.strftime("%b %-d, %Y")


def render_answer_html(answer: str) -> str:
    escaped = html.escape(answer)
    return re.sub(
        r"\[(\d+)\]",
        lambda m: f'<span class="sc-badge-inline">{m.group(1)}</span>',
        escaped,
    )


def _http_error_message(exc: requests.HTTPError) -> str:
    try:
        detail = exc.response.json().get("detail", exc.response.text)
    except ValueError:
        detail = exc.response.text
    return f"Backend returned an error: {detail}"


def _iter_sse_events(lines: Iterator[str]) -> Iterator[tuple[str, str]]:
    """Groups raw SSE lines (as requests.Response.iter_lines yields them, blank lines
    included) into (event, data) pairs, per the wire format _sse() writes on the backend."""
    event_type = None
    data_lines: list[str] = []
    for line in lines:
        if line:
            if line.startswith("event:"):
                event_type = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
            continue
        if event_type is not None:
            yield event_type, "\n".join(data_lines)
        event_type, data_lines = None, []
    if event_type is not None:
        yield event_type, "\n".join(data_lines)


def stream_backend(question: str, result: dict) -> Iterator[str]:
    """Yields answer text chunks as they arrive over SSE. Citations (or an error) are
    written into `result` once known, since the caller only consumes text chunks here —
    exactly one of result["citations"]/result["error"] is set once this generator is spent."""
    try:
        with requests.post(
            f"{BACKEND_URL}/query",
            json={"question": question, "stream": True},
            timeout=REQUEST_TIMEOUT,
            stream=True,
        ) as response:
            response.raise_for_status()
            for event_type, data in _iter_sse_events(response.iter_lines(decode_unicode=True)):
                try:
                    payload = json.loads(data) if data else {}
                except json.JSONDecodeError:
                    continue
                if event_type == "token":
                    text = payload.get("text", "")
                    if text:
                        yield text
                elif event_type == "citations":
                    result["citations"] = payload.get("citations", [])
    except requests.HTTPError as exc:
        result["error"] = _http_error_message(exc)
    except requests.RequestException as exc:
        result["error"] = f"Could not reach the backend: {exc}"


def render_source_row(citation: dict) -> None:
    statement_id = citation["statement_id"]
    state_key = f"expanded_{statement_id}"
    expanded = st.session_state.get(state_key, False)
    container_key = f"source_active_{statement_id}" if expanded else f"source_{statement_id}"

    actor = citation.get("actor") or {}
    location = citation.get("location") or {}
    name = html.escape(actor.get("name", ""))
    role = html.escape(actor.get("role", ""))
    org = html.escape(actor.get("organization", ""))
    doc = html.escape(document_label(citation.get("document_id", "")))
    doc_date = date_label(str(citation.get("document_date", "")))
    where = location_label(location)
    speech_act = html.escape(str(citation.get("speech_act", "")).capitalize())
    status_html = status_pill(citation.get("status", "current"))

    with st.container(key=container_key):
        st.markdown(
            f"""
            <div class="sc-source-row">
              <span class="sc-source-badge">{citation.get("marker")}</span>
              <div class="sc-source-meta">
                <span class="sc-source-name">{name} · {role}, {org}</span>
                <span class="sc-source-doc">{doc} — {doc_date} · {where}</span>
              </div>
              <span class="sc-pill">{speech_act}</span>{status_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
        toggle_label = "Hide quote ▴" if expanded else "Show quote ▾"
        if st.button(toggle_label, key=f"toggle_{statement_id}"):
            st.session_state[state_key] = not expanded
            st.rerun()
        if expanded:
            agreed_by = citation.get("agreed_by") or []
            agreed_html = ""
            if agreed_by:
                names = ", ".join(
                    f"{html.escape(a['name'])} ({html.escape(a['organization'])})"
                    for a in agreed_by
                )
                agreed_html = f'<span class="sc-agreed">Agreed by {names}</span>'
            else:
                agreed_html = '<span class="sc-agreed">No agreement appears in the record.</span>'
            receipts = citation.get("status_receipts") or []
            receipt_html = ""
            if receipts:
                ids = ", ".join(html.escape(receipt) for receipt in receipts)
                receipt_html = f'<span class="sc-receipt">Because of {ids}</span>'
            st.markdown(
                f"""
                <div class="sc-quote">“{html.escape(citation.get("verbatim_span", ""))}”</div>
                {agreed_html}
                {receipt_html}
                """,
                unsafe_allow_html=True,
            )


st.set_page_config(
    page_title="scandAI",
    page_icon="\U0001f4dd",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.html(STYLE)

for key, default in {
    "question": None,
    "answer": "",
    "citations": [],
    "error": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

with st.container(key="header"):
    left, right = st.columns(2)
    with left:
        st.markdown(BRAND_HTML, unsafe_allow_html=True)
    if st.session_state.question:
        with right:
            if st.button("New question", key="new_question"):
                st.session_state.question = None
                st.session_state.answer = ""
                st.session_state.citations = []
                st.session_state.error = ""
                st.rerun()

if not st.session_state.question:
    hero_placeholder = st.empty()
    with hero_placeholder.container():
        with st.container(key="hero"):
            st.markdown(
                '<h1 class="sc-hero-title">Ask about your workshop notes</h1>'
                '<p class="sc-hero-sub">scandAI answers from your meeting notes, status reports '
                "and email threads. Every claim traces back to its source.</p>",
                unsafe_allow_html=True,
            )
            with st.container(key="ask_form"):
                with st.form(key="ask_form_inner", clear_on_submit=False, border=False):
                    input_col, button_col = st.columns([11, 1])
                    with input_col:
                        question_input = st.text_input(
                            "Ask a question about your documents",
                            placeholder="Ask a question about your documents…",
                            label_visibility="collapsed",
                        )
                    with button_col:
                        submitted = st.form_submit_button("↑")
            st.markdown('<div class="sc-hint">Press Enter to ask</div>', unsafe_allow_html=True)

    if submitted and question_input.strip():
        hero_placeholder.empty()
        question = question_input.strip()
        with st.container(key="answer_page"):
            st.markdown(
                f'<span class="sc-asked-label">You asked</span>'
                f'<h1 class="sc-question">{html.escape(question)}</h1>',
                unsafe_allow_html=True,
            )
            with st.container(key="live_card"):
                st.markdown(
                    '<div class="sc-card-header"><div class="sc-card-title">'
                    '<span class="sc-logo-sm"><span>s</span></span><span>Answer</span>'
                    "</div></div>",
                    unsafe_allow_html=True,
                )
                answer_placeholder = st.empty()
                result: dict = {}
                answer = ""
                for chunk in stream_backend(question, result):
                    answer += chunk
                    answer_placeholder.markdown(
                        f'<p class="sc-answer-text">{render_answer_html(answer)}</p>',
                        unsafe_allow_html=True,
                    )
        st.session_state.question = question
        st.session_state.answer = answer
        st.session_state.citations = result.get("citations", [])
        st.session_state.error = result.get("error", "")
        st.rerun()

else:
    with st.container(key="answer_page"):
        st.markdown(
            f'<span class="sc-asked-label">You asked</span>'
            f'<h1 class="sc-question">{html.escape(st.session_state.question)}</h1>',
            unsafe_allow_html=True,
        )

        if st.session_state.error:
            error_html = html.escape(st.session_state.error)
            st.markdown(f'<div class="sc-error">{error_html}</div>', unsafe_allow_html=True)
        else:
            citations = st.session_state.citations
            citation_count = len(citations)
            doc_count = len({c["document_id"] for c in citations})
            citation_word = "citation" if citation_count == 1 else "citations"
            statement_word = "statement" if citation_count == 1 else "statements"
            doc_word = "document" if doc_count == 1 else "documents"
            answer_html = render_answer_html(st.session_state.answer)
            empty_note = (
                ""
                if citations
                else (
                    '<div class="sc-empty-note">'
                    "The record does not support a cited claim here.</div>"
                )
            )

            st.markdown(
                f"""
                <div class="sc-card">
                  <div class="sc-card-header">
                    <div class="sc-card-title">
                      <span class="sc-logo-sm"><span>s</span></span>
                      <span>Answer</span>
                    </div>
                    <span class="sc-meta">{citation_count} {citation_word}
                      · {doc_count} {doc_word}</span>
                  </div>
                  <p class="sc-answer-text">{answer_html}</p>
                  {empty_note}
                </div>
                """,
                unsafe_allow_html=True,
            )

            if citations:
                st.markdown(
                    f"""
                    <div class="sc-sources-header">
                      <h2>Sources</h2>
                      <span class="sc-meta">{citation_count} {statement_word}
                        from {doc_count} {doc_word}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.container(key="sources_list"):
                    for citation in citations:
                        render_source_row(citation)
