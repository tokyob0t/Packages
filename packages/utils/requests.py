import json
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional
from urllib.parse import urlencode

from gi.repository import Gio, GLib, Soup

HTTPMethod = Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']


@dataclass(frozen=True, slots=True)
class Response:
    url: str
    status_code: int
    ok: bool
    reason_phrase: str
    text: str
    bytes: bytes  # not GLib.Bytes
    body: Gio.InputStream

    def json(self) -> dict:
        return json.loads(self.text)


class Requests:
    _session: Soup.Session = Soup.Session()

    @staticmethod
    async def request(
        method: HTTPMethod,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[str | bytes] = None,
    ) -> Response:

        params = params or {}
        headers = headers or {}

        if params:
            url = f'{url}?{urlencode(params)}'

        uri = GLib.Uri.parse(url, GLib.UriFlags.NONE)
        message = Soup.Message.new_from_uri(method, uri)

        for name, value in headers.items():
            message.get_request_headers().append(name, value)

        if body is not None:
            content_type = headers.get('Content-Type', 'text/plain')

            if isinstance(body, str):
                body = body.encode()

            bytes_body = GLib.Bytes.new(body)
            message.set_request_body_from_bytes(content_type, bytes_body)

        stream = await Requests._session.send_async(message,
                                                    GLib.PRIORITY_DEFAULT)

        output = Gio.MemoryOutputStream.new_resizable()

        await output.splice_async(
            stream,
            Gio.OutputStreamSpliceFlags.CLOSE_SOURCE
            | Gio.OutputStreamSpliceFlags.CLOSE_TARGET,
            GLib.PRIORITY_DEFAULT,
        )

        gbytes = output.steal_as_bytes()
        text = gbytes.get_data().decode(errors='replace')

        return Response(
            url=url,
            status_code=message.get_status(),
            ok=200 <= message.get_status() < 300,
            reason_phrase=message.get_reason_phrase(),
            text=text,
            bytes=gbytes.get_data(),
            body=stream,
        )

    @staticmethod
    async def get(
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Response:
        return await Requests.request('GET',
                                      url,
                                      params=params,
                                      headers=headers)

    @staticmethod
    async def post(
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[str | bytes] = None,
    ) -> Response:
        return await Requests.request('POST',
                                      url,
                                      params=params,
                                      headers=headers,
                                      body=body)

    @staticmethod
    async def put(
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[str | bytes] = None,
    ) -> Response:
        return await Requests.request('PUT',
                                      url,
                                      params=params,
                                      headers=headers,
                                      body=body)

    @staticmethod
    async def patch(
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[str | bytes] = None,
    ) -> Response:
        return await Requests.request('PATCH',
                                      url,
                                      params=params,
                                      headers=headers,
                                      body=body)

    @staticmethod
    async def delete(
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Response:
        return await Requests.request('DELETE',
                                      url,
                                      params=params,
                                      headers=headers)
