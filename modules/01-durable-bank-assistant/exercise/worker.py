import asyncio
from datetime import timedelta

from temporalio.client import Client
from temporalio.contrib.openai_agents import ModelActivityParameters, OpenAIAgentsPlugin
from temporalio.envconfig import ClientConfig
from temporalio.worker import Worker

from agent_workflow import BankAssistantWorkflow

TASK_QUEUE = "durable-bank-assistant-tq"


async def main() -> None:
    plugin = OpenAIAgentsPlugin(
        model_params=ModelActivityParameters(
            start_to_close_timeout=timedelta(seconds=60),
        )
    )

    config = ClientConfig.load_client_connect_config()
    config.setdefault("target_host", "localhost:7233")
    client = await Client.connect(**config, plugins=[plugin])

    worker = Worker(client, task_queue=TASK_QUEUE, workflows=[BankAssistantWorkflow])
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
