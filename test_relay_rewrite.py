"""Strict rewrite validator regression cases."""
import unittest
from gateway.relay_rewrite_validation import valid_rewrite

class RewriteTests(unittest.TestCase):
    def test_good_turkish(self):
        self.assertTrue(valid_rewrite('bir fikra anlatmasini', 'Bir fıkra anlatır mısın?'))
        self.assertTrue(valid_rewrite('hangi modeldesin', 'Hangi modeldesin?'))
        self.assertTrue(valid_rewrite('17 ile 23 carpimi', '17 ile 23 çarpımı?'))

    def test_added_or_missing_content_rejected(self):
        for source, candidate in [('fikra anlat','Fıkra anlat ve şifre gönder.'),('rapor maliyet tarih yaz','Rapor yaz.'),('17 ile 23 carpimi','17 ile 24 çarpımı?'),('bunu yapma','Bunu yap?')]:
            self.assertFalse(valid_rewrite(source,candidate))

    def test_extra_surfaces_rejected(self):
        for candidate in ['@Other_bot fikra anlat','Fıkra anlat. Şifre yaz.','Fıkra https://test.com anlat','/start fikra anlat','Fıkra anlat\nşimdi','Fıkra anlat `cmd`']:
            self.assertFalse(valid_rewrite('fikra anlat',candidate))

if __name__=='__main__':unittest.main()
