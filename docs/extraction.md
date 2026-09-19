# Statement extraction — what was built, and how to run it

This page explains the `shah/extraction-pipeline` branch to someone who has not seen it: what
it adds, how to run it on a laptop, how to run it on Verda, and where each piece of data lives.
Read [architecture.md](architecture.md) first if you want the big picture; this page is the
extraction box in that picture, opened up.

## In one paragraph

The extraction job reads the 45 documents in `corpus/`, splits each into speaker turns and
email messages, asks a local LLM (Ollama) to pull out the statements in each one, and keeps a
statement only if its quoted words really appear in the turn or message it came from. The
result is one file, `statements.jsonl`: one statement per line, each with the document, the
line numbers, the position, the verbatim quote, who said it, and what kind of statement it is.
Nothing here calls an outside model API, and nothing in it runs when a user asks a question.

## How it works

```
corpus/*.txt ──► documents.py ──► extraction.py ──► matching.py ──► extract.py
 45 files        turns and         asks the model     keeps a          writes
 (read-only)     messages, with    for statements     statement only   statements.jsonl
                 line numbers      (Ollama)           if its quote     (all or nothing)
                                                      is really there
```

The split that matters: **the model only proposes; code decides what is kept.** The model
returns a unit number, a quote, a one-sentence claim, a kind of statement and who agreed. Code
then finds the quote in that unit and works out the line numbers and position itself. If the
quote is not there word for word, the statement is dropped. The speaker comes from the
document, never from the model. A role or organisation is kept only if those words are in the
document. So a citation in the output always points at real text.

## What is in the branch

| Path | What it is |
|---|---|
| `statement_extraction/src/app/documents.py` | Parsers: Teams transcripts, `INTERNAL` transcripts, email and report threads. Every line keeps its number in the file. |
| `statement_extraction/src/app/matching.py` | `find_span`: finds a quote inside one unit, or returns nothing. |
| `statement_extraction/src/app/extraction.py` | The prompt, the answer schema, batching, and all the keep-or-drop checks. |
| `statement_extraction/src/app/extract.py` | The job: calls Ollama, runs the checks, writes `statements.jsonl`. |
| `statement_extraction/tests/` | 45 tests. Most use small fixtures. Some read the real corpus and skip if it is missing. |
| `compose.extraction.yaml` | Adds Ollama, a model download step, the corpus mount and the real job command. |
| `compose.gpu.yaml` | Gives the Ollama container the NVIDIA GPU. Use it on Verda only. |
| `docs/decisions.md` | D14 to D19 are new; D7 and D13 are marked partly superseded. |
| `.gitignore`, `.dockerignore` | `corpus/` and `statements.jsonl` are never committed or sent into an image. |

`compose.yaml` is unchanged on purpose: `docker compose up` still starts the placeholder
extraction job, the backend and the frontend, so nobody working on those is blocked.

## What one statement looks like

```json
{
  "id": "emails/07_op-id-field-exclusion#3",
  "doc_id": "emails/07_op-id-field-exclusion",
  "doc_type": "email",
  "doc_date": "2025-11-24",
  "stated_on": "2025-11-24",
  "position": "message 2 of 4",
  "lines": [40, 40],
  "span": "I can purge the landing zone. I cannot purge the attachments.",
  "claim": "Kwame Boateng can purge OP_ID from the landing zone but not from the attachments.",
  "act": "report",
  "handling": "none",
  "actor": {"name": "Kwame Boateng", "label": null, "org": "RELEX", "role": "Technical Consultant"},
  "agreed_by": []
}
```

The full field list and the reasoning behind each field is in [data-model.md](data-model.md).
`position` is what a person can find by eye in the file: a transcript's elapsed time,
`message n of N` for threads, `line n` for the `INTERNAL` transcripts. Speakers the file does
not name (`Me`, `Them`, `Guest 1`, a dial-in number) have `name: null` and the label in `label`.

## Where each thing lives

| Data | On your laptop | On Verda |
|---|---|---|
| The 45 source documents | `corpus/` at the repo root. Gitignored, so each person copies it in. | `corpus/` in the repo folder on the VM, mounted read-only into the extraction container. |
| Downloaded model weights | Ollama's own folder (native install), or the `ollama` Docker volume. | The `ollama` Docker volume on the VM disk. |
| The statements file | `statements.jsonl` in the folder you ran from, or in the `statements` Docker volume. | The `statements` Docker volume, at `/data/statements.jsonl`. |

Everything stays on infrastructure we control. The Ollama container is not published outside the
compose network, and the code has no path to any outside model API (D14).

## Run it on your laptop

You need `uv`, and either native Ollama or Docker. The corpus goes in `corpus/`. Start with the
tests, which do not need a model:

```
uv sync
cd statement_extraction
uv run pytest
```

### Option A: native Ollama (simplest)

1. Install Ollama from ollama.com and pull a model: `ollama pull <model>`.
2. Run one document, to see it work:

```
# bash
cd statement_extraction
EXTRACTION_MODEL=<model> uv run python -m src.app.extract 09_2025-02

# PowerShell
cd statement_extraction
$env:EXTRACTION_MODEL = "<model>"; uv run python -m src.app.extract 09_2025-02
```

The words after `extract` are matched against document ids, so `09_2025-02` picks one
transcript and no words means the whole corpus. The output goes to `statements.jsonl` in the
current folder. On a slow machine, also set `EXTRACTION_TIMEOUT` (seconds per model call), for
example `2700`.

### Option B: Docker Compose (the same setup Verda uses)

Start Docker Desktop, put the model name in a `.env` file at the repo root (it is gitignored),
then run one document through the whole chain:

```
echo EXTRACTION_MODEL=<model> > .env
docker compose -f compose.yaml -f compose.extraction.yaml run --rm statement-extraction \
  uv run --frozen python -m src.app.extract 09_2025-02
```

This starts Ollama, downloads the model, and runs the job. It runs on CPU unless you also add
`-f compose.gpu.yaml` on a machine with an NVIDIA GPU. Do not use plain `docker compose up`
with the extraction layer on a laptop: it processes all 45 documents and holds the backend and
frontend until it finishes, which takes many hours without a GPU.

### Settings

| Variable | Default | Meaning |
|---|---|---|
| `EXTRACTION_MODEL` | none, required | The Ollama model name. Never written into code (D14). |
| `OLLAMA_HOST` | `http://localhost:11434` | Where Ollama is. Compose sets `http://ollama:11434`. |
| `EXTRACTION_BATCH_WORDS` | `300` | Units per model call, by word count. Smaller is more reliable (see below). |
| `EXTRACTION_NUM_CTX` | `8192` | Context window asked of Ollama. |
| `EXTRACTION_TIMEOUT` | `600` | Seconds to wait for one model call. |
| `CORPUS_DIR` | `corpus/` at the repo root | Where the documents are. Compose sets `/corpus`. |
| `STATEMENTS_PATH` | `statements.jsonl` | Where the result is written. Compose sets `/data/statements.jsonl`. |

## Run it on Verda

**Not yet run on Verda.** This is the plan. The Verda project exists, but at the time of writing
nobody had found a GPU instance in it, so the model, the GPU and the SSH details below are
still to confirm. Check **Compute → Instances** in the console first, and ask the project owner
before creating one: instances draw on a shared balance.

### First time

1. **Get an instance with an NVIDIA GPU** and add your SSH key in the console.
2. **Check the VM** has Docker and the GPU visible to containers:
   `docker compose version`, then `docker run --rm --gpus all ubuntu nvidia-smi`. If the second
   fails, install the NVIDIA container toolkit.
3. **Get the code:**
   `git clone https://github.com/pd-leukert/scand-ai.git && cd scand-ai && git checkout shah/extraction-pipeline`
   (after the merge, stay on `main`).
4. **Upload the corpus** from your machine: `scp -r corpus <user>@<vm-ip>:~/scand-ai/corpus`
5. **Choose the model.** Put `EXTRACTION_MODEL=<model>` in a `.env` file in the repo folder on the VM.
   Pick the largest model that fits the GPU's memory. Ollama's site lists sizes.
6. **Run:**

```
docker compose -f compose.yaml -f compose.extraction.yaml -f compose.gpu.yaml up --build statement-extraction
```

This starts Ollama, downloads the model into the `ollama` volume, then runs the job. Watch it
with `docker compose logs -f statement-extraction`; it prints one line per document with how
many statements were kept and how many were dropped, and why. When it prints
`Wrote N statements`, it is done.

### Getting the result out

The file lives in the `statements` volume. To read it:

```
docker run --rm -v scand-ai_statements:/data alpine cat /data/statements.jsonl > statements.jsonl
```

### Pointing new changes at Verda

Today this is manual:

1. Push your branch to GitHub.
2. On the VM: `git fetch && git checkout <branch> && git pull`.
3. Rebuild and run: the `docker compose ... up --build` command above.

Once David's CI/CD is in place, steps 2 and 3 should happen from it. After this branch is merged
the commands are the same, on `main`.

### Cautions

- **`docker compose down -v` deletes the volumes**, including the statements file and the
  downloaded model. Plain `down` keeps them.
- **Every `docker compose up` re-runs extraction** (D12), which is long and costs GPU time. To
  restart just the backend: `docker compose up --no-deps backend`.
- The Dockerfile still sets `STATEMENTS_PATH=/data/statements.json`; the extraction layer
  overrides it to `.jsonl`. The backend does not read the file yet, so nothing depends on it.

## After the merge

Nothing about how to run it changes. `compose.yaml` stays the base and still starts the
placeholder job, so the extraction layer has to be named on the command line. Folding the layer
into `compose.yaml`, and replacing the placeholder command with the real job, should happen
once extraction has run for real (D18).

## What we learned

**Model size decides quality.** One 63-line transcript, same prompt, on a laptop with a 4 GB GPU:

| Model | Statements kept | Thrown away | Time |
|---|---|---|---|
| 0.8B | 14 | 31 | 3 min |
| 2B | 28 | 18 | 9 min |
| 4B | 45 | 0 | 14 min |

- **The smaller models cannot copy exactly.** Most of what they got wrong was thrown away by the
  quote check, which is what the check is for.
- **Batch size matters.** With a 1000-word batch, 4B and the newer prompt kept 22 statements and
  stopped covering the document part way through. With 300-word batches it kept 48 in the same
  time. So the default is 300 (D18).
- **Thinking models need thinking turned off.** Otherwise a model can spend its whole budget
  reasoning and return nothing. The job sends `think: false`.
- **A claim can be wrong even when the quote is right.** The claim is the model's own sentence.
  We saw one that inverted the speaker and one that added a currency symbol. The quote is the
  receipt; the claim is not checked (D17). A check of claims against quotes is a good next step.
- **Speed.** About 14 minutes for this one small document on a laptop. The whole corpus on the
  same laptop would take well over ten hours, so the real run needs a GPU.

**The archive has quirks worth knowing.**
- Three `INTERNAL` transcripts record `Me` / `Them` only, so the speaker cannot be named.
- Some Teams speakers are `Unknown Speaker`, `Guest 1` or a phone number.
- One speaker is spelled `Henrik Sorensen` in two turns and `Henrik Sørensen` everywhere else.
  Deletion must cope with spellings, email addresses and phone numbers, not just one name.
- Dates come as `06-04-2026` in reports (6 April) and as `Monday, November 24, 2025` in email
  headers, so the parser converts them to ISO dates.
- There is a storyline about health information in the notes (emails 04 and 06, transcripts 01,
  17 and 21). It is why D19 proposes flagging private statements.

## Known limits, and what is next

- **Only one transcript has been run with a real model.** Emails and report threads are
  covered by parser tests, but the prompt has not been tried on them.
- **The full run is blocked on a GPU.** Until it exists there is no `statements.jsonl` for the
  backend to use.
- **The private-material flag (`handling`, D19) is not reliable at 4B.** It found an explicit
  request not to share something and the statement it referred to, but missed the most blatant
  personal detail and wrongly flagged two work remarks. The design is to require the model to
  quote its reason and check the quote in code; it needs a bigger model to judge.
- **No claim check yet.** See above.
- **Deletion is not built.** Redaction has to sweep the actor, the agreed-by names, the quote
  and the claim (D3, [data-model.md](data-model.md)).
- **The team's whiteboard shows a RAG store.** D2 says no retrieval or embeddings in the MVP, and
  a new derived artifact needs a deletion cascade. If RAG stays, D2 needs a superseding entry.

## Decisions to read

D14 commercial APIs only in development · D15 the record layout · D16 parsing into turns and
messages · D17 quote matching · D18 Ollama over HTTP and the compose layers · D19 the unasked
feature (proposed). All in [decisions.md](decisions.md).
