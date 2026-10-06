from types import NoneType
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from src.api.fastapi.common.api_excs import UnauthorizedException
from src.api.fastapi.common.deps import (
    AccessTokenPayloadDep,
    Context,
)
from src.api.fastapi.common.excs_handlers import map_exceptions_to_responses
from src.api.fastapi.common.schemas import StdResponse
from src.api.fastapi.payment_methods.payment_method_schemas import (
    PaymentMethodResp,
    PaymentMethodsResp,
    CreatePaymentMethodReq,
    UpdatePaymentMethodReq,
)
from src.domain.payment_methods import payment_method_excs


payment_methods_router = APIRouter(
    prefix="/payment-methods",
    tags=["Способы оплаты"],
)


@payment_methods_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PaymentMethodsResp],
    responses=map_exceptions_to_responses(UnauthorizedException),
)
async def get_payment_methods(
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
    include_deactivated: Annotated[bool, Query()] = False,
) -> StdResponse[PaymentMethodsResp]:
    pass


@payment_methods_router.get(
    "/{payment_method_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PaymentMethodResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        payment_method_excs.PaymentMethodNotFoundException,
    ),
)
async def get_payment_method(
    payment_method_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PaymentMethodResp]:
    pass


@payment_methods_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[PaymentMethodResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        payment_method_excs.PaymentMethodNameAlreadyExistsException,
        payment_method_excs.PaymentMethodDomainUpdateException,
    ),
)
async def create_payment_method(
    body: CreatePaymentMethodReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PaymentMethodResp]:
    pass


@payment_methods_router.patch(
    "/{payment_method_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PaymentMethodResp],
    responses=map_exceptions_to_responses(
        UnauthorizedException,
        payment_method_excs.PaymentMethodNotFoundException,
        payment_method_excs.PaymentMethodNameAlreadyExistsException,
        payment_method_excs.PaymentMethodDomainUpdateException,
    ),
)
async def update_payment_method(
    payment_method_id: UUID,
    body: UpdatePaymentMethodReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PaymentMethodResp]:
    pass


@payment_methods_router.get(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[PaymentMethodResp | NoneType],
    responses=map_exceptions_to_responses(UnauthorizedException),
    description="""
    Поиск дубликата способа оплаты.
    Порог similarity: name >= 0.35.
    """,
)
async def check_duplicate_payment_method(
    name: Annotated[str, Query(min_length=1, max_length=120)],
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[PaymentMethodResp | None]:
    pass
