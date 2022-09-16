import importlib
import logging
import os
import pkgutil
import sys

import pluggy


PLUGIN_MODULE_BUILTIN_PATH = os.path.join(os.path.dirname(__file__), "plugins")
PLUGIN_MODULE_BUILTIN_PREFIX = f"{__package__}.plugins."
PLUGIN_MODULE_PREFIX = f"{__package__}-"

log = logging.getLogger(__name__)

hookspec = pluggy.HookspecMarker(__package__)
hookimpl = pluggy.HookimplMarker(__package__)


@hookspec
def extend_cli(click_group):
    """Adds CLI parameters/arguments

    Args:
        click_group (click.Group): The root click group object

    Returns:
        None
    """
    pass


@hookspec
def list_apps():
    """Returns a list of applications from an identity provider.

    Returns:
        Iterable[authum.http.SSOApplication]: An Iterable of SSO applications
    """
    pass


@hookspec(firstresult=True)
def saml_request(url):
    """Performs a SAML request and returns the response. Note that it's up to
    each plugin to decide whether it should handle requests for a given URL
    (e.g. by checking the domain name).

    Args:
        url (str): A SAML URL

    Returns:
        Union[authum.http.SAMLAssertion, None]: A SAML assertion
    """
    pass


def load_plugins(*extra_paths: str) -> list:
    """Imports and registers plugin modules"""
    module_names = [
        m.name
        for m in pkgutil.iter_modules(
            path=[PLUGIN_MODULE_BUILTIN_PATH], prefix=PLUGIN_MODULE_BUILTIN_PREFIX
        )
    ]

    sys.path = list(extra_paths) + sys.path
    module_names += [
        m.name
        for m in pkgutil.iter_modules()
        if m.name.startswith(PLUGIN_MODULE_PREFIX)
    ]

    return [manager.register(importlib.import_module(m)) for m in module_names]


def hookcall_monitoring_before(hook_name, hook_impls, kwargs):
    log.debug(
        f"Hook request for '{hook_name}' with args={kwargs} plugins={[i.plugin_name for i in hook_impls]}"
    )


def hookcall_monitoring_after(outcome, hook_name, hook_impls, kwargs):
    log.debug(f"Hook result for '{hook_name}': {outcome.get_result()}")


manager = pluggy.PluginManager(__package__)
manager.add_hookspecs(sys.modules[__name__])
manager.add_hookcall_monitoring(hookcall_monitoring_before, hookcall_monitoring_after)
