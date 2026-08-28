package bank.hackathon;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/** Geo-IP lookup via ip-api.com and great-circle distance math. Ports geo.py 1:1. */
public final class Geo {
    // Representative public IPs for each city offered by the frontend's spoof-location dropdown -
    // same IPs as hackathon/backend/geo.py, so the two backends behave identically for the same city.
    public static final Map<String, String> SPOOFABLE_LOCATIONS = new LinkedHashMap<>();
    static {
        SPOOFABLE_LOCATIONS.put("New York", "8.8.8.8");
        SPOOFABLE_LOCATIONS.put("London", "185.86.151.11");
        SPOOFABLE_LOCATIONS.put("Tokyo", "133.242.0.3");
        SPOOFABLE_LOCATIONS.put("Lagos", "105.112.0.1");
        SPOOFABLE_LOCATIONS.put("Sydney", "1.1.1.1");
    }

    private static final double EARTH_RADIUS_KM = 6371.0;
    private static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private Geo() {}

    public record Location(String city, String country, double lat, double lon) {}

    /** No retry, no timeout handling beyond the request timeout, on purpose: a flaky geo-IP call
     * just fails the request - this backend is deliberately fragile, matching the Python side. */
    public static Location geolocateIp(String ip) throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create("http://ip-api.com/json/" + ip))
                .timeout(Duration.ofSeconds(5))
                .GET()
                .build();
        HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) {
            throw new IOException("geolocation failed for " + ip + ": HTTP " + response.statusCode());
        }
        JsonNode data = MAPPER.readTree(response.body());
        if (!"success".equals(data.path("status").asText())) {
            throw new RuntimeException("geolocation failed for " + ip + ": " + data);
        }
        return new Location(data.get("city").asText(), data.get("country").asText(),
                data.get("lat").asDouble(), data.get("lon").asDouble());
    }

    public static double haversineKm(double lat1, double lon1, double lat2, double lon2) {
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
