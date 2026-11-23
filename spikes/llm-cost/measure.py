"""Measure LLM cost per pipeline step on real page snapshots from spike #2.

Runs each step of the pipeline (one short, focused LLM call per step) on recorded
snapshots, for several models, and projects cost per run and per month.

Usage:
    python measure.py --list-models                      # check model ids available to your key
    python measure.py --resume cv.md --requirements req.md --dry-run
    python measure.py --resume cv.md --requirements req.md                # luna,terra,sol
    python measure.py --resume cv.md --requirements req.md --models luna,sol
    python measure.py --report-only results/<run>        # recompute after editing assumptions.json

Needs: OPENAI_API_KEY and `pip install openai` (ANTHROPIC_API_KEY and `pip install anthropic`
only for Claude models). `pip install pypdf` for PDF inputs.
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
PRICING = {k: v for k, v in json.loads((HERE / "pricing.json").read_text(encoding="utf-8")).items()
           if not k.startswith("_")}
ASSUMPTIONS = HERE / "assumptions.json"
STEPS = ["extract_list", "extract_vacancy", "filter", "dossier", "tailor", "review"]
MAX_OUTPUT = {"extract_list": 3000, "extract_vacancy": 1500, "filter": 400,
              "dossier": 1200, "tailor": 4000, "review": 1000}
DOSSIER_HINTS = ("Resumen", "Opiniones", "Sueldo", "Entrevista", "Overview", "Reviews", "Salaries", "Interview")


# ---------- inputs ----------

def read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            sys.exit("PDF input needs: python -m pip install pypdf (or pass a .md / .txt file)")
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

def price(model_key: str, u: dict) -> float:
    """u: input (uncached), cached, cache_write, output (incl. reasoning) tokens."""
    p = PRICING[model_key]
    prompt = u["input"] + u["cached"] + u["cache_write"]
    if "long_prompt" in p and prompt > p["long_prompt"]["threshold_tokens"]:
        p = {**p, **p["long_prompt"]}
    return (u["input"] * p["input"] + u["cached"] * p["cached_input"]
            + u["cache_write"] * p.get("cache_write", p["input"]) + u["output"] * p["output"]) / 1e6


# ---------- API ----------

_clients = {}


def client_for(provider: str):
    if provider not in _clients:
        if provider == "openai":
            if not os.environ.get("OPENAI_API_KEY"):
                sys.exit("Set OPENAI_API_KEY first")
            try:
                import openai
            except ImportError:
                sys.exit("Missing package. Run: python -m pip install openai")
            _clients[provider] = openai.OpenAI()
        else:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                sys.exit("Set ANTHROPIC_API_KEY first")
            try:
                import anthropic
            except ImportError:
                sys.exit("Missing package. Run: python -m pip install anthropic")
            _clients[provider] = anthropic.Anthropic()
    return _clients[provider]


def openai_usage(u) -> dict:
    cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
    reasoning = getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", 0) or 0
    return {"input": u.input_tokens - cached, "cached": cached, "cache_write": 0,
            "output": u.output_tokens, "reasoning": reasoning}


def complete(model_key: str, system: str, user: str, max_output: int, effort: str) -> tuple:
    """Returns (text, normalized usage)."""
    p = PRICING[model_key]
    client = client_for(p["provider"])
    if p["provider"] == "openai":
        resp = client.responses.create(model=p["model"], instructions=system, input=user,
                                       max_output_tokens=max_output * 4,  # room for reasoning tokens
                                       reasoning={"effort": effort})
        return resp.output_text or "", openai_usage(resp.usage)
    resp = client.messages.create(model=p["model"], max_tokens=max_output, system=system,
                                  messages=[{"role": "user", "content": user}])
    u = resp.usage
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return text, {"input": u.input_tokens, "cached": getattr(u, "cache_read_input_tokens", 0) or 0,
                  "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
                  "output": u.output_tokens, "reasoning": 0}


def run_model(model_key: str, inputs: dict, resume: str, requirements: str, efforts: dict) -> list:
    out = []

    def do(step, user):
        system = (HERE / "prompts" / f"{step}.md").read_text(encoding="utf-8")
        started = time.time()
        text, usage = complete(model_key, system, user, MAX_OUTPUT[step], efforts.get(step, "low"))
        r = {"model": model_key, "step": step, "usage": usage, "cost_usd": price(model_key, usage),
             "seconds": round(time.time() - started, 1), "output": text}
        out.append(r)
        print(f"  {model_key:6} {step:15} in={usage['input'] + usage['cached']:>7,} out={usage['output']:>6,} "
              f"(reasoning {usage['reasoning']:,}) ${r['cost_usd']:.4f} {r['seconds']}s")
        return text

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
        a = avg.setdefault(c["model"], {}).setdefault(
            c["step"], {"n": 0, "in": 0, "out": 0, "reasoning": 0, "cost": 0.0, "sec": 0.0})
        u = c["usage"]
        a["n"] += 1
        a["in"] += u["input"] + u["cached"] + u["cache_write"]
        a["out"] += u["output"]
        a["reasoning"] += u.get("reasoning", 0)
        a["cost"] += c["cost_usd"]
        a["sec"] += c["seconds"]
    for steps in avg.values():
        for a in steps.values():
            for k in ("in", "out", "reasoning", "cost", "sec"):
                a[k] /= a["n"]
    return avg


def nav_fallback_cost(model_key: str, A: dict) -> float:
    nf, p = A["nav_fallback"], PRICING[model_key]
    ctx, cached = nf["context_tokens_per_turn"], nf["cached_share_after_first_turn"]
    per_fallback = (ctx * p["input"]
                    + (nf["turns"] - 1) * ctx * (cached * p["cached_input"] + (1 - cached) * p["input"])
                    + nf["turns"] * nf["output_tokens_per_turn"] * p["output"]) / 1e6
    return A["vacancies_detailed_per_run"] * nf["share_of_vacancies"] * per_fallback


def run_cost(avg: dict, mix: dict, A: dict) -> tuple:
    """Cost of one run of one profile for a step->model mix. Returns (total, per-step dict) or (None, None)."""
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
    parts["nav_fallback (estimate)"] = nav_fallback_cost(mix.get("nav_fallback", mix["default"]), A)
    return sum(parts.values()), parts


def monthly(total: float, A: dict) -> list:
    return [total * s["profiles"] * s["runs_per_week"] * 52 / 12 for s in A["scenarios"]]


def write_report(run_dir: Path) -> None:
    calls = json.loads((run_dir / "calls.json").read_text(encoding="utf-8"))
    A = json.loads(ASSUMPTIONS.read_text(encoding="utf-8"))
    avg = step_averages(calls)
    L = [f"# LLM cost measurement — {run_dir.name}", "",
         "Prices from `pricing.json`; volumes from `assumptions.json`. Tokens include system prompts; "
         "output includes reasoning tokens.", "",
         "## Per step (average per call)", "",
         "| Model | Step | Calls | Input tokens | Output tokens | of which reasoning | Cost per call | Seconds |",
         "|---|---|---|---|---|---|---|---|"]
    for m, steps in avg.items():
        for s in STEPS:
            if s in steps:
                a = steps[s]
                L.append(f"| {m} | {s} | {a['n']} | {a['in']:,.0f} | {a['out']:,.0f} | {a['reasoning']:,.0f} | "
                         f"${a['cost']:.4f} | {a['sec']:.1f} |")
    L += ["", "## Per run (one profile) and per month", "",
          "| Mix | Cost per run | Cost per tailored vacancy | " + " | ".join(s["name"] for s in A["scenarios"]) + " |",
          "|---|---|---|" + "---|" * len(A["scenarios"])]
    details = []
    for name, mix in A["mixes"].items():
        total, parts = run_cost(avg, mix, A)
        if total is None:
            continue
        L.append(f"| {name} | ${total:.3f} | ${total / A['vacancies_tailored_per_run']:.3f} | "
                 + " | ".join(f"${x:.2f}/mo" for x in monthly(total, A)) + " |")
        details.append((name, total, parts))
    L += ["", "## Where the money goes (per run)", ""]
    for name, total, parts in details:
        L.append(f"**{name}** — " + ", ".join(f"{k} {v / total:.0%}" for k, v in sorted(parts.items(), key=lambda x: -x[1])))
        L.append("")
    (run_dir / "report.md").write_text("\n".join(L), encoding="utf-8")
    print(f"Report: {run_dir / 'report.md'}")


# ---------- main ----------

def list_models() -> None:
    names = sorted(m.id for m in client_for("openai").models.list() if m.id.startswith("gpt-6"))
    print("\n".join(names) or "No gpt-6* models visible to this key")
    configured = {v["model"] for v in PRICING.values() if v["provider"] == "openai"}
    missing = configured - set(names)
    if missing:
        print(f"\nNot available, fix pricing.json: {', '.join(sorted(missing))}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recordings", type=Path, default=HERE.parent / "browser-flows" / "recordings")
    ap.add_argument("--resume", type=Path)
    ap.add_argument("--requirements", type=Path)
    ap.add_argument("--models", default="luna,terra,sol")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-only", type=Path)
    ap.add_argument("--list-models", action="store_true")
    args = ap.parse_args()

    if args.list_models:
        list_models()
        return
    if args.report_only:
        write_report(args.report_only)
        return
    if not (args.resume and args.requirements):
        sys.exit("--resume and --requirements are required")
    models = [m.strip() for m in args.models.split(",")]
    for m in models:
        if m not in PRICING:
            sys.exit(f"Unknown model '{m}'. Known: {', '.join(PRICING)}")

    inputs = pick_inputs(args.recordings)
    resume, requirements = read_text(args.resume), read_text(args.requirements)
    print(f"Inputs: list page {inputs['list']['result_chars']:,} chars; "
          f"vacancies {[c['result_chars'] for c in inputs['vacancies']]}; "
          f"company pages {[c['result_chars'] for c in inputs['companies']]}; "
          f"resume {len(resume):,}; requirements {len(requirements):,} chars")
    if args.dry_run:
        return

    efforts = json.loads(ASSUMPTIONS.read_text(encoding="utf-8")).get("reasoning_effort", {})
    run_dir = HERE / "results" / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True)
    calls = []
    for m in models:
        print(f"== {m}")
        calls += run_model(m, inputs, resume, requirements, efforts)
        (run_dir / "calls.json").write_text(json.dumps(calls, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(run_dir)
    print(f"Spent on this measurement: ${sum(c['cost_usd'] for c in calls):.3f}")


if __name__ == "__main__":
    main()
