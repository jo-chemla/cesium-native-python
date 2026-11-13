from . import async_  # pyright: ignore[reportAttributeAccessIssue]

class CurlAssetAccessorOptions:
    user_agent: str
    request_headers: list[tuple[str, str]]
    allow_directory_creation: bool
    certificate_path: str
    certificate_file: str
    """CA bundle file for HTTPS (curl ``CAINFO``). Linux wheels default it to
    ``CURL_CA_BUNDLE`` / ``SSL_CERT_FILE`` or the first well-known system
    bundle when left empty; see ``CurlAssetAccessor``."""
    do_global_init: bool

class CurlAssetAccessor(async_.IAssetAccessor):
    @property
    def options(self) -> CurlAssetAccessorOptions: ...
    def __init__(self, options: CurlAssetAccessorOptions = ...) -> None: ...
