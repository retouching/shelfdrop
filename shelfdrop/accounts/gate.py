"""SetupGate: whether the set-up of the first launch is known finished, in memory (a container
singleton). Once it is, the API no longer reads the database to know it."""

from dataclasses import dataclass


@dataclass
class SetupGate:
    done: bool = False
