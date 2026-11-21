"""Pure-Python stand-in for the `bezier` package, used by python-ghost-cursor.

The real package's compiled library needs an executable stack, which the Pi 5 kernel
refuses (import fails; clearing the flag makes it segfault). Ghost-cursor only needs
Curve.from_nodes(...), .evaluate_multi(s) and .length, so we provide exactly that.
"""
import sys
import types
from math import comb

import numpy as np


class Curve:
    def __init__(self, nodes):
        self.nodes = np.asarray(nodes, dtype=float)       # shape (2, n+1)

    @classmethod
    def from_nodes(cls, nodes):
        return cls(nodes)

    def evaluate_multi(self, s):
        s = np.asarray(s, dtype=float)
        n = self.nodes.shape[1] - 1
        out = np.zeros((self.nodes.shape[0], s.size))
        for k in range(n + 1):
            out += self.nodes[:, [k]] * (comb(n, k) * (1 - s) ** (n - k) * s ** k)
        return out

    @property
    def length(self) -> float:
        pts = self.evaluate_multi(np.linspace(0.0, 1.0, 200))
        return float(np.sum(np.hypot(*np.diff(pts, axis=1))))


def install() -> None:
    mod = types.ModuleType("bezier")
    mod.curve = types.SimpleNamespace(Curve=Curve)
    sys.modules["bezier"] = mod
