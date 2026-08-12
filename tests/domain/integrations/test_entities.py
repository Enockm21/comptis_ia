import uuid
from datetime import datetime, timezone
from comptis.domain.integrations.entities import Integration

def test_token_set_true_when_flagged():
    integ = Integration(
        id=uuid.uuid4(), organization_id=uuid.uuid4(), name="pnicompta",
        api_url="https://host/api", mcp_url=None, token_set=True,
        updated_at=datetime.now(tz=timezone.utc),
    )
    assert integ.token_set is True

def test_token_set_false_by_default():
    integ = Integration(
        id=uuid.uuid4(), organization_id=uuid.uuid4(), name="pnicompta",
        api_url=None, mcp_url=None, token_set=False,
        updated_at=datetime.now(tz=timezone.utc),
    )
    assert integ.token_set is False
