"""Fetch pinned offline assets. Run once before launch/build on Windows x64."""
import hashlib
import io
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def download(url, digest):
    with urllib.request.urlopen(url, timeout=90) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError(f"Checksum mismatch: {url}")
    return io.BytesIO(data)


def main():
    vendor = ROOT / "ui/vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    if not (vendor / "vs/loader.js").is_file():
        data = download("https://registry.npmjs.org/monaco-editor/-/monaco-editor-0.52.2.tgz",
                        "c280cdcf0b0c13d1a2bf01af958d4387ed06d7f6c918401d00c4adcae1bc72b6")
        with tarfile.open(fileobj=data, mode="r:gz") as archive:
            for member in archive.getmembers():
                if member.isfile() and member.name.startswith("package/min/vs/"):
                    target = vendor / member.name.removeprefix("package/min/")
                    if not target.resolve().is_relative_to(vendor.resolve()):
                        raise RuntimeError("Unsafe archive path")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as stream:
                        target.write_bytes(stream.read())
            (vendor / "MONACO-LICENSE.txt").write_bytes(archive.extractfile("package/LICENSE").read())
    if sys.platform == "win32":
        runtime = ROOT / "runtime/python"
        runtime.mkdir(parents=True, exist_ok=True)
        if not (runtime / "python.exe").is_file():
            data = download("https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip",
                            "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3")
            with zipfile.ZipFile(data) as archive:
                archive.extractall(runtime)
        # The embeddable runtime intentionally omits pip; install it locally.
        # Include the current working directory for `python -m unittest`.
        (runtime / "python312._pth").write_text("python312.zip\n.\nLib/site-packages\nimport site\n", "utf-8")
        site = runtime / "Lib/site-packages"
        site.mkdir(parents=True, exist_ok=True)
        (site / "pypilot_cwd.pth").write_text("import os, sys; sys.path.insert(0, os.getcwd())\n", "utf-8")
        if not (site / "pip").is_dir():
            subprocess.run([sys.executable, "-m", "pip", "install", "--target", str(site), "pip==25.1.1"], check=True)
    print("Offline assets ready.")


if __name__ == "__main__":
    main()
