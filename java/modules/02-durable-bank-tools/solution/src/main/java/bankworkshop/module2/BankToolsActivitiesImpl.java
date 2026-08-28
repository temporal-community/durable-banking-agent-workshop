package bankworkshop.module2;

import com.fasterxml.jackson.annotation.JsonClassDescription;
import com.fasterxml.jackson.annotation.JsonPropertyDescription;
import com.openai.client.OpenAIClient;
import com.openai.client.okhttp.OpenAIOkHttpClient;
import com.openai.errors.OpenAIException;
import com.openai.errors.OpenAIRetryableException;
import com.openai.errors.OpenAIServiceException;
import com.openai.models.ChatModel;
import com.openai.models.chat.completions.ChatCompletion;
import com.openai.models.chat.completions.ChatCompletionCreateParams;
import com.openai.models.chat.completions.ChatCompletionMessage;
import com.openai.models.chat.completions.ChatCompletionMessageFunctionToolCall;
import com.openai.models.chat.completions.ChatCompletionMessageToolCall;
import io.temporal.failure.ApplicationFailure;
import java.util.List;
import java.util.Map;

public class BankToolsActivitiesImpl implements BankToolsActivities {

  private static final String INSTRUCTIONS =
      "You are a concise bank assistant. Use the provided tool when it would make the answer "
          + "more accurate.";

  private static final Map<String, Double> CANNED_BALANCES = Map.of("A", 5000.00, "B", 3000.00);

  private final OpenAIClient client = OpenAIOkHttpClient.fromEnv();

  @JsonClassDescription("Get the current balance of a bank account.")
  static class GetAccountBalanceArgs {
    @JsonPropertyDescription("The account identifier, e.g. \"A\" or \"B\".")
    public String accountId;
  }

  private ChatCompletion createCompletion(ChatCompletionCreateParams params) {
    try {
      return client.chat().completions().create(params);
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

  @Override
  public ModelDecision decideNextStep(String question) {
    ChatCompletionCreateParams params =
        ChatCompletionCreateParams.builder()
            .model(ChatModel.of("gpt-4o"))
            .addSystemMessage(INSTRUCTIONS)
            .addUserMessage(question)
            .addTool(GetAccountBalanceArgs.class)
            .build();
    ChatCompletion completion = createCompletion(params);
    ChatCompletionMessage message = completion.choices().get(0).message();

    List<ChatCompletionMessageToolCall> toolCalls = message.toolCalls().orElse(List.of());
    if (!toolCalls.isEmpty()) {
      ChatCompletionMessageFunctionToolCall functionCall = toolCalls.get(0).asFunction();
      GetAccountBalanceArgs args =
          functionCall.function().arguments(GetAccountBalanceArgs.class);
      return new ModelDecision(null, args.accountId);
    }
    return new ModelDecision(message.content().orElse(""), null);
  }

  @Override
  public double getAccountBalance(String accountId) {
    Double balance = CANNED_BALANCES.get(accountId);
    if (balance == null) {
      throw new IllegalArgumentException("Unknown account: " + accountId);
    }
    return balance;
  }

  @Override
  public String composeFinalAnswer(String question, String accountId, double balance) {
    String prompt =
        String.format(
            "Question: %s%nAccount %s balance: $%.2f%nAnswer the question concisely using this "
                + "balance.",
            question, accountId, balance);
    ChatCompletionCreateParams params =
        ChatCompletionCreateParams.builder()
            .model(ChatModel.of("gpt-4o"))
            .addSystemMessage(INSTRUCTIONS)
            .addUserMessage(prompt)
            .build();
    ChatCompletion completion = createCompletion(params);
    return completion.choices().get(0).message().content().orElse("");
  }
}
