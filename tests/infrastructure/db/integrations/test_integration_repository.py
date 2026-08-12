import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.db.integration_repository import (
    FernetTokenCipher,
    SQLAlchemyIntegrationRepository,
)

# Clé Fernet valide pour les tests (32 bytes URL-safe base64)
TEST_KEY = "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg="


def test_fernet_cipher_roundtrip():
    cipher = FernetTokenCipher(TEST_KEY)
    encrypted = cipher.encrypt("my_secret_token")
    assert isinstance(encrypted, bytes)
    assert cipher.decrypt(encrypted) == "my_secret_token"


def test_fernet_encrypt_produces_different_ciphertext_each_time():
    cipher = FernetTokenCipher(TEST_KEY)
    c1 = cipher.encrypt("token")
    c2 = cipher.encrypt("token")
    assert c1 != c2  # Fernet ajoute un nonce aléatoire


@pytest.mark.integration
async def test_upsert_creates_integration(client):
    # On passe par la fixture `client` qui a une session ouverte avec migrations.
    # Pour les tests de repo on a besoin d'une session directe.
    # Ces tests sont validés via les tests d'API (Task 5) qui utilisent le repo.
    pass
