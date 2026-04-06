from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import venv
from pathlib import Path


PACKAGE_NAME = "codex-switch-cli"
FORMULA_NAME = "codex-switch-cli"
CLASS_NAME = "CodexSwitchCli"
HOMEPAGE = "https://github.com/ForeverHYX/codex-switch"
DESCRIPTION = "Transparent account-aware wrapper for the Codex CLI"
PYTHON_FORMULA = "python@3.13"
TEST_COMMAND = "#{bin}/codex-switch --help"
TEST_ASSERT = "Codex Switch CLI"
SKIP_PACKAGES = {"pip", "setuptools", "wheel", PACKAGE_NAME.replace("-", "_"), PACKAGE_NAME}


def _json_from_url(url: str) -> dict:
    try:
        with urllib.request.urlopen(url) as response:
            return json.load(response)
    except Exception:
        completed = subprocess.run(
            ["curl", "-sL", url],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)


def _release_file(package_name: str, version: str) -> tuple[str, str]:
    data = _json_from_url(f"https://pypi.org/pypi/{package_name}/json")
    files = data["releases"].get(version)
    if not files:
        raise RuntimeError(f"No release files found for {package_name}=={version}")

    sdist = next((item for item in files if item["packagetype"] == "sdist"), None)
    if sdist is not None:
        return sdist["url"], sdist["digests"]["sha256"]

    wheel = next((item for item in files if item["packagetype"] == "bdist_wheel"), None)
    if wheel is not None:
        return wheel["url"], wheel["digests"]["sha256"]

    raise RuntimeError(f"No sdist or wheel found for {package_name}=={version}")


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / "bin" / "python"


def _resolve_dependencies(version: str) -> list[tuple[str, str]]:
    with tempfile.TemporaryDirectory(prefix="codex-switch-brew-") as tmp_dir:
        venv_dir = Path(tmp_dir) / ".venv"
        venv.EnvBuilder(with_pip=True).create(venv_dir)
        python = _venv_python(venv_dir)

        subprocess.run(
            [str(python), "-m", "pip", "install", f"{PACKAGE_NAME}=={version}"],
            check=True,
        )

        freeze = subprocess.run(
            [str(python), "-m", "pip", "freeze"],
            check=True,
            capture_output=True,
            text=True,
        )

    dependencies: list[tuple[str, str]] = []
    for line in freeze.stdout.splitlines():
        if "==" not in line:
            continue
        name, pinned_version = line.split("==", 1)
        normalized = name.replace("-", "_").lower()
        if normalized in {item.replace("-", "_").lower() for item in SKIP_PACKAGES}:
            continue
        dependencies.append((name, pinned_version))

    dependencies.sort(key=lambda item: item[0].lower())
    return dependencies


def _resource_block(name: str, version: str) -> str:
    url, sha256 = _release_file(name, version)
    return (
        f'  resource "{name}" do\n'
        f'    url "{url}"\n'
        f'    sha256 "{sha256}"\n'
        f"  end\n"
    )


def render_formula(version: str) -> str:
    package_url, package_sha256 = _release_file(PACKAGE_NAME, version)
    resources = "\n".join(_resource_block(name, dep_version) for name, dep_version in _resolve_dependencies(version))
    if resources:
        resources += "\n"

    return f"""class {CLASS_NAME} < Formula
  include Language::Python::Virtualenv

  desc "{DESCRIPTION}"
  homepage "{HOMEPAGE}"
  url "{package_url}"
  sha256 "{package_sha256}"

  depends_on "{PYTHON_FORMULA}"

{resources}  def install
    virtualenv_install_with_resources
  end

  test do
    output = shell_output("{TEST_COMMAND}")
    assert_match "{TEST_ASSERT}", output
  end
end
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_formula(args.version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
