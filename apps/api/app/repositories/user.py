"""User persistence operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import User
from app.schemas.user import UserCreate


class UserRepository:
    def create(self, db: Session, data: UserCreate) -> User:
        user = User(**data.model_dump())
        db.add(user)
        db.flush()
        return user

    def get(self, db: Session, user_id: str) -> User | None:
        return db.get(User, user_id)

    def get_by_username(self, db: Session, username: str) -> User | None:
        return db.scalar(select(User).where(User.username == username))
