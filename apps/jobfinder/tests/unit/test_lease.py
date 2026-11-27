"""The run lease (ADR-0007, spec AC6, AC7)."""

from datetime import UTC, datetime, timedelta

from jobfinder.storage.lease import LEASE_TTL, InMemoryLease

T0 = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


def test_free_lease_is_taken_and_second_taker_is_refused() -> None:
    lease = InMemoryLease()
    assert lease.take("a", T0)
    assert not lease.take("b", T0 + timedelta(minutes=1))


def test_expired_lease_can_be_taken() -> None:
    lease = InMemoryLease()
    assert lease.take("a", T0)
    assert lease.take("b", T0 + LEASE_TTL)


def test_renew_extends_only_for_the_holder() -> None:
    lease = InMemoryLease()
    lease.take("a", T0)
    assert lease.renew("a", T0 + timedelta(minutes=2))
    assert not lease.take("b", T0 + LEASE_TTL)  # extended past the original expiry
    assert not lease.renew("b", T0 + timedelta(minutes=3))


def test_renew_fails_after_another_holder_took_over() -> None:
    lease = InMemoryLease()
    lease.take("a", T0)
    lease.take("b", T0 + LEASE_TTL)
    assert not lease.renew("a", T0 + LEASE_TTL)


def test_release_frees_the_lease_for_the_holder_only() -> None:
    lease = InMemoryLease()
    lease.take("a", T0)
    lease.release("b")
    assert not lease.take("c", T0 + timedelta(minutes=1))
    lease.release("a")
    assert lease.take("c", T0 + timedelta(minutes=1))
