import asyncio

from temporalio.client import Client
from temporalio.envconfig import ClientConfig
from temporalio.worker import Worker

from activities import apply_transfer_to_ledger, check_transfer_for_fraud, geolocate_ip, get_account_for_transfer
from transfer_workflow import TransferWorkflow

# check-workshop's automated checks look for completed workflows on this exact task queue name
# and workflow IDs prefixed "transfer-" (see instruqt/03-durable-banking-agent/assignment.md).
TASK_QUEUE = "banking-transfer-tq"


async def main() -> None:
    config = ClientConfig.load_client_connect_config()
    config.setdefault("target_host", "localhost:7233")
    client = await Client.connect(**config)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TransferWorkflow],
        activities=[
            geolocate_ip,
            get_account_for_transfer,
            check_transfer_for_fraud,
            apply_transfer_to_ledger,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
