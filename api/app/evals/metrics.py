from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class LabelScore:
    label: str
    precision: float
    recall: float
    f1: float
    support: int


def per_label_scores(pairs: Sequence[tuple[str, str]], labels: Sequence[str]) -> list[LabelScore]:
    """pairs are (expected, predicted)."""
    scores: list[LabelScore] = []
    for label in labels:
        tp = sum(1 for e, p in pairs if e == label and p == label)
        fp = sum(1 for e, p in pairs if e != label and p == label)
        fn = sum(1 for e, p in pairs if e == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        scores.append(LabelScore(label, precision, recall, f1, tp + fn))
    return scores


def accuracy(pairs: Sequence[tuple[str, str]]) -> float:
    if not pairs:
        return 0.0
    return sum(1 for e, p in pairs if e == p) / len(pairs)


def macro_f1(scores: Sequence[LabelScore]) -> float:
    present = [s for s in scores if s.support > 0]
    if not present:
        return 0.0
    return sum(s.f1 for s in present) / len(present)


def confusion_matrix(pairs: Sequence[tuple[str, str]], labels: Sequence[str]) -> str:
    counts: Counter[tuple[str, str]] = Counter(pairs)
    width = max(len(label) for label in labels) + 1
    header = " " * (width + 2) + " ".join(f"{label[:6]:>6s}" for label in labels)
    rows = [header, " " * (width + 2) + "-" * (7 * len(labels))]
    for expected in labels:
        cells = " ".join(f"{counts[(expected, predicted)]:6d}" for predicted in labels)
        rows.append(f"{expected:<{width}} |{cells}")
    rows.append("")
    rows.append("rows are expected, columns are predicted")
    return "\n".join(rows)
