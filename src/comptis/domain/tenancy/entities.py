from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from .value_objects import OrgType, Role


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class Organization:
    name: str
    type: OrgType
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass
class Tenant:
    organization_id: UUID
    name: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass
class User:
    email: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass
class Membership:
    user_id: UUID
    tenant_id: UUID
    role: Role = Role.VIEWER
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
