package bank.solution;

import io.temporal.workflow.WorkflowInterface;
import io.temporal.workflow.WorkflowMethod;

@WorkflowInterface
public interface TransferWorkflow {
    @WorkflowMethod
    LedgerStore.Account run(String fromAccount, String toAccount, double amount, String spoofLocation);
}
