from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from agents import trace
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from temporalio.client import Client, WorkflowFailureError
from temporalio.contrib.openai_agents import ModelActivityParameters, OpenAIAgentsPlugin
from temporalio.envconfig import ClientConfig

import ledger_store
from transfer_workflow import TransferWorkflow
from worker import TASK_QUEUE

FRONTEND_INDEX = Path(__file__).parent.parent / "frontend" / "index.html"

client: Client | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    plugin = OpenAIAgentsPlugin(
        model_params=ModelActivityParameters(start_to_close_timeout=timedelta(seconds=60))
    )
    config = ClientConfig.load_client_connect_config()
    config.setdefault("target_host", "localhost:7233")
    client = await Client.connect(**config, plugins=[plugin])
    yield


app = FastAPI(title="Ledger Bank - Solution Backend", lifespan=lifespan)


@app.get("/")
def frontend() -> FileResponse:
    # Served from the same origin as the API, so the frontend never needs a cross-origin fetch,
    # CORS config, or Instruqt's per-subdomain auth cookie at all - the network control panel's
    # own Flask app (docker/proxy/controlpanel.py) uses this same same-origin pattern.
    return FileResponse(FRONTEND_INDEX)


class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: float
    spoof_location: str | None = None


@app.get("/accounts/{account_id}")
def get_account(account_id: str) -> dict:
    try:
        return ledger_store.get_account(account_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no such account: {account_id}")


@app.post("/transfer")
async def start_transfer(body: TransferRequest) -> dict:
    workflow_id = f"transfer-{uuid.uuid4()}"
    with trace("TransferWorkflow"):
        await client.start_workflow(
            TransferWorkflow.run,
            args=[body.from_account, body.to_account, body.amount, body.spoof_location],
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
    return {"workflow_id": workflow_id, "status": "pending"}


@app.get("/transfer/{workflow_id}")
async def get_transfer_status(workflow_id: str) -> dict:
    handle = client.get_workflow_handle(workflow_id)
    description = await handle.describe()
    status = description.status.name if description.status else "UNKNOWN"

    if status == "COMPLETED":
        result = await handle.result()
        return {"workflow_id": workflow_id, "status": status, "result": result}
    if status == "FAILED":
        try:
            await handle.result()
        except WorkflowFailureError as exc:
            return {"workflow_id": workflow_id, "status": status, "error": str(exc.cause or exc)}
    return {"workflow_id": workflow_id, "status": status}
