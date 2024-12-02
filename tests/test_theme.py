import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

# TODO

os.environ["PIMP_TESTING"] = "True"
from pimpmyrice.theme import ThemeManager


# Set environment variables and prepare test environment
@pytest.fixture(scope="session", autouse=True)
def setup_environment() -> Any:
    files_dir = Path("./tests/files")
    if files_dir.exists():
        shutil.rmtree(files_dir)
    yield
    shutil.rmtree(files_dir)


@pytest.fixture
def tm() -> ThemeManager:
    return ThemeManager()


@pytest.mark.asyncio(scope="session")
async def test_clone_module(tm: ThemeManager) -> None:
    res = await tm.mm.clone_module("pimp://alacritty")
    print(res)
    assert res.ok


@pytest.mark.asyncio(scope="session")
async def test_gen_theme(tm: ThemeManager) -> None:
    res = await tm.generate_theme("./tests/example.jpg")
    print(res)
    assert res.ok


@pytest.mark.asyncio(scope="session")
async def test_set_random_theme(tm: ThemeManager) -> None:
    res = await tm.set_random_theme()
    print(res)
    assert res.ok
