# Django 5.2 async ORM capabilities

## Conclusion

Django 5.2 supports asynchronous execution for most database-touching
`QuerySet`, model, and related-manager operations. It does **not** support
transactions in async mode. Keep any transaction-owning ORM workflow in one
synchronous function and invoke that function from async code with
`asgiref.sync.sync_to_async()`.

## Supported operations

- QuerySet methods that only build a query, such as `filter()`, `exclude()`,
  `select_related()`, and `prefetch_related()`, do not execute SQL and are safe
  to chain in async code. They have no `a`-prefixed counterpart.
- QuerySet methods that evaluate or mutate data have asynchronous variants,
  generally with an `a` prefix: `aget()`, `acreate()`, `aget_or_create()`,
  `aupdate_or_create()`, `abulk_create()`, `abulk_update()`, `acount()`,
  `ain_bulk()`, `aiterator()`, `alatest()`, `aearliest()`, `afirst()`,
  `alast()`, `aaggregate()`, `aexists()`, `acontains()`, `aupdate()`,
  `adelete()`, and `aexplain()`.
- Every QuerySet supports `async for`, including QuerySets produced by
  `values()` and `values_list()`. Do not force evaluation with ordinary `for`,
  `list(queryset)`, `bool(queryset)`, or similar synchronous operations.
- Database-using model methods include `asave()`, `adelete()`, and
  `arefresh_from_db()`.
- Related managers provide async mutations such as `aadd()`, `acreate()`,
  `aremove()`, `aclear()`, and `aset()`.

Sources: [Django async support](https://docs.djangoproject.com/en/5.2/topics/async/),
[async queries](https://docs.djangoproject.com/en/5.2/topics/db/queries/),
[QuerySet API](https://docs.djangoproject.com/en/5.2/ref/models/querysets/),
[model instance reference](https://docs.djangoproject.com/en/5.2/ref/models/instances/),
and [related objects reference](https://docs.djangoproject.com/en/5.2/ref/models/relations/).

## Restrictions and caveats

- Transactions are not currently supported with asynchronous queries or
  updates; attempting to use them raises `SynchronousOnlyOperation`. This
  includes trying to use `transaction.atomic()` around async ORM work.
- The ORM remains async-unsafe when called through a synchronous API from a
  thread with a running event loop. Such calls can raise
  `SynchronousOnlyOperation`; do not bypass this with `DJANGO_ALLOW_ASYNC_UNSAFE`
  in production because concurrent access can cause data loss or corruption.
- Deferred fields and lazy related-object access can trigger an implicit
  synchronous query. In async code, load needed fields up front with
  `select_related()`/`prefetch_related()` or use an explicit async query.
- Do not pass a resolved Django database connection or cursor across a
  `sync_to_async()` boundary. Encapsulate all connection use inside the sync
  helper. Django recommends the default `thread_sensitive=True` mode for
  thread-sensitive sync code such as database adapters.
- Disable persistent connections (`CONN_MAX_AGE`) in async mode; use backend or
  third-party pooling if needed.

Sources: [Django async support](https://docs.djangoproject.com/en/5.2/topics/async/)
and [async queries](https://docs.djangoproject.com/en/5.2/topics/db/queries/).

## Recommended application boundary

An async-native service may use the async ORM APIs when it does not need
transactional behavior:

```python
async def find_song(song_id):
    return await Song.objects.filter(pk=song_id).afirst()
```

Transaction-owning application logic should remain synchronous and contain the
whole atomic unit:

```python
from asgiref.sync import sync_to_async
from django.db import transaction


def _persist_import(data):
    with transaction.atomic():
        ...


async def persist_import(data):
    return await sync_to_async(_persist_import)(data)
```

This keeps the transaction and all database connection use on the sync side of
the boundary, while allowing an async adapter or view to await the operation.
Do not hold a transaction open across external network awaits.

