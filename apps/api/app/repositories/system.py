"""Minimal infrastructure probes used by the safe system-status endpoint."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class SystemRepository:
    def database_available(self, db: Session) -> bool:
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            db.rollback()
            return False
        return True
