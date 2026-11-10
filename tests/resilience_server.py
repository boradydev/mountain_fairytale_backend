"""Test-only child entrypoint; production modules are never edited."""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

if __name__ == "__main__":
    import uvicorn

    from src.common.api.app import fastapi_app
    from src.feat.dashboard_updates.app.dashboard_changes import DashboardChanges
    from src.feat.delivery_document.infra.delivery_document_uow import DeliveryDocumentsUOW

    gate = Path(os.environ["RESILIENCE_GATE"])
    original = DeliveryDocumentsUOW.commit
    original_wait = DashboardChanges.wait

    async def observed_wait(self, *, server_id, version, timeout):
        if server_id == self._server_id and version == self._version and timeout > 0:
            gate.with_suffix(".polling").write_text("waiting", encoding="utf-8")
        return await original_wait(self, server_id=server_id, version=version, timeout=timeout)

    async def gated_commit(self, events):
        if gate.exists():
            # All aggregate SQL and audit are flushed, but COMMIT has not occurred.
            await self._event_publisher.publish_many(events=events)
            await self._session.flush()
            gate.with_suffix(".reached").write_text("flushed-before-commit", encoding="utf-8")
            while gate.exists():
                await asyncio.sleep(0.02)
            raise RuntimeError("resilience: deterministic rollback before COMMIT")
        await original(self, events)

    DeliveryDocumentsUOW.commit = gated_commit
    DashboardChanges.wait = observed_wait
    uvicorn.run(fastapi_app, host="127.0.0.1", port=int(os.environ["RESILIENCE_PORT"]), log_level="warning")
