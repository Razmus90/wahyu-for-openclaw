import sys
import json
from collections import deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


def get_tools() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "munch_code_local",
                "description": "Membersihkan kode yang tidak efisien di folder workspace.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_file": {"type": "string"}
                    },
                },
            },
            {
                "name": "monitor_logs",
                "description": "Scan log OpenClaw untuk pola error terbaru dan beri ringkasan otomatis.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "log_dir": {"type": "string"},
                        "keyword": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                },
            },
        ]
    }


def find_recent_errors(root: Path, keyword: str = "error", limit: int = 20) -> List[Dict[str, Any]]:
    keyword = keyword.lower()
    matches: List[Dict[str, Any]] = []
    log_files = sorted(root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)

    for log_file in log_files:
        if len(matches) >= limit:
            break
        try:
            with log_file.open("r", encoding="utf-8", errors="ignore") as handle:
                lines = deque(handle, maxlen=limit * 5)
        except OSError:
            continue

        for raw in reversed(lines):
            if not raw or len(matches) >= limit:
                break
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue

            serialized = json.dumps(payload).lower()
            if keyword not in serialized:
                continue

            matches.append(
                {
                    "file": str(log_file),
                    "timestamp": payload.get("timestamp") or payload.get("time"),
                    "message": payload.get("message")
                    or payload.get("msg")
                    or payload.get("event")
                    or serialized[:200],
                    "payload": payload,
                }
            )
            if len(matches) >= limit:
                break

    return matches


def monitor_logs(log_dir: Optional[str] = None, keyword: str = "error", limit: int = 20) -> Dict[str, Any]:
    log_root = Path(log_dir).expanduser() if log_dir else Path.home() / ".openclaw" / "logs"
    if not log_root.exists():
        return {"status": "missing root", "root": str(log_root)}

    matches = find_recent_errors(log_root, keyword=keyword, limit=limit)
    return {"root": str(log_root), "matches": matches}


def handle_request(request: Mapping[str, Any]) -> Dict[str, Any]:
    method = request.get("method")
    if method == "list_tools":
        return {"result": get_tools()}

    if method == "monitor_logs":
        params = request.get("params") or {}
        log_dir = params.get("log_dir")
        keyword = params.get("keyword", "error")
        limit = params.get("limit", 20)
        limit = min(max(1, int(limit)), 100)
        return {"result": monitor_logs(log_dir=log_dir, keyword=keyword, limit=limit)}

    return {"result": "Operasi berhasil dijalankan di workspace."}


def main() -> None:
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            request = json.loads(line)
            response = handle_request(request)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as err:  # pragma: no cover - fail-safe runtime handler
            sys.stderr.write(f"Error: {str(err)}\n")


if __name__ == "__main__":
    main()
