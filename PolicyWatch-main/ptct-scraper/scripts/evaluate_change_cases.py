"""Runs the labelled change cases and writes docs/evidence/change_case_results.csv + summary."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from ptct.config import load_config            # noqa: E402
from ptct.evaluation import run_cases, summarise, write_csv  # noqa: E402

settings = load_config(ROOT / "config" / "sources.yaml")
results = run_cases(settings)
write_csv(results, ROOT / "docs" / "evidence" / "change_case_results.csv")
summary = summarise(results)
(ROOT / "docs" / "evidence" / "change_case_summary.json").write_text(json.dumps(summary, indent=2))
for r in results:
    print(("PASS" if r["pass"] else "FAIL"), r["case"], "| alerts:", r["actual_alerts"], "| events:", r["actual_events"])
print(json.dumps(summary, indent=2))
sys.exit(0 if summary["passed"] == summary["cases"] else 1)
