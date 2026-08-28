package bank.hackathon;

import java.time.Instant;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.openai.client.OpenAIClient;
import com.openai.client.okhttp.OpenAIOkHttpClient;
import com.openai.models.ChatModel;
import com.openai.models.chat.completions.StructuredChatCompletionCreateParams;
import com.openai.models.chat.completions.ChatCompletionCreateParams;

/** Fraud-check decision: a real model call, not a hardcoded rule. Ports fraud_check.py, but hands
 * the model pre-computed facts directly in the prompt instead of exposing them as tool calls the
 * model must invoke one by one - the four getter-tools in fraud_check.py exist mainly to show off
 * tool-calling; module 2's Java port already demonstrates the explicit tool-call loop, so this
 * fraud check stays a single structured completion to keep this file focused on the fraud logic. */
public final class FraudCheck {
    public static final double IMPOSSIBLE_TRAVEL_SPEED_KMH = 900.0;

    private static final String INSTRUCTIONS = """
            You are a fraud investigator for a bank. You are given an account's home country and \
            its travel facts since its last transaction. Decide whether to approve or decline this \
            transfer.

            Impossible travel means the implied speed between the last known location and the new \
            one exceeds %.0f km/h, the cruising speed of a commercial flight - no traveler could \
            plausibly cover that distance in that time. Decline only when the travel is genuinely \
            implausible; a short trip abroad is not fraud on its own.

            Respond with the decision only.
            """.formatted(IMPOSSIBLE_TRAVEL_SPEED_KMH);

    public static final class FraudDecision {
        @JsonProperty(required = true)
        public boolean approve;
        @JsonProperty(required = true)
        public String reason;
    }

    private final OpenAIClient client = OpenAIOkHttpClient.fromEnv();

    public FraudDecision checkTransferForFraud(
            String homeCountry, String lastCity, String lastCountry, Instant lastAt,
            String newCity, String newCountry, Instant newAt,
            double distanceKm, double elapsedHours, double impliedSpeedKmh) {
        String facts = """
                Home country: %s
                Last transaction: %s, %s at %s
                This transaction: %s, %s at %s
                Distance since last transaction: %.0f km in %.2f hours, implying %.0f km/h
                """.formatted(homeCountry, lastCity, lastCountry, lastAt, newCity, newCountry, newAt,
                distanceKm, elapsedHours, impliedSpeedKmh);

        StructuredChatCompletionCreateParams<FraudDecision> params = ChatCompletionCreateParams.builder()
                .model(ChatModel.GPT_4O)
                .addSystemMessage(INSTRUCTIONS)
                .addUserMessage(facts)
                .responseFormat(FraudDecision.class)
                .build();

        return client.chat().completions().create(params).choices().get(0).message()
                .content().orElseThrow(() -> new RuntimeException("no fraud decision returned"));
    }
}
