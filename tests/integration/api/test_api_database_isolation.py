from os import environ

from sqlalchemy import text

from src.common.api.app import fastapi_app


async def test_api_lifespan_and_fixtures_use_api_test_database(client, postgres) -> None:
    expected = environ.get("POSTGRES_API_TEST_DB", "mountain_fairytale_api_test")
    async with postgres.session_factory() as session:
        assert await session.scalar(text("SELECT current_database()")) == expected
    async with fastapi_app.state.ctx.postgres_session_factory() as session:
        assert await session.scalar(text("SELECT current_database()")) == expected
    assert (await client.get("/health/ready")).status_code == 200
