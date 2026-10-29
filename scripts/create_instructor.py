"""Interactive, local-only instructor creation/password rotation. Never logs a password."""
import argparse
from getpass import getpass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="teacher", help="Instructor account or email")
    parser.add_argument("--reset-password", action="store_true", help="Explicitly reset an existing instructor password")
    args = parser.parse_args()
    password = getpass("讲师新密码（至少 12 个字符，不显示输入）：")
    if password != getpass("再次输入密码："):
        print("两次密码不一致。", file=sys.stderr)
        return 1
    from app.db.session import init_db, SessionLocal
    from app.services.instructor_setup import configure_instructor
    init_db()
    with SessionLocal() as db:
        try:
            configure_instructor(db, args.email, password, reset_password=args.reset_password)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
    print("讲师账号已配置，可在登录页选择讲师并输入该账号及密码。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
