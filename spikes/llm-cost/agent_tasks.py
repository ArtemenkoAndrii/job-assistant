"""Measure short browser-agent tasks (MVP option C) through the Browser MCP endpoint (A-1).

Each task is one OpenAI Responses API request with A-1 attached as a remote MCP server
(Cloudflare Access service-token headers, restricted tool set, capped tool calls).
OpenAI runs the tool loop server-side; the request's usage is the task's full cost.

Usage:
    . ..\\browser-flows\\set-credentials.ps1          # A1_MCP_URL, CF_ACCESS_CLIENT_ID, CF_ACCESS_CLIENT_SECRET
    $env:OPENAI_API_KEY = Read-Host 'OpenAI API key'
    python agent_tasks.py --dry-run                    # show tasks, no API calls
    python agent_tasks.py --models luna,terra          # run tasks.json on each model
    python agent_tasks.py --models luna,terra --measure-results results/<measure run>
    python agent_tasks.py --report-only results/agent-<run> [--measure-results results/<measure run>]

Outputs go to results/agent-<timestamp>/ (git-ignored).
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from measure import ASSUMPTIONS, HERE, PRICING, client_for, monthly, openai_usage, price, step_averages

ALLOWED_TOOLS = ["browser_navigate", "browser_navigate_back", "browser_snapshot", "browser_find",
                 "browser_click", "browser_wait_for", "browser_tabs"]


def mcp_tool() -> dict:
    missing = [v for v in ("A1_MCP_URL", "CF_ACCESS_CLIENT_ID", "CF_ACCESS_CLIENT_SECRET") if not os.environ.get(v)]
    if missing:
        sys.exit(f"Missing {', '.join(missing)}. Run: . ..\\browser-flows\\set-credentials.ps1")
    return {"type": "mcp", "server_label": "browser", "server_url": os.environ["A1_MCP_URL"],
            "headers": {"CF-Access-Client-Id": os.environ["CF_ACCESS_CLIENT_ID"],
                        "CF-Access-Client-Secret": os.environ["CF_ACCESS_CLIENT_SECRET"]},
            "allowed_tools": ALLOWED_TOOLS, "require_approval": "never"}


def parse_status(text: str) -> str:
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        return json.loads(m.group(0)).get("status", "unparsed") if m else "no-json"
    except json.JSONDecodeError:
        return "unparsed"


def run_task(model_key: str, task: dict, A: dict, effort: str) -> dict:
    p = PRICING[model_key]
    if p["provider"] != "openai":
        sys.exit(f"agent_tasks.py supports OpenAI models only; got {model_key}")
    rules = (HERE / "prompts" / "agent_rules.md").read_text(encoding="utf-8")
    prompt = (HERE / "prompts" / f"agent_{task['kind']}.md").read_text(encoding="utf-8").replace("{url}", task["url"])
    started = time.time()
    try:
        resp = client_for("openai").responses.create(
            model=p["model"], instructions=rules, input=prompt, tools=[mcp_tool()],
            reasoning={"effort": effort}, max_tool_calls=A["agent"]["max_tool_calls"][task["kind"]],
            max_output_tokens=16000)
    except Exception as e:  # keep going with other tasks/models
        return {"model": model_key, "task": task["id"], "kind": task["kind"], "status": "api-error",
                "error": str(e)[:500], "cost_usd": 0.0, "tool_calls": 0, "tool_errors": 0,
                "seconds": round(time.time() - started, 1)}
    items = getattr(resp, "output", []) or []
    calls = [i for i in items if getattr(i, "type", "") == "mcp_call"]
    usage = openai_usage(resp.usage)
    return {"model": model_key, "task": task["id"], "kind": task["kind"], "status": parse_status(resp.output_text),
            "usage": usage, "cost_usd": price(model_key, usage), "tool_calls": len(calls),
            "tool_errors": sum(1 for c in calls if getattr(c, "error", None)),
            "tools_used": [getattr(c, "name", "?") for c in calls],
            "seconds": round(time.time() - started, 1), "output": resp.output_text}


def write_report(run_dir: Path, measure_dir) -> None:
    results = json.loads((run_dir / "tasks.json").read_text(encoding="utf-8"))
    A = json.loads(ASSUMPTIONS.read_text(encoding="utf-8"))
    ag = A["agent"]
    L = [f"# Agent task measurement — {run_dir.name}", "",
         "One task = one Responses API request with A-1 as a remote MCP server. Cost includes reasoning tokens "
         "and the tool list sent to the model.", "",
         "## Per task", "",
         "| Model | Task | Status | Tool calls (errors) | Input tokens | Output (reasoning) | Cost | Seconds |",
         "|---|---|---|---|---|---|---|---|"]
    by = {}
    for r in results:
        u = r.get("usage", {"input": 0, "cached": 0, "output": 0, "reasoning": 0})
        L.append(f"| {r['model']} | {r['task']} | {r['status']} | {r['tool_calls']} ({r['tool_errors']}) | "
                 f"{u['input'] + u['cached']:,} | {u['output']:,} ({u.get('reasoning', 0):,}) | "
                 f"${r['cost_usd']:.4f} | {r['seconds']} |")
        k = by.setdefault(r["model"], {}).setdefault(r["kind"], {"n": 0, "ok": 0, "cost": 0.0})
        k["n"] += 1
        k["ok"] += r["status"] == "done"
        k["cost"] += r["cost_usd"]

    L += ["", "## Per model", "", "| Model | Kind | Success | Avg cost per task |", "|---|---|---|---|"]
    nav = {}
    for m, kinds in by.items():
        for kind, k in kinds.items():
            L.append(f"| {m} | {kind} | {k['ok']}/{k['n']} | ${k['cost'] / k['n']:.4f} |")
        if all(x in kinds for x in ("search", "vacancy", "company")):
            avg = {kind: kinds[kind]["cost"] / kinds[kind]["n"] for kind in kinds}
            nav[m] = (ag["search_tasks_per_run"] * avg["search"] + ag["vacancy_tasks_per_run"] * avg["vacancy"]
                      + ag["company_tasks_per_run"] * avg["company"])

    L += ["", "## Per run (one profile) and per month", ""]
    if not nav:
        L.append("Not enough task kinds measured for a projection (need search, vacancy and company).")
    else:
        writing = {}
        if measure_dir:
            steps = step_averages(json.loads((Path(measure_dir) / "calls.json").read_text(encoding="utf-8")))
            for name, mix in ag["writing_mixes"].items():
                try:
                    writing[name] = (A["vacancies_detailed_per_run"] * steps[mix["filter"]]["filter"]["cost"]
                                     + A["vacancies_tailored_per_run"] * steps[mix["tailor"]]["tailor"]["cost"]
                                     + A["vacancies_tailored_per_run"] * A["review_rounds_per_resume"]
                                     * steps[mix["review"]]["review"]["cost"])
                except KeyError:
                    pass
        L += ["| Browsing model | Writing | Per run | " + " | ".join(s["name"] for s in A["scenarios"]) + " |",
              "|---|---|---|" + "---|" * len(A["scenarios"])]
        for m, nav_cost in nav.items():
            for wname, wcost in (writing.items() if writing else [("not included", 0.0)]):
                total = nav_cost + wcost
                L.append(f"| {m} | {wname} | ${total:.3f} | " + " | ".join(f"${x:.2f}/mo" for x in monthly(total, A)) + " |")
        if not writing:
            L += ["", "Writing steps (filter, tailor, review) not included: pass `--measure-results`."]
    (run_dir / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Report: {run_dir / 'report.md'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="luna,terra")
    ap.add_argument("--tasks", type=Path, default=HERE / "tasks.json")
    ap.add_argument("--measure-results", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-only", type=Path)
    args = ap.parse_args()

    if args.report_only:
        write_report(args.report_only, args.measure_results)
        return
    tasks = json.loads(args.tasks.read_text(encoding="utf-8"))["tasks"]
    bad = [t["id"] for t in tasks if "<" in t["url"]]
    models = [m.strip() for m in args.models.split(",")]
    for t in tasks:
        print(f"  {t['id']:20} {t['kind']:8} {t['url']}")
    if bad:
        sys.exit(f"Fill in the placeholders in {args.tasks.name}: {', '.join(bad)}")
    if args.dry_run:
        return
    A = json.loads(ASSUMPTIONS.read_text(encoding="utf-8"))
    effort = A.get("reasoning_effort", {}).get("agent_task", "low")
    run_dir = HERE / "results" / ("agent-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    run_dir.mkdir(parents=True)
    results = []
    for m in models:
        print(f"== {m}")
        for t in tasks:
            r = run_task(m, t, A, effort)
            results.append(r)
            print(f"  {t['id']:20} {r['status']:9} calls={r['tool_calls']:>2} ${r['cost_usd']:.4f} {r['seconds']}s")
            (run_dir / "tasks.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
            time.sleep(5)  # be slow with the job boards
    write_report(run_dir, args.measure_results)
    print(f"Spent on this measurement: ${sum(r['cost_usd'] for r in results):.3f}")


if __name__ == "__main__":
    main()
