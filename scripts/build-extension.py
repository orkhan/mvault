#!/usr/bin/env python3
"""Create a deterministic ZIP that can be loaded as an unpacked Chrome extension."""

import argparse
import re
import stat
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    settings = (ROOT / "mvault_project/settings.py").read_text()
    app_version = re.search(r'^APP_VERSION = "([^"]+)"', settings, re.MULTILINE)
    if not app_version or args.version != app_version.group(1):
        parser.error("--version must match APP_VERSION in mvault_project/settings.py")

    manifest = (ROOT / "extension/manifest.json").read_text()
    if '"manifest_version": 3' not in manifest:
        parser.error("extension/manifest.json is not a Manifest V3 extension")

    zip_time = (2000, 1, 1, 0, 0, 0)
    extension_dir = ROOT / "extension"
    args.out.mkdir(parents=True, exist_ok=True)
    archive = args.out / f"mvault-chrome-extension-{args.version}.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(p for p in extension_dir.rglob("*") if p.is_file() and p.name != ".DS_Store" and "__pycache__" not in p.parts):
            relative = path.relative_to(extension_dir).as_posix()
            info = ZipInfo(relative, zip_time)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            bundle.writestr(info, path.read_bytes())
    print(f"built {archive}")


if __name__ == "__main__":
    main()
