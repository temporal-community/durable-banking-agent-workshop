import asyncio
import os
from datetime import timedelta

from temporalio.client import Client
from temporalio.contrib.openai_agents import ModelActivityParameters, OpenAIAgentsPlugin
from temporalio.envconfig import ClientConfig
from temporalio.worker import Worker

from activities import apply_transfer_to_ledger, geolocate_ip, get_account_for_transfer
from transfer_workflow import TransferWorkflow

# Isolated from "banking-transfer-tq" (the convention suggested to participants for their own
# temporalized hackathon/backend) so the always-on solution preview tab never pollutes
# check-workshop's target queue. solve-workshop overrides this to "banking-transfer-tq" for its
# own verification-only run.
TASK_QUEUE = os.environ.get("TRANSFER_TASK_QUEUE", "solution-preview-tq")


async def main() -> None:
    plugin = OpenAIAgentsPlugin(
        model_params=ModelActivityParameters(
            start_to_close_timeout=timedelta(seconds=60),
        )
    )

    config = ClientConfig.load_client_connect_config()
    config.setdefault("target_host", "localhost:7233")
    client = await Client.connect(**config, plugins=[plugin])

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TransferWorkflow],
        activities=[
            geolocate_ip,
            get_account_for_transfer,
            apply_transfer_to_ledger,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
