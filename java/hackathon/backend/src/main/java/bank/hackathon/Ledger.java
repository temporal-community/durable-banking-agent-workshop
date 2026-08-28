package bank.hackathon;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

/** In-memory ledger + incident log. Deliberately unsynchronized across accounts (matches
 * hackathon/backend/ledger.py's fragility on purpose - see java/hackathon/backend's README). */
public final class Ledger {
    public static final int MAX_INCIDENTS = 20;

    public static final class Location {
        public String city;
        public String country;
        public double lat;
        public double lon;

        public Location() {}

        public Location(String city, String country, double lat, double lon) {
            this.city = city;
            this.country = country;
            this.lat = lat;
            this.lon = lon;
        }
    }

    public static final class Account {
        public double balance;
        public String home_country;
        public Location last_location;
        public String last_transaction_at;

        public Account(double balance, String homeCountry, Location lastLocation) {
            this.balance = balance;
            this.home_country = homeCountry;
            this.last_location = lastLocation;
            this.last_transaction_at = OffsetDateTime.now(ZoneOffset.UTC).toString();
        }
    }

    public final Map<String, Account> accounts = new ConcurrentHashMap<>();
    public final List<Map<String, Object>> incidents = new CopyOnWriteArrayList<>();

    public Ledger() {
        accounts.put("A", new Account(5000.0, "United States",
                new Location("New York", "United States", 40.7128, -74.0060)));
        accounts.put("B", new Account(3000.0, "United Kingdom",
                new Location("London", "United Kingdom", 51.5074, -0.1278)));
    }

    public synchronized void logIncident(Map<String, Object> entry) {
        incidents.add(entry);
        while (incidents.size() > MAX_INCIDENTS) {
            incidents.remove(0);
        }
    }
}
