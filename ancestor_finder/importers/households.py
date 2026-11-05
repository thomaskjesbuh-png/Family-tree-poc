"""Derive parents and spouse from a person's position in a census household.

Census lists give relations only as a role relative to the household head
("hans Søn", "Hustru", "d"). We read them conservatively:

* a head and a wife are each other's spouse;
* a son or daughter of the head gets the head as father (male head) or
  mother (female head), and the head's wife as mother when the role says the
  child is theirs ("deres", plain "Søn"/"s"/"d") or the head's ("hans");
* "hendes" (her) children get only the mother;
* step-, foster- and grandchildren, in-laws and servants get nothing.

Every relation found this way is marked as inferred on the record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Member:
    name: str
    sex: str          # m / f / ""
    role: str         # family role as written
    relations: dict[str, str] = field(default_factory=dict)  # father/mother/spouse -> name


_HEAD = re.compile(r"^(hf|hb|husf|huusf|hu?usfa(de)?r|hu?usbond[e]?|hovedperson|husholder|"
                   r"enkemand|enkemann|mand|gaardmand|bonde)$", re.I)
_HEAD_F = re.compile(r"^(husmo(de)?r|hm|enke|huusmoder|husholderske|madmoder)$", re.I)
_WIFE = re.compile(r"^((hans|husbondens) )?(kone|hustru|huustrue|hustrue|kona|hm|husmo(de)?r)$", re.I)
_EXCLUDE = re.compile(r"sted|stif|pleie|pleje|fos[tst]|plejl|datterdatter|datters|sønnes|sønne|søns|"
                      r"barnebarn|svoger|sviger|soster|søster|broder|bror|tjen|dreng|pige|"
                      r"logerende|losjerende|inderst|kost|faders|moders", re.I)
_CHILD = re.compile(r"\b(s|d|søn|sønn|son|datter|dotter|dat|daatter|barn|born|børn)\b", re.I)


def _norm(role: str) -> str:
    return re.sub(r"\s+", " ", role.strip().lower().replace(".", ""))


def is_head(role: str, sex: str) -> bool:
    r = _norm(role)
    return bool(_HEAD.match(r)) or (bool(_HEAD_F.match(r)) and sex == "f" and r not in ("hm",))


def is_wife(role: str) -> bool:
    return bool(_WIFE.match(_norm(role)))


def child_kind(role: str) -> str | None:
    """Return 'both', 'father', 'mother' or None for a child-of-head role."""
    r = _norm(role)
    if not r or _EXCLUDE.search(r) or not _CHILD.search(r):
        return None
    if r.startswith(("hendes", "hendis", "konens", "hustruens", "husmoderens")):
        return "mother"   # her child, maybe not his
    if r.startswith(("mandens", "husbondens", "husfaderens")):
        return "father"
    return "both"


def assign_relations(members: list[Member]) -> None:
    """Fill `relations` in place for one dwelling or apartment, in list order."""
    head: Member | None = None
    wife: Member | None = None
    for m in members:
        if is_head(m.role, m.sex) or (head is None and m.sex == "f" and is_wife(m.role)):
            # a wife-coded woman with no head before her (e.g. a widow, "hm") heads the family
            head, wife = m, None
            continue
        if head is not None and wife is None and is_wife(m.role) and head.sex != "f":
            wife = m
            m.relations["spouse"] = head.name
            head.relations["spouse"] = m.name
            continue
        kind = child_kind(m.role)
        if head is None or kind is None:
            continue
        if head.sex == "f":
            m.relations["mother"] = head.name
        else:
            if kind in ("both", "father"):
                m.relations["father"] = head.name
            if wife is not None and kind in ("both", "mother"):
                m.relations["mother"] = wife.name
