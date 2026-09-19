"""Canonical person registry, built from acme/00_README.md.

This is the single source of truth every parser and the LLM annotation step
resolves names/emails against, so a person has one canonical_id everywhere
regardless of which document or format named them. Deletion (erasing a
person from the index/embeddings/derived artifacts) operates on this id.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Person:
    canonical_id: str
    name: str
    org: str
    title: str | None
    emails: tuple[str, ...] = field(default_factory=tuple)


PEOPLE: list[Person] = [
    Person("lena_fischer", "Lena Fischer", "Acme", "Head of Supply Chain",
           ("lena.fischer@acme-org.example",)),
    Person("robert_kahn", "Robert Kahn", "Acme", "CFO", ()),
    Person("sofia_almeida", "Sofia Almeida", "Acme", "Category Manager, Fresh", ()),
    Person("priya_nair", "Priya Nair", "Acme", "IT Integration Lead",
           ("priya.nair@acme-org.example",)),
    Person("jonas_weiss", "Jonas Weiss", "Acme", "Category Manager, Ambient", ()),
    Person("katarina_voss", "Katarina Voss", "Acme", "Data Protection Officer", ()),
    Person("marco_rossi", "Marco Rossi", "RELEX", "Account Executive",
           ("marco.rossi@relexsolutions.example",)),
    Person("ana_duarte", "Ana Duarte", "RELEX", "Project Manager",
           ("ana.duarte@relexsolutions.example",)),
    Person("nadia_haddad", "Nadia Haddad", "RELEX", "Solution Consultant",
           ("n.haddad@relexsolutions.example",)),
    Person("tomas_lindholm", "Tomas Lindholm", "RELEX", "Solution Architect",
           ("tomas.lindholm@relexsolutions.example",)),
    Person("kwame_boateng", "Kwame Boateng", "RELEX", "Technical Consultant",
           ("k.boateng@relexsolutions.example",)),
    Person("charlotte_meyer", "Charlotte Meyer", "RELEX", "Service Delivery", ()),
    Person("henrik_sorensen", "Henrik Sørensen", "RELEX", "Account Director", ()),
    Person("ivan_petrov", "Ivan Petrov", "Meridian Consulting", None, ()),
    Person("ruth_oyelaran", "Ruth Oyelaran", "Meridian Consulting", None, ()),
]

_BY_NAME = {p.name.lower(): p for p in PEOPLE}
_BY_EMAIL = {e.lower(): p for p in PEOPLE for e in p.emails}


def resolve_by_name(name: str) -> Person | None:
    """Exact (case-insensitive) name match only. Never guess an alias."""
    return _BY_NAME.get(name.strip().lower())


def resolve_by_email(email: str) -> Person | None:
    return _BY_EMAIL.get(email.strip().lower())


def all_names() -> list[str]:
    return [p.name for p in PEOPLE]
