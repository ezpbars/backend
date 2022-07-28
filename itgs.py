"""This module allows for easily accessing common integrations -
the integration is only loaded upon request.
"""
from typing import Callable, Coroutine, List, Optional
import rqdb
import rqdb.async_connection
import os


class Itgs:
    """The collection of integrations available. Acts as an
    async context manager
    """

    def __init__(self) -> None:
        """Initializes a new integrations with nothing loaded.
        Must be __aenter__ 'd and __aexit__'d.
        """
        self._conn: Optional[rqdb.async_connection.AsyncConnection] = None
        """the rqlite connection, if it has been opened"""

        self._closures: List[Callable[["Itgs"], Coroutine]] = []
        """functions to run on __aexit__ to cleanup opened resources"""

    async def __aenter__(self) -> "Itgs":
        """allows support as an async context manager"""

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """closes any managed resources"""
        for closure in self._closures:
            await closure(self)
        self._closures = []

    async def conn(self) -> rqdb.async_connection.AsyncConnection:
        """Gets or creates and initializes the rqdb connection.
        The connection will be closed when the itgs is closed
        """
        if self._conn is not None:
            return self._conn

        rqlite_ips = os.environ.get("RQLITE_IPS").split(",")
        if not rqlite_ips:
            raise ValueError("RQLITE_IPS not set -> cannot connect to rqlite")

        async def cleanup(me: "Itgs") -> None:
            if me._conn is not None:
                await me._conn.__aexit__(None, None, None)
                me._conn = None

        self._closures.append(cleanup)
        self._conn = rqdb.connect_async(hosts=rqlite_ips)
        await self._conn.__aenter__()
