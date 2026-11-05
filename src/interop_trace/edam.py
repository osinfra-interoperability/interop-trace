"""Read named EDAM subclass relationships; no general OWL reasoning."""

import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

EDAM_RELEASE = "1.25.20260626T1230Z"
EDAM_URL = (
    "https://raw.githubusercontent.com/edamontology/edamontology/"
    "3a6e2ca4f5eba34d189e737808909f3c96270c84/EDAM_dev.owl"
)
_NS = {
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}


def _uri(value: str) -> str:
    """Canonicalise HTTP/HTTPS EDAM data/format URIs without guessing terms."""
    match = re.fullmatch(r"https?://edamontology.org/((?:data|format)_\d{4})", value)
    return f"http://edamontology.org/{match[1]}" if match else ""


@dataclass(frozen=True)
class Edam:
    """Active concepts and their explicitly named parents from one snapshot."""

    parents: dict[str, tuple[str, ...]]

    @classmethod
    def from_file(cls, path: Path) -> "Edam":
        """Load data and format classes, excluding deprecated concepts."""
        parents = {}
        for node in ElementTree.parse(path).findall("owl:Class", _NS):
            uri = _uri(node.get(f"{{{_NS['rdf']}}}about", ""))
            if not uri or node.findtext("owl:deprecated", "false", _NS) == "true":
                continue
            parents[uri] = tuple(
                sorted(
                    {
                        parent
                        for relation in node.findall("rdfs:subClassOf", _NS)
                        if (
                            parent := _uri(
                                relation.get(f"{{{_NS['rdf']}}}resource", "")
                            )
                        )
                    }
                )
            )
        if not parents:
            raise ValueError("No EDAM data or format classes in the ontology snapshot.")
        return cls(parents)

    def match(self, output: str, accepted: str, branch: str) -> list[str] | None:
        """Return an identity/ancestor path from output to accepted input, if known.

        Reverse ancestry, siblings, missing and obsolete concepts give no support.
        Lack of a path does not establish disjointness or incompatibility.
        """
        output, accepted = _uri(output), _uri(accepted)
        prefix = f"http://edamontology.org/{branch}_"
        if any(
            not uri.startswith(prefix) or uri not in self.parents
            for uri in (output, accepted)
        ):
            return None
        pending = deque([[output]])
        visited = {output}
        while pending:
            path = pending.popleft()
            if path[-1] == accepted:
                return path
            for parent in self.parents.get(path[-1], ()):
                if parent in self.parents and parent not in visited:
                    visited.add(parent)
                    pending.append([*path, parent])
        return None
