"""Build the browser version of laserdesign into a static folder.

The result runs the laserdesign Python package under Pyodide and can be
served by any static web server (GitHub Pages, a lab intranet, a USB stick
with ``python -m http.server``). Nothing runs on the server.

Usage::

    python tools/build_web.py                    # -> build/web, Pyodide from the jsDelivr CDN
    python tools/build_web.py --serve            # build, then serve on http://localhost:8000
    python tools/build_web.py --pyodide-dir ~/pyodide-314.0.7/pyodide
                                                 # also copy Pyodide into the site (works offline)

``--pyodide-dir`` takes an unpacked Pyodide release (the ``pyodide`` folder of
``pyodide-<version>.tar.bz2`` from https://github.com/pyodide/pyodide/releases);
only the runtime and the packages laserdesign needs (NumPy, SciPy and their
dependencies, about 35 MB) are copied.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
PACKAGE = ROOT / "src" / "laserdesign"
ICONS = PACKAGE / "gui" / "icons"

#: Pyodide version the site is tested with; keep in step with web/app.js.
PYODIDE_VERSION = "314.0.7"
CDN = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
#: Pyodide packages to load (their dependencies are added from pyodide-lock.json).
PYODIDE_PACKAGES = ("numpy", "scipy")
#: Files of the Pyodide runtime itself.
PYODIDE_CORE = ("pyodide.mjs", "pyodide.js", "pyodide.asm.mjs", "pyodide.asm.js",
                "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json")


def zip_package(dest: Path) -> int:
    """Zip the laserdesign package sources (Python files only); return the file count."""
    count = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(PACKAGE.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            zf.write(path, path.relative_to(PACKAGE.parent).as_posix())
            count += 1
    return count


def vendor_pyodide(src: Path, dest: Path) -> int:
    """Copy the Pyodide runtime and the needed packages; return the bytes copied."""
    lock = json.loads((src / "pyodide-lock.json").read_text())
    packages = lock["packages"]
    wanted, todo = set(), list(PYODIDE_PACKAGES)
    while todo:
        name = todo.pop()
        if name in wanted:
            continue
        if name not in packages:
            raise SystemExit(f"{name!r} is not in {src / 'pyodide-lock.json'}")
        wanted.add(name)
        todo.extend(packages[name].get("depends", []))
    files = [f for f in PYODIDE_CORE if (src / f).exists()]
    files += [packages[name]["file_name"] for name in sorted(wanted)]
    missing = [f for f in files if not (src / f).exists()]
    if missing:
        raise SystemExit(f"Missing from {src}: {', '.join(missing)}")
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    for f in files:
        shutil.copy2(src / f, dest / f)
        total += (dest / f).stat().st_size
    return total


def build(out: Path, pyodide_dir: Path | None = None, pyodide_url: str | None = None) -> Path:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(WEB, out, ignore=shutil.ignore_patterns("config.js", ".*"))
    shutil.copytree(ICONS, out / "icons")
    n = zip_package(out / "laserdesign.zip")
    index_url = pyodide_url or CDN
    if pyodide_dir is not None:
        size = vendor_pyodide(pyodide_dir.expanduser(), out / "pyodide")
        index_url = "pyodide/"
        print(f"Copied Pyodide runtime and packages ({size / 1e6:.1f} MB)")
    config = {"pyodideIndexURL": index_url, "packageURL": "laserdesign.zip"}
    (out / "config.js").write_text(
        "// Written by tools/build_web.py\n"
        f"window.LASERDESIGN_CONFIG = {json.dumps(config, indent=2)};\n")
    (out / ".nojekyll").write_text("")  # GitHub Pages: serve files as they are
    print(f"Built {out} ({n} Python files; Pyodide from {index_url})")
    return out


def serve(directory: Path, port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    handler.extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                              ".mjs": "text/javascript", ".js": "text/javascript",
                              ".wasm": "application/wasm"}
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Serving on http://localhost:{port}/ (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "web",
                    help="output folder (default: build/web)")
    ap.add_argument("--pyodide-dir", type=Path,
                    help="unpacked Pyodide release to copy into the site for offline use")
    ap.add_argument("--pyodide-url", help=f"Pyodide base URL (default: {CDN})")
    ap.add_argument("--serve", action="store_true", help="serve the site after building")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)
    out = build(args.out.resolve(), args.pyodide_dir, args.pyodide_url)
    if args.serve:
        serve(out, args.port)


if __name__ == "__main__":
    main()
