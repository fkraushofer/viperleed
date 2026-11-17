"""Throwaway (antagonist experiment, never merged)."""

import os
import sys


def test_fails_only_on_py310():
    assert sys.version_info[:2] != (3, 10), 'fails on 3.10 only'


def test_fails_only_serially():
    assert os.environ.get('PYTEST_XDIST_WORKER'), 'fails without xdist'
