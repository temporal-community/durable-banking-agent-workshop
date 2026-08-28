package bank.solution;

import io.temporal.client.WorkflowClient;
import io.temporal.serviceclient.WorkflowServiceStubs;
import io.temporal.serviceclient.WorkflowServiceStubsOptions;
import io.temporal.worker.Worker;
import io.temporal.worker.WorkerFactory;

public final class WorkerMain {
    public static final String TASK_QUEUE =
            System.getenv().getOrDefault("TRANSFER_TASK_QUEUE", "solution-preview-tq-java");

    public static void main(String[] args) {
        String target = System.getenv().getOrDefault("TEMPORAL_ADDRESS", "127.0.0.1:7233");
        WorkflowServiceStubs service = WorkflowServiceStubs.newServiceStubs(
                WorkflowServiceStubsOptions.newBuilder().setTarget(target).build());
        WorkflowClient client = WorkflowClient.newInstance(service);
        WorkerFactory factory = WorkerFactory.newInstance(client);
        Worker worker = factory.newWorker(TASK_QUEUE);
        worker.registerWorkflowImplementationTypes(TransferWorkflowImpl.class);
        worker.registerActivitiesImplementations(new BankActivitiesImpl());
        factory.start();
        System.out.println("Worker started on task queue " + TASK_QUEUE);
    }
}
