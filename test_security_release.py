#!/usr/bin/env python3
from tests.test_security_release import *  # noqa: F401,F403


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__]))
