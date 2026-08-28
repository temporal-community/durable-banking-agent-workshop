package bankworkshop.module1;

import io.temporal.activity.ActivityInterface;
import io.temporal.activity.ActivityMethod;

@ActivityInterface
public interface BankAssistantActivities {
  @ActivityMethod
  String answerQuestion(String question);
}
