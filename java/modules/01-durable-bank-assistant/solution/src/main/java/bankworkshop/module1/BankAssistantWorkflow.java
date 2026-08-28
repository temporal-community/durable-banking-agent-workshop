package bankworkshop.module1;

import io.temporal.workflow.WorkflowInterface;
import io.temporal.workflow.WorkflowMethod;

@WorkflowInterface
public interface BankAssistantWorkflow {
  @WorkflowMethod
  String answer(String question);
}
