from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from starlette import status

from app.depends import BiometryServiceDependency
from app.models.biometry import (BiometryCreate, BiometryDelete,
                                 BiometryResponse, BiometryUpdate)
from app.models.user import User
from app.pkg.auth import get_current_user

router = APIRouter(
    prefix='/api/v1/biometry',
    tags=['biometry']
)


@router.post("/create", response_model=BiometryResponse)
async def create_biometry(
    biometry_service: BiometryServiceDependency,
    file: Annotated[UploadFile, File(..., description="Фото для биометрии")],
    biometry_data: BiometryCreate,
    current_user: User = Depends(get_current_user)
):
    return await biometry_service.create_biometry(
        biometry_data=biometry_data,
        photo_file=file,
        current_user=current_user
    )


@router.post("/update", response_model=BiometryResponse)
async def update_biometry(
    biometry_service: BiometryServiceDependency,
    file: Annotated[UploadFile, File(..., description="Фото для биометрии")],
    biometry_data: BiometryUpdate,
    current_user: User = Depends(get_current_user)
):
    return await biometry_service.update_biometry(
        biometry_data=biometry_data,
        photo_file=file,
        current_user=current_user
    )


@router.post("/delete")
async def delete_biometry(
    biometry_service: BiometryServiceDependency,
    biometry_data: BiometryDelete,
    current_user: User = Depends(get_current_user)
):
    return await biometry_service.delete_biometry(biometry_data, current_user)


@router.get("/get/{user_id}", response_model=BiometryResponse)
async def get_biometry(
    user_id: str,
    biometry_service: BiometryServiceDependency,
    current_user: User = Depends(get_current_user)
):
    return await biometry_service.get_biometry(user_id, current_user)
