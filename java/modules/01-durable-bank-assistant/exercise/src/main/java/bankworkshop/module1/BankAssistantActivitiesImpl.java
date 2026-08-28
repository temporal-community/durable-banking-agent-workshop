package bankworkshop.module1;

import com.openai.client.OpenAIClient;
import com.openai.client.okhttp.OpenAIOkHttpClient;
import com.openai.errors.OpenAIException;
import com.openai.errors.OpenAIRetryableException;
import com.openai.errors.OpenAIServiceException;
import com.openai.models.ChatModel;
import com.openai.models.chat.completions.ChatCompletion;
import com.openai.models.chat.completions.ChatCompletionCreateParams;
import io.temporal.failure.ApplicationFailure;

public class BankAssistantActivitiesImpl implements BankAssistantActivities {

  private static final String INSTRUCTIONS = "You are a concise bank assistant.";

  // Reading OPENAI_API_KEY here, not in the workflow, is what makes this an activity in the
  // first place: talking to an external service is exactly the non-deterministic work Temporal
  // isolates into a retryable unit outside the workflow.
  private final OpenAIClient client = OpenAIOkHttpClient.fromEnv();

  @Override
  public String answerQuestion(String question) {
    ChatCompletionCreateParams params =
        ChatCompletionCreateParams.builder()
            .model(ChatModel.of("gpt-4o"))
            .addSystemMessage(INSTRUCTIONS)
            .addUserMessage(question)
            .build();
    try {
      ChatCompletion completion = client.chat().completions().create(params);
      return completion.choices().get(0).message().content().orElse("");
    } catch (OpenAIException e) {
      throw classifyOpenAiFailure(e);
    }
  }

  // OpenAIRetryableException (connection-level: timeouts, IO) and a 429/5xx OpenAIServiceException
  // are genuinely transient - let Temporal's default retry policy handle those. Everything else
  // (400/401/403/404, bad or missing key) is permanent: without this, a bad key retries forever
  // instead of failing fast, since the SDK's own exception carries no retryability hint Temporal
  // understands on its own.
  private static RuntimeException classifyOpenAiFailure(OpenAIException e) {
    if (e instanceof OpenAIRetryableException) {
      return e;
    }
    if (e instanceof OpenAIServiceException service) {
      int status = service.statusCode();
      if (status == 429 || status >= 500) {
        return e;
      }
    }
    return ApplicationFailure.newNonRetryableFailure(e.getMessage(), "OpenAIError");
  }
}
