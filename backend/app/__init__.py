import sys
import asyncio

# Ensure Windows uses ProactorEventLoop to support asyncio subprocesses
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
