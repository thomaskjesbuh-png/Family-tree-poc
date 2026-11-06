"""Derive parents and spouse from a person's position in a census household.

Census lists give relations only as a role relative to the household head
("hans Søn", "Hustru", "d"). We read them conservatively:

* a head and a wife are each other's spouse;
* a son or daughter of the head gets the head as father (male head) or
  mother (female head), and the head's wife as mother when the role says the
  child is theirs ("deres", plain "Søn"/"s"/"d") or the head's ("hans");
* "hendes" (her) children get only the mother;
* a stepchild of a married man is his wife's child from an earlier
  marriage, so it gets the wife as mother (the different surname then names
  her first husband); a stepchild of a woman gets nothing;
* the head's own parents ("hans Fader", "Mandens Moder") become the head's
  father or mother, and the wife's parents ("Konens Fader", "Svigermoder")
  the wife's;
* a retired couple on the farm (kårfolk, føderådsfolk) are taken as the
  head's parents only when the head's patronymic fits the man's given name
  (Per Larsson under kårmann Lars Persson);
* foster- and grandchildren, other in-laws and servants get nothing.

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
_STEP = re.compile(r"^((hans|mandens|husbondens|husfaderens) )?st[ei]e?[dfv]?s?(søn|sønn|son|datter|dotter|daatter|barn)$", re.I)
_PARENT = re.compile(r"^(?:(hans|mandens|husbondens|husfaderens|konens|hustruens|hendes|husmoderens) )?"
                     r"(sviger)?(fa(de)?r|mo(de)?r)$", re.I)
_RETIRED = re.compile(r"(kaar|kår|føderaad|føderåd|fderaad|forpleiningsm)", re.I)
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


def step_kind(role: str) -> bool:
    """True for a stepchild of the head ("Stedsøn", "hans Stifdatter")."""
    return bool(_STEP.match(_norm(role)))


def parent_kind(role: str) -> tuple[str, str] | None:
    """(whose, which) for a parent of the head or wife, e.g. ("head", "father").

    "hans Fader" -> head's father; "Konens Moder" / "Svigermoder" -> wife's mother.
    """
    m = _PARENT.match(_norm(role))
    if not m:
        return None
    owner, inlaw, word = m.group(1) or "", m.group(2), m.group(3)
    if inlaw and owner in ("konens", "hustruens", "hendes", "husmoderens"):
        return None   # the wife's parent-in-law is the head's parent: too rare to guess
    whose = "wife" if inlaw or owner in ("konens", "hustruens", "hendes", "husmoderens") else "head"
    return whose, "father" if word.startswith("fa") else "mother"


def is_retired(role: str) -> bool:
    return bool(_RETIRED.search(_norm(role)))


def _fits_patronymic(child_name: str, father_name: str) -> bool:
    """Does a patronymic in child_name come from father_name's given name?"""
    from ..names import father_patronymic_roots, patronymic_root
    roots = father_patronymic_roots(father_name)
    for token in child_name.split()[1:]:
        pr = patronymic_root(token)
        if pr and pr[0] in roots:
            return True
    return False


def assign_relations(members: list[Member]) -> None:
    """Fill `relations` in place for one dwelling or apartment, in list order."""
    head: Member | None = None
    wife: Member | None = None
    elder: Member | None = None   # a retired man listed just before
    elder_is_father = False
    for m in members:
        if head is not None and m.sex == "m" and is_retired(m.role):
            elder, elder_is_father = m, False
            if "father" not in head.relations and _fits_patronymic(head.name, m.name):
                head.relations["father"] = m.name
                elder_is_father = True
            continue
        if elder is not None and m.sex == "f" and (is_wife(m.role) or is_retired(m.role)):
            # the retired man's wife, listed right after him: not the head's wife
            m.relations["spouse"] = elder.name
            elder.relations["spouse"] = m.name
            if elder_is_father and "mother" not in head.relations:
                head.relations["mother"] = m.name
            elder = None
            continue
        elder = None
        pk = parent_kind(m.role) if head is not None else None
        if pk is not None:
            whose, which = pk
            target = head if whose == "head" else wife
            if target is not None and which not in target.relations and \
                    (which == "mother" or m.sex != "f") and (which == "father" or m.sex != "m"):
                target.relations[which] = m.name
            continue
        if is_head(m.role, m.sex) or (m.sex == "f" and is_wife(m.role) and (
                head is None or wife is not None or head.sex == "f")):
            # A wife-coded woman with no husband before her heads her own family:
            # a widow listed first, or a second "hm" after the household's wife
            # (e.g. a widowed mother-in-law with her own children).
            head, wife = m, None
            continue
        if head is not None and wife is None and is_wife(m.role) and head.sex != "f":
            wife = m
            m.relations["spouse"] = head.name
            head.relations["spouse"] = m.name
            continue
        if head is not None and head.sex != "f" and wife is not None and step_kind(m.role):
            m.relations["mother"] = wife.name   # her child from an earlier marriage
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
