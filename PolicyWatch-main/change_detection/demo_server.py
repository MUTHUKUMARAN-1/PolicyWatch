"""Tiny local demo website for the change detection module (standard library only).

Run from the repo root:
    python -m change_detection.demo_server            # http://localhost:8765
    python -m change_detection.demo_server --port 9000

Endpoints:
    GET  /                 demo page
    GET  /api/samples      the bundled sample policies
    POST /api/compare      body {"old": "...", "new": "...", "document_id": "..."} -> ChangeReport JSON

This is only a demo / testing aid for Part 6. The real Diff View UI is Part 4.
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .api import detect_changes

HERE = Path(__file__).resolve().parent
PAGE = HERE / "demo" / "index.html"
SAMPLES = HERE / "samples"
SAMPLE_PAIRS = {
    "privacy": ("privacy_v1.html", "privacy_v2.html"),
    "terms": ("terms_v1.txt", "terms_v2.txt"),
}
MAX_BODY = 5 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "PolicyWatchDemo/1.0"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/samples":
            data = {
                name: {"old": (SAMPLES / a).read_text(encoding="utf-8"), "new": (SAMPLES / b).read_text(encoding="utf-8")}
                for name, (a, b) in SAMPLE_PAIRS.items()
            }
            self._json(200, data)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/api/compare":
            return self._json(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._json(413, {"error": "request too large"})
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            report = detect_changes(
                str(body.get("old", "")),
                str(body.get("new", "")),
                document_id=body.get("document_id") or None,
                include_formatting=bool(body.get("include_formatting", True)),
            )
        except (ValueError, TypeError) as exc:
            return self._json(400, {"error": str(exc)})
        self._json(200, report.to_dict())

    def log_message(self, fmt, *args):
        print("[demo] " + fmt % args)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="PolicyWatch change detection demo website")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args(argv)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"PolicyWatch change detection demo running at http://localhost:{args.port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
