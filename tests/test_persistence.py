import pytest

import authum.persistence


@pytest.fixture()
def k(random_string):
    return authum.persistence.KeyringItem(random_string, {"foo": "bar", "baz": "qux"})


def test_keyring_item_getitem_error(k, random_string):
    with pytest.raises(KeyError):
        k[random_string]


def test_keyring_item_getitem_ok(k):
    assert k["foo"] == "bar"
    assert k["baz"] == "qux"


def test_keyring_item_delitem_error(k, random_string):
    with pytest.raises(KeyError):
        del k[random_string]


def test_keyring_item_delitem_ok(k):
    del k["foo"]
    assert k.asdict() == {"baz": "qux"}


def test_keyring_item_iter(k):
    assert [n for n in k] == ["foo", "baz"]


def test_keyring_item_len(k):
    assert len(k) == 2


def test_keyring_item_save(k):
    k.save()
    new_k = authum.persistence.KeyringItem(k.keyring_item_name)
    assert new_k.asdict() == k.asdict()


def test_keyring_item_delete(k):
    k.delete()
    assert k.asdict() == {}

    new_k = authum.persistence.KeyringItem(k.keyring_item_name)
    assert new_k.asdict() == {}
