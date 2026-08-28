package bankworkshop.module1;

import io.temporal.activity.ActivityOptions;
import io.temporal.workflow.Workflow;
import java.time.Duration;

public class BankAssistantWorkflowImpl implements BankAssistantWorkflow {

  private final BankAssistantActivities activities =
      Workflow.newActivityStub(
          BankAssistantActivities.class,
          ActivityOptions.newBuilder().setStartToCloseTimeout(Duration.ofSeconds(60)).build());

  @Override
  public String answer(String question) {
    return activities.answerQuestion(question);
  }
}
