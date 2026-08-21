from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_windows_build_script_targets_existing_pyinstaller_spec():
    script = (ROOT_DIR / "scripts/build-windows-exe.ps1").read_text(encoding="utf-8")

    assert "PyInstaller" in script
    assert "email_management.spec" in script
    assert "--distpath" in script
    assert "Join-Path $root 'EmailManagement.exe'" in script
    assert "Join-Path $root '.env'" in script
    assert "InstallIfMissing" in script


def test_windows_spec_is_windowed_desktop_entrypoint():
    spec = (ROOT_DIR / "email_management.spec").read_text(encoding="utf-8")

    assert 'name="EmailManagement"' in spec
    assert "console=False" in spec
    assert '"email_management.py"' in spec
    assert '"assets"' in spec
    assert 'email-management-icon.ico' in spec
    darwin_branch, windows_branch = spec.split("else:", 1)
    assert 'icon=str(icon_path)' not in darwin_branch
    assert 'icon=str(icon_path)' in windows_branch


def test_runtime_supports_env_next_to_frozen_executable():
    runtime = (ROOT_DIR / "email_management_web/runtime.py").read_text(encoding="utf-8")

    assert "Path(sys.executable).resolve().parent / \".env\"" in runtime
    assert "root = root.resolve()" in runtime
    assert "EMAIL_MANAGEMENT_ENV_FILE" in runtime


def test_local_build_preserves_project_runtime_without_copying_secrets():
    script = (ROOT_DIR / "scripts/build-windows-exe.ps1").read_text(encoding="utf-8")

    assert "EMAIL_MANAGEMENT_HOME=runtime" in script
    assert "This file contains no secrets" in script
    assert "Join-Path $root '.env'" in script


def test_packaged_icon_is_transparent_and_included_for_the_tray():
    from PIL import Image

    icon_path = ROOT_DIR / "assets/email-management-icon.png"
    tray = (ROOT_DIR / "email_management_web/windows_tray.py").read_text(encoding="utf-8")

    with Image.open(icon_path) as icon:
        assert icon.mode == "RGBA"
        assert icon.getchannel("A").getextrema()[0] == 0
        assert icon.getchannel("A").getextrema()[1] == 255
    assert 'resource_path("assets", "email-management-icon.png")' in tray
