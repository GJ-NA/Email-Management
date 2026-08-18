import importlib
import os
import tempfile
import unittest
from unittest.mock import patch


os.environ.setdefault('SECRET_KEY', 'test-secret-key')
if 'DATABASE_PATH' not in os.environ:
    _temp_dir = tempfile.mkdtemp(prefix='Email-Management-authorization-channel-tests-')
    os.environ['DATABASE_PATH'] = os.path.join(_temp_dir, 'test.db')

email_management = importlib.import_module('email_management')


class FakeTokenResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)
        self.reason = 'OK' if status_code == 200 else 'Bad Request'

    def json(self):
        return self._payload


class AuthorizationChannelTests(unittest.TestCase):
    def setUp(self):
        self.app = email_management.app
        self.app.config['TESTING'] = True
        with self.app.app_context():
            email_management.init_db()
            db = email_management.get_db()
            db.execute('DELETE FROM account_aliases')
            db.execute('DELETE FROM account_tags')
            db.execute('DELETE FROM accounts')
            db.commit()

    def _add_account(self, email='channel@example.com'):
        with self.app.app_context():
            added = email_management.add_account(
                email,
                'password',
                'client-id',
                'refresh-token',
                group_id=1,
                account_type='outlook',
                provider='outlook',
            )
            self.assertTrue(added)
            return email_management.get_account_by_email(email)

    def test_refresh_token_keeps_three_value_compatibility_and_reports_channel_on_request(self):
        with patch.object(
            email_management,
            'request_graph_token_response',
            return_value=FakeTokenResponse(400, {'error_description': 'graph denied'}),
        ) as graph_mock, patch.object(
            email_management,
            'request_imap_token_response',
            return_value=FakeTokenResponse(200, {'refresh_token': 'rotated-imap'}),
        ) as imap_mock:
            legacy_result = email_management.test_refresh_token('client', 'token')
            detailed_result = email_management.test_refresh_token(
                'client',
                'token',
                authorizationtype='graph',
                return_channel=True,
            )

        self.assertEqual(legacy_result, (True, None, 'rotated-imap'))
        self.assertEqual(detailed_result, (True, None, 'rotated-imap', 'imap'))
        self.assertEqual(graph_mock.call_count, 2)
        self.assertEqual(imap_mock.call_count, 2)

    def test_token_refresh_persists_actual_successful_channel(self):
        account = self._add_account()
        with self.app.app_context():
            db = email_management.get_db()
            row = db.execute('SELECT * FROM accounts WHERE id = ?', (account['id'],)).fetchone()
            with patch.object(
                email_management,
                'test_refresh_token',
                return_value=(True, None, '', 'imap'),
            ):
                result = email_management.refresh_outlook_account_token(row, db_conn=db)

            stored = db.execute(
                'SELECT authorizationtype FROM accounts WHERE id = ?',
                (account['id'],),
            ).fetchone()

        self.assertTrue(result['success'])
        self.assertEqual(result['authorizationtype'], 'imap')
        self.assertEqual(stored['authorizationtype'], 'imap')

    def test_mail_list_uses_remembered_imap_and_remembers_graph_after_fallback(self):
        account = self._add_account()
        with self.app.app_context():
            db = email_management.get_db()
            db.execute(
                "UPDATE accounts SET authorizationtype = 'imap' WHERE id = ?",
                (account['id'],),
            )
            db.commit()
            account = email_management.get_account_by_id(account['id'])

            with patch.object(
                email_management,
                'get_emails_imap_with_server',
                return_value={'success': True, 'emails': [], 'has_more': False},
            ) as imap_mock, patch.object(email_management, 'get_emails_graph') as graph_mock:
                result = email_management.fetch_account_folder_emails(account, 'inbox', 0, 20)

            self.assertTrue(result['success'])
            self.assertEqual(result['request_method'], 'imap')
            graph_mock.assert_not_called()
            self.assertEqual(imap_mock.call_count, 1)

            with patch.object(
                email_management,
                'get_emails_imap_with_server',
                return_value={'success': False, 'error': 'imap failed'},
            ), patch.object(
                email_management,
                'get_emails_graph',
                return_value={'success': True, 'emails': [], 'has_more': False},
            ) as graph_mock:
                result = email_management.fetch_account_folder_emails(account, 'inbox', 0, 20)

            stored = db.execute(
                'SELECT authorizationtype FROM accounts WHERE id = ?',
                (account['id'],),
            ).fetchone()

        self.assertTrue(result['success'])
        self.assertEqual(result['request_method'], 'graph')
        graph_mock.assert_called_once()
        self.assertEqual(stored['authorizationtype'], 'graph')

    def test_detail_without_explicit_method_uses_remembered_channel(self):
        account = self._add_account('detail-channel@example.com')
        with self.app.app_context():
            db = email_management.get_db()
            db.execute(
                "UPDATE accounts SET authorizationtype = 'imap' WHERE id = ?",
                (account['id'],),
            )
            db.commit()
            account = email_management.get_account_by_id(account['id'])

            imap_detail = {
                'success': True,
                'email': {'id': 'msg-1', 'subject': 'IMAP detail'},
            }
            with patch.object(
                email_management,
                'get_email_detail_imap_result',
                return_value=imap_detail,
            ) as imap_mock, patch.object(email_management, 'get_email_detail_graph_result') as graph_mock:
                result = email_management.fetch_email_detail_for_account(
                    account,
                    'msg-1',
                    method='',
                    folder='inbox',
                )

        self.assertTrue(result['success'])
        self.assertEqual(result['email']['subject'], 'IMAP detail')
        imap_mock.assert_called_once()
        graph_mock.assert_not_called()

    def test_batch_verify_preserves_successful_channel_for_later_requests(self):
        account = {
            'id': 9,
            'email': 'verify-channel@example.com',
            'password': '',
            'client_id': 'client-id',
            'refresh_token': 'encrypted-token',
            'authorizationtype': 'imap',
            'account_type': 'outlook',
            'provider': 'outlook',
            'proxy_url': '',
            'fallback_proxy_url_1': '',
            'fallback_proxy_url_2': '',
        }
        with patch.object(email_management, 'decrypt_data', return_value='plain-token'), \
             patch.object(
                 email_management,
                 'test_refresh_token',
                 return_value=(True, None, '', 'imap'),
             ) as token_mock, patch.object(
                 email_management,
                 'get_emails_graph',
                 return_value={'success': False, 'error': 'graph unavailable'},
             ), patch.object(
                 email_management,
                 'get_emails_imap',
                 return_value={'success': True, 'emails': []},
             ):
            result = email_management.verify_one_account(account, probe_imap=True)

        self.assertEqual(result['verify_status'], 'imap_ok')
        self.assertEqual(result['authorizationtype'], 'imap')
        self.assertEqual(token_mock.call_args.kwargs['authorizationtype'], 'imap')
        self.assertTrue(token_mock.call_args.kwargs['return_channel'])


if __name__ == '__main__':
    unittest.main()
