import http
import logging
import traceback
from typing import NotRequired, TypedDict, Unpack

from fastapi import Response
from fastapi.requests import Request
from pythonjsonlogger.jsonlogger import JsonFormatter

from app.pkg.logging.logs.adapters import (ErrorAdapter, RequestsAdapter,
                                           UvicornAccessAdapter)

ERROR_LOGGER = logging.getLogger('error')
REQUESTS_LOGGER = logging.getLogger('requests')
UVICORN_ACCESS_LOGGER = logging.getLogger('uvicorn.console')


class NestedJSONFormatter(JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record.update(record.__dict__)


class RequestsLogData(TypedDict):
    route: str
    body: dict
    query: NotRequired[dict]
    log_type: NotRequired[str]
    time_consumed: NotRequired[str]


def exc_to_log(request: Request):
    tb = traceback.format_exc(chain=False)
    tb = ''.join(tb).replace('^', '')

    error_adapter = ErrorAdapter(ERROR_LOGGER, extra={'traceback': tb})
    error_adapter.error('')

    extra = {
        'route': request.url.path,
        'client': request.client.host if request.client else None,
        'headers': dict(request.headers.items()),
    }
    adapter = RequestsAdapter(REQUESTS_LOGGER, extra=extra, log_type='error')
    adapter.info('')


def log_uvicorn_access(request: Request, response: Response, time_consumed: str):
    extra = {
        'host': request.client.host if request.client else None,
        'port': request.client.port if request.client else None,
        'status_code': response.status_code,
        'status_phrase': http.HTTPStatus(response.status_code).phrase,
        'http_version': request.scope.get('http_version'),
        'route': request.url.path,
        'method': request.method,
        'time_consumed': time_consumed,
    }
    adapter = UvicornAccessAdapter(UVICORN_ACCESS_LOGGER, extra=extra)
    adapter.info('')


def log_requests(**kwargs: Unpack[RequestsLogData]):
    if kwargs.get('query') is None:
        kwargs['query'] = {}
    log_type = kwargs.pop('log_type')
    if log_type == 'response':
        kwargs.pop('query')
    adapter = RequestsAdapter(REQUESTS_LOGGER, extra=kwargs, log_type=log_type)
    adapter.info('')
