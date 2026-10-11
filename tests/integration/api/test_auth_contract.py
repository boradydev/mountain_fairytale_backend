from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select, update

from src.common.api.app import fastapi_app
from src.core.uuid7 import uuid7
from src.feat.employees.domain.employee_entities import Employee


async def login(client, employee, password=None):
    response = await client.post(
        "/public/auth/login",
        json={"username": employee.username, "password": employee.password if password is None else password},
    )
    assert response.status_code == 200
    tokens = response.json()["data"]
    client.cookies.clear()
    return tokens


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


async def test_users_public_active_only(client, active_employee, inactive_employee, admin_employee):
    client.cookies.clear()
    response = await client.get("/public/auth/users")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"offset", "limit", "total", "message", "data"}
    assert all(isinstance(username, str) for username in body["data"])
    assert active_employee.username in body["data"]
    assert admin_employee.username in body["data"]
    assert inactive_employee.username not in body["data"]
    assert body["offset"] is None
    assert body["limit"] is None
    assert body["total"] is None


async def test_users_order_and_rename(client, employee_factory, employees_uow_factory, admin_employee):
    first = await employee_factory(username=f"z_{uuid7()}")
    second = await employee_factory(username=f"a_{uuid7()}")
    tied_at = datetime(2020, 1, 1)
    async with employees_uow_factory() as uow:
        for prepared in (first, second):
            employee = await uow.employees.get_by_id(prepared.employee_id)
            assert employee is not None
            employee.created_at = tied_at
            await uow.employees.update(employee)
        await uow.commit(events=[])
    expected = [employee.username for employee in sorted((first, second), key=lambda item: item.employee_id)]
    response = await client.get("/public/auth/users")
    assert response.status_code == 200
    assert [name for name in response.json()["data"] if name in expected] == expected
    tokens = await login(client, admin_employee)
    renamed = f"renamed_{uuid7()}"
    response = await client.patch(
        f"/admin/employees/{first.employee_id}",
        json={"username": renamed},
        headers=bearer(tokens["accessToken"]),
    )
    assert response.status_code == 200
    response = await client.get("/public/auth/users")
    expected = [renamed if name == first.username else name for name in expected]
    assert [name for name in response.json()["data"] if name in expected] == expected


async def test_users_empty_list(client, postgres):
    # Isolated temporary data setup; restore all original activity flags even on failure.
    async with postgres.session_factory() as session:
        active_ids = list(
            (
                await session.execute(
                    select(Employee.employee_id).where(Employee.is_active.is_(True)),
                )
            ).scalars()
        )
        await session.execute(update(Employee).values(is_active=False))
        await session.commit()
    try:
        response = await client.get("/public/auth/users")
        assert response.status_code == 200
        assert response.json()["data"] == []
    finally:
        async with postgres.session_factory() as session:
            await session.execute(update(Employee).where(Employee.employee_id.in_(active_ids)).values(is_active=True))
            await session.commit()


async def test_login_empty_password_and_uniform_rejection(client, employee_factory, inactive_employee):
    empty = await employee_factory(password="")
    regular = await employee_factory()
    await login(client, empty)
    responses = []
    for username, password in (
        (regular.username, ""),
        (regular.username, "wrong"),
        (inactive_employee.username, inactive_employee.password),
        (f"missing_{uuid7()}", "wrong"),
    ):
        response = await client.post("/public/auth/login", json={"username": username, "password": password})
        assert response.status_code == 401
        responses.append(response.json())
    assert all(body == responses[0] for body in responses)
    assert all(username not in str(responses) for username in (regular.username, inactive_employee.username))


async def test_me_returns_current_database_values(client, active_employee, admin_employee):
    tokens = await login(client, active_employee)
    response = await client.get("/protected/me", headers=bearer(tokens["accessToken"]))
    assert response.status_code == 200
    assert response.json()["data"] == {
        "employeeId": str(active_employee.employee_id),
        "username": active_employee.username,
        "role": "employee",
    }
    admin_tokens = await login(client, admin_employee)
    renamed = f"new_{uuid7()}"
    response = await client.patch(
        f"/admin/employees/{active_employee.employee_id}",
        json={"username": renamed},
        headers=bearer(admin_tokens["accessToken"]),
    )
    assert response.status_code == 200
    response = await client.get("/protected/me", headers=bearer(tokens["accessToken"]))
    assert response.status_code == 200
    assert response.json()["data"]["username"] == renamed


@pytest.mark.parametrize("path", ["/protected/me", "/protected/cars"])
@pytest.mark.parametrize(
    "kind", ["missing", "invalid", "expired", "refresh", "wrong_signature", "missing_exp", "bad_id"]
)
async def test_protected_rejects_invalid_access(client, active_employee, token_service_factory, path, kind):
    tokens = await login(client, active_employee)
    settings = fastapi_app.state.ctx.token_settings
    token = "not.a.jwt"
    if kind == "expired":
        token = token_service_factory(access_expire=-1).create_access_token(
            employee_id=str(active_employee.employee_id),
            role="employee",
        )
    elif kind == "refresh":
        token = tokens["refreshToken"]
    elif kind in {"wrong_signature", "missing_exp", "bad_id"}:
        payload = {
            "employee_id": str(active_employee.employee_id),
            "role": "employee",
            "token_type": "access",
            "exp": datetime.now(UTC) + timedelta(minutes=15),
        }
        if kind == "missing_exp":
            payload.pop("exp")
        if kind == "bad_id":
            payload["employee_id"] = "not-a-uuid"
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY if kind != "wrong_signature" else "different-signing-key-for-test",
            algorithm=settings.JWT_ALGORITHM,
        )
    response = await client.get(path, headers={} if kind == "missing" else bearer(token))
    assert response.status_code == 401


async def test_me_missing_employee(client, token_service_factory):
    token = token_service_factory(access_expire=900).create_access_token(employee_id=str(uuid7()), role="employee")
    client.cookies.clear()
    response = await client.get("/protected/me", headers=bearer(token))
    assert response.status_code == 404


async def test_jwt_ttl_and_old_tokens_survive_refresh(client, active_employee):
    before = datetime.now(UTC).timestamp()
    old = await login(client, active_employee)
    after = datetime.now(UTC).timestamp()
    for key, seconds in (("accessToken", 900), ("refreshToken", 90 * 86400)):
        payload = jwt.decode(old[key], options={"verify_signature": False})
        assert before + seconds - 1 <= payload["exp"] <= after + seconds
        assert "password" not in payload
        assert "password_hash" not in payload
    for _ in range(2):
        response = await client.post("/public/auth/refresh", json={"refreshToken": old["refreshToken"]})
        assert response.status_code == 200
        client.cookies.clear()
        new = response.json()["data"]
        for token in (old["accessToken"], new["accessToken"]):
            response = await client.get("/protected/me", headers=bearer(token))
            assert response.status_code == 200


async def test_month_old_refresh_restores_session(client, active_employee):
    settings = fastapi_app.state.ctx.token_settings
    issued = datetime.now(UTC) - timedelta(days=30)
    token = jwt.encode(
        {
            "employee_id": str(active_employee.employee_id),
            "token_type": "refresh",
            "iat": issued,
            "exp": issued + timedelta(days=90),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    client.cookies.clear()
    response = await client.post("/public/auth/refresh", json={"refreshToken": token})
    assert response.status_code == 200
    assert set(response.json()["data"]) == {"accessToken", "refreshToken"}


async def test_deactivation_after_dropdown_blocks_login_refresh_only(client, active_employee, admin_employee):
    tokens = await login(client, active_employee)
    response = await client.get("/public/auth/users")
    assert active_employee.username in response.json()["data"]
    admin_tokens = await login(client, admin_employee)
    response = await client.patch(
        f"/admin/employees/{active_employee.employee_id}",
        json={"isActive": False},
        headers=bearer(admin_tokens["accessToken"]),
    )
    assert response.status_code == 200
    response = await client.post(
        "/public/auth/login", json={"username": active_employee.username, "password": active_employee.password}
    )
    assert response.status_code == 401
    response = await client.post("/public/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert response.status_code == 403
    response = await client.get("/protected/me", headers=bearer(tokens["accessToken"]))
    assert response.status_code == 200
    response = await client.get("/public/auth/users")
    assert active_employee.username not in response.json()["data"]


async def test_password_change_uses_actor_and_preserves_tokens(client, active_employee, employee_factory):
    other = await employee_factory()
    tokens = await login(client, active_employee)
    for password in ("", "new_password"):
        response = await client.put(
            "/protected/me/change-password",
            headers=bearer(tokens["accessToken"]),
            json={"password": password, "employeeId": str(other.employee_id)},
        )
        assert response.status_code == 200
        assert response.json()["data"] is None
        await login(client, active_employee, password=password)
        await login(client, other)
        response = await client.post("/public/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
        assert response.status_code == 200
        client.cookies.clear()
    response = await client.post(
        "/public/auth/login", json={"username": active_employee.username, "password": active_employee.password}
    )
    assert response.status_code == 401


async def test_logout_clears_cookies_without_revoking_tokens(client, active_employee):
    second = await login(client, active_employee)
    response = await client.post(
        "/public/auth/login",
        json={"username": active_employee.username, "password": active_employee.password},
    )
    assert response.status_code == 200
    first = response.json()["data"]
    assert client.cookies.get("access-token") == first["accessToken"]
    assert client.cookies.get("refresh-token") == first["refreshToken"]
    response = await client.post("/protected/me/logout", headers=bearer(first["accessToken"]))
    assert response.status_code == 200
    assert response.json()["data"] is None
    assert client.cookies.get("access-token") is None
    assert client.cookies.get("refresh-token") is None
    for pair in (first, second):
        response = await client.get("/protected/me", headers=bearer(pair["accessToken"]))
        assert response.status_code == 200
        response = await client.post("/public/auth/refresh", json={"refreshToken": pair["refreshToken"]})
        assert response.status_code == 200
        client.cookies.clear()


@pytest.mark.parametrize("username", ["", " ", "\t\n"])
async def test_blank_username_rejected(client, admin_employee, active_employee, username):
    tokens = await login(client, admin_employee)
    response = await client.post(
        "/admin/employees/create",
        headers=bearer(tokens["accessToken"]),
        json={"username": username, "password": "", "commissionPercent": 0},
    )
    assert response.status_code == 422
    response = await client.patch(
        f"/admin/employees/{active_employee.employee_id}",
        headers=bearer(tokens["accessToken"]),
        json={"username": username},
    )
    assert response.status_code == 422


async def test_admin_cannot_be_deactivated_or_created_via_api(client, admin_employee):
    tokens = await login(client, admin_employee)
    response = await client.patch(
        f"/admin/employees/{admin_employee.employee_id}",
        headers=bearer(tokens["accessToken"]),
        json={"isActive": False},
    )
    assert response.status_code == 403
    response = await client.get(f"/admin/employees/{admin_employee.employee_id}", headers=bearer(tokens["accessToken"]))
    assert response.json()["data"]["isActive"] is True
    response = await client.post(
        "/admin/employees/create",
        headers=bearer(tokens["accessToken"]),
        json={"username": f"new_{uuid7()}", "password": "", "commissionPercent": 0, "role": "admin"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["role"] == "employee"


async def test_regular_employee_cannot_reset_another_password(client, active_employee, employee_factory):
    other = await employee_factory()
    tokens = await login(client, active_employee)
    response = await client.put(
        f"/admin/employees/{other.employee_id}/change-password",
        headers=bearer(tokens["accessToken"]),
        json={"password": "unauthorized_password"},
    )
    assert response.status_code == 403
    await login(client, other)


async def test_me_supports_access_cookie(client, active_employee):
    response = await client.post(
        "/public/auth/login",
        json={"username": active_employee.username, "password": active_employee.password},
    )
    assert response.status_code == 200
    response = await client.get("/protected/me")
    assert response.status_code == 200
    assert response.json()["data"]["employeeId"] == str(active_employee.employee_id)


async def test_refresh_rejects_access_token(client, active_employee):
    tokens = await login(client, active_employee)
    response = await client.post("/public/auth/refresh", json={"refreshToken": tokens["accessToken"]})
    assert response.status_code == 401


async def test_bootstrap_and_cli_follow_renamed_admin(client, employees_uow_factory, postgres, monkeypatch):
    from src.common.cli.main import change_admin_password
    from src.common.infra.bootstrap.admins.ensure_admin import ensure_admin

    async with employees_uow_factory() as uow:
        admin = await uow.employees.get_admin()
        assert admin is not None
        admin_id = admin.employee_id
        original_username = admin.username
        original_hash = admin.password_hash
    settings = fastapi_app.state.ctx.token_settings
    access = fastapi_app.state.ctx.token_service.create_access_token(employee_id=str(admin_id), role="admin")
    renamed = f"bootstrap_{uuid7()}"
    try:
        response = await client.patch(
            f"/admin/employees/{admin_id}",
            headers=bearer(access),
            json={"username": renamed},
        )
        assert response.status_code == 200
        response = await client.put(
            "/protected/me/change-password",
            headers=bearer(access),
            json={"password": "chosen_password"},
        )
        assert response.status_code == 200
        response = await client.get("/public/auth/users")
        users_before = response.json()["data"]
        monkeypatch.setenv("ADMIN_USERNAME", f"env_{uuid7()}")
        monkeypatch.setenv("ADMIN_PASSWORD", "different_env_password")
        await ensure_admin(
            uow=employees_uow_factory(),
            password_service=fastapi_app.state.ctx.passwd_service,
        )
        response = await client.get("/public/auth/users")
        assert response.json()["data"] == users_before
        response = await client.post(
            "/public/auth/login",
            json={"username": renamed, "password": "chosen_password"},
        )
        assert response.status_code == 200
        answers = iter(("cli_password", "cli_password"))
        monkeypatch.setattr("src.common.cli.main.getpass.getpass", lambda _prompt: next(answers))
        await change_admin_password()
        client.cookies.clear()
        response = await client.post(
            "/public/auth/login",
            json={"username": renamed, "password": "cli_password"},
        )
        assert response.status_code == 200
        client.cookies.clear()
        # Previously issued JWT remains valid after CLI password recovery.
        response = await client.get("/protected/me", headers=bearer(access))
        assert response.status_code == 200
        assert response.json()["data"]["employeeId"] == str(admin_id)
        assert settings.ACCESS_TOKEN_EXPIRE_SECONDS == 900
    finally:
        async with postgres.session_factory() as session:
            await session.execute(
                update(Employee)
                .where(Employee.employee_id == admin_id)
                .values(username=original_username, password_hash=original_hash),
            )
            await session.commit()
