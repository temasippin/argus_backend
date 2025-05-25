import json
from logging import Logger, LoggerAdapter
from typing import Any, MutableMapping, Optional

UVICORN_ACCESS_MSG_FORMAT = '%(host)s:%(port)s - "%(method)s %(route)s HTTP/%(http_version)s" %(status_code)s %(status_phrase)s - %(time_consumed)s'
REQUESTS_MSG_FORMAT = '%(params)s'
ERROR_MSG_FORMAT = '%(traceback)s'


class BaseAdapter(LoggerAdapter):
    def __init__(self, logger: Logger, extra: Optional[MutableMapping[str, Any]] = None, fmt: Optional[str] = None):
        if not extra:
            extra = {}

        self.extra: MutableMapping[str, Any] = extra
        super().__init__(logger, extra=extra)
        if not fmt:
            fmt = ''
        self.fmt = fmt

    def _prettify_json(self, *record_fields, indent: int = 4) -> None:
        for el in record_fields:
            self.extra[el] = json.dumps(self.extra[el], indent=indent)


class UvicornAccessAdapter(BaseAdapter):
    def __init__(self, logger: Logger, extra: Optional[dict] = None, fmt: Optional[str] = UVICORN_ACCESS_MSG_FORMAT):
        super().__init__(logger, extra=extra, fmt=fmt)

    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple[Any, MutableMapping[str, Any]]:
        message = self.fmt % self.extra
        return message, kwargs


class RequestsAdapter(BaseAdapter):
    def __init__(self, logger: Logger, extra: Optional[dict] = None, fmt: Optional[str] = REQUESTS_MSG_FORMAT, log_type: str = 'request'):
        super().__init__(logger, extra=extra, fmt=fmt)
        self.log_type = log_type

    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple[Any, MutableMapping[str, Any]]:
        params_dict = dict(self.extra)
        params_dict.update({'type': self.log_type})
        if self.log_type == 'response':
            params_dict.pop('body')
        message = params_dict
        return message, kwargs


class ErrorAdapter(BaseAdapter):
    def __init__(self, logger: Logger, extra: Optional[dict] = None, fmt: Optional[str] = ERROR_MSG_FORMAT):
        super().__init__(logger, extra=extra, fmt=fmt)

    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple[Any, MutableMapping[str, Any]]:
        self.extra['msg'] = msg
        message = self.fmt % self.extra
        return message, kwargs
