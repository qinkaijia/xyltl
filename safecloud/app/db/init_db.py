from app.db.database import Base, engine
from app.models import alarm, command, device, telemetry  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("SafeCloud database initialized.")
