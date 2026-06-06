import importlib.util
import os
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def load_renderer():
    renderer_path = REPO_ROOT / "scripts" / "render_homebrew_cask.py"
    assert renderer_path.exists(), "missing Homebrew cask renderer"
    spec = importlib.util.spec_from_file_location("render_homebrew_cask", renderer_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_homebrew_template_is_native_app_cask_not_python_formula():
    template = read("homebrew/flow-gtd.rb.template")

    assert 'cask "flow-gtd" do' in template
    assert 'app "Flow.app"' in template
    assert 'depends_on macos: ">= :sonoma"' in template
    assert "depends_on arch: {{ARCH_REQUIREMENT}}" in template
    assert "uninstall quit: \"com.flowgtd.native\"" in template

    retired_formula_terms = [
        "class FlowGtd < Formula",
        "Language::Python::Virtualenv",
        "python@3.11",
        "bin.install_symlink",
        "flow --version",
        "GTD CLI",
    ]
    for term in retired_formula_terms:
        assert term not in template


def test_cask_renderer_inserts_release_asset_url_sha_and_arch(tmp_path):
    renderer = load_renderer()
    archive = tmp_path / "Flow-1.2.3-macos-arm64.zip"
    archive.write_bytes(b"fake native app archive")

    rendered = renderer.render_cask(
        template=read("homebrew/flow-gtd.rb.template"),
        version="1.2.3",
        github_user="example",
        github_repo="flow-gtd",
        archive_path=archive,
        release_arch="arm64",
    )

    assert 'version "1.2.3"' in rendered
    assert 'sha256 "f500d7854328256045571fd5412678b8c48506dd350c2118f80aa41f3a4cb21a"' in rendered
    assert 'url "https://github.com/example/flow-gtd/releases/download/v#{version}/Flow-#{version}-macos-arm64.zip"' in rendered
    assert "depends_on arch: :arm64" in rendered
    assert "{{" not in rendered
    assert "}}" not in rendered


def test_cask_renderer_normalizes_supported_architectures():
    renderer = load_renderer()

    assert renderer.normalize_arch("arm64") == ("arm64", ":arm64")
    assert renderer.normalize_arch("aarch64") == ("arm64", ":arm64")
    assert renderer.normalize_arch("x86_64") == ("x86_64", ":x86_64")
    assert renderer.normalize_arch("amd64") == ("x86_64", ":x86_64")


def test_package_native_app_script_validates_and_zips_flow_app(tmp_path):
    script = REPO_ROOT / "scripts" / "package_native_app.sh"
    assert script.exists(), "missing native app packaging script"

    app_dir = tmp_path / "Flow.app"
    (app_dir / "Contents" / "MacOS").mkdir(parents=True)
    (app_dir / "Contents" / "Resources" / "sidecar-runtime" / "node" / "bin").mkdir(parents=True)
    (app_dir / "Contents" / "Resources" / "sidecar-runtime" / "dist").mkdir(parents=True)
    (app_dir / "Contents" / "MacOS" / "FlowMacApp").write_text("#!/bin/sh\n", encoding="utf-8")
    (app_dir / "Contents" / "MacOS" / "FlowMacApp").chmod(0o755)
    (app_dir / "Contents" / "Info.plist").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleShortVersionString</key>
  <string>9.8.7</string>
</dict>
</plist>
""",
        encoding="utf-8",
    )
    (app_dir / "Contents" / "Resources" / "sidecar-runtime" / "node" / "bin" / "node").write_text("", encoding="utf-8")
    (app_dir / "Contents" / "Resources" / "sidecar-runtime" / "node" / "bin" / "node").chmod(0o755)
    (app_dir / "Contents" / "Resources" / "sidecar-runtime" / "dist" / "main.js").write_text("", encoding="utf-8")
    (app_dir / "Contents" / "Resources" / "sidecar-runtime" / "package.json").write_text("{}", encoding="utf-8")
    (app_dir / "Contents" / "Resources" / "Flow.icns").write_bytes(b"fake icon")

    env = os.environ.copy()
    env.update(
        {
            "FLOW_NATIVE_APP_DIR": str(app_dir),
            "FLOW_NATIVE_DIST_DIR": str(tmp_path / "dist"),
            "FLOW_RELEASE_VERSION": "9.8.7",
            "FLOW_RELEASE_ARCH": "arm64",
        }
    )
    result = subprocess.run(
        [str(script)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    archive = tmp_path / "dist" / "Flow-9.8.7-macos-arm64.zip"
    assert archive.exists()
    assert re.search(r"SHA256: [0-9a-f]{64}", result.stdout)


def test_makefile_publish_is_native_release_driven():
    makefile = read("Makefile")

    assert "NORMALIZED_RELEASE_ARCH :=" in makefile
    assert "RELEASE_ASSET := Flow-$(VERSION)-macos-$(NORMALIZED_RELEASE_ARCH).zip" in makefile
    assert re.search(r"^release:.*release-preflight.*native-release-archive", makefile, re.MULTILINE)
    assert not re.search(r"^release:.*native-release-archive-signed", makefile, re.MULTILINE)
    assert re.search(r"^build-native:.*scripts/build_native_app\.sh", makefile, re.MULTILINE)
    assert re.search(r"^test-native:.*scripts/test_native_app\.sh", makefile, re.MULTILINE)
    assert re.search(r"^native-release-archive:.*build-native", makefile, re.MULTILINE)
    assert re.search(r"^native-release-archive-signed:.*build-native", makefile, re.MULTILINE)
    assert 'FLOW_REQUIRE_SIGNED=1' in makefile
    assert 'git status --porcelain --untracked-files=all' in makefile
    assert re.search(r"^brew-cask:", makefile, re.MULTILINE)
    assert re.search(r"^brew-cask-local:", makefile, re.MULTILINE)
    assert not re.search(r"^brew-cask-local:.*native-release-archive", makefile, re.MULTILINE)
    assert re.search(
        r"^publish:.*test-unit.*test-native.*release-preflight.*release.*brew-cask",
        makefile,
        re.MULTILINE,
    )
    assert "publish: test build release brew-formula" not in makefile


def test_native_build_stamps_app_bundle_version_from_project_version():
    build_script = read("scripts/build_native_app.sh")

    assert "CFBundleShortVersionString $VERSION" in build_script
    assert "CFBundleVersion $VERSION" in build_script
    assert "pyproject.toml" in build_script


def test_native_app_declares_and_builds_first_party_app_icon():
    plist = read("NativeSupport/FlowMacApp-Info.plist")
    build_script = read("scripts/build_native_app.sh")

    assert "<key>CFBundleIconFile</key>" in plist
    assert "<string>Flow.icns</string>" in plist
    assert (REPO_ROOT / "NativeSupport" / "FlowIcon.png").exists()
    assert "ICON_SOURCE" in build_script
    assert "FlowIcon.png" in build_script
    assert "Flow.icns" in build_script
    assert "iconutil -c icns" in build_script


def test_package_script_requires_native_app_icon_resource():
    package_script = read("scripts/package_native_app.sh")

    assert 'require_path "$APP_DIR/Contents/Resources/Flow.icns"' in package_script


def test_package_script_supports_signed_release_gate():
    package_script = read("scripts/package_native_app.sh")

    assert "FLOW_REQUIRE_SIGNED" in package_script
    assert "FLOW_CODESIGN_IDENTITY" in package_script
    assert "codesign --force --deep --options runtime --sign" in package_script
    assert "Set FLOW_CODESIGN_IDENTITY or sign before release" in package_script


def test_readme_documents_homebrew_cask_install_and_release_flow():
    readme = read("README.md")

    assert "brew install --cask flow-gtd" in readme
    assert "dist/Flow-<version>-macos-<arch>.zip" in readme
    assert "make native-release-archive" in readme
    assert "make brew-cask" in readme
    assert "make brew-cask-local" in readme
    assert "No Apple Developer ID certificate or App Store Connect API key is required" in readme
    assert "Homebrew Formula" not in readme


def test_github_actions_release_workflow_builds_unsigned_archive_and_updates_tap():
    workflow_path = REPO_ROOT / ".github" / "workflows" / "release-native-macos.yml"
    assert workflow_path.exists(), "missing native macOS release workflow"

    workflow = workflow_path.read_text(encoding="utf-8")

    assert "release/**" in workflow
    assert "workflow_dispatch:" in workflow
    assert "permissions:" in workflow
    assert re.search(r"permissions:\n  contents: read", workflow)
    assert re.search(r"environment:\n      name: release", workflow)
    assert "contents: write" in workflow
    assert "Check existing release" in workflow
    assert "steps.existing-release.outputs.exists != 'true'" in workflow
    assert "skipping release creation and continuing tap update" in workflow
    assert "Use existing release asset for tap repair" in workflow
    assert "steps.existing-release.outputs.exists == 'true'" in workflow
    assert "gh release download" in workflow
    assert "--clobber" in workflow
    assert "HOMEBREW_TAP_DEPLOY_KEY" in workflow
    assert "HOMEBREW_TAP_TOKEN" not in workflow
    assert "homebrew_tap_deploy_key" in workflow
    assert "git@github.com:${HOMEBREW_TAP_REPOSITORY}.git" in workflow
    assert "x-access-token" not in workflow
    assert "scripts/build_native_app.sh" in workflow
    assert "Package unsigned app" in workflow
    assert "scripts/package_native_app.sh" in workflow
    assert "gh release create" in workflow
    assert "scripts/render_homebrew_cask.py" in workflow
    assert "Casks/flow-gtd.rb" in workflow
    assert "APPLE_DEVELOPER_ID_CERTIFICATE" not in workflow
    assert "APPLE_CODESIGN_IDENTITY" not in workflow
    assert "APPLE_NOTARY" not in workflow
    assert "FLOW_REQUIRE_SIGNED" not in workflow
    assert "notarytool" not in workflow
    assert "stapler" not in workflow


def test_readme_documents_github_actions_release_automation():
    readme = read("README.md")

    assert "release/v<version>" in readme
    assert "release/<version>" in readme
    assert "HOMEBREW_TAP_DEPLOY_KEY" in readme
    assert "HOMEBREW_TAP_TOKEN" not in readme
    assert "packages the unsigned app archive" in readme
    assert "APPLE_DEVELOPER_ID_CERTIFICATE_BASE64" not in readme
    assert "APPLE_DEVELOPER_ID_CERTIFICATE_PASSWORD" not in readme
    assert "APPLE_CODESIGN_IDENTITY" not in readme
    assert "APPLE_NOTARY_KEY_BASE64" not in readme
    assert "APPLE_NOTARY_KEY_ID" not in readme
    assert "APPLE_NOTARY_ISSUER_ID" not in readme


def test_native_app_has_first_party_homebrew_update_checker():
    app_source = read("Sources/FlowMacApp/FlowMacApp.swift")
    updater_source = read("Sources/FlowMacApp/App/NativeReleaseUpdateController.swift")
    plist = read("NativeSupport/FlowMacApp-Info.plist")
    setup_doc = read("docs/release-automation-setup.md")
    readme = read("README.md")

    assert "NativeReleaseUpdateController" in app_source
    assert "Check for Updates..." in app_source
    assert "checkAutomaticallyIfNeeded" in app_source
    assert "FlowReleaseFeedURL" in plist
    assert "https://api.github.com/repos/jasonhotsauce/flow-gtd/releases/latest" in plist
    assert "FLOW_UPDATE_CHECK_URL" in updater_source
    assert "brew update" in updater_source
    assert "upgrade --cask flow-gtd" in updater_source
    assert "reinstall --cask flow-gtd" in updater_source
    assert "Sparkle" not in updater_source
    assert "first-party Homebrew update behavior" in readme
    assert "Flow checks for updates automatically on launch" in setup_doc
    assert "HOMEBREW_TAP_DEPLOY_KEY" in setup_doc
    assert "HOMEBREW_TAP_TOKEN" not in setup_doc
