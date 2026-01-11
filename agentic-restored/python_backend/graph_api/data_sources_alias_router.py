from typing import List

from fastapi import APIRouter, Query, Response

from graph_api import data_sources_router as ds

router = APIRouter(prefix="/api/_data-sources", tags=["Data Sources (Alias)"])


@router.get("/", response_model=List[ds.DataSource])
async def get_data_sources_alias(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=5000),
):
    return await ds.get_data_sources(response=response, skip=skip, limit=limit)


@router.get("", response_model=List[ds.DataSource], include_in_schema=False)
async def get_data_sources_alias_no_slash(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=5000),
):
    # Avoid relying on redirect-slashes behavior when running behind proxies.
    return await ds.get_data_sources(response=response, skip=skip, limit=limit)


@router.get("/{source_id}", response_model=ds.DataSource)
async def get_data_source_alias(source_id: str):
    return await ds.get_data_source(source_id)


@router.post("/", response_model=ds.DataSourceResponse)
async def create_data_source_alias(source: ds.DataSource):
    return await ds.create_data_source(source)


@router.put("/{source_id}", response_model=ds.DataSourceResponse)
async def update_data_source_alias(source_id: str, source: ds.DataSource):
    return await ds.update_data_source(source_id, source)


@router.delete("/{source_id}", response_model=ds.DataSourceResponse)
async def delete_data_source_alias(source_id: str):
    return await ds.delete_data_source(source_id)


@router.post("/{source_id}/test", response_model=ds.TestConnectionResponse)
async def test_data_source_connection_alias(source_id: str):
    return await ds.test_data_source_connection(source_id)


@router.get("/types/supported")
async def get_supported_types_alias():
    return await ds.get_supported_types()
