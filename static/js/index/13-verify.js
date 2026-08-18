/* global getSelectedAccountIds, handleApiError, refreshVisibleAccountList, setAccountBatchButtonLabel, showConfirmModal, showToast */

function setVerifyButtonLabel(button, label) {
    setAccountBatchButtonLabel(button, label);
}

async function verifySelectedAccounts() {
    const accountIds = typeof getSelectedAccountIds === 'function' ? getSelectedAccountIds() : [];
    const button = document.getElementById('batchVerifyAccountsBtn');
    if (!accountIds.length) {
        showToast('请先选择要验活的邮箱', 'error');
        return;
    }

    if (!(await showConfirmModal(
        `确定对所选 ${accountIds.length} 个邮箱执行 OAuth + Graph API 收件验活吗？Graph API 失败时会自动尝试 OAuth-IMAP。`,
        { title: '批量验活', confirmText: '开始验活', danger: false }
    ))) {
        return;
    }

    if (button) {
        button.disabled = true;
        button.dataset.loading = 'true';
        button.setAttribute('aria-busy', 'true');
        setVerifyButtonLabel(button, '验活中...');
    }

    try {
        const response = await fetch('/api/accounts/verify-selected', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_ids: accountIds, probe_imap: true }),
        });
        const created = await response.json();
        if (!created.success) {
            handleApiError(created, '批量验活失败');
            return;
        }

        let finished = false;
        for (let attempt = 0; attempt < 600; attempt += 1) {
            await new Promise(resolve => setTimeout(resolve, 700));
            const statusResponse = await fetch(created.status_url);
            const status = await statusResponse.json();
            if (!status.success) {
                handleApiError(status, '读取验活进度失败');
                return;
            }
            if (button && status.total) {
                setVerifyButtonLabel(button, `验活中 ${status.completed}/${status.total}`);
            }
            if (status.status === 'completed' || status.status === 'failed') {
                const results = Array.isArray(status.results) ? status.results : [];
                const ok = results.filter(item => [
                    'both_ok',
                    'graph_ok',
                    'imap_ok',
                    'oauth_ok',
                    'imap_password_ok',
                ].includes(item.verify_status)).length;
                const failed = results.length - ok;
                showToast(`验活完成：成功 ${ok}，失败 ${failed}`, failed ? 'warning' : 'success');
                finished = true;
                if (typeof refreshVisibleAccountList === 'function') {
                    await refreshVisibleAccountList(true);
                }
                break;
            }
        }
        if (!finished) {
            showToast('验活任务仍在后台运行，可稍后再次查看状态', 'warning');
        }
    } catch (error) {
        showToast(`批量验活请求失败：${error.message}`, 'error');
    } finally {
        if (button) {
            button.dataset.loading = 'false';
            button.disabled = false;
            button.removeAttribute('aria-busy');
            setVerifyButtonLabel(button, '批量验活');
        }
    }
}
