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
  /* One column the header, the ask state and the answer state all share, so the brand,
     the ask bar and every answer line start at the same x. Change it in one place. */
  --content-width:880px; --gutter:32px;
  /* The header is a fixed height rather than whatever its tallest control happens to be,
     because the hero subtracts it to fill the viewport. Before this, adding the always-on
     "Delete a person" button grew the header to 81px while the hero still subtracted a
     hard-coded 73px. */
  --header-height:72px;
  /* The ambient wash, as the accent at very low alpha rather than a new blue, so it stays
     in the palette. Alpha is the dial: above ~0.14 it stops reading as paper. */
  --wash:rgba(22,104,165,0.07); --wash-strong:rgba(22,104,165,0.11);
  /* Light only, on purpose: .streamlit/config.toml pins Streamlit's own widgets to the same
     tokens, and this pins what the browser paints for us — form controls, scrollbars,
     autofill — so a dark-mode laptop cannot turn half the page dark (D48). */
  color-scheme:light;
}
/* background-color, not the background shorthand: the shorthand also resets
   background-image, which is what the wash below paints. */
html, body, .stApp{background-color:var(--bg) !important;color:var(--text);
  font-family:'IBM Plex Sans',system-ui,-apple-system,'Segoe UI',sans-serif;}
/* Ambient wash: three very faint baby-blue blobs that drift and swell over the page. It
   lives in .stApp's own background rather than an overlay element, so it paints behind
   every component with no stacking context to manage and nothing to intercept clicks.
   Fixed attachment keeps it still while a long answer scrolls past it. */
.stApp{
  background-image:
    radial-gradient(closest-side, var(--wash-strong), transparent),
    radial-gradient(closest-side, var(--wash), transparent),
    radial-gradient(closest-side, var(--wash), transparent) !important;
  background-repeat:no-repeat !important;
  background-attachment:fixed !important;
  animation:sc-breathe 26s ease-in-out infinite;}
@keyframes sc-breathe{
  0%, 100%{background-size:58% 62%, 46% 50%, 62% 56%;
    background-position:16% 10%, 86% 22%, 62% 92%;}
  50%{background-size:66% 70%, 53% 57%, 69% 63%;
    background-position:22% 17%, 79% 15%, 55% 85%;}
}
/* Motion this slow is still motion; honour the system setting and keep the wash static. */
@media (prefers-reduced-motion: reduce){
  .stApp{animation:none !important;background-size:58% 62%, 46% 50%, 62% 56%;
    background-position:16% 10%, 86% 22%, 62% 92%;}
}
/* stHeaderActionElements is the anchor-link icon Streamlit adds inside every heading. It is
   only painted on hover, but it sits in the line the whole time, so it was pushing the
   centred hero title 12px to the left of centre. */
#MainMenu, header[data-testid="stHeader"], footer,
[data-testid="stDecoration"], [data-testid="collapsedControl"],
[data-testid="stHeaderActionElements"]{display:none !important;}
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
/* D48's rule above targets every markdown container's last child, which includes the label
   inside a button. On an inline label that margin does nothing, so it went unnoticed — but
   the send arrow's label is inline-block (it has to be, for its transform), so there the
   margin applies and pushed the glyph half of it off centre. Button labels are not the
   mis-measured blocks D48 is about. */
button [data-testid="stMarkdownContainer"] > *:last-child{margin-bottom:0 !important;}

/* header bar */
.st-key-header{background:var(--surface);border-bottom:1px solid var(--border);}
.st-key-header [data-testid="stHorizontalBlock"]{align-items:center !important;
  /* min-height, not height: Streamlit sizes these boxes itself and a height declaration
     here is simply ignored (the same wall D48 hit forcing height:auto). */
  min-height:var(--header-height) !important;
  max-width:var(--content-width) !important;width:100% !important;margin:0 auto !important;
  padding:0 var(--gutter) !important;justify-content:space-between !important;}
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
.st-key-hero{min-height:calc(100vh - var(--header-height) - 1px);
  display:flex !important;flex-direction:column !important;
  align-items:center !important;justify-content:center !important;gap:32px !important;
  max-width:var(--content-width);margin:0 auto;padding:32px var(--gutter);}
/* Streamlit's own generated heading rule (element+class) ties this class selector's
   specificity, and wins on source order — !important is what actually wins here, same
   as the vertical-block gap override above. */
.sc-hero-title{margin:0 !important;padding:0 !important;text-align:center !important;
  font-family:'Space Grotesk',sans-serif !important;font-size:32px !important;
  line-height:40px !important;font-weight:600 !important;color:var(--text) !important;}
/* What the record holds, under the title. Deliberately quiet: faint colour, 13px, and
   icons at text size, so it reads as a caption rather than a second headline. */
.sc-corpus{display:flex !important;align-items:center;justify-content:center;
  flex-wrap:wrap;gap:4px 10px;margin:14px 0 0 !important;
  font-family:'IBM Plex Sans',sans-serif;font-size:13px;line-height:20px;
  color:var(--text-faint);}
.sc-corpus-item{display:inline-flex;align-items:center;gap:6px;white-space:nowrap;}
.sc-corpus-item svg{width:14px;height:14px;flex-shrink:0;}
.sc-corpus-sep{color:var(--border-strong);}

.st-key-ask_form{width:100%;background:var(--surface);border:1px solid var(--border-strong);
  border-radius:24px;box-shadow:0 1px 2px rgba(9,20,31,0.08);padding:6px 6px 6px 20px;}
.st-key-ask_form [data-testid="stForm"]{border:none !important;padding:0 !important;}
.st-key-ask_form [data-testid="stHorizontalBlock"]{align-items:center !important;
  gap:8px !important;}
/* Streamlit's own "Press Enter to submit form" hint appears inside the pill on focus,
   saying the same thing as the .sc-hint line already under it. */
.st-key-ask_form [data-testid="InputInstructions"]{display:none !important;}
/* The grey field is painted by Streamlit's wrapper, not the input — overriding only the
   input leaves a grey box sitting inside the white pill. Clearing the wrapper (in every
   state, including focus) lets the pill itself be the only visible surface. */
.st-key-ask_form [data-testid="stTextInputRootElement"],
.st-key-ask_form [data-testid="stTextInputRootElement"]:focus-within{
  background:transparent !important;border:none !important;box-shadow:none !important;}
.st-key-ask_form input{border:none !important;background:transparent !important;
  box-shadow:none !important;font-family:'IBM Plex Sans',sans-serif;font-size:17px;
  color:var(--text) !important;padding:8px 0 !important;}
.st-key-ask_form button{width:44px;height:44px;border-radius:999px !important;
  border:none !important;background:var(--navy) !important;padding:0 !important;}
.st-key-ask_form button:hover{background:var(--accent-hover) !important;}
.st-key-ask_form button p{color:#fff !important;font-size:18px !important;line-height:1;
  /* "↑" sits low in its own em box (the glyph reserves space for descenders it doesn't
     have) — nudge it up so it looks centered in the round button. transform is a no-op
     on a plain inline box, so this also needs inline-block to take effect. */
  display:inline-block;transform:translateY(-4px);}
.sc-hint{margin-top:8px;text-align:center;font-family:'IBM Plex Sans',sans-serif;
  font-size:13px;color:var(--text-faint);}

/* answer state */
.st-key-answer_page{max-width:var(--content-width);margin:0 auto;padding:32px var(--gutter) 64px;
  display:flex !important;flex-direction:column !important;gap:24px !important;}
.st-key-sources_list{display:flex !important;flex-direction:column !important;gap:10px !important;}
.sc-asked-label{font-family:'IBM Plex Sans',sans-serif;font-size:13px;font-weight:600;
  letter-spacing:0.01em;color:var(--text-muted);}
/* Same generated heading rule again: it also carries padding:1.25rem 0 1rem, which the
   margin overrides above never touched, so both headings were sitting in 36px of Streamlit
   padding on top of their own spacing. Zero it and let the margins here be the rhythm. */
.sc-question{margin:4px 0 0 !important;padding:0 !important;
  font-family:'Space Grotesk',sans-serif !important;
  font-size:20px !important;line-height:28px !important;font-weight:600 !important;
  color:var(--text) !important;}

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
/* The newest streamed fragment fades up out of a slight blur, so text arrives rather than
   snapping in. Two names for one animation because Streamlit reuses the span between
   reruns, and an animation only restarts when its name changes. No transform: it does
   nothing on an inline box, and inline-block would break mid-sentence line wrapping. */
/* Duration is tuned to the gap between chunks, not to taste: a fragment is promoted to
   settled text on the next frame, so a fade slower than that gap gets cut off part-way and
   snaps to full — a pop, which is the opposite of the point. Starting part-lit keeps what
   is left of that step small. */
.sc-stream-in-0{animation:sc-stream-a 0.16s ease-out;}
.sc-stream-in-1{animation:sc-stream-b 0.16s ease-out;}
@keyframes sc-stream-a{from{opacity:0.25;filter:blur(2px);}to{opacity:1;filter:blur(0);}}
@keyframes sc-stream-b{from{opacity:0.25;filter:blur(2px);}to{opacity:1;filter:blur(0);}}
@media (prefers-reduced-motion: reduce){
  .sc-stream-in-0, .sc-stream-in-1{animation:none !important;}
}
/* Shown while we wait for the backend's first token. min-height matches .sc-answer-text's
   line-height so the card does not jump when the answer replaces this. */
.sc-loading{display:flex;align-items:center;gap:10px;min-height:27px;}
.sc-dots{display:flex;align-items:center;gap:5px;}
.sc-dots span{width:7px;height:7px;border-radius:50%;background:var(--accent);opacity:0.25;
  animation:sc-dot 1.2s ease-in-out infinite;}
.sc-dots span:nth-child(2){animation-delay:0.16s;}
.sc-dots span:nth-child(3){animation-delay:0.32s;}
.sc-loading-label{font-family:'IBM Plex Sans',sans-serif;font-size:14px;
  color:var(--text-muted);}
@keyframes sc-dot{0%,70%,100%{opacity:0.25;}35%{opacity:1;}}
.sc-badge-inline{display:inline-flex;align-items:center;justify-content:center;min-width:17px;
  height:17px;padding:0 4px;margin:0 1px;border-radius:6px;background:var(--accent-soft);
  color:var(--accent);font-family:'IBM Plex Sans',sans-serif;font-size:12px;font-weight:500;
  line-height:16px;vertical-align:2px;}
.sc-empty-note{font-family:'IBM Plex Sans',sans-serif;font-size:13px;color:var(--text-faint);
  margin-top:12px;}

/* delete-a-person dialog */
/* This row is nested inside the header, so the header rule above (a descendant selector)
   also lands on it — undo the column sizing here, or the two buttons get spread to the
   full content width instead of sitting together. */
.st-key-header_actions [data-testid="stHorizontalBlock"]{padding:0 !important;gap:8px !important;
  max-width:none !important;width:auto !important;margin:0 !important;
  justify-content:flex-end !important;}
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

_ICON = (
    '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"'
    ' stroke-linecap="round" stroke-linejoin="round">{}</svg>'
)
# The counts are the archive's, and the archive is fixed for the weekend because it is baked
# into the extraction image (D18). statement_extraction/tests/test_documents.py asserts these
# same three numbers against input/, so a corpus that changes fails a test rather than
# quietly leaving a false claim on the first screen a judge reads.
CORPUS_ITEMS = (
    (
        '<path d="M13.5 7.7c0 2.5-2.5 4.6-5.5 4.6-.8 0-1.6-.1-2.3-.4L2.5 13l1.1-2.4'
        'c-.7-.8-1.1-1.8-1.1-2.9 0-2.5 2.5-4.6 5.5-4.6s5.5 2.1 5.5 4.6Z"/>',
        "23 transcripts",
    ),
    (
        '<rect x="2" y="3.5" width="12" height="9" rx="1.5"/>'
        '<path d="m2.6 4.8 5.4 3.9 5.4-3.9"/>',
        "20 emails",
    ),
    (
        '<path d="M9 2H4.8c-.7 0-1.3.6-1.3 1.3v9.4c0 .7.6 1.3 1.3 1.3h6.4c.7 0 1.3-.6'
        ' 1.3-1.3V5.5L9 2Z"/><path d="M9 2v3.5h3.5"/><path d="M6 9h4M6 11.2h2.8"/>',
        "2 reports",
    ),
)
CORPUS_HTML = '<div class="sc-corpus">{}</div>'.format(
    '<span class="sc-corpus-sep">⋅</span>'.join(
        f'<span class="sc-corpus-item">{_ICON.format(paths)}{label}</span>'
        for paths, label in CORPUS_ITEMS
    )
)

LOADING_HTML = (
    '<div class="sc-loading" role="status" aria-live="polite">'
    '<div class="sc-dots"><span></span><span></span><span></span></div>'
    '<span class="sc-loading-label">Reading the record…</span>'
    "</div>"
)

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


def render_streaming_html(answer: str, tail: str, frame: int) -> str:
    """The answer so far, with only the newest chunk wrapped so it fades in.

    Wrapping just the tail is what keeps this from flickering: the text already on screen
    carries no animation and so repaints unchanged, and only the arriving fragment moves.
    The class alternates because Streamlit reuses the element between reruns — a changing
    animation-name is what makes the browser run it again."""
    head = answer[: len(answer) - len(tail)]
    # A citation marker split across the boundary would not match the badge pattern, so
    # render the frame whole rather than flash a literal "[1]" mid-stream.
    if "[" in tail or "]" in tail or head.count("[") != head.count("]"):
        return f'<p class="sc-answer-text">{render_answer_html(answer)}</p>'
    return (
        f'<p class="sc-answer-text">{render_answer_html(head)}'
        f'<span class="sc-stream-in-{frame % 2}">{render_answer_html(tail)}</span></p>'
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
                '<h1 class="sc-hero-title">Ask about your communication history</h1>'
                + CORPUS_HTML,
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
                # Held until the backend's first token, which overwrites the placeholder.
                # A local model can be slow to start, and an empty card reads as broken.
                answer_placeholder.markdown(LOADING_HTML, unsafe_allow_html=True)
                result: dict = {}
                answer = ""
                for frame, chunk in enumerate(stream_backend(question, result)):
                    answer += chunk
                    answer_placeholder.markdown(
                        render_streaming_html(answer, chunk, frame),
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
