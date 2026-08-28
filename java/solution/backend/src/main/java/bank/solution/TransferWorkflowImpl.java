package bank.solution;

import java.time.Duration;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.Map;

import io.temporal.activity.ActivityOptions;
import io.temporal.failure.ApplicationFailure;
import io.temporal.workflow.Workflow;

/** Ports transfer_workflow.py. Every risky step (geo-IP, the model call, the ledger update) is
 * its own Activity; the workflow itself only orchestrates and does pure, deterministic math -
 * this is the Java-idiomatic equivalent of Python's temporalio.contrib.openai_agents plugin,
 * which has no Java counterpart: here the "model call becomes an activity" boundary is explicit
 * rather than hidden by a framework. */
public final class TransferWorkflowImpl implements TransferWorkflow {
    private static final Duration TOOL_TIMEOUT = Duration.ofSeconds(30);
    private static final double EARTH_RADIUS_KM = 6371.0;

    public static final Map<String, String> SPOOFABLE_LOCATIONS = new LinkedHashMap<>();
    static {
        SPOOFABLE_LOCATIONS.put("New York", "8.8.8.8");
        SPOOFABLE_LOCATIONS.put("London", "185.86.151.11");
        SPOOFABLE_LOCATIONS.put("Tokyo", "133.242.0.3");
        SPOOFABLE_LOCATIONS.put("Lagos", "105.112.0.1");
        SPOOFABLE_LOCATIONS.put("Sydney", "1.1.1.1");
    }

    private final BankActivities activities = Workflow.newActivityStub(
            BankActivities.class,
            ActivityOptions.newBuilder().setStartToCloseTimeout(TOOL_TIMEOUT).build());

    @Override
    public LedgerStore.Account run(String fromAccount, String toAccount, double amount, String spoofLocation) {
        if (amount <= 0) {
            throw ApplicationFailure.newNonRetryableFailure("amount must be positive", "InvalidTransfer");
        }
        if (spoofLocation != null && !spoofLocation.isBlank() && !SPOOFABLE_LOCATIONS.containsKey(spoofLocation)) {
            throw ApplicationFailure.newNonRetryableFailure(
                    "unknown spoof location: " + spoofLocation, "InvalidTransfer");
        }
        String ip = (spoofLocation != null && !spoofLocation.isBlank())
                ? SPOOFABLE_LOCATIONS.get(spoofLocation) : "8.8.8.8";

        LedgerStore.Account sender = activities.getAccountForTransfer(fromAccount);
        activities.getAccountForTransfer(toAccount);
        if (sender.balance < amount) {
            throw ApplicationFailure.newNonRetryableFailure("insufficient funds", "InvalidTransfer");
        }

        Workflow.getLogger(TransferWorkflowImpl.class)
                .info("running fraud check for account=" + fromAccount + " ip=" + ip + ", pausing for the demo window");
        Workflow.sleep(Duration.ofSeconds(10));

        LedgerStore.Location newLocation = activities.geolocateIp(ip);

        Instant now = Instant.ofEpochMilli(Workflow.currentTimeMillis());
        Instant lastAt = Instant.parse(sender.last_transaction_at);
        double distanceKm = haversineKm(sender.last_location.lat, sender.last_location.lon,
                newLocation.lat, newLocation.lon);
        double elapsedHours = Math.max((now.getEpochSecond() - lastAt.getEpochSecond()) / 3600.0, 1e-6);
        double impliedSpeedKmh = distanceKm / elapsedHours;

        BankActivities.FraudDecision decision = activities.checkFraud(
                sender.home_country, sender.last_location.city, sender.last_location.country, lastAt.toString(),
                newLocation.city, newLocation.country, now.toString(),
                distanceKm, elapsedHours, impliedSpeedKmh);

        if (!decision.approve) {
            throw ApplicationFailure.newNonRetryableFailure(
                    "transfer declined: " + decision.reason, "FraudDeclined");
        }

        String nowIso = OffsetDateTime.ofInstant(now, ZoneOffset.UTC).toString();
        return activities.applyTransferToLedger(
                Workflow.getInfo().getWorkflowId(), fromAccount, toAccount, amount, newLocation, nowIso);
    }

    private static double haversineKm(double lat1, double lon1, double lat2, double lon2) {
        double rlat1 = Math.toRadians(lat1);
        double rlon1 = Math.toRadians(lon1);
        double rlat2 = Math.toRadians(lat2);
        double rlon2 = Math.toRadians(lon2);
        double dlat = rlat2 - rlat1;
        double dlon = rlon2 - rlon1;
        double a = Math.pow(Math.sin(dlat / 2), 2) + Math.cos(rlat1) * Math.cos(rlat2) * Math.pow(Math.sin(dlon / 2), 2);
        return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(a));
    }
}
