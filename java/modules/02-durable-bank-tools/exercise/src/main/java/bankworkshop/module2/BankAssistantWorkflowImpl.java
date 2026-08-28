package bankworkshop.module2;

import io.temporal.activity.ActivityOptions;
import io.temporal.failure.ApplicationFailure;
import io.temporal.workflow.Workflow;
import java.time.Duration;

public class BankAssistantWorkflowImpl implements BankAssistantWorkflow {

  private final BankToolsActivities activities =
      Workflow.newActivityStub(
          BankToolsActivities.class,
          ActivityOptions.newBuilder().setStartToCloseTimeout(Duration.ofSeconds(60)).build());

  @Override
  public String answer(String question) {
    // TODO: Uncomment the block below.
    // ModelDecision decision = activities.decideNextStep(question);
    // if (decision.requestedAccountId == null) {
    //   return decision.finalAnswer;
    // }
    //
    // double balance = activities.getAccountBalance(decision.requestedAccountId);
    // return activities.composeFinalAnswer(question, decision.requestedAccountId, balance);
    throw ApplicationFailure.newNonRetryableFailure("TODO not implemented", "NotImplemented");
  }
}
