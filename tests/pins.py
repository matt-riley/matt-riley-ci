"""Shared assertions for Renovate-bumped tool version pins in workflows."""
import re

MISE_RELEASE = re.compile(r'^\d{4}\.\d+\.\d+$')
NODE_MAJOR = re.compile(r'^\d+$')
LUALS_RELEASE = re.compile(r'^\d+\.\d+\.\d+$')
V_SEMVER_TAG = re.compile(r'^v\d+\.\d+\.\d+$')


def assert_nonempty_pin(test, value, pattern, label):
    text = str(value).strip()
    test.assertTrue(text, f'{label} must not be empty')
    test.assertRegex(text, pattern, f'{label} must look like a pinned version, not {value!r}')