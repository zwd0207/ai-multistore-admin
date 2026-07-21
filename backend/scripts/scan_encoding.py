from __future__ import annotations

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".css",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}
SKIP_DIRS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "backups", "logs"}
TEXT_NAMES = {".editorconfig", ".env", ".env.example", ".gitattributes", ".gitignore"}
MOJIBAKE_MARKERS = {
    "U+FFFD replacement char": "\ufffd",
    "Chinese mojibake marker": "\u951f\u65a4\u62f7",
    "Latin-1 mojibake marker": "\u00c2",
    "UTF-8 quote mojibake marker": "\u00e2\u20ac",
    "Korean mojibake marker i-grave": "\u00ec",
    "Korean mojibake marker e-diaeresis": "\u00eb",
}


def should_scan(path: Path) -> bool:
    if path.name == Path(__file__).name:
        return False
    if any(part in SKIP_DIRS for part in path.parts):
        return False
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES


def iter_text_files() -> list[Path]:
    return sorted(path for path in BACKEND_DIR.rglob("*") if path.is_file() and should_scan(path))


def relative(path: Path) -> str:
    return path.relative_to(BACKEND_DIR).as_posix()


def line_number_from_bytes(raw: bytes, offset: int) -> int:
    return raw[:offset].count(b"\n") + 1


def scan_file(path: Path) -> list[str]:
    issues: list[str] = []
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        line_number = line_number_from_bytes(raw, exc.start)
        return [f"{relative(path)}:{line_number}: invalid UTF-8 ({exc.reason})"]

    for line_number, line in enumerate(text.splitlines(), start=1):
        for label, marker in MOJIBAKE_MARKERS.items():
            if marker in line:
                excerpt = line.strip()
                issues.append(f"{relative(path)}:{line_number}: {label}: {excerpt}")
    return issues


def main() -> int:
    issues: list[str] = []
    for path in iter_text_files():
        issues.extend(scan_file(path))

    if issues:
        print("Encoding scan failed:")
        for issue in issues:
            print(issue)
        return 1

    print("Encoding scan passed: no invalid UTF-8 or mojibake markers found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
