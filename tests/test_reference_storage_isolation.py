import subprocess
import sys
from pathlib import Path

import pytest
from contracting.storage.driver import Driver

ROOT = Path(__file__).resolve().parents[1]
STANDARDS = sorted(path.parent.parent.name for path in ROOT.glob("XSC*/tests/test.py"))

# This process starts with a disposable stand-in for host storage, before any
# client or driver import. Even a missing/broken conftest cannot reach the host.
REFERENCE_RUNNER = """
import inspect
import sys
from pathlib import Path

import pytest
from contracting import constants

fallback = Path(sys.argv[1])
constants.STORAGE_HOME = fallback

class StorageProbe:
    def pytest_sessionstart(self, session):
        from contracting.local import ContractingClient

        self.storage = constants.STORAGE_HOME
        assert session.config.rootpath == Path(sys.argv[2]), "repository root not selected"
        assert self.storage != fallback, "root conftest did not isolate storage"
        assert self.storage.is_dir()
        default = inspect.signature(ContractingClient).parameters["storage_home"].default
        assert default == self.storage, "client cached a different storage default"
        with ContractingClient() as client:
            assert client.raw_driver.storage_home == self.storage
            client.flush()
        print("ISOLATED_REFERENCE_STORAGE", self.storage)

probe = StorageProbe()
result = pytest.main(["-q", "tests/test.py", "-p", "no:cacheprovider"], plugins=[probe])
if result == 0:
    assert not probe.storage.exists(), "session storage was not cleaned up"
raise SystemExit(result)
"""


@pytest.mark.parametrize("standard", STANDARDS)
def test_reference_suite_from_standard_directory_preserves_host_storage(standard, tmp_path):
    host_storage = tmp_path / "host-node-state"
    with Driver(storage_home=host_storage) as driver:
        driver.set("host-sentinel", "must survive reference tests")
        driver.commit()

    result = subprocess.run(
        [sys.executable, "-c", REFERENCE_RUNNER, str(host_storage), str(ROOT)],
        cwd=ROOT / standard,
        capture_output=True,
        text=True,
        timeout=120,
    )

    with Driver(storage_home=host_storage) as driver:
        assert driver.get("host-sentinel") == "must survive reference tests"
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ISOLATED_REFERENCE_STORAGE" in result.stdout
    print(result.stdout)
