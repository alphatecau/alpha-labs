"""Security and operational readiness guard for Level 3.

This guard is deliberately conservative: it blocks deployment until a separate
operator-controlled approval and protected ledger boundary has been verified.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Gate:
    ci_green: bool = False
    isolated_uid: bool = False
    private_signer_inaccessible: bool = False
    protected_ledger: bool = False
    durable_audit: bool = False
    crash_recovery_passed: bool = False
    android_acceptance_passed: bool = False
    connector_authorised: bool = False

    def blockers(self):
        return [name for name, passed in vars(self).items() if not passed]

    def may_activate(self):
        return not self.blockers()
