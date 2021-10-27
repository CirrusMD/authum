import authum.plugin


def test_load_plugins():
    assert authum.plugin.load_plugins() == [
        "authum.plugins.aws",
        "authum.plugins.jumpcloud",
        "authum.plugins.okta",
    ]
