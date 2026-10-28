"""Supply current document versions in tests of unrelated API behavior."""

import re
from typing import Any

from httpx import AsyncClient, Response


async def patch_with_revision(client: AsyncClient, url: str, **kwargs: Any) -> Response:
    body = kwargs.get("json")
    if re.fullmatch(r"/protected/(delivery-route-sheets|pickup-sheets)/[^/]+", url) and body:
        if "expectedRevision" not in body:
            response = await client.get(url)
            revision = response.json()["data"]["revision"] if response.status_code == 200 else 1
            kwargs["json"] = {**body, "expectedRevision": revision}
    return await client.patch(url, **kwargs)
