#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest 配置：
1. 注册 network marker（默认跳过真实网络测试）。
2. 把项目根目录加入 sys.path，使 `from shared import ...` 在 tests/ 下可直接用。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "network: 真实发起网络请求的测试（默认跳过，用 pytest -m network 显式运行）",
    )


def pytest_collection_modifyitems(config, items):
    """未显式选中 network 时，自动跳过带 network mark 的用例。"""
    if config.getoption("-m") == "":
        skip_marker = pytest.mark.skip(reason="需要网络，用 -m network 显式运行")
        for item in items:
            if "network" in item.keywords:
                item.add_marker(skip_marker)
