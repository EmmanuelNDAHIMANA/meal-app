"""
Creates your first admin login.

    python create_admin.py

Run it from the project folder (the one containing app.py) so that
.streamlit/secrets.toml is found. Run create_tables.py first.
"""
import getpass
import sys

import auth
import config


def main():
    if not config.DB_PASSWORD:
        print("ERROR: DB_PASSWORD is not set.\n")
        print("Fix: copy .streamlit/secrets.toml.example to .streamlit/secrets.toml,")
        print("put your real password in it, and run this from the project folder.")
        print("Or: export DB_PASSWORD='...'  (set DB_PASSWORD=... on Windows)")
        sys.exit(1)

    print("Create an admin user\n")
    username = input("Username: ").strip()
    if not username:
        print("Username cannot be empty."); sys.exit(1)

    try:
        if auth.get_user(username):
            print(f"User '{username}' already exists.")
            if input("Reset its password instead? [y/N] ").strip().lower() != "y":
                sys.exit(0)
            pwd = getpass.getpass("New password: ")
            if pwd != getpass.getpass("Confirm: "):
                print("Passwords do not match."); sys.exit(1)
            auth.set_password(username, pwd)
            print("Password updated.")
            return
    except Exception as e:
        print(f"Database error: {e}")
        print("\nIf this says 'Access denied ... (using password: NO)', your "
              "DB_PASSWORD is not being read — see the note above.")
        sys.exit(1)

    full_name = input("Full name: ").strip() or username
    pwd = getpass.getpass("Password: ")
    if len(pwd) < 6:
        print("Use at least 6 characters."); sys.exit(1)
    if pwd != getpass.getpass("Confirm password: "):
        print("Passwords do not match."); sys.exit(1)

    auth.create_user(username, pwd, full_name, role="admin")
    print(f"\nAdmin '{username}' created. Start the app with:  streamlit run app.py")


if __name__ == "__main__":
    main()
