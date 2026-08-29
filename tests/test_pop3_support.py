import email
import importlib
import os
import poplib
import sys
import unittest
from email.message import EmailMessage
from unittest.mock import patch


os.environ.setdefault('EMAIL_MANAGEMENT_SKIP_DOTENV', '1')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

email_management = importlib.import_module('email_management')


class FakePop3:
    def __init__(self, messages, uidl_lines=None, uidl_supported=True,
                 auth_error=None, quit_error=None, delete_errors=None):
        self.messages = dict(messages)
        self.uidl_lines = list(uidl_lines or [])
        self.uidl_supported = uidl_supported
        self.auth_error = auth_error
        self.quit_error = quit_error
        self.delete_errors = set(delete_errors or [])
        self.user_calls = []
        self.password_calls = []
        self.uidl_calls = 0
        self.list_calls = 0
        self.retr_calls = []
        self.dele_calls = []
        self.quit_calls = 0
        self.rset_calls = 0

    def user(self, username):
        self.user_calls.append(username)
        return b'+OK user accepted'

    def pass_(self, password):
        self.password_calls.append(password)
        if self.auth_error:
            raise self.auth_error
        return b'+OK password accepted'

    def uidl(self):
        self.uidl_calls += 1
        if not self.uidl_supported:
            raise poplib.error_proto('-ERR UIDL unsupported')
        return b'+OK UIDL follows', self.uidl_lines

    def list(self):
        self.list_calls += 1
        return b'+OK LIST follows', [
            f'{number} {len(payload)}'.encode('ascii')
            for number, payload in sorted(self.messages.items())
        ]

    def retr(self, number):
        number = int(number)
        self.retr_calls.append(number)
        return b'+OK message follows', self.messages[number].splitlines()

    def dele(self, number):
        number = int(number)
        self.dele_calls.append(number)
        if number in self.delete_errors:
            return b'-ERR delete failed'
        return b'+OK message marked for deletion'

    def rset(self):
        self.rset_calls += 1
        return b'+OK reset'

    def quit(self):
        self.quit_calls += 1
        if self.quit_error:
            raise self.quit_error
        return b'+OK goodbye'


def build_message(subject='POP3 subject', body='POP3 body', attachment=False):
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = 'sender@example.com'
    message['To'] = 'user@163.com'
    message['Date'] = 'Sat, 29 Aug 2026 10:00:00 +0800'
    message.set_content(body)
    if attachment:
        message.add_attachment(
            b'attachment payload',
            maintype='text',
            subtype='plain',
            filename='note.txt',
        )
    return message.as_bytes()


class Pop3SupportTests(unittest.TestCase):
    def test_163_pop3_provider_uses_host_and_port_995(self):
        connection = email_management.get_provider_connection_meta(
            '163', 'user@163.com', 'pop3'
        )

        self.assertEqual(connection, {'host': 'pop.163.com', 'port': 995})

        values = email_management.build_account_insert_values(
            'user@163.com',
            '',
            account_type='pop3',
            provider='163',
            imap_password='client-auth-code',
        )
        self.assertEqual(values[8:12], ('pop3', '163', 'pop.163.com', 995))
        self.assertEqual(email_management.decrypt_data(values[12]), 'client-auth-code')

    def test_pop3_login_uses_email_and_client_authorization_code(self):
        mail = FakePop3({1: build_message()})

        email_management.login_pop3(mail, 'user@163.com', 'client-auth-code')

        self.assertEqual(mail.user_calls, ['user@163.com'])
        self.assertEqual(mail.password_calls, ['client-auth-code'])

    def test_pop3_list_prefers_uidl_and_returns_newest_first(self):
        mail = FakePop3(
            {
                1: build_message(subject='Older', body='older'),
                2: build_message(subject='Newer', body='newer'),
            },
            uidl_lines=[b'1 uid-old', b'2 uid-new'],
        )

        with patch.object(email_management, 'create_pop3_connection', return_value=mail) as factory:
            result = email_management.get_emails_pop3(
                'user@163.com',
                'client-auth-code',
                'pop.163.com',
                995,
                provider='163',
                top=20,
            )

        self.assertTrue(result['success'])
        self.assertEqual([item['id'] for item in result['emails']], ['uid-new', 'uid-old'])
        self.assertEqual([item['id_mode'] for item in result['emails']], ['uidl', 'uidl'])
        self.assertEqual(mail.uidl_calls, 1)
        self.assertEqual(mail.list_calls, 0)
        self.assertEqual(mail.user_calls, ['user@163.com'])
        self.assertEqual(mail.password_calls, ['client-auth-code'])
        factory.assert_called_once_with('pop.163.com', 995, '')
        self.assertEqual(mail.quit_calls, 1)

    def test_pop3_without_uidl_falls_back_to_server_message_number(self):
        mail = FakePop3({1: build_message()}, uidl_supported=False)

        with patch.object(email_management, 'create_pop3_connection', return_value=mail):
            result = email_management.get_emails_pop3(
                'user@163.com', 'client-auth-code', 'pop.163.com', 995
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['emails'][0]['id'], '1')
        self.assertEqual(result['emails'][0]['id_mode'], 'number')
        self.assertEqual(mail.list_calls, 1)

    def test_pop3_detail_and_attachment_download_use_mime_message(self):
        raw_message = build_message(attachment=True)
        detail_mail = FakePop3({1: raw_message}, uidl_lines=[b'1 uid-message'])
        attachment_mail = FakePop3({1: raw_message}, uidl_lines=[b'1 uid-message'])

        with patch.object(
            email_management,
            'create_pop3_connection',
            side_effect=[detail_mail, attachment_mail],
        ):
            detail_result = email_management.get_email_detail_pop3_result(
                'user@163.com',
                'client-auth-code',
                'pop.163.com',
                995,
                'uid-message',
                provider='163',
            )
            attachment_result = email_management.download_email_attachment_pop3_result(
                'user@163.com',
                'client-auth-code',
                'pop.163.com',
                995,
                'uid-message',
                'attachment-1',
                provider='163',
            )

        self.assertTrue(detail_result['success'])
        self.assertEqual(detail_result['method'], 'POP3')
        self.assertEqual(detail_result['email']['id'], 'uid-message')
        self.assertEqual(detail_result['email']['id_mode'], 'uidl')
        self.assertEqual(detail_result['email']['attachments'][0]['name'], 'note.txt')
        self.assertTrue(attachment_result['success'])
        self.assertEqual(attachment_result['filename'], 'note.txt')
        self.assertEqual(attachment_result['content'], b'attachment payload')
        self.assertEqual(detail_mail.quit_calls, 1)
        self.assertEqual(attachment_mail.quit_calls, 1)

    def test_pop3_delete_commits_with_quit(self):
        mail = FakePop3({1: build_message()}, uidl_lines=[b'1 uid-delete'])

        with patch.object(email_management, 'create_pop3_connection', return_value=mail):
            result = email_management.delete_emails_pop3_result(
                'user@163.com',
                'client-auth-code',
                'pop.163.com',
                [{'id': 'uid-delete', 'folder': 'inbox'}],
                995,
                '163',
            )

        self.assertTrue(result['success'])
        self.assertEqual(result['deleted_ids'], ['uid-delete'])
        self.assertEqual(mail.dele_calls, [1])
        self.assertEqual(mail.quit_calls, 1)
        self.assertEqual(mail.rset_calls, 0)

    def test_pop3_delete_reports_quit_commit_failure(self):
        mail = FakePop3(
            {1: build_message()},
            uidl_lines=[b'1 uid-delete'],
            quit_error=RuntimeError('quit failed'),
        )

        with patch.object(email_management, 'create_pop3_connection', return_value=mail):
            result = email_management.delete_emails_pop3_result(
                'user@163.com',
                'client-auth-code',
                'pop.163.com',
                [{'id': 'uid-delete', 'folder': 'inbox'}],
                995,
                '163',
            )

        self.assertFalse(result['success'])
        self.assertEqual(result['deleted_ids'], [])
        self.assertEqual(result['error']['code'], 'POP3_DELETE_COMMIT_FAILED')
        self.assertEqual(mail.dele_calls, [1])
        self.assertEqual(mail.quit_calls, 1)

    def test_pop3_authentication_failure_is_structured(self):
        mail = FakePop3(
            {1: build_message()},
            auth_error=poplib.error_proto('-ERR authentication failed'),
        )

        with patch.object(email_management, 'create_pop3_connection', return_value=mail):
            result = email_management.get_emails_pop3(
                'user@163.com',
                'wrong-code',
                'pop.163.com',
                995,
                provider='163',
            )

        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'POP3_AUTH_FAILED')
        self.assertEqual(result['error']['code'], 'POP3_AUTH_FAILED')
        self.assertIn('客户端授权码', result['error']['message'])
        self.assertEqual(mail.user_calls, ['user@163.com'])
        self.assertEqual(mail.password_calls, ['wrong-code'])

    def test_pop3_mark_read_reports_unsupported_operation(self):
        result = email_management.mark_emails_read_pop3_result([
            {'id': 'uid-message', 'folder': 'inbox'},
        ])

        self.assertFalse(result['success'])
        self.assertEqual(result['success_count'], 0)
        self.assertEqual(result['failed_count'], 1)
        self.assertEqual(result['errors'][0]['error']['code'], 'POP3_UNSUPPORTED')
        self.assertEqual(result['error']['code'], 'POP3_UNSUPPORTED')


if __name__ == '__main__':
    unittest.main()
