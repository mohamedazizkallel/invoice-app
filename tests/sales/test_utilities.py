import pytest
from decimal import Decimal


class TestNum2WordsTndFr:
    def test_zero(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('0'))
        assert result == 'zéro dinars'

    def test_one_dinar(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('1.000'))
        assert result == 'un dinar'

    def test_whole_dinars(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('1234.000'))
        assert 'mille deux cent trente-quatre' in result
        assert 'dinars' in result
        assert 'millime' not in result

    def test_millimes_only(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('0.500'))
        assert 'cinq cents millimes' in result

    def test_one_millime(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('0.001'))
        assert 'un millime' in result

    def test_mixed(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('42.750'))
        assert 'quarante-deux' in result
        assert 'dinars' in result
        assert 'sept cent cinquante' in result
        assert 'millimes' in result

    def test_rounding(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('1.9999'))
        assert 'deux dinars' in result

    def test_large_number(self):
        from sales.utilities import num2words_tnd_fr
        result = num2words_tnd_fr(Decimal('999999.999'))
        assert 'neuf cent quatre-vingt-dix-neuf mille' in result
