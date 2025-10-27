from __future__ import annotations

import logging
from typing import Iterator

import pytest

import podlog.api as podlog_api
from podlog.core.manager import GLOBAL_MANAGER


@pytest.fixture(autouse=True)
def reset_podlog() -> Iterator[None]:
    yield
    GLOBAL_MANAGER.shutdown()
    podlog_api._CONFIGURED = False
    root = logging.getLogger()
    root.handlers = []
    root.setLevel(logging.NOTSET)
    logging.captureWarnings(False)
