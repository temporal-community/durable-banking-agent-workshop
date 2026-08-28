package bankworkshop.module2;

/** Serializable result of one model call: either a final answer, or a requested tool call. */
public class ModelDecision {
  public String finalAnswer;
  public String requestedAccountId;

  public ModelDecision() {}

  public ModelDecision(String finalAnswer, String requestedAccountId) {
    this.finalAnswer = finalAnswer;
    this.requestedAccountId = requestedAccountId;
  }
}
