from vadibook.textnorm import normalize_tr, to_ascii


def test_dotted_capital_i_lowercases_to_dotted_i():
    assert normalize_tr("İstanbul") == "istanbul"


def test_dotless_capital_i_lowercases_to_dotless_i():
    assert normalize_tr("ISPARTA") == "ısparta"


def test_circumflex_is_removed():
    assert normalize_tr("Kâşif Kozinoğlu") == "kaşif kozinoğlu"


def test_ascii_fold():
    assert to_ascii("Kaşifoğlu") == "kasifoglu"
    assert to_ascii("Çakır Süleyman Ömer İbrahim") == "cakir suleyman omer ibrahim"


def test_normalize_keeps_punctuation_and_spaces():
    assert normalize_tr("Polat, gel!  ") == "polat, gel!  "
