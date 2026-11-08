from billionaires.names import full_key, is_group, link, short_key, tokens


def test_tokens_fold_accents_and_drop_suffixes():
    assert tokens("Hansjörg Wyss") == ["hansjorg", "wyss"]
    assert tokens("Samuel Newhouse, Jr.") == ["samuel", "newhouse"]
    assert tokens("Liu Yonghao & family") == ["liu", "yonghao"]


def test_full_key_ignores_order_and_nicknames():
    assert full_key("Li Ka-shing") == full_key("Ka-shing Li")
    assert full_key("Jim Simons") == full_key("James Simons")
    assert full_key("Alexey Mordashov") == full_key("Alexei Mordashov")


def test_short_key_needs_two_distinct_tokens():
    assert short_key("Lin Yu-lin") == ""  # first and last token are the same
    assert short_key("Ray Hunt") == short_key("Ray Lee Hunt")


def test_group_names_are_detected():
    assert is_group("Theo and Karl Albrecht")
    assert is_group("David & Simon Reuben")
    assert not is_group("Bent Jensen & Family")
    assert not is_group("Liu Yonghao & family")


def test_link_prefers_full_then_short_and_refuses_ambiguity():
    right = [("ray-lee-hunt", "Ray Lee Hunt"), ("wang-wei-1", "Wang Wei"), ("wang-wei-2", "Wei Wang"),
             ("mike-bloomberg", "Michael Bloomberg")]
    got = link(["Ray Hunt", "Wang Wei", "Mike Bloomberg", "Theo and Karl Albrecht"], right)
    assert got["Ray Hunt"] == ("ray-lee-hunt", "short")
    assert got["Mike Bloomberg"] == ("mike-bloomberg", "full")
    assert "Wang Wei" not in got  # two people share the key: never guess
    assert "Theo and Karl Albrecht" not in got
