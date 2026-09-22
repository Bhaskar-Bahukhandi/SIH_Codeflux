import argparse
from getpass import getpass

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models.user import User, UserRole
from app.security import hash_password


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a CODEFLUX prototype user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--role",
        required=True,
        choices=[role.value for role in UserRole],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    email = args.email.strip().lower()
    full_name = args.name.strip()

    if not full_name:
        raise SystemExit("Name must not be blank.")

    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    password_hash = hash_password(password)

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(func.lower(User.email) == email))
        if existing is not None:
            raise SystemExit("A user with that email already exists.")

        user = User(
            full_name=full_name,
            email=email,
            role=UserRole(args.role),
            password_hash=password_hash,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    print(f"Created {user.role.value} user {user.email} ({user.id}).")


if __name__ == "__main__":
    main()
