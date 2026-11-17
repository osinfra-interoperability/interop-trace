"""Interpret saved OLS term responses for directional EDAM matching."""

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

OLS_EDAM_URL = "https://www.ebi.ac.uk/ols4/api/ontologies/edam"


def edam_uri(value: object) -> str:
    """Canonicalise HTTP/HTTPS data/format URIs without guessing terms."""
    match = (
        re.fullmatch(r"https?://edamontology.org/((?:data|format)_\d{4})", value)
        if isinstance(value, str)
        else None
    )
    return f"http://edamontology.org/{match[1]}" if match else ""


def term_url(uri: str) -> str:
    """OLS v2 entity paths require a twice-encoded IRI."""
    return "https://www.ebi.ac.uk/ols4/api/v2/ontologies/edam/entities/" + quote(
        quote(uri, safe=""), safe=""
    )


def referenced_terms(value: Any) -> set[str]:
    """Find unique EDAM data/format annotations in a public JSON description."""
    if isinstance(value, dict):
        uri = edam_uri(value.get("uri"))
        return ({uri} if uri else set()).union(
            *(referenced_terms(v) for v in value.values())
        )
    if isinstance(value, list):
        return set().union(*(referenced_terms(v) for v in value))
    return set()


@dataclass(frozen=True)
class Edam:
    """Subclass ancestors reported by OLS for active, resolved concepts."""

    ancestors: dict[str, frozenset[str]]

    @classmethod
    def from_responses(cls, responses: list[dict[str, Any]]) -> "Edam":
        ancestors = {}
        for response in responses:
            uri = edam_uri(response.get("iri"))
            parents = response.get("directAncestor", [])
            if (
                uri
                and response.get("isObsolete") is False
                and isinstance(parents, list)
            ):
                ancestors[uri] = frozenset(
                    parent for value in parents if (parent := edam_uri(value))
                )
        return cls(ancestors)

    def match(self, output: str, accepted: str, branch: str) -> str | None:
        """Report identity or directional subclass support; no path means unknown."""
        output, accepted = edam_uri(output), edam_uri(accepted)
        prefix = f"http://edamontology.org/{branch}_"
        if any(
            not uri.startswith(prefix) or uri not in self.ancestors
            for uri in (output, accepted)
        ):
            return None
        if output == accepted:
            return "identity"
        return "subclass" if accepted in self.ancestors[output] else None
