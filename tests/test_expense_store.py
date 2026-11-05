from concurrent.futures import ThreadPoolExecutor

import pytest

from scanner.accounts import hash_password, verify_password
from scanner.expense_reports import expense_csv, summaries
from scanner.expense_store import DuplicateReceipt, ExpenseStore

PASSWORD = "synthetic-test-password-123"


@pytest.fixture
def store(tmp_path):
    return ExpenseStore(tmp_path / "test.sqlite3")


def save(store, owner, source=b"synthetic image", **overrides):
    fields = dict(
        merchant="DEMO CAFE",
        purchased_on="2026-11-01",
        amount="10.25",
        currency="USD",
        category="Food",
        note="Test only",
        source=source,
        image=b"synthetic normalized image",
        ocr_text="DEMO CAFE",
    )
    return store.save(owner, **(fields | overrides))


def test_password_hashes_are_salted_and_not_plaintext():
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second and PASSWORD not in first
    assert verify_password(PASSWORD, first)
    assert not verify_password("incorrect-password", first)


def test_registration_login_and_case_normalization(store):
    owner = store.register("demo_user", PASSWORD)
    assert store.authenticate("DEMO_USER", PASSWORD) == (owner, "demo_user")
    assert store.authenticate("demo_user", "wrong-password-123") is None
    with pytest.raises(ValueError):
        store.register("demo_user", PASSWORD)
    with pytest.raises(ValueError):
        store.register("bad name", PASSWORD)


def test_repeated_login_failures_are_throttled(store):
    store.register("demo_user", PASSWORD)
    for _ in range(5):
        assert store.authenticate("demo_user", "wrong-password-123") is None
    with pytest.raises(ValueError, match="5 minutes"):
        store.authenticate("demo_user", PASSWORD)


def test_owner_isolation_for_list_get_and_delete(store):
    alice, bob = store.register("alice_test", PASSWORD), store.register("bob_test", PASSWORD)
    identifier = save(store, alice)
    assert store.get(bob, identifier) is None
    assert store.list(bob, "2026-01-01", "2026-12-31") == []
    store.delete(bob, identifier)
    assert store.get(alice, identifier) is not None
    assert not store.has_image(bob, b"synthetic image")
    assert not store.similar(bob, "DEMO CAFE", "2026-11-01", 1025, "USD")
    store.delete(alice, identifier)
    assert store.get(alice, identifier) is None


def test_exact_duplicate_is_atomic_and_scoped_to_user(store):
    alice, bob = store.register("alice_test", PASSWORD), store.register("bob_test", PASSWORD)
    save(store, alice)
    with pytest.raises(DuplicateReceipt):
        save(store, alice)
    save(store, bob)
    assert store.has_image(alice, b"synthetic image")


def test_concurrent_saves_only_insert_once(store):
    owner = store.register("demo_user", PASSWORD)

    def attempt():
        try:
            save(store, owner)
            return "saved"
        except DuplicateReceipt:
            return "duplicate"

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: attempt(), range(2))) == ["duplicate", "saved"]


def test_currency_separation_filters_and_csv_formula_protection(store):
    owner = store.register("demo_user", PASSWORD)
    save(store, owner, merchant="=HYPERLINK(test)", note="+formula")
    save(store, owner, source=b"second", currency="KRW", amount="12000", category="Transport")
    rows = store.list(owner, "2026-11-01", "2026-11-30")
    totals, monthly = summaries(rows)
    assert {r["Currency"]: r["Total"] for r in totals} == {"KRW": "12000", "USD": "10.25"}
    assert len(monthly) == 2
    assert len(store.list(owner, "2026-11-01", "2026-11-30", "Transport")) == 1
    csv = expense_csv(rows).decode("utf-8-sig")
    assert "'=HYPERLINK" in csv and "'+formula" in csv
    with pytest.raises(ValueError):
        store.list(owner, "2026-12-01", "2026-11-01")


def test_invalid_record_and_unknown_user_cannot_be_saved(store):
    owner = store.register("demo_user", PASSWORD)
    for overrides in (
        {"purchased_on": "2026-02-30"},
        {"merchant": ""},
        {"currency": "EUR"},
        {"amount": "-1"},
    ):
        with pytest.raises(ValueError):
            save(store, owner, **overrides)
    with pytest.raises(ValueError):
        save(store, "unknown owner")
