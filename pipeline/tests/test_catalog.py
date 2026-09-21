import json

import pytest

from vadibook import catalog


@pytest.mark.parametrize(
    "title,default,expected",
    [
        ("Kurtlar Vadisi Pusu 123. Bölüm FULL HD", "pusu", ("pusu", 123, None)),
        ("Kurtlar Vadisi - 80. Bölüm FULL HD", "kv", ("kv", 80, None)),
        ("1.Bölüm - Kurtlar Vadisi | 4K", "kv", ("kv", 1, None)),
        ("Kurtlar Vadisi Pusu 5.Bölüm 2.Kısım", "pusu", ("pusu", 5, 2)),
        ("Kurtlar Vadisi Pusu 300. Bölüm (Final)", "pusu", ("pusu", 300, None)),
        ("Kurtlar Vadisi Pusu 12. Bölüm", "kv", ("pusu", 12, None)),  # title wins over playlist
        ("KURTLAR VADİSİ 7. BÖLÜM", "kv", ("kv", 7, None)),
        ("Valley of the Wolves - Episode 1 / @ResmiPolatAlemdar", "kv", ("kv", 1, None)),
        ("Kurtlar Vadisi Fragman", "kv", None),
    ],
)
def test_parse_title(title, default, expected):
    assert catalog.parse_title(title, default) == expected


def test_build_catalog_groups_parts_and_computes_offsets():
    entries = {
        "pusu": [
            {"id": "b", "title": "Kurtlar Vadisi Pusu 5. Bölüm 2. Kısım", "duration": 3000},
            {"id": "a", "title": "Kurtlar Vadisi Pusu 5. Bölüm 1. Kısım", "duration": 2500},
            {"id": "c", "title": "Kurtlar Vadisi Pusu 6. Bölüm", "duration": 5400},
        ]
    }
    episodes, warnings = catalog.build_catalog(entries)
    assert warnings == []
    assert [e.id for e in episodes] == ["pusu/5", "pusu/6"]
    ep5 = episodes[0]
    assert [p.yt_id for p in ep5.parts] == ["a", "b"]
    assert ep5.parts[0].offset_sec == 0.0
    assert ep5.parts[1].offset_sec == 2500.0
    assert ep5.parts[1].duration_sec == 3000.0


def test_build_catalog_warns_on_unparsed_and_duplicates():
    entries = {
        "kv": [
            {"id": "x", "title": "Kurtlar Vadisi 3. Bölüm", "duration": 100},
            {"id": "y", "title": "Kurtlar Vadisi 3. Bölüm FULL HD", "duration": 100},
            {"id": "z", "title": "Kurtlar Vadisi Kamera Arkası", "duration": 100},
        ]
    }
    episodes, warnings = catalog.build_catalog(entries)
    assert len(episodes) == 1 and episodes[0].parts[0].yt_id == "x"
    assert any("unparsed" in w and "z" in w for w in warnings)
    assert any("duplicate" in w and "kv/3" in w for w in warnings)


def test_gaps_reports_missing_numbers():
    episodes, _ = catalog.build_catalog(
        {"kv": [{"id": "a", "title": "Kurtlar Vadisi 1. Bölüm", "duration": 1},
                {"id": "b", "title": "Kurtlar Vadisi 3. Bölüm", "duration": 1}]}
    )
    assert catalog.gaps(episodes, expected={"kv": 3, "pusu": 0}) == ["kv/2"]


def test_save_load_find(data_root):
    episodes, _ = catalog.build_catalog(
        {"pusu": [{"id": "a", "title": "Kurtlar Vadisi Pusu 17. Bölüm", "duration": 10}]}
    )
    catalog.save_episodes(episodes)
    raw = json.loads((data_root / "public" / "episodes.json").read_text(encoding="utf-8"))
    assert raw[0]["series"] == "pusu"
    loaded = catalog.load_episodes()
    assert loaded == episodes
    assert catalog.find_episode(loaded, "pusu/17").key == "pusu-017"
    with pytest.raises(KeyError):
        catalog.find_episode(loaded, "pusu/18")


def test_build_catalog_merges_extra_videos_only_for_missing_episodes():
    entries = {"pusu": [{"id": "a", "title": "Kurtlar Vadisi Pusu 85. Bölüm", "duration": 10}]}
    extra = [
        {"series": "pusu", "no": 86, "parts": [{"yt_id": "x86", "title": "Kurtlar Vadisi Pusu 86. Bölüm"}]},
        {"series": "pusu", "no": 85, "parts": [{"yt_id": "dup", "title": "ignored, playlist wins"}]},
    ]
    episodes, warnings = catalog.build_catalog(entries, extra=extra)
    assert [e.id for e in episodes] == ["pusu/85", "pusu/86"]
    assert episodes[0].parts[0].yt_id == "a"
    assert episodes[1].parts[0].yt_id == "x86"
    assert any("extra ignored" in w and "pusu/85" in w for w in warnings)


def test_load_extra_returns_empty_when_file_missing(data_root):
    assert catalog.load_extra() == []
