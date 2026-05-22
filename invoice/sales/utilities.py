from decimal import Decimal, ROUND_HALF_UP
from num2words import num2words

def num2words_tnd_fr(amount: Decimal) -> str:
    # Ensure Decimal input and round to 3 decimal places (millimes)
    amount = Decimal(amount).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    dinars = int(amount)
    millimes = int(((amount - Decimal(dinars)) * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    # Carry if rounding hits 1000 millimes
    if millimes == 1000:
        dinars += 1
        millimes = 0

    dinar_word = "dinar" if dinars == 1 else "dinars"
    millime_word = "millime" if millimes == 1 else "millimes"

    if millimes:
        return (
            f"{num2words(dinars, lang='fr')} {dinar_word} "
            f"et {num2words(millimes, lang='fr')} {millime_word}"
        )
    return f"{num2words(dinars, lang='fr')} {dinar_word}"