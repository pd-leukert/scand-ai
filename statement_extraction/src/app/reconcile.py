"""Second pass: group the first pass's statements by topic, then reconcile each topic.

Nothing here writes a new quote. Every relation, status, receipt and problem names a
statement id the first pass already produced; anything else is dropped. See D40.
"""

import re
from collections import Counter
from collections.abc import Callable

from .extraction import ACTS, Chat, when

RELATIONS = ["supersedes", "corrects", "conflicts-with", "answers"]
STATUSES = ["current", "stale", "never-true", "disputed", "unresolved"]
PROBLEM_KINDS = ["reversal", "never-true", "conflict", "unanswered"]
UNTAGGED = "untagged"

# Topic names the model may not use. UNTAGGED is ours. The speech acts are here because they
# are what a small model reaches for when it is asked to name a subject: "proposal" is a valid
# slug, so nothing else rejects it, and a run comes back with every statement filed under its
# own act. See D42.
RESERVED_TOPICS = {UNTAGGED, *ACTS}

# The statuses only a relation can produce. `unresolved` is not one: it falls out of a proposal
# nobody answered, which is a property of one statement rather than a link between two.
LINKED_STATUSES = {"never-true", "stale", "disputed"}

# A topic is a short kebab-case slug. Letters may be non-ASCII: the archive has Swedish and
# Danish in it, and a topic named in the language of its statements is not a wrong one.
SLUG = re.compile(r"[^\W_]+(?:-[^\W_]+)*")
SLUG_MAX = 40

# A model-written sentence in quotes is the one thing a judge could mistake for a citation.
# Double quotes and guillemets only: an apostrophe is not a quotation.
QUOTES = '"“”„«»'
NOTE_MAX = 300

# A number, with or without an internal separator: "60", "3.4", "1,200".
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")

TOPIC_SCHEMA = {
    "type": "object",
    "properties": {
        "tags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string"},
                    "topic": {"type": "string"},
                },
                "required": ["statement", "topic"],
            },
        }
    },
    "required": ["tags"],
}

RECONCILE_SCHEMA = {
    "type": "object",
    "properties": {
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "kind": {"type": "string", "enum": RELATIONS},
                },
                "required": ["from", "to", "kind"],
            },
        },
        "statuses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string"},
                    "status": {"type": "string", "enum": STATUSES},
                },
                "required": ["statement", "status"],
            },
        },
        "summary": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "statements": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["text", "statements"],
        },
        "problems": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": PROBLEM_KINDS},
                    "statements": {"type": "array", "items": {"type": "string"}},
                    "note": {"type": "string"},
                },
                "required": ["kind", "statements", "note"],
            },
        },
    },
    "required": ["relations", "statuses", "summary", "problems"],
}

TOPIC_PROMPT = """\
You sort statements from a project record into topics. A topic is one thread of subject matter \
that runs through the project: a field, a workstream, a date, a decision people kept coming back \
to.

You are given statements, each with a label, a date, who said it and what it says. You are also \
given the topics already in use in this run.

For every statement, return:
- statement: the label exactly as shown, e.g. S3. Never write a label you were not given.
- topic: a short kebab-case tag naming the subject, two to four words, lower case, letters, digits \
and hyphens only, e.g. "op-id-field-exclusion" or "bakery-workstream-scope".

Reuse a topic from the list you were given whenever it fits. Only invent one when no topic in that \
list covers the statement. Two spellings of the same subject are worse than one imperfect topic. \
Name the subject, never the speech act and never the document: "shelf-life-data-coverage", not \
"proposal" and not "email-07".

Give exactly one entry for each statement you were given. Do not repeat a label. Do not use \
"untagged". Use only the text you are given.\
"""

RECONCILE_PROMPT = """\
You read every statement in a project record about one topic, oldest first, and write down how \
they bear on each other. You never write a new fact: everything you return points at the \
statements you were given, by their labels.

Return:

- relations. from and to are labels from this topic.
  - supersedes: the statement in from replaces what to said. Later words settled it differently.
  - corrects: from says to was wrong when it was recorded. Not that things changed since — that \
the record was never right.
  - conflicts-with: from and to cannot both be true, and nothing here settles which holds.
  - answers: from answers the proposal or question in to, by accepting it, refusing it, or \
settling it either way.
  Write only a relation the words show. Most statements have none. Never link a statement to \
itself, and never link two statements that only repeat each other.

- statuses, one for each statement.
  - current: nothing here supersedes it, corrects it or contradicts it.
  - stale: a later statement supersedes it.
  - never-true: another statement says it was wrong when it was recorded.
  - disputed: it conflicts with another statement and nothing settles which is right.
  - unresolved: it is a proposal or a question and nothing here answers it.
  A status other than current is allowed only if you also wrote the relation it rests on. Never \
decide a status from dates. Being old is not being stale, and being recent is not being right.

- summary: one plain sentence saying where this topic stands, and statements: the labels that \
sentence rests on. Say it in your own words. Do not quote the record — the labels are the \
receipt, the sentence is not.

- problems: one entry for anything a reader of this record would get wrong.
  - reversal: a decision was changed later and the earlier statement still reads as current.
  - never-true: a statement was wrong when it was recorded.
  - conflict: two statements disagree and nothing settles it.
  - unanswered: something was proposed or asked and nobody ever answered it.
  Each entry names the labels involved and one plain sentence saying what a reader would get \
wrong. Do not quote the record.

Use only the statements you are given. Never write a label that is not in the list.\
"""


class ReconcileError(RuntimeError):
    """The pass produced something that does not hold together. The job exits 1."""


def tag_topics(
    records: list[dict], chat: Chat, batch: int, vocabulary_shown: int
) -> tuple[dict[str, str], Counter[str]]:
    """The topic of every statement, by statement id, and how many tags we threw away.

    Each batch is shown the topics already in use, most used first, so the vocabulary
    converges instead of forking. A statement the model did not tag, or tagged badly, falls
    to UNTAGGED.
    """
    topics: dict[str, str] = {}
    use: Counter[str] = Counter()
    dropped: Counter[str] = Counter()
    for start in range(0, len(records), batch):
        labelled = _labelled(records[start : start + batch])
        messages = [
            {"role": "system", "content": TOPIC_PROMPT},
            {
                "role": "user",
                "content": f"{_vocabulary(use, vocabulary_shown)}\n\nStatements:\n"
                f"{_render(labelled, with_act=False)}",
            },
        ]
        tagged: dict[str, str] = {}
        for item in chat(messages, schema=TOPIC_SCHEMA)["tags"]:
            label, topic = item["statement"], _slug(item["topic"])
            if label not in labelled:
                dropped["label not shown in this batch"] += 1
            elif topic is None:
                dropped["topic is not a short slug"] += 1
            elif topic in RESERVED_TOPICS:
                dropped["reserved topic"] += 1
            elif label in tagged:
                dropped["label tagged twice"] += 1
            else:
                tagged[label] = topic
        for label, record in labelled.items():
            if label not in tagged:
                dropped["statement not tagged"] += 1
            topics[record["id"]] = tagged.get(label, UNTAGGED)
        use.update(tagged.values())
    return topics, dropped


def group(records: list[dict], topics: dict[str, str], cap: int) -> list[tuple[str, list[dict]]]:
    """What to reconcile: real topics, largest first, each with its statements oldest first.

    UNTAGGED is not a topic and is not here. A topic over cap is cut into consecutive chunks
    of near-equal size, because one call has to hold it and a chunk of one links to nothing.
    """
    by_topic: dict[str, list[dict]] = {}
    for record in records:
        if topics[record["id"]] != UNTAGGED:
            by_topic.setdefault(topics[record["id"]], []).append(record)
    groups: list[tuple[str, list[dict]]] = []
    for topic, statements in sorted(by_topic.items(), key=lambda item: (-len(item[1]), item[0])):
        ordered = sorted(statements, key=chronological)
        chunks = -(-len(ordered) // cap)
        if chunks == 1:
            groups.append((topic, ordered))
            continue
        size, extra = divmod(len(ordered), chunks)
        start = 0
        for number in range(chunks):
            end = start + size + (number < extra)
            groups.append((f"{topic} ({number + 1} of {chunks})", ordered[start:end]))
            start = end
    return groups


def chronological(record: dict) -> tuple:
    return (record["stated_on"], record["doc_id"], *when(record))


def reconcile_topic(topic: str, statements: list[dict], chat: Chat) -> tuple[dict, Counter[str]]:
    """One topic: its statements, relations, statuses, summary and problems, and how many
    things the model returned that we threw away. Statements are given oldest first."""
    labelled = _labelled(statements)
    messages = [
        {"role": "system", "content": RECONCILE_PROMPT},
        {
            "role": "user",
            "content": f"Topic: {topic}\n\nStatements, oldest first:\n{_render(labelled)}",
        },
    ]
    answer = chat(messages, schema=RECONCILE_SCHEMA)
    dropped: Counter[str] = Counter()
    relations = _relations(answer["relations"], labelled, dropped)
    statuses = statuses_from(relations, statements)
    for item in answer["statuses"]:
        record = labelled.get(item["statement"])
        if record is None or item["status"] not in STATUSES:
            dropped["status for an unknown statement or of an unknown kind"] += 1
        elif item["status"] != statuses[record["id"]]:
            dropped["status differs from what the relations give"] += 1
    summary = _summary(answer["summary"], labelled, dropped)
    supported = []
    for problem in _problems(answer["problems"], labelled, dropped):
        if _supported(problem, relations, statuses):
            supported.append(problem)
        else:
            dropped["problem no relation supports"] += 1
    return {
        "topic": topic,
        "summary": summary,
        "relations": relations,
        "statuses": statuses,
        "statements": statements,
        "problems": problems_for(topic, supported, relations, statuses),
    }, dropped


def statuses_from(relations: list[dict], statements: list[dict]) -> dict[str, str]:
    """Each statement's status, by id. This is where currency is decided: by the relations
    that survived validation, never by dates and never by what the model said the status was.

    never-true deliberately beats stale: reporting a record that was never true as merely old
    is one of the three failures the brief names.
    """
    corrected = {r["to"] for r in relations if r["kind"] == "corrects"}
    superseded = {r["to"] for r in relations if r["kind"] == "supersedes"}
    answered = {r["to"] for r in relations if r["kind"] == "answers"}
    disputed = {end for r in relations if r["kind"] == "conflicts-with" for end in _ends(r)}
    statuses: dict[str, str] = {}
    for record in statements:
        id_ = record["id"]
        if id_ in corrected:
            statuses[id_] = "never-true"
        elif id_ in superseded:
            statuses[id_] = "stale"
        elif id_ in disputed:
            statuses[id_] = "disputed"
        elif record["act"] in ("proposal", "question") and id_ not in answered:
            statuses[id_] = "current" if record["agreed_by"] else "unresolved"
        else:
            statuses[id_] = "current"
    return statuses


def problems_for(
    topic: str, model_problems: list[dict], relations: list[dict], statuses: dict[str, str]
) -> list[dict]:
    """The topic's problems: the model's, then one from a template for every flagged
    statement the model did not name. The templates hold ids and nothing else, so they
    cannot invent."""
    named = {id_ for problem in model_problems for id_ in problem["statements"]}
    forgotten = {id_ for id_, status in statuses.items() if status != "current"} - named
    problems = [{**problem, "topic": topic} for problem in model_problems]

    def add(kind: str, statements: list[str], note: str) -> None:
        problems.append({"kind": kind, "topic": topic, "statements": statements, "note": note})

    for r in relations:
        source, target = _ends(r)
        if r["kind"] == "supersedes" and target in forgotten and statuses[target] == "stale":
            add(
                "reversal",
                [target, source],
                f"{source} supersedes {target}; the record still reads as if {target} stands.",
            )
        elif r["kind"] == "corrects" and target in forgotten and statuses[target] == "never-true":
            add(
                "never-true",
                [target, source],
                f"{source} says {target} was wrong when it was recorded.",
            )
        elif r["kind"] == "conflicts-with" and forgotten & {source, target}:
            add(
                "conflict",
                [source, target],
                f"{source} and {target} cannot both be true, and nothing in the record "
                "settles which holds.",
            )
    for id_, status in statuses.items():
        if id_ in forgotten and status == "unresolved":
            add(
                "unanswered",
                [id_],
                f"{id_} was proposed or asked, and nothing in the record answers it.",
            )
    return problems


def reconcile(
    records: list[dict],
    chat: Chat,
    *,
    batch: int,
    vocabulary_shown: int,
    topic_cap: int,
    max_untagged: float,
    max_topics: float,
    max_topic_share: float,
    max_flagged: float,
    progress: Callable[[str], None] = print,
) -> tuple[list[dict], list[dict], Counter[str]]:
    """Topics, problems and everything thrown away, or a ReconcileError.

    Stage A tags every statement with a topic; stage B reconciles each topic on its own,
    one call at a time, in independent contexts. Nothing is retried.
    """
    topics, dropped = tag_topics(records, chat, batch, vocabulary_shown)
    untagged = [record for record in records if topics[record["id"]] == UNTAGGED]
    names = set(topics.values()) - {UNTAGGED}
    note = f", dropped {dict(dropped)}" if dropped else ""
    progress(
        f"Tagged {len(records)} statements: {len(names)} topics, {len(untagged)} untagged{note}"
    )
    # A grouping too fragmented to link anything would label the whole record current and
    # exit 0. It is the failure that looks like success, so it stops the run instead.
    if len(untagged) > max_untagged * len(records):
        raise ReconcileError(
            f"{len(untagged)} of {len(records)} statements came back untagged, more than "
            f"RECONCILE_MAX_UNTAGGED ({max_untagged}) allows. The model is not following the "
            "tagging prompt."
        )
    if len(names) > max_topics * len(records):
        raise ReconcileError(
            f"{len(names)} topics for {len(records)} statements, more than "
            f"RECONCILE_MAX_TOPICS ({max_topics}) allows. The topics are too fragmented to "
            "link anything."
        )
    # The opposite failure, and the one neither gate above can see: everything in one bucket.
    # A topic holding the whole record is not a subject, and the call that reconciles it is
    # shown unrelated statements and asked what they have to do with each other. See D42.
    held = Counter(topic for topic in topics.values() if topic != UNTAGGED)
    if held:
        largest, size = held.most_common(1)[0]
        if size > max_topic_share * len(records):
            raise ReconcileError(
                f"The topic {largest!r} holds {size} of {len(records)} statements, more than "
                f"RECONCILE_MAX_TOPIC_SHARE ({max_topic_share}) allows. The statements are too "
                "collapsed for a topic to name a subject."
            )

    reconciled: list[dict] = []
    problems: list[dict] = []
    for name, statements in group(records, topics, topic_cap):
        topic, drops = reconcile_topic(name, statements, chat)
        problems.extend(topic.pop("problems"))
        dropped.update(drops)
        reconciled.append(topic)
        counts = Counter(topic["statuses"].values())
        note = f", dropped {dict(drops)}" if drops else ""
        # Density is a review flag, not a gate: a genuinely contested topic is dense, but a
        # small model linking every statement to every other one looks the same in the counts.
        links = len(topic["relations"])
        progress(
            f"{name}: {len(statements)} statements, {links} relations "
            f"({links / len(statements):.1f} each), statuses {dict(counts)}{note}"
        )
        # A model that links each statement to the next one in the list flags nearly the whole
        # topic, and `corrects` is deliberately not date-guarded (D40), so nothing else rejects
        # it. Density was a review flag under D40; over this share it is a gate. See D42.
        flagged = sum(1 for status in topic["statuses"].values() if status in LINKED_STATUSES)
        if flagged > max_flagged * len(statements):
            raise ReconcileError(
                f"{name}: a relation flagged {flagged} of {len(statements)} statements, more "
                f"than RECONCILE_MAX_FLAGGED ({max_flagged}) allows. Relations this dense are "
                "a chain the model walked, not links it read."
            )
    if untagged:
        # Nothing was reconciled here, so nothing can be said against these: they are current
        # only in the sense that no relation names them.
        reconciled.append(
            {
                "topic": UNTAGGED,
                "summary": None,
                "relations": [],
                "statuses": {record["id"]: "current" for record in untagged},
                "statements": sorted(untagged, key=chronological),
            }
        )
    _check(reconciled, problems, records)
    return reconciled, problems, dropped


def _check(topics: list[dict], problems: list[dict], records: list[dict]) -> None:
    """The whole-artifact gate, run before anything is written. It reads the result, not the
    filters that produced it, because a bug in those is exactly what they would not catch."""
    held = {topic["topic"]: [record["id"] for record in topic["statements"]] for topic in topics}
    if len(held) != len(topics):
        raise ReconcileError("Two topics share a name.")
    wanted = Counter(record["id"] for record in records)
    found = Counter(id_ for ids in held.values() for id_ in ids)
    if found != wanted:
        lost, invented = wanted - found, found - wanted
        raise ReconcileError(
            f"Statements are not in exactly one topic each: {sum(lost.values())} missing or "
            f"short, {sum(invented.values())} repeated or not in the input."
        )
    flagged: set[str] = set()
    for topic in topics:
        ids = set(held[topic["topic"]])
        for relation in topic["relations"]:
            if relation["kind"] not in RELATIONS or not set(_ends(relation)) <= ids:
                raise ReconcileError(f"A relation in {topic['topic']} does not hold together.")
        summary = topic["summary"]
        if summary and not (summary["text"] and summary["statements"]):
            raise ReconcileError(f"The summary of {topic['topic']} has no text or no receipts.")
        if summary and not set(summary["statements"]) <= ids:
            raise ReconcileError(f"The summary of {topic['topic']} cites a statement not in it.")
        if set(topic["statuses"]) != ids:
            raise ReconcileError(f"{topic['topic']} does not give every statement a status.")
        if not set(topic["statuses"].values()) <= set(STATUSES):
            raise ReconcileError(f"{topic['topic']} has a status outside the five.")
        flagged |= {id_ for id_, status in topic["statuses"].items() if status != "current"}
    named: set[str] = set()
    for problem in problems:
        ids = set(held.get(problem["topic"], []))
        if problem["kind"] not in PROBLEM_KINDS or not problem["statements"]:
            raise ReconcileError(f"A problem in {problem['topic']} has no kind or no statements.")
        if not set(problem["statements"]) <= ids:
            raise ReconcileError(f"A problem in {problem['topic']} names a statement not in it.")
        named.update(problem["statements"])
    if flagged - named:
        raise ReconcileError(f"{len(flagged - named)} flagged statements are named in no problem.")


def _labelled(records: list[dict]) -> dict[str, dict]:
    """The model never sees a statement id. It sees S1, S2, … and we map back, so a copied id
    cannot be corrupted into a silently dropped link, and a label we did not hand out is
    recognisably invented."""
    return {f"S{number}": record for number, record in enumerate(records, 1)}


def _render(labelled: dict[str, dict], *, with_act: bool = True) -> str:
    """The statements as the model sees them.

    Stage A is shown no act. Asked to name a subject while looking at one, a small model copies
    the column it was given, and every topic comes back named after a speech act (D42). Stage B
    keeps it, because `unresolved` is defined on proposals and questions.
    """
    lines = []
    for label, record in labelled.items():
        actor = record["actor"]
        who = actor["name"] or actor["label"] or "unknown speaker"
        org = f" ({actor['org']})" if actor["org"] else ""
        span = " ".join(record["span"].split())
        act = f"{record['act']} | " if with_act else ""
        lines.append(f"[{label}] {record['stated_on']} | {who}{org} | {act}{span}")
    return "\n".join(lines)


def _vocabulary(use: Counter[str], shown: int) -> str:
    ranked = sorted(use.items(), key=lambda item: (-item[1], item[0]))[:shown]
    return "Topics already in use: " + (", ".join(topic for topic, _ in ranked) or "none yet") + "."


def _slug(topic: str) -> str | None:
    slug = " ".join(topic.split()).casefold().replace(" ", "-")
    return slug if len(slug) <= SLUG_MAX and SLUG.fullmatch(slug) else None


def _ends(relation: dict) -> tuple[str, str]:
    return relation["from"], relation["to"]


def _relations(items: list[dict], labelled: dict[str, dict], dropped: Counter[str]) -> list[dict]:
    relations: list[dict] = []
    seen: set[tuple] = set()
    for item in items:
        kind = item["kind"]
        source, target = labelled.get(item["from"]), labelled.get(item["to"])
        if kind not in RELATIONS:
            dropped["relation of an unknown kind"] += 1
            continue
        if source is None or target is None:
            dropped["relation names a statement outside the topic"] += 1
            continue
        if source is target:
            dropped["relation to itself"] += 1
            continue
        # The one date this pass reads (D40). It rejects a model error and creates no status:
        # a supersession cannot run backwards, and a same-day one passes because a transcript
        # carries only its meeting date. It is deliberately not applied to `corrects`, the
        # relation that produces never-true, so that relation stays entirely date-free.
        if kind == "supersedes" and source["stated_on"] < target["stated_on"]:
            dropped["supersedes runs backwards in time"] += 1
            continue
        ends = (source["id"], target["id"])
        # Two statements cannot both be true in either direction, so that is one relation.
        key = (kind, *sorted(ends)) if kind == "conflicts-with" else (kind, *ends)
        if key in seen:
            dropped["duplicate relation"] += 1
            continue
        seen.add(key)
        relations.append({"from": ends[0], "to": ends[1], "kind": kind})
    return relations


def _summary(raw: dict, labelled: dict[str, dict], dropped: Counter[str]) -> dict | None:
    text = " ".join(raw["text"].split())
    if _quotes(text):
        dropped["summary contains a quotation"] += 1
        return None
    if _invents_a_figure(text, labelled):
        dropped["summary states a figure the topic does not"] += 1
        return None
    receipts: list[str] = []
    for label in raw["statements"]:
        record = labelled.get(label)
        if record is None:
            dropped["summary receipt not in the topic"] += 1
        elif record["id"] not in receipts:
            receipts.append(record["id"])
    if not text or not receipts:
        dropped["summary without text or receipts"] += 1
        return None
    return {"text": text, "statements": receipts}


def _problems(items: list[dict], labelled: dict[str, dict], dropped: Counter[str]) -> list[dict]:
    problems: list[dict] = []
    for item in items:
        note = " ".join(item["note"].split())
        ids: list[str] = []
        outside = False
        for label in item["statements"]:
            record = labelled.get(label)
            outside = outside or record is None
            if record is not None and record["id"] not in ids:
                ids.append(record["id"])
        if item["kind"] not in PROBLEM_KINDS:
            dropped["problem of an unknown kind"] += 1
        elif outside:
            dropped["problem names a statement outside the topic"] += 1
        elif not ids:
            dropped["problem names no statement"] += 1
        elif not note or len(note) > NOTE_MAX or _quotes(note):
            dropped["problem note empty, too long or quoted"] += 1
        elif _invents_a_figure(note, labelled):
            dropped["problem note states a figure the topic does not"] += 1
        else:
            problems.append({"kind": item["kind"], "statements": ids, "note": note})
    return problems


def _supported(problem: dict, relations: list[dict], statuses: dict[str, str]) -> bool:
    """A problem stands only on a link: a relation of the matching kind between two of the
    statements it names, or, for unanswered, every one of them being unresolved."""
    named = set(problem["statements"])
    if problem["kind"] == "unanswered":
        return all(statuses[id_] == "unresolved" for id_ in named)
    kind = {"reversal": "supersedes", "never-true": "corrects", "conflict": "conflicts-with"}[
        problem["kind"]
    ]
    return any(r["kind"] == kind and set(_ends(r)) <= named for r in relations)


def _quotes(text: str) -> bool:
    return any(mark in text for mark in QUOTES)


def _figures(text: str) -> set[str]:
    """The numbers in a piece of text, normalised on the separator so that 1,200 and 1.200 are
    the same figure."""
    return {match.group().replace(",", ".") for match in NUMBER.finditer(text)}


def _invents_a_figure(text: str, labelled: dict[str, dict]) -> bool:
    """Whether model prose states a number none of the topic's statements contain.

    Numbers only, deliberately. A figure is the invention that does most damage in a derived
    artifact — the archive is full of half-said percentages — and it needs no heuristic to
    spot. Prose that contradicts the statuses, or says something false about a person in words
    the record does contain, is not reachable from here; `KEEP_PROSE` in output.py is still the
    answer to that one. See D42.
    """
    known = {f for record in labelled.values() for f in _figures(record["span"])}
    return bool(_figures(text) - known)
