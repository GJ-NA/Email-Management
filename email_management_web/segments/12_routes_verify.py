"""Batch mailbox verification inspired by outlook-mail-helper.

The verifier runs outside the request thread and only writes status fields from
the main worker thread. It deliberately reuses the existing Graph/IMAP helpers
and account encryption instead of introducing a second credential database.
"""

from __future__ import annotations

# The segmented app intentionally resolves these names from shared globals.
# Keep Ruff focused on issues that are meaningful for this execution model.
# ruff: noqa: F405

import os
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    # Segments are executed in the shared email_management globals at runtime.
    # This import keeps IDE and Ruff checks aware of those shared names.
    from email_management import *  # noqa: F403


verify_tasks: Dict[str, Dict[str, Any]] = {}
verify_tasks_lock = threading.Lock()
verify_schema_lock = threading.Lock()
VERIFY_TASK_TTL_SECONDS = 3600
VERIFY_MAX_ACCOUNTS = 5000
VERIFY_CONCURRENCY_DEFAULT = 8
VERIFY_CONCURRENCY_MAX = 16


def ensure_verify_columns() -> None:
    # init_db() normally performs this migration. Keep this defensive check for
    # older databases, but serialize it so concurrent requests cannot race on
    # PRAGMA table_info followed by ALTER TABLE.
    with verify_schema_lock:
        conn = sqlite3.connect(DATABASE, timeout=30)
        conn.execute('PRAGMA busy_timeout = 30000')
        try:
            columns = {row[1] for row in conn.execute('PRAGMA table_info(accounts)').fetchall()}
            additions = {
                'last_verify_at': 'TEXT',
                'verify_status': "TEXT DEFAULT 'unknown'",
                'verify_imap_status': "TEXT DEFAULT 'not_run'",
                'verify_error': 'TEXT',
                'verify_latency_ms': 'INTEGER',
            }
            for name, definition in additions.items():
                if name in columns:
                    continue
                try:
                    conn.execute(f'ALTER TABLE accounts ADD COLUMN {name} {definition}')
                except sqlite3.OperationalError as exc:
                    # A second process may have completed the same migration
                    # after the PRAGMA check. Treat only that race as benign.
                    if 'duplicate column name' not in str(exc).lower():
                        raise
            conn.commit()
        finally:
            conn.close()


def get_verify_max_workers() -> int:
    """Return a bounded worker count even when the environment is malformed."""
    raw_value = os.getenv('VERIFY_CONCURRENCY', str(VERIFY_CONCURRENCY_DEFAULT))
    try:
        configured = int(str(raw_value).strip())
    except (TypeError, ValueError):
        configured = VERIFY_CONCURRENCY_DEFAULT
    return max(1, min(VERIFY_CONCURRENCY_MAX, configured))


def prune_verify_tasks() -> None:
    cutoff = time.time() - VERIFY_TASK_TTL_SECONDS
    for task_id in list(verify_tasks):
        task = verify_tasks[task_id]
        if task.get('updated_at', 0) < cutoff:
            verify_tasks.pop(task_id, None)


def finalize_verify_result(result: Dict[str, Any], started: float) -> Dict[str, Any]:
    result['latency_ms'] = int((time.perf_counter() - started) * 1000)
    return result


def load_verify_accounts(account_ids: List[int]) -> List[Dict[str, Any]]:
    if not account_ids:
        return []
    placeholders = ','.join('?' for _ in account_ids)
    conn = sqlite3.connect(DATABASE, timeout=30)
    conn.execute('PRAGMA busy_timeout = 30000')
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f'''
            SELECT id, email, password, client_id, refresh_token,
                   account_type, provider, proxy_url,
                   fallback_proxy_url_1, fallback_proxy_url_2,
                   imap_host, imap_port, imap_password, authorizationtype
            FROM accounts
            WHERE id IN ({placeholders})
            ''',
            tuple(account_ids),
        ).fetchall()
        order = {account_id: index for index, account_id in enumerate(account_ids)}
        return sorted((dict(row) for row in rows), key=lambda row: order.get(row['id'], 999999))
    finally:
        conn.close()


def verify_one_account(account: Dict[str, Any], probe_imap: bool) -> Dict[str, Any]:
    started = time.perf_counter()
    account_id = int(account['id'])
    email = str(account.get('email') or '')
    client_id = str(account.get('client_id') or '').strip()
    encrypted_refresh_token = str(account.get('refresh_token') or '')

    result: Dict[str, Any] = {
        'id': account_id,
        'email': email,
        'verify_status': 'invalid',
        'verify_imap_status': 'not_run',
        'error': '',
        'rotated_refresh_token': '',
        'authorizationtype': normalize_account_authorization_type(account.get('authorizationtype')),
    }

    proxy_url = str(account.get('proxy_url') or '').strip()
    fallback_proxy_urls = [
        str(account.get('fallback_proxy_url_1') or '').strip(),
        str(account.get('fallback_proxy_url_2') or '').strip(),
    ]

    account_type = normalize_mail_account_type(
        account.get('account_type'), account.get('provider', ''), account.get('email', '')
    )
    if account_type in {'imap', 'pop3'}:
        # 普通 IMAP/POP3 账号没有 OAuth 字段；兼容旧数据中把密码保存在
        # password 列的记录，避免在 OAuth 字段检查处被提前判为失效。
        imap_password_value = str(
            account.get('imap_password') or account.get('password') or ''
        )
        try:
            imap_password_value = decrypt_data(imap_password_value) if imap_password_value else ''
        except Exception as exc:
            result['verify_status'] = 'pop3_password_failed' if account_type == 'pop3' else 'imap_password_failed'
            result['verify_imap_status'] = 'failed'
            protocol_label = 'POP3 授权码' if account_type == 'pop3' else 'IMAP 密码'
            result['error'] = sanitize_error_details(f'解密{protocol_label}失败: {exc}')
            return finalize_verify_result(result, started)

        if not imap_password_value or not account.get('imap_host'):
            result['verify_status'] = 'invalid'
            result['verify_imap_status'] = 'not_run'
            protocol_label = 'POP3 授权码' if account_type == 'pop3' else 'IMAP 密码'
            result['error'] = f'缺少{protocol_label}或服务器地址'
            return finalize_verify_result(result, started)

        if account_type == 'pop3':
            imap_result = get_emails_pop3(
                email,
                imap_password_value,
                str(account.get('imap_host') or ''),
                int(account.get('imap_port') or 995),
                folder='inbox',
                provider=str(account.get('provider') or '163'),
                skip=0,
                top=1,
                proxy_url=proxy_url,
            )
        else:
            imap_result = get_emails_imap_generic(
                email,
                imap_password_value,
                str(account.get('imap_host') or ''),
                int(account.get('imap_port') or 993),
                folder='inbox',
                provider=str(account.get('provider') or 'custom'),
                skip=0,
                top=1,
                proxy_url=proxy_url,
            )
        if imap_result.get('success'):
            result['verify_status'] = 'pop3_password_ok' if account_type == 'pop3' else 'imap_password_ok'
            result['verify_imap_status'] = 'ok'
        else:
            result['verify_status'] = 'pop3_password_failed' if account_type == 'pop3' else 'imap_password_failed'
            result['verify_imap_status'] = 'failed'
            fallback_message = 'POP3 验证失败' if account_type == 'pop3' else 'IMAP 验证失败'
            result['error'] = sanitize_error_details(str(imap_result.get('error') or fallback_message))
        return finalize_verify_result(result, started)

    if not client_id or not encrypted_refresh_token:
        result['error'] = '缺少 client_id 或 refresh_token'
        return finalize_verify_result(result, started)

    try:
        refresh_token = decrypt_data(encrypted_refresh_token)
    except Exception as exc:
        result['error'] = sanitize_error_details(f'解密 refresh_token 失败: {exc}')
        return finalize_verify_result(result, started)

    validation_result = test_refresh_token(
        client_id,
        refresh_token,
        proxy_url,
        fallback_proxy_urls,
        authorizationtype=account.get('authorizationtype', ''),
        return_channel=True,
    )
    if isinstance(validation_result, (tuple, list)) and len(validation_result) >= 3:
        success, error_message, rotated = validation_result[:3]
        successful_channel = (
            normalize_account_authorization_type(validation_result[3])
            if len(validation_result) >= 4 else ''
        )
    else:
        success, error_message, rotated, successful_channel = (
            False,
            'Token 验证返回格式无效',
            '',
            '',
        )
    if not success:
        result['verify_status'] = 'oauth_failed'
        result['error'] = sanitize_error_details(error_message or 'OAuth 验证失败')
        return finalize_verify_result(result, started)

    result['verify_status'] = 'oauth_ok'
    result['rotated_refresh_token'] = rotated or ''
    result['authorizationtype'] = successful_channel or get_account_authorization_channel_order(account)[0]

    if probe_imap:
        # Graph 可收件时已经足以判定账号有效；Graph 失败时再回退到 OAuth-IMAP。
        graph_result = get_emails_graph(
            client_id,
            rotated or refresh_token,
            folder='inbox',
            skip=0,
            top=1,
            proxy_url=proxy_url,
            fallback_proxy_urls=fallback_proxy_urls,
        )
        if graph_result.get('success'):
            result['verify_status'] = 'graph_ok'
            result['authorizationtype'] = 'graph'
        else:
            imap_result = get_emails_imap(
                email,
                client_id,
                rotated or refresh_token,
                folder='inbox',
                skip=0,
                top=1,
                proxy_url=proxy_url,
                fallback_proxy_urls=fallback_proxy_urls,
            )
            if imap_result.get('success'):
                result['verify_status'] = 'imap_ok'
                result['verify_imap_status'] = 'ok'
                result['authorizationtype'] = 'imap'
            else:
                result['verify_status'] = 'receive_failed'
                result['verify_imap_status'] = 'failed'
                graph_error = sanitize_error_details(str(graph_result.get('error') or 'Graph API 收件探测失败'))
                imap_error = sanitize_error_details(str(imap_result.get('error') or 'IMAP 收件探测失败'))
                result['error'] = f'Graph API: {graph_error}; IMAP: {imap_error}'

    return finalize_verify_result(result, started)


def persist_verify_result(conn: sqlite3.Connection, result: Dict[str, Any]) -> None:
    rotated = str(result.get('rotated_refresh_token') or '').strip()
    if rotated:
        persist_rotated_refresh_token(int(result['id']), rotated, db_conn=conn)
    authorizationtype = normalize_account_authorization_type(result.get('authorizationtype'))
    if authorizationtype:
        conn.execute(
            'UPDATE accounts SET authorizationtype = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (authorizationtype, int(result['id'])),
        )
    conn.execute(
        '''
        UPDATE accounts
        SET last_verify_at = CURRENT_TIMESTAMP,
            verify_status = ?,
            verify_imap_status = ?,
            verify_error = ?,
            verify_latency_ms = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''',
        (
            result.get('verify_status') or 'invalid',
            result.get('verify_imap_status') or 'not_run',
            result.get('error') or None,
            int(result.get('latency_ms') or 0),
            int(result['id']),
        ),
    )


def run_verify_task(task_id: str, account_ids: List[int], probe_imap: bool) -> None:
    conn = None
    results: List[Dict[str, Any]] = []
    try:
        ensure_verify_columns()
        accounts = load_verify_accounts(account_ids)
        conn = sqlite3.connect(DATABASE, timeout=30)
        conn.execute('PRAGMA busy_timeout = 30000')
        max_workers = get_verify_max_workers()

        with verify_tasks_lock:
            task = verify_tasks.get(task_id)
            if not task:
                return
            task.update({'status': 'running', 'total': len(accounts), 'updated_at': time.time()})

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='account-verify') as executor:
            futures = [executor.submit(verify_one_account, account, probe_imap) for account in accounts]
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        'id': 0,
                        'email': '',
                        'verify_status': 'worker_error',
                        'verify_imap_status': 'not_run',
                        'error': sanitize_error_details(str(exc)),
                        'latency_ms': 0,
                    }
                if result.get('id'):
                    persist_verify_result(conn, result)
                    conn.commit()
                public_result = {key: value for key, value in result.items() if key != 'rotated_refresh_token'}
                results.append(public_result)
                with verify_tasks_lock:
                    task = verify_tasks.get(task_id)
                    if task:
                        task['completed'] = len(results)
                        task['results'] = list(results)
                        task['updated_at'] = time.time()

        with verify_tasks_lock:
            task = verify_tasks.get(task_id)
            if task:
                task.update({'status': 'completed', 'updated_at': time.time()})
    except Exception as exc:
        with verify_tasks_lock:
            task = verify_tasks.get(task_id)
            if task:
                task.update({'status': 'failed', 'error': sanitize_error_details(str(exc)), 'updated_at': time.time()})
    finally:
        if conn is not None:
            conn.close()


@app.route('/api/accounts/verify-selected', methods=['POST'])
@login_required
def api_verify_selected_accounts():
    try:
        ensure_verify_columns()
    except Exception as exc:
        return jsonify({
            'success': False,
            'error': f'初始化验活字段失败: {sanitize_error_details(str(exc))}',
        }), 500
    data = request.get_json(silent=True) or {}
    raw_ids = data.get('account_ids') or []
    if not isinstance(raw_ids, list):
        return jsonify({'success': False, 'error': '账号列表格式错误'}), 400

    account_ids = []
    seen = set()
    for raw_id in raw_ids:
        try:
            account_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if account_id > 0 and account_id not in seen:
            seen.add(account_id)
            account_ids.append(account_id)
    if not account_ids:
        return jsonify({'success': False, 'error': '请选择要验活的账号'}), 400
    if len(account_ids) > VERIFY_MAX_ACCOUNTS:
        return jsonify({'success': False, 'error': f'单次最多验活 {VERIFY_MAX_ACCOUNTS} 个账号'}), 400

    task_id = uuid.uuid4().hex
    probe_imap = bool(data.get('probe_imap', True))
    with verify_tasks_lock:
        prune_verify_tasks()
        verify_tasks[task_id] = {
            'task_id': task_id,
            'status': 'queued',
            'total': len(account_ids),
            'completed': 0,
            'results': [],
            'probe_imap': probe_imap,
            'created_at': time.time(),
            'updated_at': time.time(),
        }

    thread = threading.Thread(
        target=run_verify_task,
        args=(task_id, account_ids, probe_imap),
        name='account-verify-task',
        daemon=True,
    )
    thread.start()
    return jsonify({
        'success': True,
        'task_id': task_id,
        'status_url': f'/api/accounts/verify-selected/{task_id}',
        'total': len(account_ids),
    })


@app.route('/api/accounts/verify-selected/<task_id>', methods=['GET'])
@login_required
def api_verify_selected_status(task_id: str):
    with verify_tasks_lock:
        prune_verify_tasks()
        task = verify_tasks.get(task_id)
        if not task:
            return jsonify({'success': False, 'error': '验活任务不存在或已过期'}), 404
        payload = dict(task)
        payload['results'] = list(task.get('results') or [])
    payload['success'] = True
    return jsonify(payload)
