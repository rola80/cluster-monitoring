"""auth: 비밀번호 해시/검증 + 로그인 시도 제한 헬퍼."""
from cluster_screening import auth


def test_hash_verify_roundtrip():
    rec = auth.hash_password("s3cret!")
    assert auth.verify_password(rec, "s3cret!")
    assert not auth.verify_password(rec, "wrong")


def test_hash_salt_per_user():
    a = auth.hash_password("same")
    b = auth.hash_password("same")
    assert a["salt"] != b["salt"] and a["hash"] != b["hash"]  # salt 무작위 → 해시 상이


def test_verify_password_손상레코드는_False():
    assert not auth.verify_password({"salt": "zz", "hash": "x"}, "any")


def test_lock_remaining():
    assert auth.lock_remaining(0, 100) == 0
    assert auth.lock_remaining(150, 100) == 50


def test_next_fail_state_escalation():
    fails, lock = 0, 0.0
    for _ in range(auth.LOGIN_MAX_FAILS - 1):       # 임계 직전까지는 잠금 없음
        fails, lock = auth.next_fail_state(fails, now=1000)
        assert lock == 0.0 and fails > 0
    fails, lock = auth.next_fail_state(fails, now=1000)  # 임계 도달 → 잠금
    assert fails == 0 and lock == 1000 + auth.LOGIN_LOCK_SECONDS
