#!/usr/bin/env python3
"""CLI explícito para la API oficial de send.now.

Ejemplos:
  bago sendnow account info
  bago sendnow files list
  bago sendnow files info --code ABC123
  bago sendnow upload file ruta\archivo.zip
  bago sendnow folder create --name "Docs" --parent 58
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.table import Table

from bago.constants import USER_BAGO
from bago.sendnow_api import SendNowClient, SendNowError
from bago.tumba import tumba_get


console = Console()


def _load_credentials() -> dict[str, Any]:
    cred_file = USER_BAGO / "credentials.json"
    if not cred_file.exists():
        return {}
    try:
        return json.loads(cred_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _resolve_api_key() -> str:
    for key in (
        os.environ.get("BAGO_SEND_API_KEY", ""),
        os.environ.get("SENDNOW_API_KEY", ""),
        os.environ.get("SENDCM_API_KEY", ""),
    ):
        if key.strip():
            return key.strip()

    creds = _load_credentials()
    token = creds.get("sendcm", {}).get("api_key", "")
    if token:
        return str(token).strip()

    for key_name in ("SendCM API Key", "sendnow api key", "sendcm api key", "sendcm"):
        token = tumba_get(key_name)
        if token:
            return token.strip()

    return ""


def _client_from_args(args: argparse.Namespace, require_key: bool = True) -> SendNowClient:
    api_key = getattr(args, "api_key", "") or _resolve_api_key()
    if require_key and not api_key and not getattr(args, "anon", False):
        raise SystemExit("Falta API key. Usa credentials/tumba o pasa --api-key.")
    return SendNowClient(
        api_key=api_key,
        base_url=getattr(args, "base_url", None),
        public_base_url=getattr(args, "public_base_url", None),
    )


def _json(obj: Any) -> None:
    console.print_json(data=json.dumps(obj, ensure_ascii=False, indent=2))


def _print_table(title: str, columns: list[str], rows: list[list[Any]]) -> None:
    table = Table(title=title, box=box.SIMPLE_HEAVY)
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(v) for v in row])
    console.print(table)


def _print_payload(payload: Any, as_json: bool = False) -> None:
    if as_json:
        _json(payload)
    else:
        console.print_json(data=json.dumps(payload, ensure_ascii=False, indent=2))


def _account_info(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    data = client.account_info()
    result = data.get("result", {})
    _print_table(
        "send.now account/info",
        ["campo", "valor"],
        [
            ["email", result.get("email", "")],
            ["balance", result.get("balance", "")],
            ["premium_bandwidth", result.get("premium_bandwidth", "")],
            ["storage_used", result.get("storage_used", "")],
            ["storage_left", result.get("storage_left", "")],
            ["premium_expire", result.get("premium_expire", "")],
            ["status", data.get("status", "")],
            ["msg", data.get("msg", "")],
        ],
    )
    return 0


def _account_stats(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    data = client.account_stats(args.last)
    rows = data.get("result", [])
    if args.json:
        _json(data)
        return 0
    if not rows:
        console.print("[dim]Sin datos.[/dim]")
        return 0
    table = Table(title="send.now account/stats", box=box.SIMPLE_HEAVY)
    for col in ("day", "downloads", "sales", "profit_total", "profit_dl", "profit_site", "profit_refs", "profit_rebills", "profit_sales"):
        table.add_column(col)
    for row in rows:
        table.add_row(
            str(row.get("day", "")),
            str(row.get("downloads", "")),
            str(row.get("sales", "")),
            str(row.get("profit_total", "")),
            str(row.get("profit_dl", "")),
            str(row.get("profit_site", "")),
            str(row.get("profit_refs", "")),
            str(row.get("profit_rebills", "")),
            str(row.get("profit_sales", "")),
        )
    console.print(table)
    return 0


def _dmca(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    data = client.dmca_reports(args.last)
    if args.json:
        _json(data)
        return 0
    rows = data.get("result", [])
    table = Table(title="send.now dmca/list", box=box.SIMPLE_HEAVY)
    for col in ("file_code", "name", "del_time"):
        table.add_column(col)
    for row in rows:
        table.add_row(str(row.get("file_code", "")), str(row.get("name", "")), str(row.get("del_time", "")))
    console.print(table)
    return 0


def _trash(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    data = client.trash(args.last)
    if args.json:
        _json(data)
        return 0
    rows = data.get("result", [])
    table = Table(title="send.now files/deleted", box=box.SIMPLE_HEAVY)
    for col in ("file_code", "name", "deleted", "deleted_ago_sec"):
        table.add_column(col)
    for row in rows:
        table.add_row(
            str(row.get("file_code", "")),
            str(row.get("name", "")),
            str(row.get("deleted", "")),
            str(row.get("deleted_ago_sec", "")),
        )
    console.print(table)
    return 0


def _upload_server(args: argparse.Namespace) -> int:
    client = _client_from_args(args, require_key=not args.anon)
    data = client.upload_server(anon=args.anon)
    if args.json:
        _json(data)
        return 0
    _print_table(
        "send.now upload/server",
        ["campo", "valor"],
        [
            ["result", data.get("result", "")],
            ["sess_id", data.get("sess_id", "")],
            ["status", data.get("status", "")],
            ["msg", data.get("msg", "")],
        ],
    )
    return 0


def _upload_file(args: argparse.Namespace) -> int:
    client = _client_from_args(args, require_key=not args.anon)
    upload = client.upload_file(args.file, anon=args.anon)
    if args.json:
        _json(
            {
                "file_code": upload.file_code,
                "url": upload.url,
                "payload": upload.payload,
                "upload_server": upload.upload_server,
            }
        )
        return 0
    console.print(f"[green]file_code[/green]: {upload.file_code}")
    console.print(f"[green]url[/green]: {upload.url}")
    return 0


def _remote_upload(args: argparse.Namespace) -> int:
    client = _client_from_args(args, require_key=not args.anon)
    data = client.remote_upload(args.url, anon=args.anon)
    if args.json:
        _json(data)
        return 0
    result = data.get("result", {})
    filecode = result.get("filecode") or result.get("file_code") or ""
    console.print(f"[green]filecode[/green]: {filecode}")
    return 0


def _files_list(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    data = client.file_list(
        page=args.page,
        per_page=args.per_page,
        fld_id=args.fld_id,
        public=args.public,
        created=args.created,
        name=args.name,
    )
    if args.json:
        _json(data)
        return 0
    result = data.get("result", {})
    rows = result.get("files", [])
    table = Table(title="send.now file/list", box=box.SIMPLE_HEAVY)
    for col in ("file_code", "name", "fld_id", "public", "downloads", "size", "uploaded", "link"):
        table.add_column(col)
    for row in rows:
        table.add_row(
            str(row.get("file_code", "")),
            str(row.get("name", "")),
            str(row.get("fld_id", "")),
            str(row.get("public", "")),
            str(row.get("downloads", "")),
            str(row.get("size", "")),
            str(row.get("uploaded", "")),
            str(row.get("link", "")),
        )
    console.print(table)
    return 0


def _files_info(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    data = client.file_info(file_code=args.code, url=args.url)
    if args.json:
        _json(data)
        return 0
    _print_payload(data, as_json=False)
    return 0


def _files_rename(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.file_rename(args.code, args.name), as_json=args.json)
    return 0


def _files_copy(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.file_clone(args.code), as_json=args.json)
    return 0


def _files_move(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.file_set_folder(args.code, args.folder), as_json=args.json)
    return 0


def _files_delete(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.file_delete(args.code), as_json=args.json)
    return 0


def _files_password(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.file_password(args.code, args.password), as_json=args.json)
    return 0


def _files_unpassword(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.file_remove_password(args.code), as_json=args.json)
    return 0


def _files_public(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.file_public(args.code), as_json=args.json)
    return 0


def _files_private(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.file_private(args.code), as_json=args.json)
    return 0


def _files_direct_link(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.file_direct_link(args.code), as_json=args.json)
    return 0


def _folder_list(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    data = client.folder_list(args.folder)
    if args.json:
        _json(data)
        return 0
    result = data.get("result", {})
    folders = result.get("folders", [])
    files = result.get("files", [])
    if folders:
        table = Table(title="send.now folder/list - folders", box=box.SIMPLE_HEAVY)
        for col in ("fld_id", "name", "code", "fld_files"):
            table.add_column(col)
        for row in folders:
            table.add_row(
                str(row.get("fld_id", "")),
                str(row.get("name", "")),
                str(row.get("code", "")),
                str(row.get("fld_files", "")),
            )
        console.print(table)
    if files:
        table = Table(title="send.now folder/list - files", box=box.SIMPLE_HEAVY)
        for col in ("file_code", "name", "fld_id", "uploaded", "link"):
            table.add_column(col)
        for row in files:
            table.add_row(
                str(row.get("file_code", "")),
                str(row.get("name", "")),
                str(row.get("fld_id", "")),
                str(row.get("uploaded", "")),
                str(row.get("link", "")),
            )
        console.print(table)
    return 0


def _folder_create(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.folder_create(args.name, parent_id=args.parent), as_json=args.json)
    return 0


def _folder_rename(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.folder_rename(args.folder, args.name), as_json=args.json)
    return 0


def _folder_move(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.folder_move(args.source, args.dest), as_json=args.json)
    return 0


def _folder_copy(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.folder_copy(args.source, args.dest), as_json=args.json)
    return 0


def _folder_delete(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.folder_delete(args.folder), as_json=args.json)
    return 0


def _folder_password(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.folder_password(args.folder, args.password), as_json=args.json)
    return 0


def _folder_unpassword(args: argparse.Namespace) -> int:
    client = _client_from_args(args)
    _print_payload(client.folder_remove_password(args.folder), as_json=args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bago sendnow", description="Cliente CLI para send.now")
    parser.add_argument("--api-key", default="", help="API key explícita")
    parser.add_argument("--base-url", default="", help="Base URL API (por defecto https://send.now/api)")
    parser.add_argument("--public-base-url", default="", help="Base URL pública (por defecto https://send.now)")
    parser.add_argument("--json", action="store_true", help="Imprime JSON crudo")

    sub = parser.add_subparsers(dest="scope", required=True)

    p = sub.add_parser("account", help="Consultas de cuenta")
    sub_a = p.add_subparsers(dest="action", required=True)
    sub_a.add_parser("info", help="Account information").set_defaults(func=_account_info)
    p_stats = sub_a.add_parser("stats", help="Account statistics")
    p_stats.add_argument("--last", type=int, default=None)
    p_stats.set_defaults(func=_account_stats)
    p_dmca = sub_a.add_parser("dmca", help="DMCA reports")
    p_dmca.add_argument("--last", type=int, default=None)
    p_dmca.set_defaults(func=_dmca)
    p_trash = sub_a.add_parser("trash", help="Deleted files")
    p_trash.add_argument("--last", type=int, default=None)
    p_trash.set_defaults(func=_trash)

    p = sub.add_parser("upload", help="Subidas")
    sub_u = p.add_subparsers(dest="action", required=True)
    p_server = sub_u.add_parser("server", help="Get upload server")
    p_server.add_argument("--anon", action="store_true", help="Usar endpoint anónimo")
    p_server.set_defaults(func=_upload_server)
    p_file = sub_u.add_parser("file", help="Upload a local file")
    p_file.add_argument("file", type=Path)
    p_file.add_argument("--anon", action="store_true", help="Usar endpoint anónimo")
    p_file.set_defaults(func=_upload_file)
    p_remote = sub_u.add_parser("remote", help="Remote upload by URL")
    p_remote.add_argument("url")
    p_remote.add_argument("--anon", action="store_true", help="Usar endpoint anónimo")
    p_remote.set_defaults(func=_remote_upload)

    p = sub.add_parser("files", help="Operaciones de archivos")
    sub_f = p.add_subparsers(dest="action", required=True)
    p_list = sub_f.add_parser("list", help="List files")
    p_list.add_argument("--page", type=int, default=None)
    p_list.add_argument("--per-page", dest="per_page", type=int, default=None)
    p_list.add_argument("--fld", dest="fld_id", type=int, default=None)
    p_list.add_argument("--public", type=int, choices=[0, 1], default=None)
    p_list.add_argument("--created", default=None)
    p_list.add_argument("--name", default=None)
    p_list.set_defaults(func=_files_list)
    p_info = sub_f.add_parser("info", help="File info")
    p_info.add_argument("--code", default="")
    p_info.add_argument("--url", default="")
    p_info.set_defaults(func=_files_info)
    p_rename = sub_f.add_parser("rename", help="Rename file")
    p_rename.add_argument("--code", required=True)
    p_rename.add_argument("--name", required=True)
    p_rename.set_defaults(func=_files_rename)
    p_copy = sub_f.add_parser("copy", help="Copy file")
    p_copy.add_argument("--code", required=True)
    p_copy.set_defaults(func=_files_copy)
    p_move = sub_f.add_parser("move", help="Move file to folder")
    p_move.add_argument("--code", required=True)
    p_move.add_argument("--folder", type=int, required=True)
    p_move.set_defaults(func=_files_move)
    p_del = sub_f.add_parser("delete", help="Delete file")
    p_del.add_argument("--code", required=True)
    p_del.set_defaults(func=_files_delete)
    p_pwd = sub_f.add_parser("password", help="Set file password")
    p_pwd.add_argument("--code", required=True)
    p_pwd.add_argument("--password", required=True)
    p_pwd.set_defaults(func=_files_password)
    p_unpwd = sub_f.add_parser("unpassword", help="Remove file password")
    p_unpwd.add_argument("--code", required=True)
    p_unpwd.set_defaults(func=_files_unpassword)
    p_pub = sub_f.add_parser("public", help="Make file public")
    p_pub.add_argument("--code", required=True)
    p_pub.set_defaults(func=_files_public)
    p_priv = sub_f.add_parser("private", help="Make file private")
    p_priv.add_argument("--code", required=True)
    p_priv.set_defaults(func=_files_private)
    p_dl = sub_f.add_parser("direct-link", help="Get premium direct link")
    p_dl.add_argument("--code", required=True)
    p_dl.set_defaults(func=_files_direct_link)

    p = sub.add_parser("folder", help="Operaciones de carpetas")
    sub_d = p.add_subparsers(dest="action", required=True)
    p_fl = sub_d.add_parser("list", help="List folder")
    p_fl.add_argument("--folder", type=int, required=True)
    p_fl.set_defaults(func=_folder_list)
    p_fc = sub_d.add_parser("create", help="Create folder")
    p_fc.add_argument("--name", required=True)
    p_fc.add_argument("--parent", type=int, default=None)
    p_fc.set_defaults(func=_folder_create)
    p_fr = sub_d.add_parser("rename", help="Rename folder")
    p_fr.add_argument("--folder", type=int, required=True)
    p_fr.add_argument("--name", required=True)
    p_fr.set_defaults(func=_folder_rename)
    p_fm = sub_d.add_parser("move", help="Move folder")
    p_fm.add_argument("--source", type=int, required=True)
    p_fm.add_argument("--dest", type=int, required=True)
    p_fm.set_defaults(func=_folder_move)
    p_fcp = sub_d.add_parser("copy", help="Copy folder")
    p_fcp.add_argument("--source", type=int, required=True)
    p_fcp.add_argument("--dest", type=int, required=True)
    p_fcp.set_defaults(func=_folder_copy)
    p_fd = sub_d.add_parser("delete", help="Delete folder")
    p_fd.add_argument("--folder", type=int, required=True)
    p_fd.set_defaults(func=_folder_delete)
    p_fpwd = sub_d.add_parser("password", help="Set folder password")
    p_fpwd.add_argument("--folder", type=int, required=True)
    p_fpwd.add_argument("--password", required=True)
    p_fpwd.set_defaults(func=_folder_password)
    p_funpwd = sub_d.add_parser("unpassword", help="Remove folder password")
    p_funpwd.add_argument("--folder", type=int, required=True)
    p_funpwd.set_defaults(func=_folder_unpassword)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "base_url", ""):
        args.base_url = str(args.base_url).rstrip("/")
    if getattr(args, "public_base_url", ""):
        args.public_base_url = str(args.public_base_url).rstrip("/")
    try:
        return int(args.func(args))
    except SendNowError as exc:
        console.print(f"[red]{exc}[/red]")
        if getattr(exc, "payload", None) is not None and args.json:
            _json(exc.payload)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
