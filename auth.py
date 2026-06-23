"""간단한 다중 사용자 로그인. 추가 패키지 없이 표준 라이브러리만 사용.

- 비밀번호는 평문 저장하지 않고 PBKDF2-HMAC-SHA256(salt, 200k iter) 해시로 users.json 에 저장.
- users.json 은 비밀이므로 git에 올리지 않는다(.gitignore).

계정 관리(CLI):
    python -m cluster_screening.auth add <아이디> [<비밀번호>]   # 비번 생략 시 안전 입력
    python -m cluster_screening.auth list
    python -m cluster_screening.auth delete <아이디>
"""
import os, json, hashlib, hmac

ITERATIONS = 200_000
USERS_PATH = os.path.join(os.path.dirname(__file__), "users.json")


# ── 해시 ──
def hash_password(pw, salt=None, iterations=ITERATIONS):
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, iterations)
    return {"salt": salt.hex(), "hash": dk.hex(), "iter": iterations}


def verify_password(rec, pw):
    try:
        salt = bytes.fromhex(rec["salt"])
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, rec.get("iter", ITERATIONS))
        return hmac.compare_digest(dk.hex(), rec["hash"])
    except Exception:
        return False


# ── 사용자 저장소 ──
def load_users():
    if os.path.exists(USERS_PATH):
        with open(USERS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users):
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def add_user(username, pw):
    users = load_users()
    users[username] = hash_password(pw)
    save_users(users)
    return users


def delete_user(username):
    users = load_users()
    users.pop(username, None)
    save_users(users)


def authenticate(username, pw):
    rec = load_users().get(username)
    return bool(rec) and verify_password(rec, pw)


# ── Streamlit 게이트 ──
def streamlit_login_gate():
    """미로그인 시 로그인 폼을 렌더하고 False 반환. 로그인 상태면 True."""
    import streamlit as st
    if st.session_state.get("auth_user"):
        return True

    st.title("🔒 로그인")
    st.caption("창업·벤처 녹색융합클러스터 — 신청서류 적합 검토")
    with st.form("login_form"):
        username = st.text_input("아이디")
        pw = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인", type="primary")
    if submitted:
        if authenticate(username, pw):
            st.session_state["auth_user"] = username
            st.rerun()
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    if not load_users():
        st.warning("등록된 사용자가 없습니다. 터미널에서 계정을 만드세요:\n\n"
                   "`python -m cluster_screening.auth add <아이디>`")
    return False


def streamlit_logout_button():
    """사이드바에 현재 사용자 표시 + 로그아웃 버튼."""
    import streamlit as st
    user = st.session_state.get("auth_user")
    if user:
        with st.sidebar:
            st.caption(f"👤 로그인: {user}")
            if st.button("로그아웃"):
                del st.session_state["auth_user"]
                st.rerun()


# ── CLI ──
def _main():
    import sys, getpass
    args = sys.argv[1:]
    usage = ("사용법:\n"
             "  python -m cluster_screening.auth add <아이디> [<비밀번호>]\n"
             "  python -m cluster_screening.auth list\n"
             "  python -m cluster_screening.auth delete <아이디>")
    if not args:
        print(usage); return
    cmd = args[0]
    if cmd == "add" and len(args) >= 2:
        username = args[1]
        pw = args[2] if len(args) >= 3 else getpass.getpass("비밀번호: ")
        add_user(username, pw)
        print(f"계정 추가됨: {username}")
    elif cmd == "list":
        users = load_users()
        print("\n".join(users.keys()) if users else "(등록된 사용자 없음)")
    elif cmd == "delete" and len(args) >= 2:
        delete_user(args[1])
        print(f"계정 삭제됨: {args[1]}")
    else:
        print(usage)


if __name__ == "__main__":
    _main()
