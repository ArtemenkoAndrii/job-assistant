"""Extract browser MCP calls and token usage from a Claude Code session transcript.

Usage:
    python extract.py <scenario-name> [--transcript PATH]

Without --transcript, the newest transcript under ~/.claude/projects that
contains browser MCP calls is used. Output goes to recordings/<scenario-name>/:
    calls.jsonl  - one line per MCP call: tool, input, result text, size, error flag
    summary.md   - call counts, response sizes, token usage, duration
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PREFIX = "mcp__browser__"


def find_transcript() -> Path:
    root = Path.home() / ".claude" / "projects"
    candidates = sorted(root.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        if PREFIX in path.read_text(encoding="utf-8", errors="ignore"):
            return path
    sys.exit(f"No transcript with {PREFIX} calls found under {root}")


def result_text(content) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
        else:
            parts.append(f"<{block.get('type', 'non-text')} omitted>")
    return "\n".join(parts)


def parse_ts(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--transcript", type=Path)
    args = ap.parse_args()

    path = args.transcript or find_transcript()
    calls, order, usage_by_msg, models, stamps = {}, [], {}, set(), []

    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = parse_ts(entry.get("timestamp"))
        if ts:
            stamps.append(ts)
        msg = entry.get("message") or {}
        content = msg.get("content")
        if entry.get("type") == "assistant":
            if msg.get("model"):
                models.add(msg["model"])
            if msg.get("usage"):
                usage_by_msg[msg.get("id") or len(usage_by_msg)] = msg["usage"]
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_use" and block.get("name", "").startswith(PREFIX):
                    calls[block["id"]] = {
                        "seq": len(order) + 1,
                        "timestamp": entry.get("timestamp"),
                        "tool": block["name"][len(PREFIX):],
                        "input": block.get("input"),
                    }
                    order.append(block["id"])
        elif entry.get("type") == "user" and isinstance(content, list):
            for block in content:
                if block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                    text = result_text(block.get("content"))
                    calls[block["tool_use_id"]].update(
                        result=text, result_chars=len(text), is_error=bool(block.get("is_error"))
                    )

    out = Path("recordings") / args.scenario
    out.mkdir(parents=True, exist_ok=True)
    with (out / "calls.jsonl").open("w", encoding="utf-8") as f:
        for cid in order:
            f.write(json.dumps(calls[cid], ensure_ascii=False) + "\n")

    per_tool = defaultdict(lambda: [0, 0, 0])  # calls, chars, errors
    for cid in order:
        c = calls[cid]
        t = per_tool[c["tool"]]
        t[0] += 1
        t[1] += c.get("result_chars", 0)
        t[2] += int(c.get("is_error", False))

    tokens = defaultdict(int)
    for u in usage_by_msg.values():
        for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"):
            tokens[key] += u.get(key) or 0

    duration = (max(stamps) - min(stamps)) if len(stamps) > 1 else None
    lines = [
        f"# Recording: {args.scenario}",
        "",
        f"- Transcript: `{path.name}`",
        f"- Model(s): {', '.join(sorted(models)) or 'unknown'}",
        f"- Duration: {duration}",
        f"- MCP calls: {len(order)}",
        f"- Model turns: {len(usage_by_msg)}",
        "",
        "## Tokens",
        "",
        "| Kind | Tokens |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v:,} |" for k, v in tokens.items()]
    lines += [
        "",
        "## MCP calls by tool",
        "",
        "| Tool | Calls | Avg response chars | Total chars | Errors |",
        "|---|---|---|---|---|",
    ]
    for tool, (n, chars, errs) in sorted(per_tool.items(), key=lambda x: -x[1][1]):
        lines.append(f"| {tool} | {n} | {chars // n:,} | {chars:,} | {errs} |")
    lines += ["", "Rough rule: 1 token ≈ 4 characters of English text.", ""]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(order)} calls to {out}")


if __name__ == "__main__":
    main()
