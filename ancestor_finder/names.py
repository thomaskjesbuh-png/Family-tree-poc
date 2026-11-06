"""Normalisation and comparison of historical Norwegian names.

Handles the variation typical of 1800s records:

* spelling variants: Christine / Kristine / Kirstine, Thore / Tore,
  Hansdatter / Hansdtr. / Hansd., Olssøn / Olsen, aa / å
* patronymics: Olsen, Olsdatter and Olssøn all point to the father "Ole",
  so they share a root
* farm names used as surnames: "Anders Pedersen Holm" may appear as
  "Anders Holm" or as "Anders Pedersen" living on the farm Holm
"""

from __future__ import annotations

import re
import unicodedata

# Patronymic suffixes and the gender they imply ("" = used for both sexes,
# e.g. "-sen" in later census records). The genitive "s" before the suffix is
# removed from the root afterwards, so Olsen / Olsdatter / Olssøn share "ol".
_PATRONYMIC_SUFFIXES = {
    "datter": "f", "dotter": "f", "dattr": "f", "datr": "f", "dtr": "f",
    "sønn": "m", "søn": "m", "son": "m",
    "sen": "",
}

# Given names written in different ways for the same person in Norwegian
# records. Each group maps to its first entry. Grouping only says the names
# are compatible; birth year, place and family still have to agree.
_GIVEN_NAME_GROUPS = [
    ["kristine", "christine", "kirstine", "kristina", "christina", "kirsti", "kjersti", "kersti"],
    ["kristian", "christian", "kristen", "christen"],
    ["karen", "kari"],
    ["marie", "maria", "mari"],
    ["anne", "anna", "ane"],
    ["johan", "johannes", "johs", "jon"],
    ["johanne", "johanna"],
    ["peder", "per", "peter", "petter"],
    ["hans", "hanns"],
    ["ole", "ola", "olle"],
    ["lars", "lauritz", "laurits"],
    ["nils", "niels"],
    ["tore", "thore", "thor", "tor"],
    ["torsten", "thorsten", "torstein", "thorstein"],
    ["helge", "helje"],
    ["gunhild", "gunnhild", "gunild"],
    ["andreas", "anders"],
    ["karl", "carl"],
    ["karoline", "caroline", "carolina", "karolina"],
    ["elisabeth", "elisabet", "lisbeth", "lisbet"],
    ["mathias", "matias", "matthias"],
    ["mathilde", "matilde"],
    ["martin", "morten"],
    ["eli", "elie"],
    ["inger", "ingeborg"],
    # seen in real finds: the same person written differently across records
    ["olav", "olaf", "oluf", "olof"],
    ["mikal", "mikkel", "mikael", "michael", "michel"],
    ["salomon", "salamon"],
    ["hedvig", "hedda", "hedevig"],
    ["paul", "pål", "povel"],
    ["pernille", "petronelle", "petronella", "petternille", "petronille"],
    ["birgitte", "bergitte", "birgithe", "brigitte"],
    ["henrikke", "henrikka", "henrika", "hendrikke"],
]


def _strip_accents_keep_norwegian(s: str) -> str:
    """Remove diacritics except the Norwegian letters æ, ø, å."""
    out = []
    for ch in unicodedata.normalize("NFC", s):
        if ch in "æøåÆØÅ":
            out.append(ch)
            continue
        decomposed = unicodedata.normalize("NFD", ch)
        out.append("".join(c for c in decomposed if not unicodedata.combining(c)))
    return "".join(out)


def clean(s: str) -> str:
    """Lowercase, strip accents (keeping æøå), drop punctuation except dots."""
    s = _strip_accents_keep_norwegian(s or "").lower().strip()
    s = s.replace("ö", "ø").replace("ä", "æ")
    s = re.sub(r"[^a-zæøå.\s-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def phonetic(word: str) -> str:
    """Collapse common historical spelling differences of a single word.

    Not a full phonetic algorithm: only rules that are safe for Norwegian.
    """
    w = clean(word).replace(".", "").replace("-", "")
    if not w:
        return ""
    w = w.replace("aa", "å").replace("oe", "ø").replace("ae", "æ")
    w = w.replace("ch", "k").replace("ph", "f").replace("th", "t")
    w = w.replace("qu", "kv").replace("q", "k").replace("x", "ks")
    w = w.replace("w", "v").replace("z", "s")
    w = re.sub(r"c(?=[eiy])", "s", w)
    w = w.replace("c", "k")
    w = w.replace("dt", "t")
    w = re.sub(r"(.)\1+", r"\1", w)   # double letters
    w = w.replace("ie", "i")          # Kirstie / Kirsti
    return w


_GIVEN_INDEX: dict[str, str] = {}
for _group in _GIVEN_NAME_GROUPS:
    _canon = phonetic(_group[0])
    for _name in _group:
        _GIVEN_INDEX[phonetic(_name)] = _canon


def canonical_given(name: str) -> str:
    """Canonical key for one given name (first token only)."""
    tokens = clean(name).split()
    if not tokens:
        return ""
    p = phonetic(tokens[0])
    return _GIVEN_INDEX.get(p, p)


def patronymic_root(word: str) -> tuple[str, str] | None:
    """If word looks like a patronymic, return (root, gender).

    "Olsen" -> ("ol", "m"), "Olsdatter" -> ("ol", "f"), "Hansd." -> ("han", "f").
    The root is phonetic and drops the genitive "s", so Olsen/Olsdatter/Olssøn
    share a root. Gender is "m", "f" or "" (sen is used for both in later records).
    """
    raw = clean(word)
    if not raw:
        return None
    w = phonetic(raw)
    for suffix, gender in sorted(_PATRONYMIC_SUFFIXES.items(), key=lambda kv: -len(kv[0])):
        s = phonetic(suffix)
        if w.endswith(s) and len(w) - len(s) >= 2:
            return _strip_genitive(w[: -len(s)]), gender
    # Abbreviated patronymic (1900 census): "Ols.", "Anders.", "Olaves."
    m = re.fullmatch(r"([a-zæøå]{2,}s)\.", raw)
    if m:
        return _strip_genitive(phonetic(m.group(1))), ""
    # Abbreviated daughter form: "Olsd." / "Hansd."
    m = re.fullmatch(r"([a-zæøå]{2,}s)d\.?", raw)
    if m:
        return _strip_genitive(phonetic(m.group(1))), "f"
    return None


def _strip_genitive(root: str) -> str:
    return root[:-1] if root.endswith("s") and len(root) > 2 else root


def surname_keys(name: str) -> set[str]:
    """All comparison keys for a surname: phonetic form and patronymic root."""
    keys: set[str] = set()
    for token in clean(name).split():
        p = phonetic(token)
        if not p:
            continue
        keys.add(p)
        pr = patronymic_root(token)
        if pr:
            keys.add("patr:" + pr[0])
    return keys


def father_patronymic_roots(father_name: str) -> set[str]:
    """Patronymic roots a child of this father could carry.

    "Ole Larsen" -> {"ol"} (Olsen, Olsdatter), "Anders" -> {"ander", "andrea"}
    (Andersen, Andreassen). A final vowel is dropped like the records do.
    """
    tokens = clean(father_name).split()
    if not tokens:
        return set()
    roots = {_name_root(p) for p in {phonetic(tokens[0]), canonical_given(tokens[0])}}
    # every spelling of the same name gives the same patronymic (Olaf -> Olufsdatter)
    canon = canonical_given(tokens[0])
    roots |= {r for r, c in _ROOT_INDEX.items() if c == canon}
    return roots


def _name_root(p: str) -> str:
    if len(p) > 2 and p[-1] in "eai":
        p = p[:-1]
    return _strip_genitive(p)


# patronymic root of every grouped given name -> the group's canonical name
_ROOT_INDEX: dict[str, str] = {}
for _group in _GIVEN_NAME_GROUPS:
    for _name in _group:
        _ROOT_INDEX.setdefault(_name_root(phonetic(_name)), phonetic(_group[0]))


def same_patronymic_root(a: str, b: str) -> bool:
    """Roots from the same father's name, allowing its spellings (Lars / Lauritz)."""
    return a == b or (a in _ROOT_INDEX and _ROOT_INDEX.get(a) == _ROOT_INDEX.get(b))


# --- similarity -----------------------------------------------------------

def jaro_winkler(a: str, b: str) -> float:
    """Jaro-Winkler similarity in [0, 1]."""
    if a == b:
        return 1.0 if a else 0.0
    if not a or not b:
        return 0.0
    match_dist = max(len(a), len(b)) // 2 - 1
    a_flags = [False] * len(a)
    b_flags = [False] * len(b)
    matches = 0
    for i, ca in enumerate(a):
        lo, hi = max(0, i - match_dist), min(i + match_dist + 1, len(b))
        for j in range(lo, hi):
            if not b_flags[j] and b[j] == ca:
                a_flags[i] = b_flags[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    t = k = 0
    for i in range(len(a)):
        if a_flags[i]:
            while not b_flags[k]:
                k += 1
            if a[i] != b[k]:
                t += 1
            k += 1
    t /= 2
    jaro = (matches / len(a) + matches / len(b) + (matches - t) / matches) / 3
    prefix = 0
    for ca, cb in zip(a[:4], b[:4]):
        if ca != cb:
            break
        prefix += 1
    return jaro + prefix * 0.1 * (1 - jaro)


def word_similarity(a: str, b: str) -> float:
    """Jaro-Winkler on phonetic forms, damped when lengths differ a lot.

    Jaro-Winkler rewards shared prefixes, so "Hansen" vs "Hansebakken" would
    otherwise score 0.92; the length damping brings that down to about 0.68.
    """
    pa, pb = phonetic(a), phonetic(b)
    if not pa or not pb:
        return 0.0
    sim = jaro_winkler(pa, pb)
    ratio = min(len(pa), len(pb)) / max(len(pa), len(pb))
    return sim * (ratio ** 0.5) if ratio < 0.8 else sim


def given_name_similarity(a: str, b: str) -> float:
    """Similarity of two given names (first names compared; equivalents = 1)."""
    ca, cb = canonical_given(a), canonical_given(b)
    if not ca or not cb:
        return 0.0
    if ca == cb:
        return 1.0
    return word_similarity(ca, cb)


def surname_similarity(query_surname: str, rec_surname: str, rec_farm: str = "") -> tuple[float, str]:
    """Compare a queried surname to a record's surname and farm.

    Returns (similarity, how) where how explains what matched.
    """
    q_tokens = [t for t in clean(query_surname).split() if t]
    if not q_tokens:
        return 0.0, "no surname given"
    rec_tokens = [t for t in clean(rec_surname).split() if t]
    farm_tokens = [t for t in clean(rec_farm).split() if t]
    best, how = 0.0, "no surname match"
    for qt in q_tokens:
        q_pat = patronymic_root(qt)
        for rt in rec_tokens:
            r_pat = patronymic_root(rt)
            if q_pat and r_pat and same_patronymic_root(q_pat[0], r_pat[0]):
                if q_pat[1] and r_pat[1] and q_pat[1] != r_pat[1]:
                    score, h = 0.85, f"same patronymic root ({qt} / {rt}), different form"
                else:
                    score, h = 1.0, f"same patronymic ({qt} / {rt})"
            elif q_pat and r_pat:
                # Two patronymics from different fathers' names (Hansen vs Larsen):
                # compare the roots, not the shared "-sen" ending.
                score = word_similarity(q_pat[0], r_pat[0]) * 0.8
                h = f"different patronymics ({qt} / {rt})"
            else:
                score = word_similarity(qt, rt)
                h = f"surname {qt} vs {rt}"
            if score > best:
                best, how = score, h
        for ft in farm_tokens:
            if q_pat:
                break  # a patronymic is never a farm name
            score = word_similarity(qt, ft)
            if score > best:
                best, how = score, f"surname {qt} matches farm name {ft}"
    return best, how


def all_given_names(query_given: str, variants: list[str]) -> list[str]:
    names = [query_given] + [v.split()[0] for v in variants if v.strip()]
    seen, out = set(), []
    for n in names:
        k = canonical_given(n)
        if k and k not in seen:
            seen.add(k)
            out.append(n)
    return out


def all_surnames(query_surname: str, variants: list[str]) -> list[str]:
    out = [query_surname] if query_surname else []
    for v in variants:
        parts = v.split()
        if len(parts) > 1:
            out.append(" ".join(parts[1:]))
    return out


_PLACE_ABBREV = {"l": "lille", "st": "stor", "n": "nordre", "s": "søndre", "ø": "østre", "v": "vestre"}
_PLACE_NOISE = {"prgj", "prestegjeld", "herred", "sogn", "sogen", "landsogn", "kjøpstad", "by",
                "sm", "smaal", "smaalenene", "h", "hed", "sverige", "sverge", "norge"}


def place_key(place: str) -> str:
    """Comparable form of a place name: 'L. Elvedals Prgj.' and 'Lille Elvedalen' -> 'lilleelvedal'.

    Expands L./St. abbreviations, drops words like 'herred' and 'prgj', and
    removes a genitive -s and the definite endings -en/-et/-n.
    """
    words = [w.strip(".") for w in clean(place).replace("-", " ").split()]
    out = []
    for i, w in enumerate(words):
        if not w:
            continue
        if i == 0 and len(words) > 1 and w in ("l", "st"):
            out.append(_PLACE_ABBREV[w])
            continue
        if w in _PLACE_NOISE:
            continue
        out.append(w)
    k = phonetic("".join(out)).replace("øi", "øy")   # old spelling: Høilandet = Høylandet
    for suffix in ("ens", "ets", "en", "et", "s", "n"):
        if k.endswith(suffix) and len(k) - len(suffix) >= 4:
            k = k[: -len(suffix)]
            break
    return k
