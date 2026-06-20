"""
Add or update a login account.

    python utils/add_user.py --email jane@acme.com --name "Jane Doe" --role admin
    python utils/add_user.py --email bob@acme.com  --name "Bob"      --role viewer --password "s3cret"

Roles: superadmin | admin | viewer  (any string works; the app treats
"superadmin"/"admin" as privileged). If --password is omitted, a strong one is
generated and printed once. Writes bcrypt hashes to config/users.yaml.
List / remove:
    python utils/add_user.py --list
    python utils/add_user.py --remove jane@acme.com
"""
import argparse
import secrets
import string
from pathlib import Path

import bcrypt
import yaml

USERS_FILE = Path(__file__).resolve().parents[1] / "config" / "users.yaml"


def load() -> dict:
    if USERS_FILE.exists():
        return yaml.safe_load(USERS_FILE.read_text(encoding="utf-8")) or {}
    return {}


def save(cfg: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(yaml.dump(cfg, default_flow_style=False, allow_unicode=True), encoding="utf-8")


def gen_password(n: int = 14) -> str:
    pool = string.ascii_letters + string.digits + "!#$%"
    return "".join(secrets.choice(pool) for _ in range(n))


def ensure_shape(cfg: dict) -> dict:
    cfg.setdefault("credentials", {}).setdefault("usernames", {})
    cfg.setdefault("cookie", {"name": "ev_research_auth",
                              "key": "dev-only-change-me-set-AUTH_COOKIE_KEY-in-env",
                              "expiry_days": 30})
    return cfg


def main() -> None:
    ap = argparse.ArgumentParser(description="Manage login accounts")
    ap.add_argument("--email", help="Email / username (the login id)")
    ap.add_argument("--name", help="Display name")
    ap.add_argument("--role", default="admin", help="superadmin | admin | viewer")
    ap.add_argument("--password", help="Password (generated if omitted)")
    ap.add_argument("--list", action="store_true", help="List accounts")
    ap.add_argument("--remove", help="Remove an account by email")
    args = ap.parse_args()

    cfg = ensure_shape(load())
    users = cfg["credentials"]["usernames"]

    if args.list:
        if not users:
            print("No accounts yet.")
        for u, d in users.items():
            print(f"  {u:32}  {d.get('name',''):20}  [{d.get('role','user')}]")
        return

    if args.remove:
        if args.remove in users:
            del users[args.remove]
            save(cfg)
            print(f"Removed {args.remove}")
        else:
            print(f"No such account: {args.remove}")
        return

    if not args.email or not args.name:
        ap.error("--email and --name are required to add/update an account")

    pw = args.password or gen_password()
    users[args.email] = {
        "name": args.name,
        "role": args.role,
        "password": bcrypt.hashpw(pw.encode(), bcrypt.gensalt(12)).decode(),
    }
    save(cfg)
    action = "Updated" if args.email in load()["credentials"]["usernames"] else "Created"
    print(f"{action} account:")
    print(f"  login (email): {args.email}")
    print(f"  password:      {pw}")
    print(f"  role:          {args.role}")
    print("\nShare these credentials with the user. The password is only shown now.")


if __name__ == "__main__":
    main()
