"""
OroGest Lex — Server-Sent Events (SSE)
Real-time event stream for dashboard updates, notifications, and case changes.

Usage from frontend:
    const evtSource = new EventSource('/api/v1/events/stream?token=JWT_TOKEN');
    evtSource.onmessage = (e) => { const data = JSON.parse(e.data); ... };
"""

import asyncio
import json
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.models.models import User

router = APIRouter(prefix="/events", tags=["events"])

# ── Event Bus (in-memory, production: Redis Pub/Sub) ──
_event_queues: dict[str, asyncio.Queue] = defaultdict(lambda: asyncio.Queue(maxsize=100))


async def publish_event(event_type: str, data: dict, user_id: str | None = None):
    """
    Publish an event to connected SSE clients.
    If user_id is specified, only that user's queue receives it.
    If None, broadcast to all.
    """
    event = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(UTC).isoformat(),
        "id": uuid.uuid4().hex[:8],
    }

    if user_id:
        queue_key = f"user:{user_id}"
        if queue_key in _event_queues:
            try:
                _event_queues[queue_key].put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop oldest if full
    else:
        # Broadcast
        for key, queue in list(_event_queues.items()):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass


async def _event_generator(user_id: str):
    """Generate SSE events for a specific user."""
    queue_key = f"user:{user_id}"
    queue = _event_queues[queue_key]

    # Send initial connection event
    yield _format_sse(
        {
            "type": "connected",
            "data": {"message": "OroGest Lex real-time stream connected"},
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield _format_sse(event)
            except TimeoutError:
                # Send keepalive ping every 30s
                yield ": keepalive\n\n"
    finally:
        # Cleanup on disconnect
        _event_queues.pop(queue_key, None)


def _format_sse(event: dict) -> str:
    """Format event as SSE string."""
    event_type = event.get("type", "message")
    data = json.dumps(event)
    return f"event: {event_type}\ndata: {data}\n\n"


@router.get("/stream")
async def event_stream(
    request: Request,
    user: User = Depends(get_current_user),
):
    """
    SSE endpoint for real-time updates.
    Connect from frontend with EventSource.

    Events emitted:
    - notification.new: new notification
    - case.updated: case status change
    - deadline.approaching: upcoming deadline alert
    - ai.completed: AI query finished
    - system.health: periodic health status
    """
    return StreamingResponse(
        _event_generator(str(user.id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/test-publish")
async def test_publish(
    message: str = Query("Test event from OroGest"),
    user: User = Depends(get_current_user),
):
    """Test endpoint to publish an event to your own stream."""
    await publish_event(
        "test",
        {"message": message, "from": user.full_name},
        user_id=str(user.id),
    )
    return {"status": "published", "message": message}
