"""Host-provider abstraction.

GitHub and GitLab ship; Bitbucket and Gitea are deferred. Self-hosted
instances declare themselves in ~/.haywire/config.toml, or travel with a
published library as ``origin_provider``.

Providers are host-parameterised: a self-hosted forge gets its own instance
bound to its hostname, so every URL it builds targets that host rather than
the ``github.com`` / ``gitlab.com`` default.
"""

import re

from haywire.core.marketstall.host_providers.base import HostProvider, ParsedRef
from haywire.core.marketstall.host_providers.github import GitHubProvider
from haywire.core.marketstall.host_providers.gitlab import GitLabProvider
from haywire.core.marketstall.host_providers import config as _host_config

__all__ = [
    "HostProvider",
    "ParsedRef",
    "HOST_PROVIDERS",
    "PROVIDER_CLASSES",
    "provider_for",
    "resolve_host",
    "ssh_to_https",
]

#: Provider classes by ``name``, for constructing a per-host instance. Keep the
#: keys in sync with ``config._SHIPPED_PROVIDERS`` — a name accepted there but
#: absent here silently yields no provider.
PROVIDER_CLASSES: dict[str, type] = {
    "github": GitHubProvider,
    "gitlab": GitLabProvider,
    # "bitbucket" — deferred
    # "gitea"     — deferred
}

#: Default-host instances, in match order. Used only for the built-in fallback;
#: a self-hosted host never resolves through these.
HOST_PROVIDERS: list[HostProvider] = [
    GitHubProvider(),
    GitLabProvider(),
]


def provider_for(provider_name: str, hostname: str) -> HostProvider | None:
    """Build the named provider bound to *hostname*, or None if unknown.

    Resolves without any local configuration, so a published library's
    ``origin_provider`` and ``origin`` are enough to reach a self-hosted
    instance the consumer has never heard of.

    Args:
        provider_name: A key of ``PROVIDER_CLASSES`` — "github" or "gitlab".
    """
    cls = PROVIDER_CLASSES.get(provider_name)
    return cls(hostname) if cls is not None else None


def resolve_host(hostname: str) -> HostProvider | None:
    """Resolve a hostname to its HostProvider.

    Consults the user's self-hosted config (~/.haywire/config.toml) first; a
    matching [[hosts]] entry naming a shipped provider yields an instance bound
    to that hostname. Otherwise falls back to the built-in default-host
    providers.

    Returns None — never a guess — for an unrecognised host.
    """
    user_hosts = _host_config.load_self_hosted_hosts()
    if hostname in user_hosts:
        return provider_for(user_hosts[hostname], hostname)

    for provider in HOST_PROVIDERS:
        if provider.matches(hostname):
            return provider
    return None


def ssh_to_https(url: str) -> str:
    """Convert an SSH-style git URL to HTTPS; any other URL passes through unchanged.

    Takes whatever ``git remote get-url origin`` returns and yields a form a
    hostname can be parsed out of::

        git@github.com:user/repo.git  ->  https://github.com/user/repo.git

    Any trailing ``.git`` is preserved.
    """
    match = re.match(r"^git@([^:]+):(.+)$", url)
    if match:
        host, path = match.groups()
        return f"https://{host}/{path}"
    return url
