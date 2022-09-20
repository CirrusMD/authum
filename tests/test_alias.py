import pytest

import authum.alias


@pytest.fixture()
def a(random_string):
    aliases = authum.alias.Aliases(f"alias.{random_string}")
    aliases.clear()
    aliases.add("foo", "http://foobar")
    return aliases


def test_aliases_add_error(a, random_string):
    with pytest.raises(Exception):
        a.add(random_string, random_string)


def test_aliases_add_ok(a, random_string, random_url):
    a.add(random_string, random_url)
    assert a[random_string] == random_url


def test_aliases_resolve_url(a, random_url):
    assert a.resolve(random_url) == random_url


def test_aliases_resolve_alias_error(a):
    with pytest.raises(authum.alias.AliasError):
        a.resolve("bar")


def test_aliases_resolve_alias_ok(a):
    assert a.resolve("foo") == "http://foobar"


def test_aliases_aliases_for(a):
    assert a.aliases_for("http://foobar") == ["foo"]


def test_aliases_mv_error(a, random_string):
    with pytest.raises(authum.alias.AliasError):
        a.mv("invalid", random_string)


def test_aliases_mv_ok(a, random_string):
    a.mv("foo", random_string)
    assert a.asdict() == {random_string: "http://foobar"}


def test_aliases_rm_error(a, random_string):
    with pytest.raises(authum.alias.AliasError):
        a.rm(random_string)


def test_aliases_rm_ok(a):
    a.rm("foo")
    assert a.asdict() == {}
    a.delete()
