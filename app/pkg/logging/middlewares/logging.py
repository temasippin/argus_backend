import json
import time
import typing
from json import JSONDecodeError

from fastapi.responses import Response
from starlette.middleware.base import (BaseHTTPMiddleware,
                                       RequestResponseEndpoint)
from starlette.requests import Request
from starlette.responses import StreamingResponse

from app.pkg.logging.logs.helpers import log_requests, log_uvicorn_access


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def validate_body(body: typing.Any) -> typing.Any:
        if not body:
            return None
        try:
            return json.loads(body)
        except (JSONDecodeError, UnicodeDecodeError):
            return body

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        req_body = await request.body()

        route = request.url.path
        req_query = dict(request.query_params)

        log_requests(route=route, body=self.validate_body(req_body), log_type='request', query=req_query)

        start = time.time()
        response = typing.cast(StreamingResponse, await call_next(request))
        end = time.time()

        time_consumed = (end - start) * 1000
        time_consumed = round(time_consumed, 3)
        time_consumed = f'{time_consumed} ms'

        res_body: bytes = b''
        async for chunk in response.body_iterator:
            res_body += chunk if isinstance(chunk, bytes) else chunk.encode()

        log_uvicorn_access(request=request, response=response, time_consumed=time_consumed)

        log_requests(route=route, body=self.validate_body(res_body), log_type='response', time_consumed=time_consumed)

        return Response(content=res_body, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
