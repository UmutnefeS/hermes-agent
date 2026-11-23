import unittest
from unittest.mock import patch
from gateway import relay_model_rewrite as model

class RetryTests(unittest.TestCase):
    def test_timeout_retries_once(self):
        with patch.dict(model.os.environ, {'MILIONSEEK_API_KEY':'test'}), patch.object(model,'_attempt',side_effect=[(None,True),('Saat kaç?',False)]) as p:
            self.assertEqual(model._rewrite('saati sor'), 'Saat kaç?')
            self.assertEqual(p.call_count,2)
    def test_hard_validation_no_retry(self):
        with patch.dict(model.os.environ, {'MILIONSEEK_API_KEY':'test'}), patch.object(model,'_attempt',return_value=(None,False)) as p:
            self.assertIsNone(model._rewrite('saati sor'))
            self.assertEqual(p.call_count,1)
    def test_never_more_than_two(self):
        with patch.dict(model.os.environ, {'MILIONSEEK_API_KEY':'test'}), patch.object(model,'_attempt',return_value=(None,True)) as p:
            self.assertIsNone(model._rewrite('saati sor'))
            self.assertEqual(p.call_count,2)

if __name__=='__main__':unittest.main()
