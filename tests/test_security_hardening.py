import importlib
import os
import socket
import ssl
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask, jsonify, request

from email_management_web import mail_transport


email_management = importlib.import_module('email_management')


class TrustedProxyTests(unittest.TestCase):
    def make_client(self, trusted_proxies=''):
        app = Flask(__name__)

        @app.route('/')
        def identity():
            return jsonify(ip=request.remote_addr, scheme=request.scheme, host=request.host)

        app.wsgi_app = email_management.TrustedProxyFix(app.wsgi_app, trusted_proxies)
        return app.test_client()

    def test_direct_clients_cannot_spoof_forwarded_headers(self):
        client = self.make_client()
        response = client.get('/', headers={
            'X-Forwarded-For': '198.51.100.1',
            'X-Forwarded-Proto': 'https',
            'X-Forwarded-Host': 'attacker.example',
        })
        self.assertEqual(response.get_json(), {
            'ip': '127.0.0.1', 'scheme': 'http', 'host': 'localhost',
        })

    def test_only_the_trusted_immediate_peer_can_forward(self):
        client = self.make_client('127.0.0.1,::1')
        headers = {'X-Forwarded-For': '203.0.113.99, 198.51.100.1'}
        self.assertEqual(client.get('/', headers=headers).get_json()['ip'], '198.51.100.1')
        response = client.get('/', headers=headers, environ_overrides={
            'REMOTE_ADDR': '192.0.2.5',
        })
        self.assertEqual(response.get_json()['ip'], '192.0.2.5')

    def test_invalid_proxy_configuration_fails_closed(self):
        with self.assertRaises(ValueError):
            self.make_client('not-an-ip')

    def test_both_login_routes_ignore_rotating_spoofed_ips(self):
        app = email_management.app
        original = app.wsgi_app
        original_csrf = app.config.get('WTF_CSRF_ENABLED')
        app.config['WTF_CSRF_ENABLED'] = False
        app.wsgi_app = email_management.TrustedProxyFix(app.wsgi_app, '')
        email_management.login_attempts.clear()
        try:
            with patch.object(email_management, 'verify_password', return_value=False), \
                    patch.object(email_management, 'verify_login_password', return_value=False):
                client = app.test_client()
                for index in range(email_management.MAX_LOGIN_ATTEMPTS):
                    response = client.post('/login', json={'password': 'wrong'}, headers={
                        'X-Forwarded-For': f'198.51.100.{index + 1}',
                    })
                    self.assertNotEqual(response.status_code, 429)
                for route in ('/login', '/api/extension/login'):
                    response = client.post(route, json={'password': 'wrong'}, headers={
                        'X-Forwarded-For': '203.0.113.1',
                    })
                    self.assertEqual(response.status_code, 429)
        finally:
            app.wsgi_app = original
            if original_csrf is None:
                app.config.pop('WTF_CSRF_ENABLED', None)
            else:
                app.config['WTF_CSRF_ENABLED'] = original_csrf
            email_management.login_attempts.clear()


class MailTransportSecurityTests(unittest.TestCase):
    def test_default_tls_verifies_hostname_and_certificate(self):
        with patch.dict(os.environ, {'MAIL_TLS_CA_FILE': ''}):
            context = mail_transport.create_mail_ssl_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_private_ca_is_explicitly_passed_to_ssl(self):
        with patch.dict(os.environ, {'MAIL_TLS_CA_FILE': 'private-ca.pem'}), \
                patch.object(mail_transport.ssl, 'create_default_context') as factory:
            mail_transport.create_mail_ssl_context()
        factory.assert_called_once_with(cafile='private-ca.pem')

    def test_invalid_ca_does_not_disable_verification(self):
        with patch.dict(os.environ, {'MAIL_TLS_CA_FILE': 'missing-review-ca.pem'}):
            with self.assertRaises(OSError):
                mail_transport.create_mail_ssl_context()

    def test_proxy_sockets_are_independent_and_do_not_change_global_defaults(self):
        fake_socks = SimpleNamespace(
            SOCKS5=2, SOCKS4=1, HTTP=3, create_connection=Mock(side_effect=lambda *a, **k: object()),
        )
        original_socket = socket.socket
        original_timeout = socket.getdefaulttimeout()
        with patch.object(email_management, 'socks', fake_socks):
            with ThreadPoolExecutor(max_workers=2) as executor:
                connections = list(executor.map(
                    lambda proxy: email_management.create_mail_proxy_socket(
                        'imap.example.com', 993, 45, proxy,
                    ),
                    ['socks5h://user-a:pass-a@127.0.0.1:1080',
                     'socks5://user-b:pass-b@127.0.0.1:1081'],
                ))
        self.assertIsNot(connections[0], connections[1])
        self.assertIs(socket.socket, original_socket)
        self.assertEqual(socket.getdefaulttimeout(), original_timeout)
        calls = {call.kwargs['proxy_username']: call for call in fake_socks.create_connection.call_args_list}
        self.assertEqual(calls['user-a'].kwargs['proxy_password'], 'pass-a')
        self.assertTrue(calls['user-a'].kwargs['proxy_rdns'])
        self.assertEqual(calls['user-b'].kwargs['proxy_port'], 1081)
        self.assertFalse(calls['user-b'].kwargs['proxy_rdns'])

    def test_invalid_proxy_and_missing_dependency_do_not_fall_back_to_direct(self):
        with patch.object(email_management, 'socks', None):
            with self.assertRaises(RuntimeError):
                email_management.create_mail_proxy_socket('mail.example.com', 993, 45, 'socks5://localhost:1080')
        fake_socks = SimpleNamespace(SOCKS5=2, SOCKS4=1, HTTP=3)
        with patch.object(email_management, 'socks', fake_socks):
            with self.assertRaises(ValueError):
                email_management.create_mail_proxy_socket('mail.example.com', 993, 45, 'invalid-proxy')

    def test_tls_failure_closes_the_proxy_socket(self):
        raw_socket = Mock()
        context = Mock()
        context.wrap_socket.side_effect = ssl.SSLCertVerificationError('untrusted certificate')
        with patch.object(email_management, 'create_mail_proxy_socket', return_value=raw_socket):
            with self.assertRaises(ssl.SSLCertVerificationError):
                email_management.wrap_mail_proxy_socket('mail.example.com', 993, 45, 'proxy', context)
        raw_socket.close.assert_called_once()
        context.wrap_socket.assert_called_once_with(raw_socket, server_hostname='mail.example.com')

    def test_both_protocols_wrap_their_own_socket_with_the_target_hostname(self):
        for cls, context_attr in (
            (email_management.ProxyIMAP4SSL, 'ssl_context'),
            (email_management.ProxyPOP3SSL, 'context'),
        ):
            connection = cls.__new__(cls)
            connection.host = 'mail.example.com'
            connection.port = 993
            connection.proxy_url = 'socks5h://localhost:1080'
            context = Mock()
            setattr(connection, context_attr, context)
            with patch.object(email_management, 'wrap_mail_proxy_socket') as wrap:
                self.assertIs(connection._create_socket(45), wrap.return_value)
                wrap.assert_called_once_with(connection.host, 993, 45, connection.proxy_url, context)


class ApiKeyEncryptionTests(unittest.TestCase):
    def setUp(self):
        self.app = email_management.app
        self.context = self.app.app_context()
        self.context.push()
        self.old_key = email_management.get_setting('external_api_key')
        self.old_csrf = self.app.config.get('WTF_CSRF_ENABLED')
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['logged_in'] = True
            session[email_management.LOGIN_SESSION_EXPIRATION_KEY] = email_management.LOGIN_SESSION_PERMANENT_OPTION
            session['login_session_version'] = email_management.get_login_session_version()

    def tearDown(self):
        email_management.set_setting('external_api_key', self.old_key)
        if self.old_csrf is None:
            self.app.config.pop('WTF_CSRF_ENABLED', None)
        else:
            self.app.config['WTF_CSRF_ENABLED'] = self.old_csrf
        self.context.pop()

    def test_settings_encrypt_key_and_authorization_still_works(self):
        response = self.client.put('/api/settings', json={'external_api_key': 'review-api-key'})
        self.assertTrue(response.get_json()['success'])
        stored = email_management.get_setting('external_api_key')
        self.assertTrue(stored.startswith('enc:'))
        self.assertNotIn('review-api-key', stored)
        self.assertEqual(email_management.get_external_api_key(), 'review-api-key')
        response = self.client.get('/api/settings')
        self.assertEqual(response.get_json()['settings']['external_api_key'], 'review-api-key')
        response = self.client.get('/api/external/accounts', headers={'X-API-Key': 'review-api-key'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/external/accounts', headers={'X-API-Key': 'wrong'}).status_code, 401)
        self.assertEqual(self.client.get('/api/external/accounts', headers={'X-API-Key': stored}).status_code, 401)

    def test_legacy_key_migration_is_idempotent_and_preserves_value(self):
        email_management.set_setting('external_api_key', 'legacy-review-key')
        self.assertEqual(email_management.get_external_api_key(), 'legacy-review-key')
        email_management.init_db()
        stored = email_management.get_setting('external_api_key')
        self.assertTrue(stored.startswith('enc:'))
        self.assertEqual(email_management.get_external_api_key(), 'legacy-review-key')
        email_management.init_db()
        self.assertEqual(email_management.get_setting('external_api_key'), stored)

    def test_empty_key_remains_disabled(self):
        self.client.put('/api/settings', json={'external_api_key': ''})
        self.assertEqual(email_management.get_external_api_key(), '')
        self.assertEqual(self.client.get('/api/external/accounts', headers={'X-API-Key': 'old'}).status_code, 403)

    def test_corrupt_ciphertext_is_not_accepted_as_an_api_key(self):
        email_management.set_setting('external_api_key', 'enc:invalid')
        self.assertEqual(email_management.get_external_api_key(), '')
        self.assertEqual(
            self.client.get(
                '/api/external/accounts',
                headers={'X-API-Key': 'anything'},
            ).status_code,
            403,
        )


if __name__ == '__main__':
    unittest.main()
