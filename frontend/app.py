import html
import json
import os
import re
from collections.abc import Iterator
from datetime import date as date_cls

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
# Read timeout: seconds of silence between chunks the backend forwards, not a cap on the
# whole answer. Matches the backend's own LLM_TIMEOUT default (backend/README.md) so a
# large, slow model isn't cut off here after the backend was configured to wait for it.
REQUEST_TIMEOUT = float(os.environ.get("BACKEND_REQUEST_TIMEOUT", "600"))

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
  --danger:#8a2c2c; --danger-hover:#6f2323;
  /* Light only, on purpose: .streamlit/config.toml pins Streamlit's own widgets to the same
     tokens, and this pins what the browser paints for us — form controls, scrollbars,
     autofill — so a dark-mode laptop cannot turn half the page dark (D48). */
  color-scheme:light;
}
html, body, .stApp{background:var(--bg) !important;color:var(--text);
  font-family:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif;}
#MainMenu, header[data-testid="stHeader"], footer,
[data-testid="stDecoration"], [data-testid="collapsedControl"]{display:none !important;}
.block-container{padding:0 !important;max-width:100% !important;}
/* Streamlit's own vertical-block gap beats a plain class selector on specificity;
   !important on every section override below is what actually wins. */
div[data-testid="stVerticalBlock"]{gap:0;}
/* Streamlit sizes a markdown element's box on the assumption that its last child carries the
   default 1rem bottom margin, and cancels that margin again when it lays the block out. Our
   components set margin:0, so every one of them measured 16px shorter than its text and the
   next control landed on top of it — the "Delete permanently" button over its own warning.
   Giving the last child the margin back costs no visible space and fixes all of them (D48). */
[data-testid="stMarkdownContainer"] > *:last-child{margin-bottom:1rem !important;}
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

/* delete-a-person dialog */
.st-key-header_actions [data-testid="stHorizontalBlock"]{padding:0 !important;gap:8px !important;}
[data-testid="stDialog"] [data-testid="stVerticalBlock"]{gap:14px !important;}
[data-testid="stDialog"] section{background:var(--surface) !important;border-radius:16px;}
[data-testid="stDialog"] h2{font-family:'Space Grotesk',sans-serif !important;font-size:20px;
  font-weight:600;color:var(--text);}
[data-testid="stDialog"] [data-testid="stTextInputRootElement"]{border-radius:10px;
  background:var(--bg) !important;border:1px solid var(--border-strong) !important;}
[data-testid="stDialog"] input{font-family:'IBM Plex Sans',sans-serif;font-size:15px;
  color:var(--text) !important;}
.st-key-confirm_deletion button{background:var(--danger) !important;border:none !important;
  border-radius:10px;height:40px;padding:0 18px;}
.st-key-confirm_deletion button:hover{background:var(--danger-hover) !important;}
.st-key-confirm_deletion button p{color:#fff !important;font-weight:600;}
.st-key-close_deletion button{border:1px solid var(--border-strong) !important;
  background:var(--surface) !important;border-radius:10px;height:40px;padding:0 18px;}
.sc-dialog-note{font-family:'IBM Plex Sans',sans-serif;font-size:14px;line-height:22px;
  color:var(--text-muted);margin:0;}
.sc-dialog-warn{font-family:'IBM Plex Sans',sans-serif;font-size:14px;line-height:22px;
  color:var(--danger);font-weight:600;margin:0;}
.sc-receipt{display:flex;flex-direction:column;gap:8px;}
.sc-receipt p{margin:0;font-family:'IBM Plex Sans',sans-serif;font-size:15px;line-height:24px;
  color:var(--text);}
.sc-receipt .muted{color:var(--text-muted);font-size:13px;line-height:20px;}

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
.sc-quote{background:var(--chip-bg);border-radius:8px;padding:12px 14px;
  font-family:'IBM Plex Sans',sans-serif;font-size:13px;line-height:20px;color:var(--text);}
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
                elif event_type == "error":
                    result["error"] = payload.get("message", "The model did not answer.")
    except requests.HTTPError as exc:
        result["error"] = _http_error_message(exc)
    except requests.RequestException as exc:
        result["error"] = f"Could not reach the backend: {exc}"


def request_deletion(name: str) -> dict:
    """Asks the backend to delete a person and hands back its receipt, or {"error": ...}.

    Shown once and then dropped — the receipt names the person, and keeping it anywhere would
    undo the deletion (docs/decisions.md D42)."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/delete", json={"name": name}, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        return {"error": _http_error_message(exc)}
    except requests.RequestException as exc:
        return {"error": f"Could not reach the backend: {exc}"}


def deletion_confirmation_html(receipt: dict) -> str:
    """A confirmation, not a receipt dump: who was removed, and who was deliberately kept.

    The second half is the part that cannot be dropped. The archive holds two people sharing a
    first name (docs/corpus.md), so a name still in the record after a deletion is either
    another person we resolved and left on purpose, or a deletion that missed — and only this
    says which (docs/deletion.md)."""
    deleted = receipt.get("deleted")
    requested = html.escape(receipt.get("requested", ""))
    if deleted is None:
        return (
            f'<div class="sc-receipt"><p>No one called “{requested}” is in the record, so '
            "nothing was changed. They may already be deleted.</p></div>"
        )
    count = deleted["statements_changed"]
    lines = [
        f"<p><strong>{html.escape(deleted['name'])}</strong> is gone from the record. "
        f"{count} {'statement' if count == 1 else 'statements'} now read "
        f"{html.escape(deleted['placeholder'])}.</p>"
    ]
    kept = [
        html.escape(person["name"])
        for person in receipt.get("considered", [])
        if person["outcome"] == "left"
    ]
    if kept:
        lines.append(
            f'<p class="muted">{", ".join(kept)} stayed — a different person, kept by name.</p>'
        )
    lines += [
        f'<p class="muted">Left in place: {html.escape(note)}.</p>'
        for note in receipt.get("left_in_place", [])
    ]
    return f'<div class="sc-receipt">{"".join(lines)}</div>'


@st.dialog("Delete a person")
def deletion_dialog() -> None:
    """Name, confirm, done. Streamlit reruns only this function while the dialog is open, so
    the receipt lives in session state between the click and the confirmation."""
    receipt = st.session_state.deletion_receipt
    if receipt is None:
        st.markdown(
            '<p class="sc-dialog-note">Every spelling of that person is replaced by their '
            "role, in the claims as well as the speaker fields. Everyone else stays named, "
            "and the decisions around them keep answering.</p>",
            unsafe_allow_html=True,
        )
        name = st.text_input(
            "Name",
            placeholder="Who should be deleted? e.g. Kwame Boateng",
            key="deletion_name",
            label_visibility="collapsed",
        ).strip()
        st.markdown(
            '<p class="sc-dialog-warn">This rewrites the record and cannot be undone.</p>',
            unsafe_allow_html=True,
        )
        if st.button("Delete permanently", key="confirm_deletion", type="primary"):
            if not name:
                st.markdown(
                    '<p class="sc-dialog-note">Type a name first.</p>', unsafe_allow_html=True
                )
                return
            st.session_state.deletion_receipt = request_deletion(name)
            # The dialog is a fragment, so only it reruns — and this run has already drawn the
            # form above. Without the rerun the confirmation appears under a live
            # "Delete permanently" button.
            st.rerun(scope="fragment")
    if receipt is None:
        return
    if receipt.get("error"):
        st.markdown(
            f'<div class="sc-error">{html.escape(receipt["error"])}</div>', unsafe_allow_html=True
        )
    else:
        st.markdown(deletion_confirmation_html(receipt), unsafe_allow_html=True)
    if st.button("Done", key="close_deletion"):
        # The answer on screen was written before the deletion and can still name the person,
        # so it goes with them. The next question is answered from the rewritten file.
        st.session_state.deletion_receipt = None
        st.session_state.question = None
        st.session_state.answer = ""
        st.session_state.citations = []
        st.session_state.error = ""
        st.rerun()


def render_source_row(citation: dict) -> None:
    statement_id = citation["statement_id"]
    container_key = f"source_{statement_id}"

    actor = citation.get("actor") or {}
    name = html.escape(actor.get("name", ""))
    org = html.escape(actor.get("organization", ""))
    doc = html.escape(document_label(citation.get("document_id", "")))
    doc_date = date_label(str(citation.get("document_date", "")))
    speech_act = html.escape(str(citation.get("speech_act", "")).capitalize())
    claim = html.escape(citation.get("claim", ""))

    with st.container(key=container_key):
        st.markdown(
            f"""
            <div class="sc-source-row">
              <span class="sc-source-badge">{citation.get("marker")}</span>
              <div class="sc-source-meta">
                <span class="sc-source-name">{name} · {org}</span>
                <span class="sc-source-doc">{doc} — {doc_date}</span>
              </div>
              <span class="sc-pill">{speech_act}</span>
            </div>
            <div class="sc-quote">{claim}</div>
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
    "deletion_receipt": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

with st.container(key="header"):
    left, right = st.columns(2)
    with left:
        st.markdown(BRAND_HTML, unsafe_allow_html=True)
    with right, st.container(key="header_actions"):
        new_question_col, delete_col = st.columns(2)
        if st.session_state.question:
            with new_question_col:
                if st.button("New question", key="new_question"):
                    st.session_state.question = None
                    st.session_state.answer = ""
                    st.session_state.citations = []
                    st.session_state.error = ""
                    st.rerun()
        with delete_col:
            # Opened from here rather than from a session flag: Streamlit closes the dialog when
            # the script reruns without this call, which is what the ✕ needs to work.
            if st.button("Delete a person", key="open_deletion"):
                st.session_state.deletion_receipt = None
                deletion_dialog()

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
