"""Host-provider abstraction.

GitHub + GitLab ship in the first cut. Bitbucket and Gitea are deferred.
Self-hosted instances declare themselves in ~/.haywire/config.toml.
"""

from haywire.core.marketstall.host_providers.base import HostProvider, ParsedRef
from haywire.core.marketstall.host_providers.github import GitHubProvider
from haywire.core.marketstall.host_providers.gitlab import GitLabProvider
from haywire.core.marketstall.host_providers import config as _host_config

__all__ = ["HostProvider", "ParsedRef", "HOST_PROVIDERS", "resolve_host"]

HOST_PROVIDERS: list[HostProvider] = [
    GitHubProvider(),
    GitLabProvider(),
    # BitbucketProvider() — deferred
    # GiteaProvider()     — deferred
]

_PROVIDER_BY_NAME: dict[str, HostProvider] = {p.name: p for p in HOST_PROVIDERS}


def resolve_host(hostname: str) -> HostProvider | None:
    """Resolve a hostname to its HostProvider.

    Consults the user's self-hosted config (~/.haywire/config.toml) first; if a
    matching [[hosts]] entry names a shipped provider, that provider handles
    the hostname. Otherwise falls back to built-in `provider.matches(hostname)`.
    """
    user_hosts = _host_config.load_self_hosted_hosts()
    if hostname in user_hosts:
        return _PROVIDER_BY_NAME.get(user_hosts[hostname])

    for provider in HOST_PROVIDERS:
        if provider.matches(hostname):
            return provider
    return None
