"""Measure LLM cost per pipeline step on real page snapshots from spike #2.

Runs each step of a lean pipeline (one short, focused LLM call per step) on
recorded snapshots, for several models, and projects cost per run and per month.

Usage:
    python measure.py --resume my-resume.md --requirements my-requirements.md
    python measure.py ... --models haiku,sonnet,opus
    python measure.py ... --dry-run        # show chosen inputs and sizes, no API calls
    python measure.py --report-only results/<run>   # recompute report after editing assumptions.json

Needs: ANTHROPIC_API_KEY, `pip install anthropic` (and `pip install pypdf` for PDF inputs).
Outputs go to results/<timestamp>/ (git-ignored: they contain personal data).
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRICING = json.loads((HERE / "pricing.json").read_text(encoding="utf-8"))
STEPS = ["extract_list", "extract_vacancy", "filter", "dossier", "tailor", "review"]
MAX_TOKENS = {"extract_list": 3000, "extract_vacancy": 1500, "filter": 400,
              "dossier": 1200, "tailor": 4000, "review": 1000}
DOSSIER_HINTS = ("Resumen", "Opiniones", "Sueldo", "Entrevista", "Overview", "Reviews", "Salaries", "Interview")


# ---------- inputs ----------

def read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            sys.exit("PDF input needs: pip install pypdf (or pass a .md / .txt file)")
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8")


def load_calls(recordings: Path, prefix: str) -> list:
    dirs = sorted(d for d in recordings.iterdir() if d.is_dir() and d.name.startswith(prefix))
    if not dirs:
        sys.exit(f"No recording starting with '{prefix}' in {recordings}")
    calls = []
    for line in (dirs[0] / "calls.jsonl").read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        if not c.get("is_error") and c.get("result"):
            calls.append(c)
    return calls


def pick_inputs(recordings: Path) -> dict:
    page_tools = ("browser_snapshot", "browser_find")
    s01 = [c for c in load_calls(recordings, "01") if c["tool"] in page_tools]
    s02 = [c for c in load_calls(recordings, "02") if c["tool"] == "browser_snapshot" and c["result_chars"] > 3000]
    s03 = [c for c in load_calls(recordings, "03") if c["tool"] == "browser_snapshot" and c["result_chars"] > 2000
           and any(h in json.dumps(c.get("input")) + c["result"][:3000] for h in DOSSIER_HINTS)]
    if not (s01 and s02 and s03):
        sys.exit("Could not find list / vacancy / company snapshots in the recordings")
    return {
        "list": max(s01, key=lambda c: c["result_chars"]),
        "vacancies": sorted(s02, key=lambda c: -c["result_chars"])[:3],
        "companies": sorted(s03, key=lambda c: -c["result_chars"])[:3],
    }


# ---------- cost ----------

def price(model_key: str, usage: dict) -> float:
    p = PRICING[model_key]
    prompt = usage["input_tokens"] + usage["cache_creation_input_tokens"] + usage["cache_read_input_tokens"]
    if "long_prompt" in p and prompt > p["long_prompt"]["threshold_tokens"]:
        p = {**p, **p["long_prompt"]}
    return (usage["input_tokens"] * p["input"] + usage["output_tokens"] * p["output"]
            + usage["cache_creation_input_tokens"] * p["cache_write"]
            + usage["cache_read_input_tokens"] * p["cache_read"]) / 1e6


# ---------- API ----------

def call(client, model_key: str, step: str, user: str) -> dict:
    system = (HERE / "prompts" / f"{step}.md").read_text(encoding="utf-8")
    started = time.time()
    resp = client.messages.create(model=PRICING[model_key]["model"], max_tokens=MAX_TOKENS[step],
                                  system=system, messages=[{"role": "user", "content": user}])
    u = resp.usage
    usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
             "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
             "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0}
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return {"model": model_key, "step": step, "usage": usage, "cost_usd": price(model_key, usage),
            "seconds": round(time.time() - started, 1), "input_chars": len(system) + len(user), "output": text}


def run_model(client, model_key: str, inputs: dict, resume: str, requirements: str) -> list:
    out = []

    def do(step, user):
        r = call(client, model_key, step, user)
        out.append(r)
        print(f"  {model_key:6} {step:15} in={r['usage']['input_tokens']:>7,} out={r['usage']['output_tokens']:>6,} "
              f"${r['cost_usd']:.4f} {r['seconds']}s")
        return r["output"]

    do("extract_list", inputs["list"]["result"])
    vacancies = [do("extract_vacancy", c["result"]) for c in inputs["vacancies"]]
    for v in vacancies:
        do("filter", f"<requirements>\n{requirements}\n</requirements>\n<vacancy>\n{v}\n</vacancy>")
    for c in inputs["companies"]:
        do("dossier", c["result"])
    tailored = do("tailor", f"<resume>\n{resume}\n</resume>\n<vacancy>\n{vacancies[0]}\n</vacancy>")
    do("review", f"<original_resume>\n{resume}\n</original_resume>\n<vacancy>\n{vacancies[0]}\n</vacancy>\n"
                 f"<tailored_resume>\n{tailored}\n</tailored_resume>")
    return out


# ---------- report ----------

def step_averages(calls: list) -> dict:
    avg = {}
    for c in calls:
        a = avg.setdefault(c["model"], {}).setdefault(c["step"], {"n": 0, "in": 0, "out": 0, "cost": 0.0, "sec": 0.0})
        a["n"] += 1
        a["in"] += c["usage"]["input_tokens"] + c["usage"]["cache_creation_input_tokens"] + c["usage"]["cache_read_input_tokens"]
        a["out"] += c["usage"]["output_tokens"]
        a["cost"] += c["cost_usd"]
        a["sec"] += c["seconds"]
    for steps in avg.values():
        for a in steps.values():
            for k in ("in", "out", "cost", "sec"):
                a[k] /= a["n"]
    return avg


def run_cost(avg: dict, mix: dict, A: dict) -> tuple:
    """Cost of one run of one profile for a step->model mix. Returns (total, per-step dict)."""
    counts = {
        "extract_list": A["search_pages_per_run"],
        "extract_vacancy": A["vacancies_detailed_per_run"],
        "filter": A["vacancies_detailed_per_run"],
        "dossier": A["companies_researched_per_run"] * A["dossier_pages_per_company"],
        "tailor": A["vacancies_tailored_per_run"],
        "review": A["vacancies_tailored_per_run"] * A["review_rounds_per_resume"],
    }
    parts = {}
    for step, n in counts.items():
        m = mix.get(step, mix["default"])
        if m not in avg or step not in avg[m]:
            return None, None
        parts[step] = n * avg[m][step]["cost"]
    nf = A["nav_fallback"]
    m = mix.get("nav_fallback", mix["default"])
    p = PRICING[m]
    ctx, cached = nf["context_tokens_per_turn"], nf["cached_share_after_first_turn"]
    per_fallback = (ctx * p["input"]
                    + (nf["turns"] - 1) * ctx * (cached * p["cache_read"] + (1 - cached) * p["input"])
                    + nf["turns"] * nf["output_tokens_per_turn"] * p["output"]) / 1e6
    parts["nav_fallback (estimate)"] = A["vacancies_detailed_per_run"] * nf["share_of_vacancies"] * per_fallback
    return sum(parts.values()), parts


def write_report(run_dir: Path) -> None:
    calls = json.loads((run_dir / "calls.json").read_text(encoding="utf-8"))
    A = json.loads((HERE / "assumptions.json").read_text(encoding="utf-8"))
    avg = step_averages(calls)
    L = [f"# LLM cost measurement — {run_dir.name}", "",
         "Prices from `pricing.json`; volumes from `assumptions.json`. Tokens include system prompts.", "",
         "## Per step (average per call)", "",
         "| Model | Step | Calls | Input tokens | Output tokens | Cost per call | Seconds |", "|---|---|---|---|---|---|---|"]
    for m, steps in avg.items():
        for s in STEPS:
            if s in steps:
                a = steps[s]
                L.append(f"| {m} | {s} | {a['n']} | {a['in']:,.0f} | {a['out']:,.0f} | ${a['cost']:.4f} | {a['sec']:.1f} |")
    L += ["", "## Per run (one profile) and per month", "",
          "| Mix | Cost per run | Cost per tailored vacancy | " + " | ".join(s["name"] for s in A["scenarios"]) + " |",
          "|---|---|---|" + "---|" * len(A["scenarios"])]
    details = []
    for name, mix in A["mixes"].items():
        total, parts = run_cost(avg, mix, A)
        if total is None:
            continue
        months = [total * s["profiles"] * s["runs_per_week"] * 52 / 12 for s in A["scenarios"]]
        L.append(f"| {name} | ${total:.3f} | ${total / A['vacancies_tailored_per_run']:.3f} | "
                 + " | ".join(f"${x:.2f}/mo" for x in months) + " |")
        details.append((name, total, parts))
    L += ["", "## Where the money goes (per run)", ""]
    for name, total, parts in details:
        L.append(f"**{name}** — " + ", ".join(f"{k} {v / total:.0%}" for k, v in sorted(parts.items(), key=lambda x: -x[1])))
        L.append("")
    (run_dir / "report.md").write_text("\n".join(L), encoding="utf-8")
    print(f"Report: {run_dir / 'report.md'}")


# ---------- main ----------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recordings", type=Path, default=HERE.parent / "browser-flows" / "recordings")
    ap.add_argument("--resume", type=Path)
    ap.add_argument("--requirements", type=Path)
    ap.add_argument("--models", default="haiku,sonnet")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-only", type=Path)
    args = ap.parse_args()

    if args.report_only:
        write_report(args.report_only)
        return
    if not (args.resume and args.requirements):
        sys.exit("--resume and --requirements are required")
    models = [m.strip() for m in args.models.split(",")]
    for m in models:
        if m not in PRICING:
            sys.exit(f"Unknown model '{m}'. Known: {', '.join(k for k in PRICING if not k.startswith('_'))}")

    inputs = pick_inputs(args.recordings)
    resume, requirements = read_text(args.resume), read_text(args.requirements)
    print(f"Inputs: list page {inputs['list']['result_chars']:,} chars; "
          f"vacancies {[c['result_chars'] for c in inputs['vacancies']]}; "
          f"company pages {[c['result_chars'] for c in inputs['companies']]}; "
          f"resume {len(resume):,}; requirements {len(requirements):,} chars")
    if args.dry_run:
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first")

    import anthropic
    client = anthropic.Anthropic()
    run_dir = HERE / "results" / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True)
    calls = []
    for m in models:
        print(f"== {m}")
        calls += run_model(client, m, inputs, resume, requirements)
        (run_dir / "calls.json").write_text(json.dumps(calls, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(run_dir)
    total = sum(c["cost_usd"] for c in calls)
    print(f"Spent on this measurement: ${total:.3f}")


if __name__ == "__main__":
    main()
