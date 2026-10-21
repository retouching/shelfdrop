"""shelfdrop.settings.service: the settings read and changed, their audit, the import of the
environment."""

import pytest

from shelfdrop.settings.cipher import SecretBox
from shelfdrop.settings.exceptions import InvalidSettingsError
from shelfdrop.settings.service import SettingsService
from shelfdrop.settings.types import SettingsChange
from tests.unit.settings.support import TEST_SECRET_KEY, FakeSettingsRepository
from tests.unit.works.support import FixedClock


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def new_service() -> tuple[SettingsService, FakeSettingsRepository]:
    repository = FakeSettingsRepository()
    return SettingsService(repository, SecretBox(TEST_SECRET_KEY), FixedClock()), repository


@pytest.mark.anyio
async def test_the_settings_never_saved_have_their_default_and_no_secret() -> None:
    service, _ = new_service()

    view = await service.read()

    assert view.values["search.max_names"] == 6
    assert view.values["prowlarr.url"] is None
    assert view.secrets["prowlarr.api_key"] is None


@pytest.mark.anyio
async def test_a_change_is_saved_and_audited_without_its_value() -> None:
    service, repository = new_service()

    view = await service.save(
        SettingsChange(
            values={"prowlarr.url": "http://prowlarr:9696", "search.max_names": 6},
            secrets={"prowlarr.api_key": "secret-key-1"},
        ),
        "sylvain",
    )

    assert view.values["prowlarr.url"] == "http://prowlarr:9696"
    assert view.secrets["prowlarr.api_key"] == int(FixedClock().now())
    assert b"secret-key-1" not in repository.sealed["prowlarr.api_key"][0]
    # The default given again is no change.
    assert [(e.actor, e.action, e.target) for e in repository.audit] == [
        ("sylvain", "changed", "prowlarr.url"),
        ("sylvain", "replaced", "prowlarr.api_key"),
    ]
    assert all("secret-key-1" not in repr(entry) for entry in repository.audit)
    assert repository.commits == 1


@pytest.mark.anyio
async def test_a_secret_cleared_is_gone_and_audited_once() -> None:
    service, repository = new_service()
    await service.save(SettingsChange(values={}, secrets={"jellyfin.api_key": "k1"}), "a")

    view = await service.save(SettingsChange(values={}, secrets={"jellyfin.api_key": None}), "b")
    await service.save(SettingsChange(values={}, secrets={"jellyfin.api_key": None}), "b")

    assert view.secrets["jellyfin.api_key"] is None
    assert [e.action for e in repository.audit] == ["replaced", "cleared"]


@pytest.mark.anyio
async def test_an_invalid_change_saves_nothing() -> None:
    service, repository = new_service()

    with pytest.raises(InvalidSettingsError) as refused:
        await service.save(
            SettingsChange(
                values={"prowlarr.url": "http://ok:9696", "search.max_names": 99},
                secrets={"nothing.key": "x"},
            ),
            "sylvain",
        )

    assert refused.value.keys == ["nothing.key", "search.max_names"]
    assert repository.values == {}
    assert repository.commits == 0


@pytest.mark.anyio
async def test_the_environment_is_imported_once() -> None:
    service, repository = new_service()
    found = {"prowlarr.url": "http://prowlarr:9696", "prowlarr.api_key": "env-key"}

    first = await service.import_environment(found)
    await service.save(SettingsChange(values={}, secrets={"prowlarr.api_key": None}), "sylvain")
    again = await service.import_environment(found)

    assert first == ["prowlarr.api_key", "prowlarr.url"]
    assert again == []
    assert "prowlarr.api_key" not in repository.sealed
    assert [(e.actor, e.action) for e in repository.audit[:2]] == [
        ("environment", "imported"),
        ("environment", "imported"),
    ]


@pytest.mark.anyio
async def test_a_value_set_later_in_the_environment_is_imported_then() -> None:
    service, _ = new_service()
    await service.import_environment({"prowlarr.url": "http://prowlarr:9696"})

    imported = await service.import_environment(
        {"prowlarr.url": "http://other:9696", "jellyfin.url": "http://jellyfin:8096"}
    )

    view = await service.read()
    assert imported == ["jellyfin.url"]
    assert view.values["prowlarr.url"] == "http://prowlarr:9696"
    assert view.values["jellyfin.url"] == "http://jellyfin:8096"


@pytest.mark.anyio
async def test_the_environment_never_overwrites_the_page() -> None:
    service, _ = new_service()
    await service.save(SettingsChange(values={"jellyfin.url": "http://page:8096"}, secrets={}), "s")

    assert await service.import_environment({"jellyfin.url": "http://env:8096"}) == []
    assert (await service.read()).values["jellyfin.url"] == "http://page:8096"
