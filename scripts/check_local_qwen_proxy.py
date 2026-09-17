import asyncio
import json

from websockets.asyncio.client import connect


async def main() -> None:
    async with connect(
        "ws://127.0.0.1:8000/ws/qwen-realtime",
        origin="http://localhost:3000",
        open_timeout=10,
    ) as websocket:
        for _ in range(3):
            event = json.loads(await asyncio.wait_for(websocket.recv(), timeout=15))
            print(json.dumps({"type": event.get("type"), "error": event.get("error")}))
            if event.get("type") in {"session.updated", "error", "proxy.error"}:
                break


if __name__ == "__main__":
    asyncio.run(main())
