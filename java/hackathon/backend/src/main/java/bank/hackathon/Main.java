package bank.hackathon;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.Map;

import io.javalin.Javalin;
import io.javalin.http.Context;
import io.javalin.http.HttpStatus;

/** Plain, fragile HTTP backend - no retries, no idempotency, in-memory state. Ports main.py. */
public final class Main {
    private static final Path FRONTEND_INDEX = Path.of(
            System.getProperty("frontend.index", "../../../hackathon/frontend/index.html"));

    private final Ledger ledger = new Ledger();
    private final FraudCheck fraudCheck = new FraudCheck();

    public static void main(String[] args) {
        new Main().start();
    }

    private void start() {
        Javalin.create(config -> {
            config.routes.get("/", ctx -> {
                ctx.contentType("text/html");
                ctx.result(Files.readAllBytes(FRONTEND_INDEX));
            });
            config.routes.get("/accounts/{id}", this::getAccount);
            config.routes.get("/incidents", ctx -> ctx.json(ledger.incidents));
            config.routes.post("/transfer", this::transfer);
        }).start(8000);
    }

    private void getAccount(Context ctx) {
        String id = ctx.pathParam("id");
        Ledger.Account account = ledger.accounts.get(id);
        if (account == null) {
            ctx.status(HttpStatus.NOT_FOUND).json(Map.of("detail", "no such account: " + id));
            return;
        }
        ctx.json(account);
    }

    private record TransferRequest(String from_account, String to_account, double amount, String spoof_location) {}

    private void transfer(Context ctx) {
        TransferRequest body = ctx.bodyAsClass(TransferRequest.class);

        if (!ledger.accounts.containsKey(body.from_account()) || !ledger.accounts.containsKey(body.to_account())) {
            ctx.status(HttpStatus.NOT_FOUND).json(Map.of("detail", "unknown account"));
            return;
        }
        if (body.amount() <= 0) {
            ctx.status(HttpStatus.BAD_REQUEST).json(Map.of("detail", "amount must be positive"));
            return;
        }

        Ledger.Account sender = ledger.accounts.get(body.from_account());
        if (sender.balance < body.amount()) {
            ctx.status(HttpStatus.BAD_REQUEST).json(Map.of("detail", "insufficient funds"));
            return;
        }

        String ip;
        if (body.spoof_location() != null && !body.spoof_location().isBlank()) {
            String spoofIp = Geo.SPOOFABLE_LOCATIONS.get(body.spoof_location());
            if (spoofIp == null) {
                ctx.status(HttpStatus.BAD_REQUEST)
                        .json(Map.of("detail", "unknown spoof location: " + body.spoof_location()));
                return;
            }
            ip = spoofIp;
        } else {
            // ip-api.com refuses loopback/private ranges, which is all a local dev run ever sees.
            String clientIp = ctx.ip();
            ip = (clientIp == null || clientIp.equals("127.0.0.1") || clientIp.equals("0:0:0:0:0:0:0:1"))
                    ? "8.8.8.8" : clientIp;
        }

        // No retry, no timeout handling beyond the request itself, on purpose - a flaky geo-IP
        // call just fails the request. This backend is deliberately fragile.
        Geo.Location location;
        try {
            location = Geo.geolocateIp(ip);
        } catch (Exception e) {
            ctx.status(HttpStatus.INTERNAL_SERVER_ERROR).json(Map.of("detail", "geolocation failed: " + e.getMessage()));
            return;
        }

        Instant now = Instant.now();
        Ledger.Location lastLocation = sender.last_location;
        Instant lastAt = Instant.parse(sender.last_transaction_at);
        double distanceKm = Geo.haversineKm(lastLocation.lat, lastLocation.lon, location.lat(), location.lon());
        double elapsedHours = Math.max((now.getEpochSecond() - lastAt.getEpochSecond()) / 3600.0, 1e-6);
        double impliedSpeedKmh = distanceKm / elapsedHours;

        FraudCheck.FraudDecision decision;
        try {
            decision = fraudCheck.checkTransferForFraud(
                    sender.home_country, lastLocation.city, lastLocation.country, lastAt,
                    location.city(), location.country(), now, distanceKm, elapsedHours, impliedSpeedKmh);
        } catch (Exception e) {
            ctx.status(HttpStatus.INTERNAL_SERVER_ERROR).json(Map.of("detail", "fraud check failed: " + e.getMessage()));
            return;
        }

        Map<String, Object> locationJson = Map.of("city", location.city(), "country", location.country(),
                "lat", location.lat(), "lon", location.lon());

        if (!decision.approve) {
            Map<String, Object> incident = new LinkedHashMap<>();
            incident.put("from_account", body.from_account());
            incident.put("to_account", body.to_account());
            incident.put("amount", body.amount());
            incident.put("location", locationJson);
            incident.put("implied_speed_kmh", impliedSpeedKmh);
            incident.put("verdict", "declined-fraud");
            incident.put("reason", decision.reason);
            incident.put("at", now.toString());
            ledger.logIncident(incident);
            ctx.status(HttpStatus.FORBIDDEN).json(Map.of("detail", "transfer declined: " + decision.reason));
            return;
        }

        sender.balance -= body.amount();
        ledger.accounts.get(body.to_account()).balance += body.amount();
        sender.last_location = new Ledger.Location(location.city(), location.country(), location.lat(), location.lon());
        sender.last_transaction_at = OffsetDateTime.ofInstant(now, ZoneOffset.UTC).toString();

        Map<String, Object> incident = new LinkedHashMap<>();
        incident.put("from_account", body.from_account());
        incident.put("to_account", body.to_account());
        incident.put("amount", body.amount());
        incident.put("location", locationJson);
        incident.put("implied_speed_kmh", impliedSpeedKmh);
        incident.put("verdict", "accepted");
        incident.put("reason", decision.reason);
        incident.put("at", now.toString());
        ledger.logIncident(incident);

        ctx.json(Map.of(
                "status", "accepted",
                "from_account", ledger.accounts.get(body.from_account()),
                "to_account", ledger.accounts.get(body.to_account()),
                "impossible_travel_threshold_kmh", FraudCheck.IMPOSSIBLE_TRAVEL_SPEED_KMH));
    }
}
