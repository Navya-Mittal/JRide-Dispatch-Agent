import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait(url: str, secs: float = 20.0) -> None:
    end = time.time() + secs
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"timeout waiting for {url}")


@pytest.fixture(scope="session")
def mock_decider():
    port = _free_port()
    p = subprocess.Popen([sys.executable, str(ROOT / "mock" / "mock_decider.py"), "--port", str(port)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait(f"http://127.0.0.1:{port}/health")
        yield f"127.0.0.1:{port}"
    finally:
        p.terminate()


@pytest.fixture(scope="session")
def engine_url():
    if not shutil.which("javac"):
        pytest.skip("JDK not installed")
    classes = ROOT / "engine" / "target" / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    srcs = [str(p) for p in (ROOT / "engine" / "src" / "main").rglob("*.java")]
    subprocess.run(["javac", "-d", str(classes), *srcs], check=True, capture_output=True)
    port = _free_port()
    p = subprocess.Popen(["java", "-cp", str(classes), "com.navya.dispatchengine.sim.Main", "--server",
                          "--port", str(port), "--drivers", "0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait(f"http://127.0.0.1:{port}/health")
        yield f"http://127.0.0.1:{port}"
    finally:
        p.terminate()
