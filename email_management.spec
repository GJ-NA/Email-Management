# -*- mode: python ; coding: utf-8 -*-

import ast
import os
import sys
from pathlib import Path


project_root = Path(SPECPATH).resolve()
segments_root = project_root / "email_management_web" / "segments"

datas = [
    (str(project_root / "templates"), "templates"),
    (str(project_root / "static"), "static"),
    (str(project_root / "assets"), "assets"),
    (str(project_root / "email_management_web" / "segments"), "email_management_web/segments"),
    (str(project_root / "VERSION"), "."),
]


def collect_segment_hiddenimports():
    hidden = set()
    for segment_path in segments_root.glob("*.py"):
        tree = ast.parse(segment_path.read_text(encoding="utf-8"), filename=str(segment_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name != "__future__":
                        hidden.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if not node.module or node.module == "__future__":
                    continue
                if node.module == "email_management":
                    continue
                hidden.add(node.module)
    hidden.add("email_management_web.runtime")
    hidden.add("email_management_web.windows_tray")
    return sorted(hidden)


hiddenimports = collect_segment_hiddenimports()
app_version = (project_root / "VERSION").read_text(encoding="utf-8").strip()
icon_path = project_root / "assets" / "email-management-icon.ico"
codesign_identity = os.getenv("MACOS_CODESIGN_IDENTITY") or None
entitlements_file = os.getenv("MACOS_ENTITLEMENTS_FILE") or None


a = Analysis(
    ["email_management.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="EmailManagement",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=codesign_identity,
        entitlements_file=entitlements_file,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="EmailManagement",
    )
    app = BUNDLE(
        coll,
        name="EmailManagement.app",
        icon=None,
        bundle_identifier="org.emailmanagement.app",
        info_plist={
            "CFBundleName": "Email Management",
            "CFBundleDisplayName": "Email Management",
            "CFBundleShortVersionString": app_version,
            "CFBundleVersion": app_version,
            "NSHighResolutionCapable": True,
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="EmailManagement",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        icon=str(icon_path),
        codesign_identity=codesign_identity,
        entitlements_file=entitlements_file,
    )
