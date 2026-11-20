"""Smoke test: the package is installed in the environment and importable."""

import irpf_assistant


def test_package_is_importable() -> None:
    assert irpf_assistant.__version__
