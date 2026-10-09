"""TLS policy shared by the web application and the mail diagnostic tool."""

import os
import ssl


def create_mail_ssl_context():
    """Verify the server identity, optionally using an administrator-supplied CA."""
    ca_file = (os.getenv('MAIL_TLS_CA_FILE') or '').strip() or None
    return ssl.create_default_context(cafile=ca_file)
