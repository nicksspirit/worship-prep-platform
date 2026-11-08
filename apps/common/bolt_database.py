from collections.abc import Callable

from asgiref.sync import sync_to_async
from django.db import connections


def _run_database_call[**P, T](service: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    try:
        return service(*args, **kwargs)
    finally:
        # Bolt's async loop cannot close Django connections opened in its sync worker.
        connections.close_all()


async def call_bolt_database[**P, T](
    service: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    """Run a sync Django service and release its worker-thread connections."""

    return await sync_to_async(_run_database_call, thread_sensitive=True)(
        service, *args, **kwargs
    )
