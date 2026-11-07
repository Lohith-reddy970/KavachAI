"""Security agent - the first gate in the KAVACH pipeline.

Confirms airgapped mode, verifies the active model provider is local (not an
external cloud API), and records that the run is permitted to proceed.
"""
from __future__ import annotations

from .. import config
from ..models.providers import get_provider
from ..security.guard import assert_provider_allowed
from .base import BaseAgent, RunContext


class SecurityAgent(BaseAgent):
    name = "security_agent"

    def run(self, ctx: RunContext) -> RunContext:
        provider = get_provider()
        assert_provider_allowed(provider.name, is_external=provider.is_external)
        mode = config.KAVACH_MODE
        ctx.artifacts["security"] = {
            "mode": mode,
            "provider": provider.name,
            "external_blocked": config.IS_AIRGAPPED,
            "network": "airgapped" if config.IS_AIRGAPPED else "open",
        }
        ctx.add_step(
            self.name,
            "Provider policy checked",
            detail=f"KAVACH_MODE={mode}; local provider '{provider.name}' authorized; "
                   "model connections are restricted by application policy; host isolation is deployment-managed.",
        )
        return ctx
