package bank.hackathon;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.fail;

import java.time.Duration;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import io.temporal.client.WorkflowClient;
import io.temporal.client.WorkflowFailedException;
import io.temporal.client.WorkflowOptions;
import io.temporal.failure.ApplicationFailure;
import io.temporal.failure.TimeoutFailure;
import io.temporal.testing.TestWorkflowEnvironment;
import io.temporal.worker.Worker;

/** Exercises the two learner-facing TODOs in TransferWorkflowImpl without a real Temporal server,
 * geo-IP call, or OpenAI call - BankActivities is replaced with an in-memory FakeBankActivities so
 * these tests only depend on the workflow's own orchestration logic. */
public class TransferWorkflowTest {

    private static final String TASK_QUEUE = "test-transfer-tq";

    private TestWorkflowEnvironment testEnv;
    private WorkflowClient client;
    private Worker worker;

    @BeforeEach
    public void setUp() {
        testEnv = TestWorkflowEnvironment.newInstance();
        worker = testEnv.newWorker(TASK_QUEUE);
        worker.registerWorkflowImplementationTypes(TransferWorkflowImpl.class);
    }

    @AfterEach
    public void tearDown() {
        testEnv.close();
    }

    private TransferWorkflow newStub(String workflowId) {
        client = testEnv.getWorkflowClient();
        return client.newWorkflowStub(TransferWorkflow.class,
                WorkflowOptions.newBuilder()
                        .setWorkflowId(workflowId)
                        .setTaskQueue(TASK_QUEUE)
                        .setWorkflowExecutionTimeout(Duration.ofSeconds(20))
                        .build());
    }

    /** TODO B: applyTransferToLedger's idempotency key. The shipped code passes the constant
     * placeholder "TODO-fill-in-workflow-id" for EVERY workflow instead of the real workflow ID,
     * so the ledger's idempotency guard treats every transfer after the first as an already-seen
     * duplicate and silently skips it - two distinct transfers collapse into one applied debit. */
    @Test
    public void secondDistinctTransferIsAppliedOnlyWhenIdempotencyKeyIsTheRealWorkflowId() {
        FakeBankActivities activities = new FakeBankActivities();
        activities.approveAll = true;
        worker.registerActivitiesImplementations(activities);
        testEnv.start();

        TransferWorkflow first = newStub("test-transfer-idempotency-1");
        first.run("A", "B", 100.0, null);

        TransferWorkflow second = newStub("test-transfer-idempotency-2");
        second.run("A", "B", 50.0, null);

        double expectedBalance = FakeBankActivities.STARTING_BALANCE_A - 100.0 - 50.0;
        double actualBalance = activities.accounts.get("A").balance;
        assertEquals(expectedBalance, actualBalance, 0.001,
                "Account A's balance after two distinct transfers (100 then 50) should reflect BOTH "
                        + "debits (expected " + expectedBalance + ", got " + actualBalance + "). If this "
                        + "is off by exactly one transfer's amount, applyTransferToLedger is being called "
                        + "with the same idempotency key for every workflow instead of "
                        + "Workflow.getInfo().getWorkflowId() - fix TODO B in TransferWorkflowImpl.run().");
    }

    /** TODO C: a fraud decline's failure type. The shipped code throws a plain RuntimeException
     * from workflow code on a decline, which Temporal treats as a workflow task failure and
     * retries indefinitely rather than failing the workflow - so the workflow only stops once its
     * execution timeout fires, and the client sees a TimeoutFailure instead of the intended
     * non-retryable ApplicationFailure("FraudDeclined"). */
    @Test
    public void fraudDeclineFailsNonRetryableInsteadOfRetryingForever() {
        FakeBankActivities activities = new FakeBankActivities();
        activities.approveAll = false;
        worker.registerActivitiesImplementations(activities);
        testEnv.start();

        TransferWorkflow workflow = newStub("test-transfer-decline");
        WorkflowFailedException failure = assertThrows(WorkflowFailedException.class,
                () -> workflow.run("A", "B", 100.0, null));

        Throwable cause = failure.getCause();
        if (cause instanceof TimeoutFailure) {
            fail("Workflow only stopped because its execution timeout fired, not because the fraud "
                    + "decline failed the workflow. That means the decline is still being retried "
                    + "forever instead of raising a non-retryable ApplicationFailure - fix TODO C in "
                    + "TransferWorkflowImpl.run() (throw ApplicationFailure.newNonRetryableFailure(...) "
                    + "instead of the placeholder RuntimeException).");
        }
        ApplicationFailure appFailure = assertInstanceOf(ApplicationFailure.class, cause,
                "Expected the fraud decline to surface as an ApplicationFailure, got " + cause);
        assertEquals("FraudDeclined", appFailure.getType());
        org.junit.jupiter.api.Assertions.assertTrue(appFailure.isNonRetryable(),
                "A genuine fraud decline must be non-retryable, so a retried workflow doesn't keep "
                        + "re-running a fraud check that will always decline the same way.");
    }

    /** Minimal stand-in for BankActivitiesImpl: no HTTP, no OpenAI, fully deterministic, with its
     * own tiny in-memory idempotent ledger mirroring LedgerStore's semantics. */
    static final class FakeBankActivities implements BankActivities {
        static final double STARTING_BALANCE_A = 5000.0;

        boolean approveAll = true;
        final Map<String, LedgerStore.Account> accounts = new HashMap<>();
        final Set<String> appliedWorkflowIds = new HashSet<>();

        FakeBankActivities() {
            LedgerStore.Account a = new LedgerStore.Account();
            a.balance = STARTING_BALANCE_A;
            a.home_country = "United States";
            a.last_location = new LedgerStore.Location("New York", "United States", 40.7128, -74.0060);
            a.last_transaction_at = "2026-01-01T00:00:00+00:00";
            LedgerStore.Account b = new LedgerStore.Account();
            b.balance = 3000.0;
            b.home_country = "United Kingdom";
            b.last_location = new LedgerStore.Location("London", "United Kingdom", 51.5074, -0.1278);
            b.last_transaction_at = "2026-01-01T00:00:00+00:00";
            accounts.put("A", a);
            accounts.put("B", b);
        }

        @Override
        public LedgerStore.Location geolocateIp(String ip) {
            return new LedgerStore.Location("New York", "United States", 40.7128, -74.0060);
        }

        @Override
        public LedgerStore.Account getAccountForTransfer(String accountId) {
            LedgerStore.Account account = accounts.get(accountId);
            if (account == null) {
                throw ApplicationFailure.newNonRetryableFailure("no such account: " + accountId, "NoSuchAccount");
            }
            return account;
        }

        @Override
        public FraudDecision checkFraud(String homeCountry, String lastCity, String lastCountry, String lastAt,
                                          String newCity, String newCountry, String newAt,
                                          double distanceKm, double elapsedHours, double impliedSpeedKmh) {
            return approveAll ? new FraudDecision(true, "ok") : new FraudDecision(false, "impossible travel");
        }

        @Override
        public synchronized LedgerStore.Account applyTransferToLedger(String workflowId, String fromAccount,
                String toAccount, double amount, LedgerStore.Location newLocation, String newAt) {
            if (appliedWorkflowIds.contains(workflowId)) {
                return accounts.get(fromAccount);
            }
            LedgerStore.Account from = accounts.get(fromAccount);
            LedgerStore.Account to = accounts.get(toAccount);
            from.balance -= amount;
            to.balance += amount;
            from.last_location = newLocation;
            from.last_transaction_at = newAt;
            appliedWorkflowIds.add(workflowId);
            return from;
        }
    }
}
