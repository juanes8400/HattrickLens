"""Cifrado de los tokens OAuth de CHPP en reposo."""
import pytest

from app.infrastructure.security.tokens import (
    TokenDecryptionError,
    decrypt_token,
    encrypt_token,
)


def test_round_trips() -> None:
    enc = encrypt_token("oauth-token-value")
    assert decrypt_token(enc) == "oauth-token-value"


def test_ciphertext_does_not_contain_the_plaintext() -> None:
    plaintext = "super-secret-oauth-token-42"  # noqa: S105 — test fixture, not a real credential
    enc = encrypt_token(plaintext)
    assert plaintext.encode() not in enc


def test_garbage_fails_to_decrypt() -> None:
    with pytest.raises(TokenDecryptionError):
        decrypt_token(b"not-a-real-fernet-token")
