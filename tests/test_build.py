from billionaires import build


def test_canonical_ids_merges_reordered_names_but_not_namesakes(profiles, lists):
    alias = build.canonical_ids(profiles, lists)
    assert alias == {"yonghao-liu": "liu-yonghao"}  # same person, re-filed by Forbes
    # wang-wei and wei-wang share a key and birth year but appear on the same
    # list, so they are two people and must stay apart.


def test_build_end_to_end(profiles, lists, corgis):
    t = build.build(corgis, profiles, lists)
    p = t["people"].set_index("person_id")

    assert "yonghao-liu" not in p.index
    assert p.loc["liu-yonghao", "months_listed"] == 3
    assert p.loc["liu-yonghao", "first_seen_year"] == 2019
    assert not p.loc["liu-yonghao", "first_seen_exact"]  # on the very first list: censored

    ada = p.loc["ada-lovelace"]
    assert ada["first_seen_year"] == 2021 and ada["first_seen_exact"]
    assert ada["age_at_first_seen"] == 46
    assert ada["dropout"] and ada["education_level"] == "dropout"
    assert ada["industry"] == "Technology" and ada["on_latest_list"]

    old = p.loc["old-timer"]
    assert old["first_seen_year"] == 1996 and not old["first_seen_exact"]
    assert old["historical_lists"] == "1996" and old["linked_across_sources"]

    gone = p.loc["piie-gone-forever"]
    assert gone["wealth_origin"] == "self-made" and gone["industry"] == "Technology"
    assert gone["country"] == "France" and not gone["on_latest_list"]

    assert set(t["annual"]["year"]) == {2019, 2020, 2021}


def test_degree_level():
    assert build.degree_level(None) == "unknown"
    assert build.degree_level([{"degree": "Master of Business Administration"}]) == "master"
    assert build.degree_level([{"degree": "Bachelor of Arts/Science"}, {"degree": "Ph.D"}]) == "doctorate"
    assert build.degree_level([{"degree": "Drop Out"}]) == "dropout"


def test_country_name():
    assert build.country_name("ru") == "Russia"
    assert build.country_name("kz") == "Kazakhstan"
    assert build.country_name(None) is None
