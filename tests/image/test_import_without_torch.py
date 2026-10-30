import subprocess
import sys

import pytest

pytestmark = pytest.mark.unit


def test_value_package_does_not_import_torch():
    code = "import sys, haybale_image.value; assert 'torch' not in sys.modules"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0
