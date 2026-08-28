package bank.solution;

import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;

/** File-backed ledger, ported from ledger_store.py. Deliberately outside the project directory
 * (like Python's) so nothing watching this tree for changes restarts on every transfer.
 *
 * Concurrency: Temporal can run activities concurrently within one worker process, and this is a
 * single JSON file with no other concurrency control - without a lock, two concurrent
 * applyTransfer calls could each read the same on-disk state before either writes back, silently
 * losing one of the two updates (the exact class of bug the Python port's fcntl-based fix closed).
 * A java.nio.channels.FileLock on a sidecar lock file serializes the read-modify-write section. */
public final class LedgerStore {
    private static final Path LEDGER_PATH = Path.of("/tmp/durable-banking-ledger-java.json");
    private static final Path LOCK_PATH = Path.of("/tmp/durable-banking-ledger-java.lock");
    private static final ObjectMapper MAPPER = new ObjectMapper();

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
    }

    public static final class State {
        public Map<String, Account> accounts = new LinkedHashMap<>();
        public List<String> applied_workflow_ids = new ArrayList<>();
    }

    private LedgerStore() {}

    private static State defaultState() {
        State state = new State();
        Account a = new Account();
        a.balance = 5000.0;
        a.home_country = "United States";
        a.last_location = new Location("New York", "United States", 40.7128, -74.0060);
        a.last_transaction_at = "2026-01-01T00:00:00+00:00";
        Account b = new Account();
        b.balance = 3000.0;
        b.home_country = "United Kingdom";
        b.last_location = new Location("London", "United Kingdom", 51.5074, -0.1278);
        b.last_transaction_at = "2026-01-01T00:00:00+00:00";
        state.accounts.put("A", a);
        state.accounts.put("B", b);
        return state;
    }

    private interface LockedWork<T> {
        T run() throws IOException;
    }

    private static <T> T locked(LockedWork<T> work) {
        try (RandomAccessFile raf = new RandomAccessFile(LOCK_PATH.toFile(), "rw");
             FileChannel channel = raf.getChannel();
             FileLock lock = channel.lock()) {
            return work.run();
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    private static State load() throws IOException {
        if (!Files.exists(LEDGER_PATH)) {
            save(defaultState());
        }
        return MAPPER.readValue(Files.readString(LEDGER_PATH), State.class);
    }

    private static void save(State state) throws IOException {
        Files.writeString(LEDGER_PATH, MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(state));
    }

    public static void reset() {
        locked(() -> {
            save(defaultState());
            return null;
        });
    }

    public static Account getAccount(String accountId) {
        return locked(() -> {
            Account account = load().accounts.get(accountId);
            if (account == null) {
                throw new NoSuchAccountException(accountId);
            }
            return account;
        });
    }

    public static final class NoSuchAccountException extends RuntimeException {
        public NoSuchAccountException(String accountId) {
            super("no such account: " + accountId);
        }
    }

    /** Debit/credit the ledger, keyed on workflowId so a resumed run can't double-apply. */
    public static Account applyTransfer(String workflowId, String fromAccount, String toAccount,
                                          double amount, Location newLocation, String newAt) {
        return locked(() -> {
            State state = load();
            if (state.applied_workflow_ids.contains(workflowId)) {
                return state.accounts.get(fromAccount);
            }
            Account from = state.accounts.get(fromAccount);
            Account to = state.accounts.get(toAccount);
            if (from == null || to == null) {
                throw new IllegalArgumentException("unknown account: " + (from == null ? fromAccount : toAccount));
            }
            if (amount <= 0) {
                throw new IllegalArgumentException("amount must be positive");
            }
            if (from.balance < amount) {
                throw new IllegalArgumentException("insufficient funds in account " + fromAccount);
            }
            from.balance -= amount;
            to.balance += amount;
            from.last_location = newLocation;
            from.last_transaction_at = newAt;
            state.applied_workflow_ids.add(workflowId);
            save(state);
            return from;
        });
    }
}
