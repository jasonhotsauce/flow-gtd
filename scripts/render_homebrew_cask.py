#!/usr/bin/env python3
"""Render the Flow GTD Homebrew Cask from a checked release archive."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = REPO_ROOT / "homebrew" / "flow-gtd.rb.template"


def normalize_arch(arch: str) -> tuple[str, str]:
    normalized = arch.strip().lower()
    if normalized in {"arm64", "aarch64"}:
        return "arm64", ":arm64"
    if normalized in {"x86_64", "amd64"}:
        return "x86_64", ":x86_64"
    raise ValueError(f"Unsupported release architecture: {arch}")


def archive_sha256(archive_path: Path) -> str:
    digest = hashlib.sha256()
    with archive_path.open("rb") as archive:
        for chunk in iter(lambda: archive.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_project_version(pyproject_path: Path = REPO_ROOT / "pyproject.toml") -> str:
    match = re.search(
        r'^version\s*=\s*"([^"]+)"',
        pyproject_path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if not match:
        raise ValueError(f"Could not read version from {pyproject_path}")
    return match.group(1)


def render_cask(
    *,
    template: str,
    version: str,
    github_user: str,
    github_repo: str,
    archive_path: Path | str,
    release_arch: str,
) -> str:
    asset_arch, arch_requirement = normalize_arch(release_arch)
    archive = Path(archive_path)
    if not archive.exists():
        raise FileNotFoundError(f"Release archive does not exist: {archive}")

    replacements = {
        "{{VERSION}}": version,
        "{{GITHUB_USER}}": github_user,
        "{{GITHUB_REPO}}": github_repo,
        "{{SHA256}}": archive_sha256(archive),
        "{{RELEASE_ARCH}}": asset_arch,
        "{{ARCH_REQUIREMENT}}": arch_requirement,
    }
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def default_archive_path(version: str, release_arch: str) -> Path:
    asset_arch, _ = normalize_arch(release_arch)
    return REPO_ROOT / "dist" / f"Flow-{version}-macos-{asset_arch}.zip"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--version", default=os.environ.get("FLOW_RELEASE_VERSION"))
    parser.add_argument("--github-user", default=os.environ.get("GITHUB_USER"))
    parser.add_argument("--github-repo", default=os.environ.get("GITHUB_REPO", "flow-gtd"))
    parser.add_argument(
        "--release-arch",
        "--arch",
        dest="release_arch",
        default=os.environ.get("FLOW_RELEASE_ARCH", platform.machine()),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version = args.version or read_project_version()
    archive = args.archive or default_archive_path(version, args.release_arch)
    if not args.github_user:
        raise SystemExit("Missing GitHub user. Pass --github-user or set GITHUB_USER.")

    rendered = render_cask(
        template=args.template.read_text(encoding="utf-8"),
        version=version,
        github_user=args.github_user,
        github_repo=args.github_repo,
        archive_path=archive,
        release_arch=args.release_arch,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
