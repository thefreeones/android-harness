"""The android-harness CLI: exec Python from stdin with helpers in scope.

Usage:
  android-harness <<'PY'
  print(screen_size())
  ocr_results = ocr()
  tap_text("Weather")
  PY

Commands:
  android-harness --doctor    diagnose ADB, device, capture, and OCR
  android-harness skill       print the android-harness SKILL.md text
  android-harness --help      show this message
"""

import sys
from pathlib import Path

USAGE = """Usage:
  android-harness <<'PY'
  print(screen_size())
  PY

Commands:
  android-harness --doctor    diagnose ADB, device, capture, and OCR
  android-harness skill       print the android-harness skill text
  android-harness --help      show this message
"""


def main():
    args = sys.argv[1:]

    if args and args[0] in ("-h", "--help"):
        print(USAGE)
        return

    if args and args[0] in ("--doctor", "doctor"):
        from .admin import run_doctor
        sys.exit(run_doctor())

    if args and args[0] == "skill":
        repo_root = Path(__file__).resolve().parent.parent.parent
        skill_path = repo_root / "SKILL.md"
        if skill_path.exists():
            print(skill_path.read_text(encoding="utf-8"), end="")
        else:
            print("SKILL.md not found", file=sys.stderr)
            sys.exit(1)
        return

    if args or sys.stdin.isatty():
        print(USAGE)
        sys.exit(0 if not args else 1)

    code = sys.stdin.read()
    if not code.strip():
        print(USAGE)
        sys.exit(1)

    from . import helpers
    g = {k: v for k, v in vars(helpers).items() if not k.startswith("_")}
    g["__name__"] = "__main__"
    exec(code, g)


if __name__ == "__main__":
    main()
