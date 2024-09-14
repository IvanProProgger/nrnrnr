import asyncio

from db.db import ApprovalDB

__all__ = ["db"]
db = ApprovalDB()

loop = asyncio.get_event_loop()
loop.run_until_complete(db.create_table())
