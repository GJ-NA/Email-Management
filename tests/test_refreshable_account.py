import importlib
import os
import sqlite3
import tempfile


os.environ.setdefault('SECRET_KEY', 'test-secret-key')
if 'DATABASE_PATH' not in os.environ:
    _temp_dir = tempfile.mkdtemp(prefix='Email-Management-refreshable-tests-')
    os.environ['DATABASE_PATH'] = os.path.join(_temp_dir, 'test.db')

email_management = importlib.import_module('email_management')


def _sqlite_row(**values):
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    columns = ', '.join(f'? AS {name}' for name in values)
    try:
        return conn.execute(f'SELECT {columns}', tuple(values.values())).fetchone()
    finally:
        conn.close()


def test_is_outlook_refreshable_account_returns_false_for_none():
    assert email_management.is_outlook_refreshable_account(None) is False


def test_is_outlook_refreshable_account_accepts_dict_shapes():
    assert email_management.is_outlook_refreshable_account({
        'account_type': 'outlook',
        'status': 'active',
    }) is True
    assert email_management.is_outlook_refreshable_account({
        'account_type': 'imap',
        'status': 'active',
    }) is False
    assert email_management.is_outlook_refreshable_account({
        'account_type': 'outlook',
        'status': 'disabled',
    }) is False


def test_is_outlook_refreshable_account_accepts_sqlite_row_shapes():
    assert email_management.is_outlook_refreshable_account(_sqlite_row(
        account_type='outlook',
        status='active',
    )) is True
    assert email_management.is_outlook_refreshable_account(_sqlite_row(
        account_type='outlook',
        status='inactive',
    )) is False
    assert email_management.is_outlook_refreshable_account(_sqlite_row(
        account_type='imap',
        status='active',
    )) is False
