import os
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
if 'DATABASE_PATH' not in os.environ:
    _temp_dir = tempfile.mkdtemp(prefix='Email-Management-verify-tests-')
    os.environ['DATABASE_PATH'] = os.path.join(_temp_dir, 'test.db')

import email_management  # noqa: E402


class VerifyLogicTests(unittest.TestCase):
    def test_plain_imap_account_does_not_require_oauth_fields(self):
        account = {
            'id': 7,
            'email': 'imap@example.com',
            'password': 'legacy-password',
            'client_id': '',
            'refresh_token': '',
            'account_type': 'imap',
            'provider': 'custom',
            'imap_host': 'imap.example.com',
            'imap_port': 993,
            'imap_password': '',
        }

        with patch.object(email_management, 'decrypt_data', side_effect=lambda value: value), \
             patch.object(email_management, 'get_emails_imap_generic', return_value={'success': True}) as imap_mock, \
             patch.object(email_management, 'test_refresh_token') as refresh_mock:
            result = email_management.verify_one_account(account, probe_imap=True)

        self.assertEqual(result['verify_status'], 'imap_password_ok')
        self.assertEqual(result['verify_imap_status'], 'ok')
        self.assertEqual(result['error'], '')
        refresh_mock.assert_not_called()
        imap_mock.assert_called_once_with(
            'imap@example.com',
            'legacy-password',
            'imap.example.com',
            993,
            folder='inbox',
            provider='custom',
            skip=0,
            top=1,
            proxy_url='',
        )

    def test_163_imap_verify_falls_back_to_pop3(self):
        account = {
            'id': 8,
            'email': 'user@163.com',
            'password': '',
            'client_id': '',
            'refresh_token': '',
            'account_type': 'imap',
            'provider': '163',
            'imap_host': 'imap.163.com',
            'imap_port': 993,
            'imap_password': 'client-auth-code',
            'proxy_url': '',
            'fallback_proxy_url_1': '',
            'fallback_proxy_url_2': '',
        }

        with patch.object(email_management, 'decrypt_data', side_effect=lambda value: value), \
             patch.object(
                 email_management,
                 'get_emails_imap_generic',
                 return_value={
                     'success': False,
                     'error_code': 'IMAP_AUTH_FAILED',
                     'error': {'code': 'IMAP_AUTH_FAILED', 'message': 'IMAP authentication failed'},
                 },
             ), patch.object(
                 email_management,
                 'get_emails_pop3',
                 return_value={'success': True, 'emails': [], 'method': 'POP3'},
             ) as pop3_mock:
            result = email_management.verify_one_account(account, probe_imap=True)

        self.assertEqual(result['verify_status'], 'pop3_password_ok')
        self.assertEqual(result['verify_imap_status'], 'ok')
        self.assertEqual(result['detected_account_type'], 'pop3')
        self.assertEqual(result['detected_imap_host'], 'pop.163.com')
        self.assertEqual(result['detected_imap_port'], 995)
        pop3_mock.assert_called_once_with(
            'user@163.com',
            'client-auth-code',
            'pop.163.com',
            995,
            folder='inbox',
            provider='163',
            skip=0,
            top=1,
            proxy_url='',
        )

    def test_verify_concurrency_is_bounded_when_environment_is_invalid(self):
        with patch.dict(os.environ, {'VERIFY_CONCURRENCY': 'not-a-number'}, clear=False):
            self.assertEqual(email_management.get_verify_max_workers(), 8)
        with patch.dict(os.environ, {'VERIFY_CONCURRENCY': '99'}, clear=False):
            self.assertEqual(email_management.get_verify_max_workers(), 16)
        with patch.dict(os.environ, {'VERIFY_CONCURRENCY': '0'}, clear=False):
            self.assertEqual(email_management.get_verify_max_workers(), 1)

    def test_colors_are_reduced_to_safe_hex_values(self):
        self.assertEqual(email_management.normalize_hex_color('#A1B2C3'), '#a1b2c3')
        self.assertEqual(email_management.normalize_hex_color('#abc'), '#aabbcc')
        self.assertEqual(email_management.normalize_hex_color('rgb(1, 2, 3)'), '#1a1a1a')
        self.assertEqual(
            email_management.normalize_hex_color('url(javascript:alert(1))', '#9ca3af'),
            '#9ca3af',
        )


if __name__ == '__main__':
    unittest.main()
