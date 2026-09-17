"""Optional standalone WebUI acceptance; its real built assets are required."""
import re

import pytest
from fastapi.testclient import TestClient
from mempulse.web import create_app


@pytest.mark.standalone_webui
def test_standalone_webui_serves_real_page_and_javascript(tmp_path):
    with TestClient(create_app(tmp_path / "webui.db", serve_ui=True)) as client:
        page = client.get("/")
        # These original page assertions remain mandatory for WebUI delivery.
        assert page.status_code == 200
        assert "root" in page.text
        assert page.headers["content-type"].startswith("text/html")
        scripts = re.findall(r'<script[^>]+src=[\"\']([^\"\']+)[\"\']', page.text)
        assert scripts, "Build the real standalone WebUI; an empty placeholder is not sufficient"
        for source in scripts:
            asset = client.get(source)
            assert asset.status_code == 200
            assert "javascript" in asset.headers["content-type"]
            assert len(asset.content) > 100
