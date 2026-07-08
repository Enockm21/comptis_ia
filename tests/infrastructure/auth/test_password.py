from comptis.infrastructure.auth.password import BcryptPasswordHasher


def test_hash_and_verify_roundtrip():
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash("my_password")
    assert hasher.verify("my_password", hashed) is True


def test_wrong_password_returns_false():
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash("correct")
    assert hasher.verify("wrong", hashed) is False


def test_two_hashes_of_same_password_differ():
    hasher = BcryptPasswordHasher()
    h1 = hasher.hash("same")
    h2 = hasher.hash("same")
    assert h1 != h2
