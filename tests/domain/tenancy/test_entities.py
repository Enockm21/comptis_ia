from uuid import UUID, uuid4
from datetime import datetime
from comptis.domain.tenancy.entities import Organization, Tenant, User, Membership
from comptis.domain.tenancy.value_objects import OrgType, Role


def test_organization_auto_generates_uuid():
    org = Organization(name="Cabinet Dupont", type=OrgType.CABINET)
    assert isinstance(org.id, UUID)


def test_two_organizations_have_different_ids():
    a = Organization(name="Org A", type=OrgType.CABINET)
    b = Organization(name="Org B", type=OrgType.CABINET)
    assert a.id != b.id


def test_tenant_requires_organization_id():
    org_id = uuid4()
    tenant = Tenant(organization_id=org_id, name="Boulangerie Martin")
    assert isinstance(tenant.id, UUID)
    assert tenant.organization_id == org_id


def test_user_stores_email():
    user = User(email="comptable@cabinet.fr")
    assert user.email == "comptable@cabinet.fr"
    assert isinstance(user.id, UUID)


def test_membership_default_role_is_viewer():
    m = Membership(user_id=uuid4(), tenant_id=uuid4())
    assert m.role == Role.VIEWER


def test_membership_can_be_set_to_accountant():
    m = Membership(user_id=uuid4(), tenant_id=uuid4(), role=Role.ACCOUNTANT)
    assert m.role == Role.ACCOUNTANT


def test_entities_have_created_at():
    org = Organization(name="X", type=OrgType.PME_DIRECTE)
    assert isinstance(org.created_at, datetime)
