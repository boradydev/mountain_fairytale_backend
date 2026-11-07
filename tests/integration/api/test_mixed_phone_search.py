"""BUG-001: real HTTP/SQL regressions on the standard isolated API test database."""

from uuid import uuid4

import pytest

from tests.document_requests import create_delivery
from tests.integration.api.test_delivery_document_routers import TestDeliveryDocumentRouters as API


def marker():
    # No digits: the regression must exercise exactly the digits in QA-CORE-01.
    return uuid4().hex[:16].translate(str.maketrans("0123456789", "ghijklmnop"))


async def query(client, path, params):
    response = await client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("clients_history", [True, False])
async def test_history_mixed_text_and_phone(client, active_employee, client_factory, clients_history):
    await API.login(client, active_employee)
    tag = marker()
    customers = [
        await client_factory(
            name=f"QA-CORE-{number} {tag}",
            phone=f"{tag}-{phone}",
            address=f"Ленина, 10 {tag}" if number == "01" else f"Other {tag}",
        )
        for number, phone in [("01", "0001"), ("10", "0010"), ("11", "0011")]
    ]
    day = "2388-06-01" if clients_history else "2388-06-02"
    docs = []
    for customer in customers:
        response = await create_delivery(
            client, json={"plannedDate": day, "points": [{"clientId": str(customer.client_id), "items": []}]}
        )
        assert response.status_code == 201, response.text
        docs.append(response.json()["data"])
    path = "/protected/client-delivery-history" if clients_history else "/protected/delivery-history"
    params = dict(date_from=day, date_to=day, limit=100)

    async def found(term, **extra):
        body = await query(client, path, params | dict(search=term) | extra)
        rows = body["data"]["deliveries" if clients_history else "documents"]
        ids = [row["pointId" if clients_history else "deliveryDocumentId"] for row in rows]
        assert len(ids) == len(set(ids))
        return body, ids

    ids = [d["points"][0]["pointId"] if clients_history else d["deliveryDocumentId"] for d in docs]
    for term in [f"QA-CORE-01 {tag}", f"  qa-core-01 {tag.upper()}  ", f"Ленина, 10 {tag}"]:
        body, actual = await found(term)
        assert body["total"] == 1
        assert actual == [ids[0]]
    for term in ["QA-CORE-00", f"{tag}-0001", "12A34"]:
        assert (await found(term))[0]["total"] == 0
    body, actual = await found("01")
    assert body["total"] == 3
    assert set(actual) == set(ids)
    page, first = await found("01", limit=1)
    _, second = await found("01", limit=1, offset=1)
    assert page["total"] == 3
    assert first != second
    assert (await found("   "))[0] == (await query(client, path, params))

    if clients_history:
        # Current text/phone finds both points; the historical values find only the old snapshot.
        response = await client.patch(
            f"/protected/clients/{customers[0].client_id}", json=dict(name=f"Changed {tag}", phone=f"{tag}-9876")
        )
        assert response.status_code == 200, response.text
        response = await create_delivery(
            client, json={"plannedDate": day, "points": [{"clientId": str(customers[0].client_id), "items": []}]}
        )
        assert response.status_code == 201, response.text
        newest = response.json()["data"]["points"][0]["pointId"]
        for term in ["9876", "(98) 76", f"Changed {tag}"]:
            body, actual = await found(term)
            assert body["total"] == 2
            assert set(actual) == {ids[0], newest}
        for term in ["0001", f"QA-CORE-01 {tag}"]:
            body, actual = await found(term)
            assert body["total"] == 1
            assert actual == [ids[0]]
        assert (
            await client.post(f"/protected/delivery-route-sheets/{docs[0]['deliveryDocumentId']}/cancel")
        ).status_code == 200
        assert (await found("0001"))[0]["total"] == 0
        pickup = await client.post(
            "/protected/pickup-sheets/create", json={"plannedDate": day, "points": [{"items": []}]}
        )
        assert pickup.status_code == 201
        assert (await found("9876"))[0]["total"] == 1


@pytest.mark.parametrize("mode", ["database", "follow_up"])
async def test_client_list_mixed_text_and_phone(client, active_employee, client_factory, mode):
    await API.login(client, active_employee)
    tag = marker()
    customers = [
        await client_factory(name=f"QA-CORE-{number} {tag}", phone=f"{tag}-{phone}", sleeping_threshold_days=0)
        for number, phone in [("01", "0001"), ("10", "0010"), ("11", "0011")]
    ]
    own = {str(c.client_id) for c in customers}

    async def found(term, **extra):
        body = await query(client, "/protected/clients", dict(mode=mode, search=term, limit=100) | extra)
        return body, {c["clientId"] for c in body["data"]["clients"]}

    for term in [f"QA-CORE-01 {tag}", f"  qa-core-01 {tag.upper()}  "]:
        body, actual = await found(term)
        assert body["total"] == 1
        assert actual == {str(customers[0].client_id)}
    for term in [f"QA-CORE-00 {tag}", f"{tag}-0001"]:
        assert (await found(term))[0]["total"] == 0
    assert (await found("01"))[1] & own == own
    assert (await found("(00) 01"))[1] & own == {str(customers[0].client_id)}
    body, actual = await found(tag, offset=1, limit=1)
    assert body["total"] == 3
    assert len(actual) == 1
    response = await client.patch(f"/protected/clients/{customers[0].client_id}", json={"isActive": False})
    assert response.status_code == 200
    assert (await found(f"QA-CORE-01 {tag}"))[0]["total"] == 0
    body, actual = await found(f"QA-CORE-01 {tag}", include_deactivated=True)
    assert body["total"] == (1 if mode == "database" else 0)


@pytest.mark.parametrize(
    ("path", "mode"),
    [
        ("/protected/clients", "database"),
        ("/protected/clients", "follow_up"),
        ("/protected/client-delivery-history", None),
        ("/protected/delivery-history", None),
    ],
)
async def test_search_metacharacters_remain_literal(client, active_employee, client_factory, path, mode):
    await API.login(client, active_employee)
    tag = marker()
    customers = [
        await client_factory(name=f"{tag}{symbol}name", sleeping_threshold_days=0) for symbol in ["%", "_", "\\", "X"]
    ]
    params = dict(limit=100)
    if mode:
        params["mode"] = mode
    else:
        day = "2389-01-01" if "client-delivery" in path else "2389-01-02"
        params |= dict(date_from=day, date_to=day)
        response = await create_delivery(
            client,
            json={"plannedDate": day, "points": [{"clientId": str(c.client_id), "items": []} for c in customers]},
        )
        assert response.status_code == 201, response.text
    for symbol, customer in zip(["%", "_", "\\"], customers, strict=False):
        body = await query(client, path, params | dict(search=tag + symbol))
        assert body["total"] == 1
        if mode:
            actual = body["data"]["clients"]
        elif "client-delivery" in path:
            actual = body["data"]["deliveries"]
        else:
            actual = body["data"]["documents"][0]["matchedClients"]
        assert [row["clientId"] for row in actual] == [str(customer.client_id)]
