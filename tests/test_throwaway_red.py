"""Throwaway: fails on Windows only (not for upstream)."""

import sys


def test_fails_on_windows():
    assert sys.platform != 'win32'
