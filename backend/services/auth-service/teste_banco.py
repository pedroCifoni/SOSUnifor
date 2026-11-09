from sqlalchemy import text

from app.core.database import engine


def test_database_connection() -> None:
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT 1")
        )

        print(
            "Banco conectado:",
            result.scalar()
        )


if __name__ == "__main__":
    test_database_connection()