"""Cliente BAGO para la API oficial de send.now.

Cobertura:
  - account/info, account/stats, dmca/list, files/deleted
  - upload/server, upload/url
  - file/* y folder/*

La API usa GET para la mayoría de operaciones y JSON siempre en respuesta.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


def _env_base_url() -> str:
    return os.environ.get("BAGO_SEND_API_BASE_URL", "https://send.now/api").rstrip("/")


def _env_public_base_url() -> str:
    return os.environ.get("BAGO_SEND_PUBLIC_BASE_URL", "https://send.now").rstrip("/")


class SendNowError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status = status
        self.payload = payload


@dataclass(slots=True)
class SendNowUploadResult:
    file_code: str
    url: str
    payload: Any
    upload_server: dict[str, Any]


class SendNowClient:
    def __init__(
        self,
        api_key: str = "",
        *,
        base_url: str | None = None,
        public_base_url: str | None = None,
        session: requests.Session | None = None,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = (base_url or _env_base_url()).rstrip("/")
        self.public_base_url = (public_base_url or _env_public_base_url()).rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout

    def public_file_url(self, file_code: str) -> str:
        return f"{self.public_base_url}/{file_code}"

    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return f"{self.base_url}/{path_or_url.lstrip('/')}"

    def _json_or_error(self, response: requests.Response) -> Any:
        try:
            payload = response.json()
        except Exception as exc:
            raise SendNowError(f"Respuesta no JSON: {exc}", status=response.status_code) from exc

        if isinstance(payload, list):
            return payload

        if not isinstance(payload, dict):
            return payload

        status = payload.get("status")
        if isinstance(status, int) and status != 200:
            msg = payload.get("msg") or payload.get("message") or f"HTTP {status}"
            raise SendNowError(str(msg), status=status, payload=payload)
        return payload

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        auth: bool = True,
        timeout: int | None = None,
    ) -> Any:
        params = dict(params or {})
        if auth:
            if not self.api_key:
                raise SendNowError("Falta API key de send.now")
            params.setdefault("key", self.api_key)

        resp = self.session.request(
            method,
            self._url(path),
            params=params,
            data=data,
            files=files,
            timeout=timeout or self.timeout,
        )
        payload = self._json_or_error(resp)
        if resp.status_code >= 400:
            if isinstance(payload, dict):
                msg = payload.get("msg") or payload.get("message") or resp.text[:240] or f"HTTP {resp.status_code}"
            else:
                msg = resp.text[:240] or f"HTTP {resp.status_code}"
            raise SendNowError(str(msg), status=resp.status_code, payload=payload)
        return payload

    # ── Account ──────────────────────────────────────────────────────────────

    def account_info(self) -> dict[str, Any]:
        return self._request("GET", "/account/info", auth=True)

    def account_stats(self, last: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if last is not None:
            params["last"] = last
        return self._request("GET", "/account/stats", params=params, auth=True)

    def dmca_reports(self, last: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if last is not None:
            params["last"] = last
        return self._request("GET", "/dmca/list", params=params, auth=True)

    def trash(self, last: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if last is not None:
            params["last"] = last
        return self._request("GET", "/files/deleted", params=params, auth=True)

    # ── Upload ───────────────────────────────────────────────────────────────

    def upload_server(self, *, anon: bool = False) -> dict[str, Any]:
        return self._request("GET", "/upload/server", auth=not anon)

    def upload_file(
        self,
        file_path: str | Path,
        *,
        anon: bool = False,
        utype: str = "prem",
    ) -> SendNowUploadResult:
        file_path = Path(file_path)
        server = self.upload_server(anon=anon)
        upload_url = server.get("result") or server.get("upload_url") or server.get("data", {}).get("upload_url")
        sess_id = server.get("sess_id") or server.get("data", {}).get("sess_id")
        if not upload_url or not sess_id:
            sess_id = ""

        with file_path.open("rb") as fh:
            data = {"utype": utype}
            if sess_id:
                data["sess_id"] = sess_id
            resp = self.session.post(
                upload_url,
                data=data,
                files={"file_0": (file_path.name, fh)},
                timeout=max(self.timeout, 300),
            )
        payload = self._json_or_error(resp)
        if resp.status_code >= 400:
            if isinstance(payload, dict):
                msg = payload.get("msg") or payload.get("message") or resp.text[:240] or f"HTTP {resp.status_code}"
            else:
                msg = resp.text[:240] or f"HTTP {resp.status_code}"
            raise SendNowError(str(msg), status=resp.status_code, payload=payload)

        item: dict[str, Any] = {}
        if isinstance(payload, list) and payload:
            item = payload[0] if isinstance(payload[0], dict) else {}
        elif isinstance(payload, dict):
            item = payload.get("result") if isinstance(payload.get("result"), dict) else payload

        file_code = str(item.get("file_code") or item.get("filecode") or "").strip()
        if not file_code:
            raise SendNowError("upload respondió sin file_code", payload=payload)

        return SendNowUploadResult(
            file_code=file_code,
            url=self.public_file_url(file_code),
            payload=payload,
            upload_server=server,
        )

    def remote_upload(self, url: str, *, anon: bool = False) -> dict[str, Any]:
        return self._request("GET", "/upload/url", params={"url": url}, auth=not anon)

    # ── Files ────────────────────────────────────────────────────────────────

    def file_list(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
        fld_id: int | None = None,
        public: int | None = None,
        created: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if fld_id is not None:
            params["fld_id"] = fld_id
        if public is not None:
            params["public"] = public
        if created:
            params["created"] = created
        if name:
            params["name"] = name
        return self._request("GET", "/file/list", params=params, auth=True)

    def file_info(self, *, file_code: str | None = None, url: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if file_code:
            params["file_code"] = file_code
        if url:
            params["url"] = url
        return self._request("GET", "/file/info", params=params, auth=True)

    def file_rename(self, file_code: str, name: str) -> dict[str, Any]:
        return self._request("GET", "/file/rename", params={"file_code": file_code, "name": name}, auth=True)

    def file_clone(self, file_code: str) -> dict[str, Any]:
        return self._request("GET", "/file/clone", params={"file_code": file_code}, auth=True)

    def file_set_folder(self, file_code: str, fld_id: int) -> dict[str, Any]:
        return self._request("GET", "/file/set_folder", params={"file_code": file_code, "fld_id": fld_id}, auth=True)

    def file_delete(self, file_code: str) -> dict[str, Any]:
        return self._request("GET", "/file/delete", params={"file_code": file_code}, auth=True)

    def file_password(self, file_code: str, file_password: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/file/password",
            params={"file_code": file_code, "file_password": file_password},
            auth=True,
        )

    def file_remove_password(self, file_code: str) -> dict[str, Any]:
        return self._request("GET", "/file/password", params={"file_code": file_code}, auth=True)

    def file_public(self, file_code: str) -> dict[str, Any]:
        return self._request("GET", "/file/public", params={"file_code": file_code}, auth=True)

    def file_private(self, file_code: str) -> dict[str, Any]:
        return self._request("GET", "/file/private", params={"file_code": file_code}, auth=True)

    def file_direct_link(self, file_code: str) -> dict[str, Any]:
        return self._request("GET", "/file/direct_link", params={"file_code": file_code}, auth=True)

    # ── Folders ─────────────────────────────────────────────────────────────

    def folder_list(self, fld_id: int) -> dict[str, Any]:
        return self._request("GET", "/folder/list", params={"fld_id": fld_id}, auth=True)

    def folder_create(self, name: str, parent_id: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"name": name}
        if parent_id is not None:
            params["parent_id"] = parent_id
        return self._request("GET", "/folder/create", params=params, auth=True)

    def folder_rename(self, fld_id: int, name: str) -> dict[str, Any]:
        return self._request("GET", "/folder/rename", params={"fld_id": fld_id, "name": name}, auth=True)

    def folder_move(self, fld_id1: int, fld_id2: int) -> dict[str, Any]:
        return self._request("GET", "/folder/move", params={"fld_id1": fld_id1, "fld_id2": fld_id2}, auth=True)

    def folder_copy(self, fld_id1: int, fld_id2: int) -> dict[str, Any]:
        return self._request("GET", "/folder/copy", params={"fld_id1": fld_id1, "fld_id2": fld_id2}, auth=True)

    def folder_delete(self, fld_id: int) -> dict[str, Any]:
        return self._request("GET", "/folder/delete", params={"fld_id": fld_id}, auth=True)

    def folder_password(self, fld_id: int, fld_passwd: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/folder/password",
            params={"fld_id": fld_id, "fld_passwd": fld_passwd},
            auth=True,
        )

    def folder_remove_password(self, fld_id: int) -> dict[str, Any]:
        return self._request("GET", "/folder/password", params={"fld_id": fld_id}, auth=True)
