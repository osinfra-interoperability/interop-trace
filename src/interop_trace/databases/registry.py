"""Registered database providers; implementations are imported by this package."""

from interop_trace.components import Registry
from interop_trace.databases.base import DatabaseProvider

registry: Registry[DatabaseProvider] = Registry()
