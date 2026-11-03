from os import environ

from sqlalchemy import text


async def test_repository_fixtures_use_repo_test_database(postgres) -> None:
    expected = environ.get("POSTGRES_REPO_TEST_DB", "mountain_fairytale_repo_test")
    async with postgres.session_factory() as session:
        assert await session.scalar(text("SELECT current_database()")) == expected
