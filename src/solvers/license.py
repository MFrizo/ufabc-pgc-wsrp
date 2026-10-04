"""
Module: license
Description: Provisions the Gurobi Web License Service (WLS) credentials on hosts
             without a local gurobi.lic (e.g., Google Colab), so gurobipy runs under
             the full academic license instead of the size-limited pip license.
"""

import os
from pathlib import Path
from typing import Optional

from src.utils.logger import project_logger


WLS_KEYS = ('WLSACCESSID', 'WLSSECRET', 'LICENSEID')


def _read_colab_secrets() -> dict[str, str]:
    """
    Reads the WLS credentials stored in the Colab Secrets panel.

    Returns:
        dict[str, str]: The credentials found, empty outside Colab.
    """
    try:
        from google.colab import userdata
    except ImportError:
        return {}

    credentials = {}
    for key in WLS_KEYS:
        try:
            credentials[key] = userdata.get(key)
        except (userdata.SecretNotFoundError, userdata.NotebookAccessError):
            continue
    return credentials


def configure_wls_license(license_path: Path = Path.home() / 'gurobi.lic') -> Optional[Path]:
    """
    Writes a gurobi.lic from the WLS credentials and points GRB_LICENSE_FILE to it.

    Credentials come from environment variables first, then from Colab Secrets.
    Gurobi reads the license once, when its default environment starts, so this
    must run before the first solve of the Python process.

    Args:
        license_path (Path): Where the license file is written. Keep it outside
            the repository, since it holds the WLS secret.

    Returns:
        Optional[Path]: The license file written, or None when no credential was
            found and Gurobi is left to its own license lookup.
    """
    credentials = {key: os.environ[key] for key in WLS_KEYS if os.environ.get(key)}
    for key, value in _read_colab_secrets().items():
        credentials.setdefault(key, value)

    if not credentials:
        project_logger.warning(
            "No Gurobi WLS credentials found. Gurobi falls back to its default license "
            "lookup, which on Colab is the size-limited pip license."
        )
        return None

    missing_keys = [key for key in WLS_KEYS if key not in credentials]
    if missing_keys:
        raise ValueError(f"Incomplete Gurobi WLS credentials, missing: {', '.join(missing_keys)}")

    license_path.write_text(''.join(f"{key}={credentials[key]}\n" for key in WLS_KEYS))
    license_path.chmod(0o600)
    os.environ['GRB_LICENSE_FILE'] = str(license_path)

    project_logger.info(f"Gurobi WLS license {credentials['LICENSEID']} written to {license_path}")
    return license_path
