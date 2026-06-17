from comptis.domain.tenancy.value_objects import OrgType, Role


def test_role_values():
    assert Role.OWNER == "owner"
    assert Role.ACCOUNTANT == "accountant"
    assert Role.VIEWER == "viewer"


def test_org_type_values():
    assert OrgType.EDITEUR == "editeur"
    assert OrgType.CABINET == "cabinet"
    assert OrgType.PME_DIRECTE == "pme_directe"


def test_role_is_string():
    assert isinstance(Role.ACCOUNTANT, str)


def test_org_type_from_string():
    assert OrgType("cabinet") == OrgType.CABINET
