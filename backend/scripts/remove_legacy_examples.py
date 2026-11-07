"""Remove provable legacy example records, preserving uploaded documents.

Run from the repository root: python backend/scripts/remove_legacy_examples.py
Preview is the default. Add --apply to remove the listed records and reports.
Stop the backend before applying this one-time cleanup.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def cleanup(database: Path, root: Path, apply: bool = False) -> dict:
    if not database.exists():
        return {"documents": 0, "runs": 0, "reports": 0, "applied": apply}
    root = root.resolve()
    examples = root / "demo-data"
    generated = root / "generated"
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        documents = list(connection.execute("SELECT id, filename, path FROM documents"))
        seeded = [d for d in documents if Path(d["path"]).resolve().parent == examples]
        sources = {d["filename"] for d in seeded}
        # Older industrial fixtures cited display names rather than disk names.
        sources.update({"Inspection_Report_2026.pdf", "Engineering_Calculation.pdf", "Equipment_Manual.pdf"})
        uploaded_names = {d["filename"] for d in documents if d not in seeded}
        uploaded_names_lower = {name.lower() for name in uploaded_names}
        run_ids = []
        for run in connection.execute("SELECT id, scenario FROM agent_runs"):
            evidence = list(connection.execute("SELECT source FROM evidence WHERE run_id=?", (run["id"],)))
            cited = {e["source"] for e in evidence}
            document_name = (run["scenario"] or "").removeprefix("document:")
            # A duplicate uploaded filename makes provenance ambiguous: retain it.
            if cited and cited <= sources and not {name.lower() for name in cited} & uploaded_names_lower:
                run_ids.append(run["id"])
            elif not cited and document_name in sources - uploaded_names:
                run_ids.append(run["id"])
        reports = []
        for run_id in run_ids:
            reports.extend(connection.execute("SELECT path FROM deliverables WHERE run_id=?", (run_id,)))
        report_paths = {Path(r["path"]).resolve() for r in reports
                        if Path(r["path"]).resolve().parent == generated}
        # Remove orphan exports only when their paired text explicitly identifies an example.
        for text in generated.glob("kavach_report_run*.txt"):
            content = text.read_text(encoding="utf-8", errors="replace")
            if "FICTIONAL" in content:
                report_paths.update(p.resolve() for p in generated.glob(text.stem + ".*") if p.is_file())
        if apply:
            with connection:
                for run_id in run_ids:
                    connection.execute("DELETE FROM reviews WHERE finding_id IN (SELECT id FROM findings WHERE run_id=?)", (run_id,))
                    for table in ("evidence", "findings", "agent_steps", "deliverables"):
                        connection.execute(f"DELETE FROM {table} WHERE run_id=?", (run_id,))
                    connection.execute("DELETE FROM tasks WHERE run_id=? OR id IN (SELECT task_id FROM agent_runs WHERE id=?)", (run_id, run_id))
                    connection.execute("DELETE FROM agent_runs WHERE id=?", (run_id,))
                for doc in seeded:
                    connection.execute("DELETE FROM documents WHERE id=?", (doc["id"],))
            for path in report_paths:
                if path.parent != generated:
                    raise ValueError("Report path escaped the generated directory")
                path.unlink(missing_ok=True)
            for document in seeded:
                path = Path(document["path"]).resolve()
                if path.parent != examples:
                    raise ValueError("Example path escaped the legacy directory")
                path.unlink(missing_ok=True)
        return {"documents": len(seeded), "runs": len(run_ids), "reports": len(report_paths), "applied": apply}
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    print(cleanup(args.database or root / "backend" / "kavach.db", root, args.apply))
