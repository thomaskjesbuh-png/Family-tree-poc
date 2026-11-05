import pytest

from ancestor_finder import names


@pytest.mark.parametrize("a,b", [
    ("Kristine", "Christine"), ("Kristine", "Kirstine"), ("Thore", "Tore"),
    ("Carl", "Karl"), ("Marie", "Maria"), ("Anders", "Andreas"), ("Ole", "Ola"),
])
def test_given_name_equivalents(a, b):
    assert names.given_name_similarity(a, b) == 1.0


@pytest.mark.parametrize("a,b", [("Ole", "Hans"), ("Kristine", "Karen"), ("Peder", "Lars")])
def test_different_given_names_are_not_close(a, b):
    assert names.given_name_similarity(a, b) < 0.8


@pytest.mark.parametrize("word,root,gender", [
    ("Olsen", "ol", ""), ("Olsdatter", "ol", "f"), ("Olssøn", "ol", "m"),
    ("Olsd.", "ol", "f"), ("Hansdtr", "han", "f"), ("Pedersen", "peder", ""),
    ("Johansdatter", "johan", "f"), ("Larssen", "lar", ""),
])
def test_patronymic_root(word, root, gender):
    assert names.patronymic_root(word) == (root, gender)


@pytest.mark.parametrize("word", ["Holm", "Bakken", "Ree", "Haugen"])
def test_farm_names_are_not_patronymics(word):
    assert names.patronymic_root(word) is None


def test_patronymic_forms_match():
    score, how = names.surname_similarity("Olsdatter", "Olsen")
    assert score == 1.0 and "patronymic" in how


def test_different_patronymics_do_not_match_on_sen_ending():
    score, _ = names.surname_similarity("Hansen", "Larsen")
    assert score < 0.6


def test_farm_name_used_as_surname():
    score, how = names.surname_similarity("Pedersen Holm", "Holm")
    assert score == 1.0
    score, how = names.surname_similarity("Holm", "Pedersen", "Holm")
    assert score == 1.0 and "farm" in how


def test_prefix_lookalike_farm_is_damped():
    score, _ = names.surname_similarity("Hansen", "", "Hansebakken")
    assert score < 0.8


def test_father_roots():
    assert names.father_patronymic_roots("Ole Larsen") == {"ol"}
    assert "ander" in names.father_patronymic_roots("Anders")


@pytest.mark.parametrize("a,b", [("Gaarden", "Gården"), ("Thorsen", "Torsen"), ("Wilhelm", "Vilhelm")])
def test_phonetic_spelling(a, b):
    assert names.phonetic(a) == names.phonetic(b)


def test_jaro_winkler_bounds():
    assert names.jaro_winkler("", "") == 0.0
    assert names.jaro_winkler("abc", "abc") == 1.0
    assert 0 < names.jaro_winkler("martha", "marhta") < 1
