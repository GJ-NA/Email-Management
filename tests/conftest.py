import os
import sys
import tempfile
from pathlib import Path


SMOKE_TEST_FILES = {
    "test_account_secret_reveal_frontend.py",
    "test_attachment_size_formatting.py",
    "test_error_handlers.py",
    "test_imap_server_helper_contract.py",
    "test_pop3_support.py",
    "test_refreshable_account.py",
    "test_runtime.py",
    "test_security_hardening.py",
    "test_txt_import_frontend.py",
    "test_verify_logic.py",
    "test_windows_packaging.py",
}


def pytest_addoption(parser):
    parser.addoption(
        "--full",
        action="store_true",
        default=False,
        help="collect the complete integration and regression suite",
    )


def pytest_ignore_collect(collection_path, config):
    """Keep the default run small without deleting the larger test modules."""
    if config.getoption("--full"):
        return False
    return collection_path.is_file() and collection_path.name.startswith("test_") and (
        collection_path.name not in SMOKE_TEST_FILES
    )


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Never let a local .env point the test suite at the user's real mailbox DB.
os.environ['EMAIL_MANAGEMENT_SKIP_DOTENV'] = '1'
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
_test_root = Path(ROOT_DIR) / '.test_tmp'
_test_root.mkdir(parents=True, exist_ok=True)
_temp_dir = tempfile.mkdtemp(prefix='pytest-', dir=_test_root)
os.environ['DATABASE_PATH'] = os.path.join(_temp_dir, 'test.db')
