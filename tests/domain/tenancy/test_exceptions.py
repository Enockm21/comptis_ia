from comptis.domain.tenancy.exceptions import MissingTenantContextError


def test_missing_tenant_context_is_an_exception():
    err = MissingTenantContextError("no context set")
    assert isinstance(err, Exception)
    assert "no context set" in str(err)


def test_missing_tenant_context_can_be_raised():
    import pytest
    with pytest.raises(MissingTenantContextError, match="tenant context required"):
        raise MissingTenantContextError("tenant context required")
