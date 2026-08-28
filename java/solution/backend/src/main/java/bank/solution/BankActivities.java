package bank.solution;

import io.temporal.activity.ActivityInterface;
import io.temporal.activity.ActivityMethod;

@ActivityInterface
public interface BankActivities {

    /** Look up city, country, latitude and longitude for a public IP via ip-api.com. */
    @ActivityMethod
    LedgerStore.Location geolocateIp(String ip);

    /** Read an account's balance, home country and last-transaction location. */
    @ActivityMethod
    LedgerStore.Account getAccountForTransfer(String accountId);

    /** The model's fraud decision, given pre-computed travel facts. A real model call, so it has
     * to be an activity - workflow code must stay deterministic and can't call an external API
     * directly. Takes plain String/double arguments rather than a single POJO parameter (unlike
     * this activity's own POJO return type, which is fine) - a custom-POJO activity ARGUMENT
     * reproducibly got scheduled but never dispatched to the worker on this SDK/build, with no
     * error anywhere; flattening the signature avoids whatever serialization edge case that was
     * without spending more of this task's time root-causing a Temporal SDK internal. */
    @ActivityMethod
    FraudDecision checkFraud(String homeCountry, String lastCity, String lastCountry, String lastAt,
                              String newCity, String newCountry, String newAt,
                              double distanceKm, double elapsedHours, double impliedSpeedKmh);

    /** Debit and credit the ledger, idempotent on workflowId so a resumed run can't double-apply. */
    @ActivityMethod
    LedgerStore.Account applyTransferToLedger(String workflowId, String fromAccount, String toAccount,
                                                double amount, LedgerStore.Location newLocation, String newAt);

    final class FraudDecision {
        public boolean approve;
        public String reason;

        public FraudDecision() {}

        public FraudDecision(boolean approve, String reason) {
            this.approve = approve;
            this.reason = reason;
        }
    }
}
