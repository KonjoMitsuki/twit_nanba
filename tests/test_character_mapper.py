from processing.character_mapper import character_for_tags, load_character_map


def test_character_for_tags_normalizes_hash_case_and_whitespace(tmp_path):
    path = tmp_path / "character_map.csv"
    path.write_text(
        "tag,character\n#Miku fan, 初音ミク \nother,巡音ルカ\n",
        encoding="utf-8",
    )

    assert character_for_tags(["  #MIKU FAN  "], path) == "初音ミク"


def test_character_map_keeps_first_duplicate_and_ignores_invalid_rows(tmp_path):
    path = tmp_path / "character_map.csv"
    path.write_text(
        "tag,character\nfoo,初音ミク\nfoo,巡音ルカ\n,missing tag\nmissing,\n",
        encoding="utf-8",
    )

    assert load_character_map(path) == {"foo": "初音ミク"}
    assert character_for_tags(["unknown"], path) is None