import json
from functools import partial
from typing import Any

import requests

from .args import process_args
from .config import SERVER_PID_FILE
from .files import ConfigDirWatchdog
from .logger import LogLevel, get_logger
from .theme import ThemeManager
from .theme_utils import dump_theme
from .utils import Lock, Result

log = get_logger(__name__)


async def run_server() -> None:
    import uvicorn
    from fastapi import (APIRouter, FastAPI, Request, WebSocket,
                         WebSocketDisconnect)
    from fastapi.routing import APIRoute

    class ConnectionManager:
        def __init__(self) -> None:
            self.active_connections: list[WebSocket] = []

        async def connect(self, websocket: WebSocket) -> None:
            await websocket.accept()
            self.active_connections.append(websocket)

        def disconnect(self, websocket: WebSocket) -> None:
            self.active_connections.remove(websocket)

        async def send_personal_message(
            self, message: str, websocket: WebSocket
        ) -> None:
            await websocket.send_text(message)

        async def broadcast(self, message: str) -> None:
            for connection in self.active_connections:
                await connection.send_text(message)

    def custom_generate_unique_id(route: APIRoute) -> str:
        return f"{route.name}"

    tm = ThemeManager()
    app = FastAPI(generate_unique_id_function=custom_generate_unique_id)
    manager = ConnectionManager()
    v1_router = APIRouter()

    tm.event_handler.subscribe(
        "theme_applied",
        partial(
            manager.broadcast,
            json.dumps({"type": "config_changed", "config": vars(tm.config)}),
        ),
    )

    @v1_router.websocket("/ws/{client_id}")
    async def websocket_endpoint(websocket: WebSocket, client_id: int) -> None:
        await manager.connect(websocket)
        await manager.send_personal_message(
            json.dumps({"type": "config_changed", "config": vars(tm.config)}), websocket
        )
        try:
            while True:
                data = await websocket.receive_text()
                print(data)
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    @v1_router.get("/albums")
    async def get_albums() -> list[str]:
        albums = [a for a in tm.albums.keys()]
        return albums

    @v1_router.get("/current_theme")
    async def get_current_theme() -> dict[str, Any] | None:
        if not tm.config.theme:
            return None
        theme = tm.albums[tm.config.album][tm.config.theme]
        dump = dump_theme(theme, for_api=True)

        msg = {"config": vars(tm.config), "theme": dump}

        return msg

    @v1_router.put("/current_theme")
    async def set_theme(
        name: str | None = None, album: str | None = None, random: str | None = None
    ) -> str:
        if random is None:
            res = await tm.apply_theme(theme_name=name, album=album)
        else:
            res = await tm.set_random_theme(theme_name_includes=name, album=album)

        msg = {
            "event": "theme_applied",
            "config": vars(tm.config),
            "result": res.dump(),
        }

        json_str = json.dumps(msg)

        # await manager.broadcast(
        #     json.dumps({"type": "config_changed", "config": vars(tm.config)})
        # )
        return json_str

    @v1_router.get("/theme/{name}")
    async def get_theme(
        request: Request, name: str, album: str | None = None
    ) -> dict[str, Any]:
        client_host = request.client.host if request.client else "127.0.0.1"

        if client_host != "127.0.0.1":
            log.error("streaming images not yet implemented")

        res = {"theme": dump_theme(tm.albums[album or "default"][name], for_api=True)}
        return res

    @v1_router.get("/themes")
    async def get_themes(request: Request, album: str | None = None) -> dict[str, Any]:
        client_host = request.client.host if request.client else "127.0.0.1"

        if client_host != "127.0.0.1":
            log.error("streaming images not yet implemented")

        res = {
            "themes": [
                dump_theme(theme, for_api=True)
                for theme in tm.albums[album or "default"].values()
            ]
        }
        return res

    @v1_router.get("/base_style")
    async def get_base_style(request: Request) -> dict[str, Any]:
        res = {"keywords": tm.base_style}
        return res

    @v1_router.post("/cli_command")
    async def cli_command(req: Request) -> str:
        req_json = await req.json()

        if req_json["server"] and req_json["reload"]:
            nonlocal tm
            tm = ThemeManager()

            result = Result().success("configuration reloaded")

            msg = {
                "event": "command_executed",
                "config": vars(tm.config),
                "result": result.dump(),
            }

            json_str = json.dumps(msg)

            return json_str

        result = await process_args(tm, req_json)

        msg = {
            "event": "command_executed",
            "config": vars(tm.config),
            "result": result.dump(),
        }

        json_str = json.dumps(msg)

        # if "applied" in json_str:
        #     await manager.broadcast(
        #         json.dumps({"type": "config_changed", "config": vars(tm.config)})
        #     )
        return json_str

    app.include_router(v1_router, prefix="/v1")

    config = uvicorn.Config(app, port=5000)
    server = uvicorn.Server(config)

    with Lock(SERVER_PID_FILE), ConfigDirWatchdog(tm):
        await server.serve()


def send_to_server(
    args: dict[str, Any], address: str = "http://127.0.0.1:5000"
) -> None:

    log.debug(f"connecting to {address}")

    try:
        response = requests.post(f"{address}/v1/cli_command", json=args)
        res_json = json.loads(response.json())

        for record in res_json["result"]["records"]:
            log.log(LogLevel[record["level"]].value, record["msg"])

    except Exception as e:
        log.exception(e)
    finally:
        log.debug("closing connection")
