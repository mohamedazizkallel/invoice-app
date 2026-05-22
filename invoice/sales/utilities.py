from decimal import Decimal, ROUND_HALF_UP
from num2words import num2words

# Per-currency wording. TND uses millimes (3 decimals); € uses centimes (2).
_CURRENCY_WORDS = {
    'TND': {'major': ('dinar', 'dinars'), 'minor': ('millime', 'millimes'), 'subunit': 1000, 'places': 3},
    '€':   {'major': ('euro', 'euros'),   'minor': ('centime', 'centimes'), 'subunit': 100,  'places': 2},
    'EUR': {'major': ('euro', 'euros'),   'minor': ('centime', 'centimes'), 'subunit': 100,  'places': 2},
}


def num2words_tnd_fr(amount: Decimal, currency: str = 'TND') -> str:
    """French amount-in-words, currency-aware. Defaults to TND (millimes)."""
    cfg = _CURRENCY_WORDS.get(currency, _CURRENCY_WORDS['TND'])
    subunit = cfg['subunit']
    q = Decimal(1).scaleb(-cfg['places'])  # 0.001 for TND, 0.01 for €

    amount = Decimal(amount).quantize(q, rounding=ROUND_HALF_UP)
    major = int(amount)
    minor = int(((amount - Decimal(major)) * subunit).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    # Carry if rounding hits a full unit
    if minor == subunit:
        major += 1
        minor = 0

    major_word = cfg['major'][0] if major == 1 else cfg['major'][1]
    minor_word = cfg['minor'][0] if minor == 1 else cfg['minor'][1]

    if minor:
        return (
            f"{num2words(major, lang='fr')} {major_word} "
            f"et {num2words(minor, lang='fr')} {minor_word}"
        )
    return f"{num2words(major, lang='fr')} {major_word}"
