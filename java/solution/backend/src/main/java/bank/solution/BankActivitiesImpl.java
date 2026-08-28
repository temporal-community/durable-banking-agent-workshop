package bank.solution;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.openai.client.OpenAIClient;
import com.openai.client.okhttp.OpenAIOkHttpClient;
import com.openai.errors.OpenAIException;
import com.openai.errors.OpenAIRetryableException;
import com.openai.errors.OpenAIServiceException;
import com.openai.models.ChatModel;
import com.openai.models.chat.completions.ChatCompletionCreateParams;
import com.openai.models.chat.completions.StructuredChatCompletionCreateParams;
import io.temporal.failure.ApplicationFailure;

public final class BankActivitiesImpl implements BankActivities {

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
    private static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final double IMPOSSIBLE_TRAVEL_SPEED_KMH = 900.0;

    private final OpenAIClient openAi = OpenAIOkHttpClient.fromEnv();

    @Override
    public LedgerStore.Location geolocateIp(String ip) {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create("http://ip-api.com/json/" + ip))
                    .timeout(Duration.ofSeconds(5))
                    .GET()
                    .build();
            HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
            JsonNode data = MAPPER.readTree(response.body());
            if (!"success".equals(data.path("status").asText())) {
                // Transient (e.g. rate-limited) - let Temporal's default retry policy handle it.
                throw new RuntimeException("geolocation failed for " + ip + ": " + data);
            }
            return new LedgerStore.Location(data.get("city").asText(), data.get("country").asText(),
                    data.get("lat").asDouble(), data.get("lon").asDouble());
        } catch (IOException | InterruptedException e) {
            throw new RuntimeException(e);
        }
    }

    @Override
    public LedgerStore.Account getAccountForTransfer(String accountId) {
        try {
            return LedgerStore.getAccount(accountId);
        } catch (LedgerStore.NoSuchAccountException e) {
            throw ApplicationFailure.newNonRetryableFailure(e.getMessage(), "NoSuchAccount");
        }
    }

    public static final class FraudDecisionJson {
        @JsonProperty(required = true)
        public boolean approve;
        @JsonProperty(required = true)
        public String reason;
    }

    @Override
    public FraudDecision checkFraud(String homeCountry, String lastCity, String lastCountry, String lastAt,
                                      String newCity, String newCountry, String newAt,
                                      double distanceKm, double elapsedHours, double impliedSpeedKmh) {
        String instructions = """
                You are a fraud investigator for a bank. You are given an account's home country \
                and its travel facts since its last transaction. Decide whether to approve or \
                decline this transfer.

                Impossible travel means the implied speed between the last known location and the \
                new one exceeds %.0f km/h, the cruising speed of a commercial flight - no traveler \
                could plausibly cover that distance in that time. Decline only when the travel is \
                genuinely implausible; a short trip abroad is not fraud on its own.
                """.formatted(IMPOSSIBLE_TRAVEL_SPEED_KMH);
        String userFacts = """
                Home country: %s
                Last transaction: %s, %s at %s
                This transaction: %s, %s at %s
                Distance since last transaction: %.0f km in %.2f hours, implying %.0f km/h
                """.formatted(homeCountry, lastCity, lastCountry, lastAt,
                newCity, newCountry, newAt,
                distanceKm, elapsedHours, impliedSpeedKmh);

        StructuredChatCompletionCreateParams<FraudDecisionJson> params = ChatCompletionCreateParams.builder()
                .model(ChatModel.GPT_4O)
                .addSystemMessage(instructions)
                .addUserMessage(userFacts)
                .responseFormat(FraudDecisionJson.class)
                .build();

        FraudDecisionJson decision;
        try {
            decision = openAi.chat().completions().create(params).choices().get(0).message()
                    .content().orElseThrow(() -> new RuntimeException("no fraud decision returned"));
        } catch (OpenAIException e) {
            throw classifyOpenAiFailure(e);
        }
        return new FraudDecision(decision.approve, decision.reason);
    }

    @Override
    public LedgerStore.Account applyTransferToLedger(String workflowId, String fromAccount, String toAccount,
                                                        double amount, LedgerStore.Location newLocation, String newAt) {
        try {
            return LedgerStore.applyTransfer(workflowId, fromAccount, toAccount, amount, newLocation, newAt);
        } catch (IllegalArgumentException e) {
            throw ApplicationFailure.newNonRetryableFailure(e.getMessage(), "InvalidTransfer");
        }
    }
}
