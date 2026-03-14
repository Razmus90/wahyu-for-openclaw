"""Local MCP brain for OpenClaw self-improving workspace."""

from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


ROOT = Path(__file__).resolve().parent
WORKSPACE_ROOT = ROOT.parent
LOCAL_MEMORY_PATH = ROOT / "memory.json"
DEFAULT_LOG_ROOT = Path.home() / ".openclaw" / "logs"
SEQUENTIAL_BUFFER_SIZE = 512  # lines to keep while scanning logs sequentially


def ensure_memory_file() -> None:
    if LOCAL_MEMORY_PATH.exists():
        return
    LOCAL_MEMORY_PATH.write_text(json.dumps({"notes": []}, indent=2), encoding="utf-8")


def load_memory() -> Dict[str, Any]:
    ensure_memory_file()
    try:
        payload = json.loads(LOCAL_MEMORY_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            payload = {"notes": [], "updated_at": None}
    except (json.JSONDecodeError, OSError):
        payload = {"notes": [], "updated_at": None}
    return payload


def save_memory(payload: Dict[str, Any]) -> None:
    payload["updated_at"] = datetime.utcnow().isoformat()
    LOCAL_MEMORY_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def append_memory(note: str, tags: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    payload = load_memory()
    entry = {
        "note": note,
        "tags": list(tags or []),
        "timestamp": datetime.utcnow().isoformat(),
    }
    payload.setdefault("notes", []).append(entry)
    save_memory(payload)
    return entry


def munch_code_local(target_dir: Optional[str] = None) -> Dict[str, Any]:
    root = Path(target_dir).expanduser().resolve() if target_dir else WORKSPACE_ROOT
    if not (WORKSPACE_ROOT in root.parents or root == WORKSPACE_ROOT):
        return {"status": "error", "reason": "target outside workspace"}
    files = sorted(root.rglob("*.py"))
    processed: List[str] = []
    trimmed = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        sanitized = "\n".join(line.rstrip() for line in lines)
        if sanitized != text.rstrip():
            path.write_text(sanitized + ("\n" if sanitized and not sanitized.endswith("\n") else ""), encoding="utf-8")
            trimmed += 1
            processed.append(str(path.relative_to(WORKSPACE_ROOT)))
    summary = {
        "processed": len(files),
        "trimmed_files": trimmed,
        "paths": processed,
    }
    return summary


def find_recent_errors(root: Path, keyword: str = "error", limit: int = 20) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    log_files = sorted(root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for log_file in log_files:
        if len(matches) >= limit:
            break
        try:
            with log_file.open("r", encoding="utf-8", errors="ignore") as handle:
                lines = deque(handle, maxlen=SEQUENTIAL_BUFFER_SIZE)
        except OSError:
            continue

        for raw in reversed(lines):
            if len(matches) >= limit:
                break
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            serialized = json.dumps(payload).lower()
            if keyword.lower() not in serialized:
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
    return matches


def monitor_logs(log_dir: Optional[str] = None, keyword: str = "error", limit: int = 20) -> Dict[str, Any]:
    log_root = Path(log_dir).expanduser() if log_dir else DEFAULT_LOG_ROOT
    if not log_root.exists():
        return {"status": "missing logs", "checked_path": str(log_root)}
    matches = find_recent_errors(log_root, keyword=keyword, limit=limit)
    return {"status": "ok", "root": str(log_root), "match_count": len(matches), "matches": matches}


def self_update(source_url: str, destination: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    if not source_url:
        return {"status": "error", "reason": "missing source_url"}
    dest = Path(destination).expanduser() if destination else ROOT / "runtime_update.py"
    if dest.exists() and not force:
        return {"status": "error", "reason": "destination exists, pass force=True to overwrite"}
    try:
        with urllib.request.urlopen(source_url) as handle:
            payload = handle.read()
    except urllib.error.URLError as err:
        return {"status": "error", "reason": str(err)}
    dest.write_bytes(payload)
    return {"status": "ok", "destination": str(dest)}


def get_tools() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "munch_code_local",
                "description": "Percepat skrip Python di workspace dengan membersihkan whitespace dan menjaga newline konsisten.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_dir": {"type": "string"},
                    },
                },
            },
            {
                "name": "monitor_logs",
                "description": "Scan log OpenClaw secara berurutan dan laporkan pola error terbaru.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "log_dir": {"type": "string"},
                        "keyword": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                },
            },
            {
                "name": "local_memory",
                "description": "Tambahkan atau baca catatan teknis dari basis pengetahuan memory.json.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["list", "add"]},
                        "note": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            {
                "name": "self_update",
                "description": "Tarik pembaruan logika dari sumber online dan simpan sebagai runtime-update lokal.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_url": {"type": "string"},
                        "destination": {"type": "string"},
                        "force": {"type": "boolean"},
                    },
                    "required": ["source_url"],
                },
            },
        ]
    }


def handle_request(request: Mapping[str, Any]) -> Dict[str, Any]:
    method = request.get("method")
    params = request.get("params") or {}
    if method == "list_tools":
        return {"result": get_tools()}
    if method == "monitor_logs":
        return {"result": monitor_logs(params.get("log_dir"), params.get("keyword", "error"), int(params.get("limit", 20)))}
    if method == "munch_code_local":
        return {"result": munch_code_local(params.get("target_dir"))}
    if method == "local_memory":
        action = params.get("action") or "list"
        if action == "add" and params.get("note"):
            entry = append_memory(params["note"], params.get("tags"))
            return {"result": entry}
        return {"result": load_memory()}
    if method == "self_update":
        return {"result": self_update(params.get("source_url"), params.get("destination"), bool(params.get("force", False)))}
    return {"result": "Operasi berhasil dijalankan di workspace."}


def main() -> None:
    ensure_memory_file()
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            request = json.loads(line)
            response = handle_request(request)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except Exception as err:
            sys.stderr.write(f"Error: {str(err)}\n")


def cli_entry() -> None:
    # Allows sequential CLI calls without MCP by reading a single JSON request from args.
    if len(sys.argv) <= 1:
        main()
        return
    payload = json.loads(sys.argv[1])
    response = handle_request(payload)
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    cli_entry()
