from .bitbucket import BitbucketProvider


def get_provider(kind: str, **kwargs):
    if kind == "bitbucket":
        return BitbucketProvider(**kwargs)
    raise ValueError(f"Unsupported provider: {kind}")