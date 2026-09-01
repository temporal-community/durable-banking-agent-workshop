from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from temporalio.client import Client, WorkflowFailureError
from temporalio.envconfig import ClientConfig

import ledger
from transfer_workflow import TransferWorkflow
from worker import TASK_QUEUE

FRONTEND_INDEX = Path(__file__).parent.parent / "frontend" / "index.html"

client: Client | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    config = ClientConfig.load_client_connect_config()
    config.setdefault("target_host", "localhost:7233")
    client = await Client.connect(**config)
    yield


app = FastAPI(title="Ledger Bank - Hackathon Backend", lifespan=lifespan)


@app.get("/")
def frontend() -> FileResponse:
    # Served from the same origin as the API, so the frontend never needs a cross-origin fetch,
    # CORS config, or Instruqt's per-subdomain auth cookie at all.
    return FileResponse(FRONTEND_INDEX)


class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: float
    spoof_location: str | None = None


def _root_cause(exc: BaseException) -> BaseException:
    # A workflow failure caused by an activity failure is wrapped: WorkflowFailureError.cause is
    # an ActivityError whose own generic message ("Activity task failed") isn't useful - the
    # actual reason (e.g. "no such account: Z") is further down the .cause chain.
    while getattr(exc, "cause", None) is not None:
        exc = exc.cause
    return exc


@app.get("/accounts/{account_id}")
def get_account(account_id: str) -> dict:
    try:
        return ledger.get_account(account_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no such account: {account_id}")


@app.post("/transfer")
async def start_transfer(body: TransferRequest) -> dict:
    workflow_id = f"transfer-{uuid.uuid4()}"
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
            return {"workflow_id": workflow_id, "status": status, "error": str(_root_cause(exc))}
    return {"workflow_id": workflow_id, "status": status}
