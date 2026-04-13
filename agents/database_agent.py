from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

try:
    import mysql.connector  # type: ignore[import-untyped]
except Exception:
    mysql = None
else:
    mysql = mysql.connector


def _utc_now_naive() -> datetime:
    # MySQL DATETIME is stored without timezone. We keep UTC convention.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DatabaseAgent:
    """Simple repository wrapper for local MySQL persistence."""

    def __init__(self) -> None:
        self._enabled = os.getenv("DB_ENABLED", "1") == "1"
        self._host = os.getenv("DB_HOST", "127.0.0.1")
        self._port = int(os.getenv("DB_PORT", "6000"))
        self._user = os.getenv("DB_USER", "user")
        self._password = os.getenv("DB_PASSWORD", "pass")
        self._database = os.getenv("DB_NAME", "db_objet")

        if mysql is None:
            logger.warning("mysql-connector-python non disponible: persistance DB désactivée.")
            self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if not self._enabled or mysql is None:
            yield None
            return
        conn = None
        try:
            conn = mysql.connect(
                host=self._host,
                port=self._port,
                user=self._user,
                password=self._password,
                database=self._database,
                autocommit=False,
            )
            yield conn
            conn.commit()
        except Exception as exc:
            if conn is not None:
                conn.rollback()
            logger.warning("Erreur DB: %s", exc)
            yield None
        finally:
            if conn is not None:
                conn.close()

    def insert_action(self, commande: str, valeur: Optional[float]) -> None:
        with self._connection() as conn:
            if conn is None:
                return
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO actions (id_date, commande, valeur)
                VALUES (%s, %s, %s)
                """,
                (_utc_now_naive(), commande, valeur),
            )
            cursor.close()

    def insert_event(
        self,
        moteur: str,
        direction: Optional[str],
        vitesse: Optional[float],
        distance: Optional[float],
        erreur: str,
        avertissement: Optional[str],
    ) -> None:
        with self._connection() as conn:
            if conn is None:
                return
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (id_date, moteur, direction, vitesse, distance, erreur, avertissement)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (_utc_now_naive(), moteur, direction, vitesse, distance, erreur, avertissement),
            )
            cursor.close()

    def insert_message_envoye(self, payload: dict[str, Any]) -> None:
        with self._connection() as conn:
            if conn is None:
                return
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO messages_envoyes (
                    id_message, id_objet, id_date, status, temperature, luminosite,
                    ouverture_automatique, mode, ouverture_reelle, erreur, avertissement
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    payload["id_message"],
                    payload["id_objet"],
                    payload["id_date"],
                    payload["status"],
                    payload["temperature"],
                    payload["luminosite"],
                    payload["ouverture_automatique"],
                    payload["mode"],
                    payload["ouverture_reelle"],
                    payload["erreur"],
                    payload["avertissement"],
                ),
            )
            cursor.close()

    def mark_message_envoye(self, id_message: str) -> None:
        with self._connection() as conn:
            if conn is None:
                return
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE messages_envoyes SET status='envoye' WHERE id_message=%s",
                (id_message,),
            )
            cursor.close()

    def fetch_pending_messages(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connection() as conn:
            if conn is None:
                return []
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id_message, id_objet, id_date, status, temperature, luminosite,
                       ouverture_automatique, mode, ouverture_reelle, erreur, avertissement
                FROM messages_envoyes
                WHERE status='en_attente'
                ORDER BY id_date ASC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            cursor.close()
            return rows

