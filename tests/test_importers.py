"""Importer tests on invented lines in the archive formats (no real data in git)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from ancestor_finder.importers import booklets as B
from ancestor_finder.importers.ft1801 import parse_1801
from ancestor_finder.importers.households import Member, assign_relations, child_kind

H1865 = "Nr. Namn                          Kj. Siv. Fam.          Yrkje                        Fødd         Fødestad"
H1910 = "Nr. Namn                             Kj. Siv. Bust.Fam.            Yrkje                        Fødd         Fødestad              Statsb.Tru."


def test_parse_1865_line():
    cols = B._header_cols(H1865)
    p = B._parse_person("003 Lars Andreas Olsen          m ug hans Søn                                       2 (alder)    Rakkestad",
                        cols, 1865, 9, "Bakken")
    assert (p.name, p.sex, p.marital, p.role, p.born, p.birthplace) == \
        ("Lars Andreas Olsen", "m", "ug", "hans Søn", "2 (alder)", "Rakkestad")
    assert B._birth_year(p.born, 1865) == (1863, True)


def test_parse_1910_line_with_codes_and_no_marital_status():
    cols = B._header_cols(H1910)
    p = B._parse_person("004 Signe Marie Hansen             k        b d                 Skolebarn                     04.03.1899 Tune Sm               n      s",
                        cols, 1910, 3, "Lia")
    assert (p.name, p.sex, p.marital, p.role, p.occupation, p.birthplace) == \
        ("Signe Marie Hansen", "f", "", "d", "Skolebarn", "Tune Sm")
    assert B._birth_year(p.born, 1910) == (1899, False)


def test_birthplace_glued_to_codes_is_cleaned():
    h = "Nr. Namn                   Kj. Siv. Bust.Fam.        Yrkje                     Fødd      FødestadStatsb. Tru."
    p = B._parse_person("001 Ole Hansen                m g b hf                  Gaardbruker               27.10.1868Torsnes n       s",
                        B._header_cols(h), 1910, 1, "")
    assert p.birthplace == "Torsnes"


def test_short_year_dates():
    assert B._birth_year("81.11.27", 1900) == (1881, False)
    assert B._birth_year("00.03.01", 1900) == (1900, False)


def test_split_name():
    assert B.split_name("Carl Andreas Steffensen") == ("Carl Andreas", "Steffensen")
    assert B.split_name("Anders Pedersen Holm") == ("Anders", "Pedersen Holm")
    assert B.split_name("Edevard Anders.") == ("Edevard", "Anders.")
    assert B.split_name("Engelbrektson") == ("Engelbrektson", "")


def test_household_relations():
    ms = [Member("Ole Hansen", "m", "Husfader"), Member("Kari Olsdatter", "f", "hans Kone"),
          Member("Hans Olsen", "m", "deres Søn"), Member("Berte Larsdatter", "f", "Tjenestepige"),
          Member("Anne Pedersdatter", "f", "Konens Datter"), Member("Lise Olsdatter", "f", "hendes Datter")]
    assign_relations(ms)
    assert ms[0].relations == {"spouse": "Kari Olsdatter"}
    assert ms[2].relations == {"father": "Ole Hansen", "mother": "Kari Olsdatter"}
    assert ms[3].relations == {}
    assert ms[4].relations == {"mother": "Kari Olsdatter"}   # wife's daughter: not his
    assert ms[5].relations == {"mother": "Kari Olsdatter"}


def test_widow_head_and_coded_roles():
    ms = [Member("Maren Olsen", "f", "hm"), Member("Johan Olsen", "m", "s")]
    assign_relations(ms)
    assert ms[1].relations == {"mother": "Maren Olsen"}


@pytest.mark.parametrize("role,kind", [("hans Søn", "both"), ("d", "both"), ("hendes Søn", "mother"),
                                       ("Datterdatter", None), ("pleiesøn", None), ("Stedsøn", None),
                                       ("tj", None), ("Svigersøn", None),
                                       ("Konens Søn", "mother"), ("Mandens Datter", "father")])
def test_child_kind(role, kind):
    assert child_kind(role) == kind


def test_inconsistent_father_dropped():
    ms = [Member("Arnt Andersen", "m", "hf"), Member("Augusta Andersen", "f", "hm"),
          Member("Karola Pettersen", "f", "d"), Member("Olaf Arntsen", "m", "s")]
    assign_relations(ms)
    B._drop_inconsistent_fathers(ms)
    assert "father" not in ms[2].relations and ms[2].relations["mother"] == "Augusta Andersen"
    assert ms[3].relations["father"] == "Arnt Andersen"


def test_parse_1801(tmp_path):
    header = ("kjonn;alder;faar;HHOLD;PERNUM;MOMLOC;POPLOC;SPLOC;fornavn;patr;slektsnavn;famst;"
              "PFID;bosted;prgj;amt")
    rows = ["m;40;1760;000001;0001;00;00;02;Ole;Hansen;;Huusbonde;pf0001;Bakke;Idde;Smaalehnene",
            "k;35;1765;000001;0002;00;00;01;Kari;Olsdatter;;Hans kone;pf0002;Bakke;Idde;Smaalehnene",
            "m;8;1792;000001;0003;02;01;00;Hans;Olsen;;Deres søn;pf0003;Bakke;Idde;Smaalehnene"]
    f = tmp_path / "Ft1801_forsk_01Ostfold_v1.txt"
    f.write_bytes(("\n".join([header] + rows) + "\n").encode("latin-1"))
    recs = parse_1801(f)
    son = recs[2]
    assert (son.given_name, son.surname, son.birth_year, son.father_name, son.mother_name) == \
        ("Hans", "Olsen", 1792, "Ole Hansen", "Kari Olsdatter")
    assert son.relations_inferred and son.url.endswith("/pf0003")
    assert recs[0].spouse_name == "Kari Olsdatter"


@pytest.mark.skipif(not shutil.which("pdftotext"), reason="needs poppler pdftotext")
def test_page_split(tmp_path, monkeypatch):
    class R:
        stdout = "page one\fpage two".encode()
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: R())
    assert B.pdf_to_pages(tmp_path / "x.pdf") == ["page one", "page two"]


def test_second_housewife_starts_her_own_family():
    ms = [Member("Lars Larsen", "m", "hf"), Member("Marte Larsen", "f", "hm"),
          Member("Johan Larsen", "m", "s"), Member("Berte Olsen", "f", "hm"),
          Member("Nils Andersen", "m", "s")]
    assign_relations(ms)
    assert ms[2].relations == {"father": "Lars Larsen", "mother": "Marte Larsen"}
    assert ms[4].relations == {"mother": "Berte Olsen"}


def test_labelled_note_is_not_added_to_name(tmp_path, monkeypatch):
    page = "\n".join([
        "Bustadnr. Krets           Namn                           Gnr.          Bnr.",
        "0001      001 Nes         Bakken                         1             1",
        "Nr. Namn                   Kj. Siv. Bust.Fam.        Yrkje                     Fødd      Fødestad",
        "001 Lars Larsen           m g b hf                  Arbeider                31.08.1877 Sverige",
        "    Heimvendt norsk-amerikanar: Utflytta frå Noreg: 1907",
        "002 Marte Larsen           k g b hm                  Husmor                    06.10.1879 Varteig",
    ])
    monkeypatch.setattr(B, "pdf_to_pages", lambda pdf: ["intro", page])
    recs = B.parse_booklet(tmp_path / "f9100199_hefte.pdf", 1910)
    assert [r.full_name for r in recs] == ["Lars Larsen", "Marte Larsen"]
    assert recs[0].spouse_name == "Marte Larsen" and recs[0].farm == "Bakken"
