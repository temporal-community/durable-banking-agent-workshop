package bankworkshop.module2;

import io.temporal.activity.ActivityInterface;
import io.temporal.activity.ActivityMethod;

@ActivityInterface
public interface BankToolsActivities {

  /** Ask the model to answer the question, offering it the account-balance tool. */
  @ActivityMethod
  ModelDecision decideNextStep(String question);

  /**
   * Get the current balance of a bank account.
   *
   * @param accountId The account identifier, e.g. "A" or "B".
   */
  @ActivityMethod
  double getAccountBalance(String accountId);

  /** Ask the model to turn a looked-up balance into a final answer for the user. */
  @ActivityMethod
  String composeFinalAnswer(String question, String accountId, double balance);
}
