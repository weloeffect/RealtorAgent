import asyncio
import json

from packages.providers.qwen_realtime import QwenRealtimeProvider


async def main() -> None:
    result = await QwenRealtimeProvider().probe()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
