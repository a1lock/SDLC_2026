from app.security import LoginThrottle, hash_password, verify_password


def test_password_is_hashed_with_bcrypt_and_verified():
    hashed = hash_password("Secret-pass-1")
    assert hashed.startswith("$2")
    assert "Secret-pass-1" not in hashed
    assert verify_password("Secret-pass-1", hashed)
    assert not verify_password("secret-pass-1", hashed)


def test_verify_password_handles_garbage_safely():
    assert not verify_password("x" * 100, hash_password("short-pass-1"))  # больше 72 байт
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_throttle_locks_and_unlocks():
    now = [0.0]
    throttle = LoginThrottle(max_attempts=3, lock_seconds=60, clock=lambda: now[0])
    throttle.register_failure("User")
    throttle.register_failure("user")
    assert throttle.seconds_locked("user") == 0
    throttle.register_failure("USER")
    assert throttle.seconds_locked("user") == 60
    now[0] = 59.5
    assert throttle.seconds_locked("user") == 1
    now[0] = 60.0
    assert throttle.seconds_locked("user") == 0
    throttle.register_failure("user")
    assert throttle.seconds_locked("user") == 0


def test_throttle_is_per_login_and_resettable():
    throttle = LoginThrottle(max_attempts=2, lock_seconds=60, clock=lambda: 0.0)
    throttle.register_failure("a")
    throttle.register_failure("a")
    assert throttle.seconds_locked("a") == 60
    assert throttle.seconds_locked("b") == 0
    throttle.reset("a")
    assert throttle.seconds_locked("a") == 0
    throttle.register_failure("b")
    throttle.clear()
    throttle.register_failure("b")
    assert throttle.seconds_locked("b") == 0
