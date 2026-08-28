package bankworkshop.module2;

import io.temporal.client.WorkflowClient;
import io.temporal.serviceclient.WorkflowServiceStubs;
import io.temporal.serviceclient.WorkflowServiceStubsOptions;
import io.temporal.worker.WorkerFactory;

public final class Worker {

  public static final String TASK_QUEUE = "durable-bank-tools-tq-java";
  static final String TARGET = System.getenv().getOrDefault("TEMPORAL_ADDRESS", "127.0.0.1:7233");

  public static void main(String[] args) {
    WorkflowServiceStubs service =
        WorkflowServiceStubs.newServiceStubs(
            WorkflowServiceStubsOptions.newBuilder().setTarget(TARGET).build());
    WorkflowClient client = WorkflowClient.newInstance(service);

    WorkerFactory factory = WorkerFactory.newInstance(client);
    io.temporal.worker.Worker worker = factory.newWorker(TASK_QUEUE);
    worker.registerWorkflowImplementationTypes(BankAssistantWorkflowImpl.class);
    worker.registerActivitiesImplementations(new BankToolsActivitiesImpl());
    factory.start();

    System.out.println("Worker started, polling task queue " + TASK_QUEUE);
  }
}
