"""Application errors. Messages are safe to show to users: they never contain secrets or stack traces,
and the authentication/join errors are deliberately generic so they do not reveal whether an email or a
patient ID exists."""

from __future__ import annotations


class AppError(Exception):
    """Base class. ``code`` is stable for tests/templates; ``message`` is shown to the user."""

    code = "error"
    message = "Something went wrong."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class ValidationFailed(AppError):
    code = "validation"
    message = "Please check the highlighted fields."

    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors.values()) or self.message)


class InvalidCredentials(AppError):
    code = "invalid_credentials"
    message = "Email or password is not correct."


class AccountNotCreated(AppError):
    code = "account_not_created"
    message = "We could not create that account. If you already have one, try logging in."


class Throttled(AppError):
    code = "throttled"
    message = "Too many attempts. Please wait a few minutes and try again."


class NotAllowed(AppError):
    code = "not_allowed"
    message = "You do not have permission to do that."


class NotFound(AppError):
    code = "not_found"
    message = "We could not find that."


class InvalidIdOrCode(AppError):
    """Wrong patient ID, wrong code, or a code issued for a different care circle: indistinguishable."""

    code = "invalid_id_or_code"
    message = "That patient ID and invitation code do not match. Check both and try again."


class InvitationExpired(AppError):
    code = "invitation_expired"
    message = "This invitation has expired. Ask the person who invited you for a new one."


class InvitationUsed(AppError):
    code = "invitation_used"
    message = "This invitation has already been used. Ask for a new one."


class AlreadyMember(AppError):
    code = "already_member"
    message = "You are already a member of this care circle."


class MembershipPending(AppError):
    code = "membership_pending"
    message = "Your request to join is waiting for approval."


class MembershipRevoked(AppError):
    code = "membership_revoked"
    message = "Your access to this care circle has been removed."


class QueueFull(AppError):
    """Too many notes are already waiting to be prepared (for this care circle, or for the whole app)."""

    code = "queue_full"
    message = ("Notes are already waiting to be prepared for this care circle. "
               "Please wait for them to finish before adding another.")
