"""Phase P10 — security regressions (catalog URL scheme guard)."""

import pytest

from agentrouter.refresh import RefreshError, _http_get_json


@pytest.mark.security
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "file://C:/Windows/win.ini",
        "ftp://example.com/models.json",
        "gopher://evil/",
        "data:text/plain,hi",
    ],
)
def test_refresh_refuses_non_http_schemes(url):
    # Must reject before any network/file access — a malicious/typo'd registry
    # URL cannot be used to read local files or reach custom handlers.
    with pytest.raises(RefreshError, match="non-http"):
        _http_get_json(url, api_key=None)
