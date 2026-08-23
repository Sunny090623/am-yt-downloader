import asyncio
import json
from typing import Dict, Set, AsyncGenerator, Any, Tuple
from app.schemas.task import TaskProgressUpdate

class SSEHub:
    def __init__(self):
        # Maps user_id -> Set of asyncio.Queue
        self._user_subscribers: Dict[str, Set[asyncio.Queue]] = {}
        # Subscribers for admin (receives all events)
        self._admin_subscribers: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self, user_id: str, is_admin: bool) -> Tuple[asyncio.Queue, AsyncGenerator[str, None]]:
        queue = asyncio.Queue()
        async with self._lock:
            if is_admin:
                self._admin_subscribers.add(queue)
            else:
                if user_id not in self._user_subscribers:
                    self._user_subscribers[user_id] = set()
                self._user_subscribers[user_id].add(queue)
        
        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                # Send initial connected message
                yield f"event: connected\ndata: {json.dumps({'status': 'connected'})}\n\n"
                
                while True:
                    try:
                        # Wait for message with 15s timeout for keepalive
                        data = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield f"event: task_update\ndata: {json.dumps(data)}\n\n"
                    except asyncio.TimeoutError:
                        # Send keepalive comment to prevent reverse proxies from timing out
                        yield ": keepalive\n\n"
            finally:
                async with self._lock:
                    if is_admin:
                        self._admin_subscribers.discard(queue)
                    else:
                        if user_id in self._user_subscribers:
                            self._user_subscribers[user_id].discard(queue)
                            if not self._user_subscribers[user_id]:
                                del self._user_subscribers[user_id]

        return queue, event_generator()

    async def broadcast_task_update(self, user_id: str, update: TaskProgressUpdate) -> None:
        """Broadcasts a task progress update to matching user and admin connections."""
        data = update.model_dump(mode="json")
        async with self._lock:
            # 1. Send to specific user queues
            if user_id in self._user_subscribers:
                for q in self._user_subscribers[user_id]:
                    try:
                        q.put_nowait(data)
                    except asyncio.QueueFull:
                        pass
            
            # 2. Send to all admin queues
            for q in self._admin_subscribers:
                try:
                    q.put_nowait(data)
                except asyncio.QueueFull:
                    pass

sse_hub = SSEHub()
