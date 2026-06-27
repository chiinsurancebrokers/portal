"""
fix_email_queue.py
───────────────────────────────────────────────────────────────────────────
One-off repair script for the CHI portal database.

BACKGROUND
A bug in agent_send_payment_notification() (app.py) used to create
EmailQueue rows like this:

    eq = m.EmailQueue(
        client_id=pay_id, policy_id=pay_id, payment_id=pay_id, ...
    )

i.e. client_id and policy_id were both set to the PAYMENT's id instead of
the real client's / policy's id. The code has since been fixed, but any
EmailQueue rows created *before* the fix still have the wrong client_id /
policy_id baked in, so the Email Queue page shows the wrong customer name
next to the (correct) recipient email address.

WHAT THIS SCRIPT DOES
For every EmailQueue row that has a payment_id, it walks the *reliable*
chain  Payment -> Policy -> Client  (payment_id was never touched by the
bug, so it's trustworthy) and compares the row's stored client_id/policy_id
against what that chain says they should be. Any row that disagrees is
corrected. Rows that already match are left untouched, and rows with no
payment_id (e.g. ones created by the renewal-draft flow, which was never
buggy) are skipped entirely.

This is data-driven rather than pattern-matching on "client_id == payment_id"
specifically, so it will also catch any other accidental mismatch, not just
the exact historical bug signature.

USAGE
    python3 fix_email_queue.py              # dry run, shows what WOULD change
    python3 fix_email_queue.py --apply      # actually writes the fix

Always run without --apply first and read the report before applying.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models as m


def main():
    apply_changes = "--apply" in sys.argv
    db = m.get_session()

    try:
        rows = (
            db.query(m.EmailQueue)
            .filter(m.EmailQueue.payment_id.isnot(None))
            .order_by(m.EmailQueue.id)
            .all()
        )

        total = len(rows)
        checked = 0
        mismatched = 0
        unfixable = 0
        fixed = 0

        print(f"Found {total} EmailQueue row(s) with a payment_id to check.\n")

        for eq in rows:
            checked += 1
            payment = db.get(m.Payment, eq.payment_id)
            if not payment:
                unfixable += 1
                print(
                    f"  [SKIP] EmailQueue #{eq.id}: payment_id={eq.payment_id} "
                    f"does not exist anymore — cannot verify, leaving as-is."
                )
                continue

            policy = db.get(m.Policy, payment.policy_id)
            if not policy:
                unfixable += 1
                print(
                    f"  [SKIP] EmailQueue #{eq.id}: payment #{payment.id} points to "
                    f"policy #{payment.policy_id} which no longer exists — "
                    f"leaving as-is."
                )
                continue

            correct_policy_id = policy.id
            correct_client_id = policy.client_id

            if eq.policy_id == correct_policy_id and eq.client_id == correct_client_id:
                continue  # already correct

            mismatched += 1
            old_client = db.get(m.Client, eq.client_id)
            new_client = db.get(m.Client, correct_client_id)
            old_policy = db.get(m.Policy, eq.policy_id)

            print(f"  [MISMATCH] EmailQueue #{eq.id} (sent to {eq.recipient_email}):")
            print(
                f"      stored client_id={eq.client_id} "
                f"({old_client.name if old_client else '— no such client —'})"
            )
            print(f"      correct client_id={correct_client_id} ({new_client.name if new_client else '?'})")
            print(
                f"      stored policy_id={eq.policy_id} "
                f"({old_policy.policy_number if old_policy else '— no such policy —'})"
            )
            print(f"      correct policy_id={correct_policy_id} ({policy.policy_number})")

            if apply_changes:
                eq.client_id = correct_client_id
                eq.policy_id = correct_policy_id
                fixed += 1
                print("      -> FIXED")
            else:
                print("      -> would fix (dry run, use --apply to write)")
            print()

        if apply_changes and fixed:
            db.commit()

        print("─" * 60)
        print(f"Checked:    {checked}")
        print(f"Mismatched: {mismatched}")
        print(f"Unfixable:  {unfixable} (orphaned payment/policy reference)")
        if apply_changes:
            print(f"Fixed:      {fixed}")
            print("\nChanges have been committed to the database.")
        else:
            print(f"Would fix:  {mismatched}")
            print("\nThis was a DRY RUN — no changes were saved.")
            print("Re-run with --apply to write the fix to the database.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
