"""Protein sequence databases and their providers."""

from interop_trace.databases.base import Database, DatabaseProvider
from interop_trace.databases.uniprot import UniProtProvider

__all__ = ["Database", "DatabaseProvider", "UniProtProvider"]
