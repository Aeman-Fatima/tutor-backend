"""
CLI wrapper for OCR — same stdin/stdout JSON pattern as cli_wrapper.py.

Input  (stdin):  {"image_path": "/absolute/path/to/image.jpg"}
Output (stdout): {"ok": true, "text": "..."} | {"ok": false, "error": "..."}
"""

import sys
import os
import json

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_REPO_ROOT, "tutor", ".env"))


def main():
    try:
        req = json.loads(sys.stdin.read())
        image_path = req["image_path"]
    except Exception as e:
        sys.stdout.write(json.dumps({"ok": False, "error": f"Invalid input: {e}"}))
        sys.exit(0)

    if not os.path.isfile(image_path):
        sys.stdout.write(json.dumps({"ok": False, "error": f"File not found: {image_path}"}))
        sys.exit(0)

    try:
        from tutor.core.ocr import extract_text
        text = extract_text(image_path)
        sys.stdout.write(json.dumps({"ok": True, "text": text}))
    except Exception as e:
        import traceback
        sys.stdout.write(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}))

    sys.exit(0)


if __name__ == "__main__":
    main()
