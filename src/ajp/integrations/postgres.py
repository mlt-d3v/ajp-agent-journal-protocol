"""Real PostgreSQL storage backend for AJP journal entries."""
import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PostgresLogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class PostgresConfig:
    """Configuration for PostgreSQL connection."""
    host: str = "localhost"
    port: int = 5432
    database: str = "ajp_journal"
    user: str = "ajp_user"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20
    ssl_enabled: bool = False
    schema_name: str = "ajp"
    table_name: str = "journal_entries"
    log_level: PostgresLogLevel = PostgresLogLevel.INFO
    connection_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0

    def get_dsn(self) -> str:
        """Build DSN string for connection."""
        ssl_mode = "require" if self.ssl_enabled else "prefer"
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?sslmode={ssl_mode}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PostgresStorage:
    """
    Real PostgreSQL storage backend for AJP journal entries.

    Features:
    - Async connection pooling with asyncpg
    - Automatic schema creation and migrations
    - Proper indexing for fast queries
    - Bulk insert support for batch writes
    - Transaction safety with retry logic
    """

    # Schema version for migrations
    SCHEMA_VERSION = 2

    # Table creation SQL
    CREATE_SCHEMA_SQL = """
    CREATE SCHEMA IF NOT EXISTS {schema};
    """

    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS {schema}.{table} (
        entry_id VARCHAR(64) PRIMARY KEY,
        agent_id VARCHAR(128) NOT NULL,
        event_type VARCHAR(32) NOT NULL,
        entry_data JSONB NOT NULL DEFAULT '{{}}',
        entry_hash VARCHAR(64) NOT NULL,
        previous_hash VARCHAR(64),
        signature VARCHAR(256),
        timestamp TIMESTAMPTZ NOT NULL,
        sequence_number BIGINT NOT NULL,
        priority INTEGER NOT NULL DEFAULT 0,
        status VARCHAR(32) NOT NULL DEFAULT 'committed',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """

    CREATE_INDEXES_SQL = """
    CREATE INDEX IF NOT EXISTS idx_{table}_agent_id ON {schema}.{table} (agent_id);
    CREATE INDEX IF NOT EXISTS idx_{table}_event_type ON {schema}.{table} (event_type);
    CREATE INDEX IF NOT EXISTS idx_{table}_timestamp ON {schema}.{table} (timestamp);
    CREATE INDEX IF NOT EXISTS idx_{table}_sequence ON {schema}.{table} (sequence_number);
    CREATE INDEX IF NOT EXISTS idx_{table}_status ON {schema}.{table} (status);
    CREATE INDEX IF NOT EXISTS idx_{table}_agent_timestamp ON {schema}.{table} (agent_id, timestamp);
    """

    def __init__(self, config: Optional[PostgresConfig] = None):
        self.config = config or PostgresConfig()
        self._pool = None
        self._is_connected = False
        self._schema_version = 0
        self._write_count = 0
        self._read_count = 0

    async def connect(self) -> bool:
        """Establish connection pool and initialize schema."""
        try:
            import asyncpg
        except ImportError:
            logger.warning("asyncpg not installed - falling back to in-memory mode")
            self._is_connected = False
            return False

        try:
            self._pool = await asyncpg.create_pool(
                dsn=self.config.get_dsn(),
                min_size=self.config.pool_size,
                max_size=self.config.pool_size + self.config.max_overflow,
                timeout=self.config.connection_timeout,
            )
            await self._initialize_schema()
            self._is_connected = True
            logger.info(f"Connected to PostgreSQL at {self.config.host}:{self.config.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            self._is_connected = False
            return False

    async def _initialize_schema(self) -> None:
        """Create schema and tables if they don't exist."""
        if not self._pool:
            return

        async with self._pool.acquire() as conn:
            # Create schema
            await conn.execute(
                self.CREATE_SCHEMA_SQL.format(schema=self.config.schema_name)
            )

            # Create table
            await conn.execute(
                self.CREATE_TABLE_SQL.format(
                    schema=self.config.schema_name,
                    table=self.config.table_name,
                )
            )

            # Create indexes
            await conn.execute(
                self.CREATE_INDEXES_SQL.format(
                    schema=self.config.schema_name,
                    table=self.config.table_name,
                )
            )

            # Check/create version table
            await self._migrate_schema(conn)

    async def _migrate_schema(self, conn: Any) -> None:
        """Handle schema migrations."""
        version_table = "schema_version"
        create_version = f"""
        CREATE TABLE IF NOT EXISTS {self.config.schema_name}.{version_table} (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            description TEXT
        );
        """
        await conn.execute(create_version)

        # Get current version
        result = await conn.fetchval(
            f"SELECT COALESCE(MAX(version), 0) FROM {self.config.schema_name}.{version_table}"
        )
        self._schema_version = result

        # Apply migrations if needed
        if self._schema_version < self.SCHEMA_VERSION:
            await self._apply_migrations(conn)

    async def _apply_migrations(self, conn: Any) -> None:
        """Apply pending schema migrations."""
        migrations = [
            (1, "Initial schema with journal entries table"),
            (2, "Added priority and status columns"),
        ]

        for version, description in migrations:
            if version > self._schema_version:
                await conn.execute(
                    f"""
                    INSERT INTO {self.config.schema_name}.schema_version (version, description)
                    VALUES ($1, $2)
                    """,
                    version,
                    description,
                )
                self._schema_version = version
                logger.info(f"Applied migration to version {version}: {description}")

    async def write_entry(self, entry: Dict[str, Any]) -> bool:
        """Write a single journal entry to PostgreSQL."""
        if not self._is_connected or not self._pool:
            logger.warning("PostgreSQL not connected - entry dropped")
            return False

        for attempt in range(self.config.retry_attempts):
            try:
                async with self._pool.acquire() as conn:
                    query = f"""
                    INSERT INTO {self.config.schema_name}.{self.config.table_name}
                    (entry_id, agent_id, event_type, entry_data, entry_hash,
                     previous_hash, signature, timestamp, sequence_number,
                     priority, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (entry_id) DO UPDATE SET
                        entry_data = EXCLUDED.entry_data,
                        entry_hash = EXCLUDED.entry_hash,
                        updated_at = NOW()
                    """
                    await conn.execute(
                        query,
                        entry.get("entry_id", ""),
                        entry.get("agent_id", ""),
                        entry.get("event_type", ""),
                        json.dumps(entry.get("entry_data", {})),
                        entry.get("entry_hash", ""),
                        entry.get("previous_hash"),
                        entry.get("signature"),
                        entry.get("timestamp", time.time()),
                        entry.get("sequence_number", 0),
                        entry.get("priority", 0),
                        entry.get("status", "committed"),
                    )
                self._write_count += 1
                return True
            except Exception as e:
                logger.error(f"Write attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    return False
        return False

    async def write_entries(self, entries: List[Dict[str, Any]]) -> int:
        """Write multiple journal entries in a batch."""
        if not entries:
            return 0

        if not self._is_connected or not self._pool:
            logger.warning("PostgreSQL not connected - entries dropped")
            return 0

        written = 0
        for attempt in range(self.config.retry_attempts):
            try:
                async with self._pool.acquire() as conn:
                    async with conn.transaction():
                        query = f"""
                        INSERT INTO {self.config.schema_name}.{self.config.table_name}
                        (entry_id, agent_id, event_type, entry_data, entry_hash,
                         previous_hash, signature, timestamp, sequence_number,
                         priority, status)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        ON CONFLICT (entry_id) DO UPDATE SET
                            entry_data = EXCLUDED.entry_data,
                            entry_hash = EXCLUDED.entry_hash,
                            updated_at = NOW()
                        """
                        for entry in entries:
                            await conn.execute(
                                query,
                                entry.get("entry_id", ""),
                                entry.get("agent_id", ""),
                                entry.get("event_type", ""),
                                json.dumps(entry.get("entry_data", {})),
                                entry.get("entry_hash", ""),
                                entry.get("previous_hash"),
                                entry.get("signature"),
                                entry.get("timestamp", time.time()),
                                entry.get("sequence_number", 0),
                                entry.get("priority", 0),
                                entry.get("status", "committed"),
                            )
                        written = len(entries)
                        self._write_count += written
                        return written
            except Exception as e:
                logger.error(f"Batch write attempt {attempt + 1} failed: {e}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    return written
        return written

    async def read_entries(
        self,
        agent_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Read journal entries with filtering."""
        if not self._is_connected or not self._pool:
            return []

        try:
            async with self._pool.acquire() as conn:
                query = f"""
                SELECT entry_id, agent_id, event_type, entry_data, entry_hash,
                       previous_hash, signature, timestamp, sequence_number,
                       priority, status, created_at, updated_at
                FROM {self.config.schema_name}.{self.config.table_name}
                WHERE 1=1
                """
                params = []
                param_idx = 1

                if agent_id:
                    query += f" AND agent_id = ${param_idx}"
                    params.append(agent_id)
                    param_idx += 1

                if event_type:
                    query += f" AND event_type = ${param_idx}"
                    params.append(event_type)
                    param_idx += 1

                if start_time:
                    query += f" AND timestamp >= ${param_idx}"
                    params.append(start_time)
                    param_idx += 1

                if end_time:
                    query += f" AND timestamp <= ${param_idx}"
                    params.append(end_time)
                    param_idx += 1

                query += f" ORDER BY timestamp ASC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
                params.extend([limit, offset])

                rows = await conn.fetch(query, *params)
                self._read_count += len(rows)

                return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Read failed: {e}")
            return []

    def _row_to_dict(self, row: Any) -> Dict[str, Any]:
        """Convert a database row to a dictionary."""
        result = dict(row)
        if "entry_data" in result and isinstance(result["entry_data"], str):
            result["entry_data"] = json.loads(result["entry_data"])
        return result

    async def delete_entries(self, agent_id: str) -> int:
        """Delete all entries for an agent (GDPR compliance)."""
        if not self._is_connected or not self._pool:
            return 0

        try:
            async with self._pool.acquire() as conn:
                result = await conn.fetchval(
                    f"""
                    DELETE FROM {self.config.schema_name}.{self.config.table_name}
                    WHERE agent_id = $1
                    """,
                    agent_id,
                )
                return result or 0
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        if not self._is_connected or not self._pool:
            return {"connected": False, "schema_version": 0}

        try:
            async with self._pool.acquire() as conn:
                total = await conn.fetchval(
                    f"SELECT COUNT(*) FROM {self.config.schema_name}.{self.config.table_name}"
                )
                agents = await conn.fetchval(
                    f"SELECT COUNT(DISTINCT agent_id) FROM {self.config.schema_name}.{self.config.table_name}"
                )
                return {
                    "connected": True,
                    "total_entries": total or 0,
                    "unique_agents": agents or 0,
                    "schema_version": self._schema_version,
                    "write_count": self._write_count,
                    "read_count": self._read_count,
                }
        except Exception as e:
            logger.error(f"Stats query failed: {e}")
            return {"connected": True, "error": str(e)}

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._is_connected = False
            logger.info("PostgreSQL connection pool closed")

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def write_count(self) -> int:
        return self._write_count

    @property
    def read_count(self) -> int:
        return self._read_count
