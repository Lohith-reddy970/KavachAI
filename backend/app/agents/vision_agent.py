"""Vision agent - detects equipment regions in the P&ID schematic.

Uses the configured multimodal vision model for images. The demo still returns
fixture bounding boxes because model text is not parsed into coordinates.
"""
from __future__ import annotations

from pathlib import Path

from .. import config
from ..models.providers import GenerationResult, generate_with_fallback
from ..services import scenario
from .base import BaseAgent, RunContext


class VisionAgent(BaseAgent):
    name = "vision_agent"

    def run(self, ctx: RunContext) -> RunContext:
        uploaded = ctx.artifacts.get("document")
        if uploaded:
            path = Path(uploaded["path"])
            if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                mode = ctx.artifacts.get("analysis_mode", "risk_review")
                if mode != "summary":
                    ctx.add_step(
                        self.name,
                        "Image analysis skipped for selected task",
                        status="skipped",
                        detail=(f"{mode.replace('_', ' ')} requires extracted text. "
                                "Select Summary for a local visual description; OCR is not enabled."),
                    )
                    return ctx
                result = self._analyze_image(
                    path, ctx.artifacts.get("analysis_profile", "general"))
                if result:
                    self._store_result(ctx, result)
                    ctx.add_step(
                        self.name,
                        "Uploaded image analysis completed",
                        detail=self._result_detail(result),
                    )
                else:
                    ctx.add_step(self.name, "Uploaded image could not be read",
                                 status="warning", detail=uploaded["filename"])
                return ctx
            # The canned regions describe the demo P&ID only; never attribute
            # them to a user's file.
            ctx.add_step(self.name, "Vision analysis skipped", status="skipped",
                         detail="No image input in this document; text files are handled "
                                "by local extraction and source-term analysis.")
            return ctx

        pid_path = config.DEMO_DATA_DIR / "plant_pid.png"
        result = self._analyze_image(pid_path, ctx.artifacts.get("analysis_profile", "industrial"))
        if result:
            self._store_result(ctx, result)
            ctx.add_step(self.name, "P&ID image analysis completed",
                         detail=self._result_detail(result))

        # Deterministic pseudo-regions for each equipment item on the P&ID.
        # The visual model response is preserved above; bounding boxes remain
        # fixed fixture data because the prototype has no region-coordinate parser.
        regions = []
        for i, eq in enumerate(scenario.EQUIPMENT):
            regions.append({
                "equipment_id": eq["id"],
                "type": eq["type"],
                "bbox": [60 + i * 150, 120, 130, 90],
                "confidence": round(0.9 + (i % 3) * 0.02, 2),
            })
        ctx.artifacts["pid_regions"] = regions
        ctx.add_step(self.name, "P&ID regions detected",
                     detail=f"Detected {len(regions)} equipment regions: "
                             + ", ".join(r["equipment_id"] for r in regions)
                             + "; demo bounding boxes are fixture-based.")
        return ctx

    @staticmethod
    def _analyze_image(path: Path, profile_id: str) -> GenerationResult | None:
        try:
            image = path.read_bytes()
        except OSError:
            return None
        if profile_id == "industrial":
            prompt = (
                "Describe the attached industrial image or schematic. Transcribe only "
                "readable equipment tags and labels, and describe visible components "
                "and connections. State uncertainty; do not infer measurements or defects."
            )
        else:
            prompt = (
                "Describe the attached document image. Summarize its visible structure "
                "and transcribe only text that is clearly readable. State uncertainty "
                "instead of guessing missing text."
            )
        return generate_with_fallback(prompt, role="vision", images=[image])

    @staticmethod
    def _store_result(ctx: RunContext, result: GenerationResult) -> None:
        ctx.artifacts["vision_analysis"] = result.text
        ctx.artifacts["vision_model"] = result.model
        ctx.artifacts["vision_provider"] = result.provider

    @staticmethod
    def _result_detail(result: GenerationResult) -> str:
        excerpt = " ".join(result.text.split())[:360]
        return (f"model={result.model}; provider={result.provider}; "
                f"unverified visual output: {excerpt}")
