"""System test configuration: override global socket blocking for Docker tests."""

import pytest_socket

# Re-enable real TCP sockets at import time so session-scoped Docker fixtures
# can make real HTTP calls before any test function runs.
pytest_socket.enable_socket()
