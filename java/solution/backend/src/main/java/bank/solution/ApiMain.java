package bank.solution;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.UUID;

import io.javalin.Javalin;
import io.javalin.http.Context;
import io.javalin.http.HttpStatus;
import io.temporal.api.enums.v1.WorkflowExecutionStatus;
import io.temporal.client.WorkflowClient;
import io.temporal.client.WorkflowFailedException;
import io.temporal.client.WorkflowOptions;
import io.temporal.client.WorkflowStub;
import io.temporal.serviceclient.WorkflowServiceStubs;
import io.temporal.serviceclient.WorkflowServiceStubsOptions;

/** Same-origin API + frontend, mirroring solution/backend/main.py. POST /transfer starts the
 * workflow and returns immediately; GET /transfer/{id} polls status. */
public final class ApiMain {
    private static final Path FRONTEND_INDEX = Path.of(
            System.getProperty("frontend.index", "../../../solution/frontend/index.html"));

    private static WorkflowClient client;

    public static void main(String[] args) {
        String target = System.getenv().getOrDefault("TEMPORAL_ADDRESS", "127.0.0.1:7233");
        WorkflowServiceStubs service = WorkflowServiceStubs.newServiceStubs(
                WorkflowServiceStubsOptions.newBuilder().setTarget(target).build());
        client = WorkflowClient.newInstance(service);

        Javalin.create(config -> {
            config.routes.get("/", ctx -> {
                ctx.contentType("text/html");
                ctx.result(Files.readAllBytes(FRONTEND_INDEX));
            });
            config.routes.get("/accounts/{id}", ApiMain::getAccount);
            config.routes.post("/transfer", ApiMain::startTransfer);
            config.routes.get("/transfer/{id}", ApiMain::getTransferStatus);
        }).start(Integer.parseInt(System.getenv().getOrDefault("PORT", "8001")));
    }

    private static void getAccount(Context ctx) {
        String id = ctx.pathParam("id");
        try {
            ctx.json(LedgerStore.getAccount(id));
        } catch (LedgerStore.NoSuchAccountException e) {
            ctx.status(HttpStatus.NOT_FOUND).json(Map.of("detail", e.getMessage()));
        }
    }

    private record TransferRequest(String from_account, String to_account, double amount, String spoof_location) {}

    private static void startTransfer(Context ctx) {
        TransferRequest body = ctx.bodyAsClass(TransferRequest.class);
        String workflowId = "transfer-" + UUID.randomUUID();
        TransferWorkflow workflow = client.newWorkflowStub(TransferWorkflow.class,
                WorkflowOptions.newBuilder()
                        .setWorkflowId(workflowId)
                        .setTaskQueue(WorkerMain.TASK_QUEUE)
                        .build());
        WorkflowClient.start(workflow::run, body.from_account(), body.to_account(), body.amount(), body.spoof_location());
        ctx.json(Map.of("workflow_id", workflowId, "status", "pending"));
    }

    private static void getTransferStatus(Context ctx) {
        String workflowId = ctx.pathParam("id");
        WorkflowStub stub = client.newUntypedWorkflowStub(workflowId);
        WorkflowExecutionStatus status = stub.describe().getWorkflowExecutionInfo().getStatus();
        String statusName = status.name().replace("WORKFLOW_EXECUTION_STATUS_", "");

        if (status == WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_COMPLETED) {
            LedgerStore.Account result = stub.getResult(LedgerStore.Account.class);
            ctx.json(Map.of("workflow_id", workflowId, "status", statusName, "result", result));
            return;
        }
        if (status == WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_FAILED) {
            try {
                stub.getResult(LedgerStore.Account.class);
            } catch (WorkflowFailedException e) {
                Throwable cause = e.getCause() != null ? e.getCause() : e;
                ctx.json(Map.of("workflow_id", workflowId, "status", statusName, "error", String.valueOf(cause.getMessage())));
                return;
            }
        }
        ctx.json(Map.of("workflow_id", workflowId, "status", statusName));
    }
}
