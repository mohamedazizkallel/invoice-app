from num2words import num2words
from decimal import Decimal

def num2words_tnd_fr(amount: Decimal):
    dinars = int(amount)
    millimes = int((amount - dinars) * 1000)

    dinar_word = "dinar " if dinars == 1 else "dinars "
    millime_word = "millime" if millimes == 1 else "millimes"

    if millimes:
        return (
            f"{num2words(dinars, lang='fr')} {dinar_word} "
            f"et {num2words(millimes, lang='fr')} {millime_word}"
        )
    return f"{num2words(dinars, lang='fr')} {dinar_word}"
