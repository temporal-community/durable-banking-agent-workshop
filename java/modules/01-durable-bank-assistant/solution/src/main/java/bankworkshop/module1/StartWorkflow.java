package bankworkshop.module1;

import io.temporal.client.WorkflowClient;
import io.temporal.client.WorkflowOptions;
import io.temporal.serviceclient.WorkflowServiceStubs;
import io.temporal.serviceclient.WorkflowServiceStubsOptions;
import java.util.UUID;

public final class StartWorkflow {

  public static void main(String[] args) {
    String question = args.length > 0 ? args[0] : "What is my account balance?";

    WorkflowServiceStubs service =
        WorkflowServiceStubs.newServiceStubs(
            WorkflowServiceStubsOptions.newBuilder().setTarget(Worker.TARGET).build());
    WorkflowClient client = WorkflowClient.newInstance(service);

    BankAssistantWorkflow workflow =
        client.newWorkflowStub(
            BankAssistantWorkflow.class,
            WorkflowOptions.newBuilder()
                .setWorkflowId("durable-bank-assistant-" + UUID.randomUUID())
                .setTaskQueue(Worker.TASK_QUEUE)
                .build());

    String answer = workflow.answer(question);
    System.out.println(answer);
    System.exit(0);
  }
}
