"""
manage_users.py - generate hashed passwords for users.yaml

USAGE:
------
1. Edit the USERS dict below with your desired username → plain-text password pairs
2. Run:  .venv\Scripts\python.exe utils\manage_users.py
3. Copy the printed YAML block into config/users.yaml under credentials.usernames

The plain-text passwords are NEVER stored anywhere - only the bcrypt hashes
go into users.yaml. You hand the plain-text passwords to users separately.
"""

import bcrypt

# ---------------------------------------------------------------------------
# Edit this - username: plain_text_password
# ---------------------------------------------------------------------------
USERS = {
    "admin":  "admin123",
    "user1":  "changeme1",
    "user2":  "changeme2",
}
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Paste this block into config/users.yaml")
    print("under:  credentials > usernames")
    print("=" * 60)
    print()

    for username, password in USERS.items():
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
        display_name = username.replace("_", " ").title()
        print(f"    {username}:")
        print(f"      name: {display_name}")
        print(f"      password: {hashed}")
        print()

    print("=" * 60)
    print("Plain-text credentials to share with each user:")
    print("=" * 60)
    for username, password in USERS.items():
        print(f"  {username:15} : {password}")
