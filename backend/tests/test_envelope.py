import base64
import os

import pytest
from hypothesis import given
from hypothesis import strategies as st

from aicfo.crypto import (
    DecryptionError,
    KeyProviderError,
    LocalKeyProvider,
    TenantCipher,
    WrappedKey,
    rewrap,
)


@pytest.fixture
def provider() -> LocalKeyProvider:
    return LocalKeyProvider({"k1": os.urandom(32)}, active_key_id="k1")


def test_round_trip(provider: LocalKeyProvider) -> None:
    cipher, wrapped = TenantCipher.create(provider, "tenant-a")
    token = cipher.seal(b"50.000", aad="holdings:h1:units")
    reopened = TenantCipher.open(provider, "tenant-a", wrapped)
    assert reopened.open_field(token, aad="holdings:h1:units") == b"50.000"


def test_ciphertext_hides_plaintext_and_uses_fresh_nonces(provider: LocalKeyProvider) -> None:
    cipher, _ = TenantCipher.create(provider, "t")
    a = cipher.seal(b"INE009A01021", aad="x")
    b = cipher.seal(b"INE009A01021", aad="x")
    assert a != b
    assert "INE009A01021" not in a


def test_field_moved_to_another_row_fails(provider: LocalKeyProvider) -> None:
    cipher, _ = TenantCipher.create(provider, "t")
    token = cipher.seal(b"secret", aad="holdings:h1:units")
    with pytest.raises(DecryptionError):
        cipher.open_field(token, aad="holdings:h2:units")


def test_other_tenant_cannot_open_wrapped_key(provider: LocalKeyProvider) -> None:
    _, wrapped = TenantCipher.create(provider, "tenant-a")
    with pytest.raises(KeyProviderError):
        TenantCipher.open(provider, "tenant-b", wrapped)


def test_other_tenant_cipher_cannot_open_field(provider: LocalKeyProvider) -> None:
    a, _ = TenantCipher.create(provider, "tenant-a")
    b, _ = TenantCipher.create(provider, "tenant-b")
    token = a.seal(b"secret", aad="f")
    with pytest.raises(DecryptionError):
        b.open_field(token, aad="f")


def test_tampered_ciphertext_fails(provider: LocalKeyProvider) -> None:
    cipher, _ = TenantCipher.create(provider, "t")
    version, nonce, ct = cipher.seal(b"secret", aad="f").split(".")
    raw = bytearray(base64.urlsafe_b64decode(ct))
    raw[0] ^= 1
    tampered = ".".join((version, nonce, base64.urlsafe_b64encode(bytes(raw)).decode()))
    with pytest.raises(DecryptionError):
        cipher.open_field(tampered, aad="f")


@pytest.mark.parametrize("token", ["", "f1.only-two", "f9.AAAA.AAAA", "f1.!!!.???"])
def test_malformed_tokens_fail(provider: LocalKeyProvider, token: str) -> None:
    cipher, _ = TenantCipher.create(provider, "t")
    with pytest.raises(DecryptionError):
        cipher.open_field(token, aad="f")


def test_kek_rotation_rewraps_without_touching_data() -> None:
    old = os.urandom(32)
    provider_v1 = LocalKeyProvider({"k1": old}, active_key_id="k1")
    cipher, wrapped_v1 = TenantCipher.create(provider_v1, "t")
    token = cipher.seal(b"data", aad="f")

    provider_v2 = LocalKeyProvider({"k1": old, "k2": os.urandom(32)}, active_key_id="k2")
    wrapped_v2 = rewrap(provider_v2, "t", wrapped_v1)
    assert wrapped_v2.key_id == "k2"

    # After k1 is retired, data still opens through the re-wrapped key.
    provider_k2_only = LocalKeyProvider({"k2": provider_v2._keks["k2"]}, active_key_id="k2")
    reopened = TenantCipher.open(provider_k2_only, "t", wrapped_v2)
    assert reopened.open_field(token, aad="f") == b"data"


def test_crypto_shredding_unknown_key_cannot_open() -> None:
    provider = LocalKeyProvider({"k1": os.urandom(32)}, active_key_id="k1")
    _, wrapped = TenantCipher.create(provider, "t")
    destroyed = LocalKeyProvider({"k9": os.urandom(32)}, active_key_id="k9")
    with pytest.raises(KeyProviderError):
        TenantCipher.open(destroyed, "t", wrapped)


def test_wrapped_key_token_round_trip(provider: LocalKeyProvider) -> None:
    _, wrapped = TenantCipher.create(provider, "t")
    assert WrappedKey.from_token(wrapped.to_token()) == wrapped


def test_env_value_parsing() -> None:
    k1, k2 = LocalKeyProvider.generate_kek(), LocalKeyProvider.generate_kek()
    provider = LocalKeyProvider.from_env_value(f"k1:{k1}, k2:{k2}", active_key_id="k2")
    assert provider.active_key_id == "k2"


@pytest.mark.parametrize(
    ("keks", "active"),
    [
        ({"k1": b"short"}, "k1"),
        ({"k1": os.urandom(32)}, "missing"),
        ({"a.b": os.urandom(32)}, "a.b"),
    ],
)
def test_invalid_keyrings_rejected(keks: dict[str, bytes], active: str) -> None:
    with pytest.raises(KeyProviderError):
        LocalKeyProvider(keks, active_key_id=active)


@given(plaintext=st.binary(max_size=4096), aad=st.text(max_size=64))
def test_round_trip_property(plaintext: bytes, aad: str) -> None:
    provider = LocalKeyProvider({"k1": b"\x01" * 32}, active_key_id="k1")
    cipher, _ = TenantCipher.create(provider, "t")
    assert cipher.open_field(cipher.seal(plaintext, aad=aad), aad=aad) == plaintext
