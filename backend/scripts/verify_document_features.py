"""Exercise batches, evidence, and actual local document chat in isolated storage.

Run from the repository root: python backend/scripts/verify_document_features.py
Requires the configured local reasoning model. Never reads the user's Vault.
"""
from pathlib import Path
import json
import os
import sys
import tempfile
import time

backend = Path(__file__).resolve().parents[1]
scratch = backend.parent / "tmp"
scratch.mkdir(exist_ok=True)
state = Path(tempfile.mkdtemp(prefix="document-features-", dir=scratch))
assert state.resolve().is_relative_to(scratch.resolve())
os.environ.update(KAVACH_DB=str(state / "check.db"), KAVACH_UPLOADS=str(state / "uploads"),
                  KAVACH_GENERATED=str(state / "reports"), KAVACH_EMBEDDING_BACKEND="hash", KAVACH_SANDBOX_ENABLED="false")
sys.path.insert(0, str(backend))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

with TestClient(app) as client:
    docs = []
    for name, text in [("renewal.txt", b"Supplier agreement. The renewal deadline is 2030-01-12. Contact contracts@example.test."),
                       ("budget.txt", b"Project budget. Approved amount USD 2500.00. Reference PO-2026-100.")]:
        response = client.post("/api/documents/upload", files={"file": (name, text)})
        response.raise_for_status(); docs.append(response.json())
    print("Uploaded two isolated source fixtures.", flush=True)
    response = client.post("/api/analysis/batches", json={"document_ids": [d["id"] for d in docs], "analysis_mode": "extract_fields"})
    response.raise_for_status(); batch_id = response.json()["id"]
    deadline = time.monotonic() + 30
    while True:
        batch = client.get(f"/api/analysis/batches/{batch_id}").json()
        if batch["status"] in {"completed", "completed_with_errors"}:
            break
        assert time.monotonic() < deadline, "Batch timed out"
        time.sleep(.1)
    assert batch["counts"]["completed"] == 2 and batch["counts"]["error"] == 0, batch
    highlighted = 0
    for item in batch["items"]:
        run = client.get(f"/api/agents/runs/{item['run_id']}").json()
        for finding in run["findings"]:
            for evidence in finding["evidence"]:
                response = client.get(f"/api/evidence/{evidence['id']}/preview")
                response.raise_for_status(); preview = response.json()
                assert preview["text"][preview["highlight_start"]:preview["highlight_end"]] == evidence["excerpt"]
                highlighted += 1
    assert highlighted > 0
    print(f"Batch completed; verified {highlighted} source highlights. Asking the actual local model…", flush=True)
    response = client.post("/api/chat", json={"document_ids": [docs[0]["id"]], "question": "What is the renewal deadline?"})
    response.raise_for_status(); chat = response.json()
    assert chat["status"] == "cited" and "2030-01-12" in chat["answer"], chat
    assert chat["citations"] and all(c["document_id"] == docs[0]["id"] for c in chat["citations"])
    for citation in chat["citations"]:
        client.post(f"/api/documents/{citation['document_id']}/passage", json=citation).raise_for_status()
    follow_up = client.post("/api/chat", json={"document_ids": [docs[0]["id"]], "question": "What does that date refer to?", "history": [
        {"role": "user", "content": "What is the renewal deadline?"}, {"role": "assistant", "content": chat["answer"]}]})
    follow_up.raise_for_status()
    assert follow_up.json()["status"] == "cited" and "renewal" in follow_up.json()["answer"].lower(), follow_up.json()
    summary = {"batch_documents": 2, "verified_highlights": highlighted, "chat": chat, "follow_up": follow_up.json(), "isolated_storage": str(state)}
    (state / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
