import os
import sys
import tempfile


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Never let a local .env point the test suite at the user's real mailbox DB.
os.environ.setdefault('EMAIL_MANAGEMENT_SKIP_DOTENV', '1')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
if 'DATABASE_PATH' not in os.environ:
    _temp_dir = tempfile.mkdtemp(prefix='email-management-pytest-')
    os.environ['DATABASE_PATH'] = os.path.join(_temp_dir, 'test.db')
