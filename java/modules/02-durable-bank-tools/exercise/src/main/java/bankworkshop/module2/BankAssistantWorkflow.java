package bankworkshop.module2;

import io.temporal.workflow.WorkflowInterface;
import io.temporal.workflow.WorkflowMethod;

@WorkflowInterface
public interface BankAssistantWorkflow {
  @WorkflowMethod
  String answer(String question);
}
