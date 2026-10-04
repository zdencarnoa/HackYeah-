"""Pitch figures for the ML evaluation (PNG, slide-ready).

    python -m app.ml.figures      # from backend/ -> app/ml/figures/*.png

1. confusion_holdout.png  honest test: DistilBERT on CEAS_08, a source it never saw
2. demo_ml_vs_system.png  team demo emails: ML alone vs the full system (rules + ML fusion)
Numbers come from the training logs and from running the system, never typed in.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "figures"
LOG = HERE / "logs" / "calib_ceas.log"  # the run whose calibration the shipped model uses

# Sequential blue ramp (steps 100 -> 600) and text tokens from the dataviz reference palette.
BLUES = LinearSegmentedColormap.from_list("blues", ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"])
INK, INK_MUTED, SURFACE, GRID = "#1f1f1e", "#6b6a66", "#ffffff", "#e4e2dd"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13, "text.color": INK,
                     "axes.labelcolor": INK_MUTED, "xtick.color": INK, "ytick.color": INK})


def holdout_counts() -> tuple[int, int, int, int]:
    m = re.findall(r"confusion: TN=(\d+) FP=(\d+) FN=(\d+) TP=(\d+)", LOG.read_text(encoding="utf-8"))
    return tuple(int(x) for x in m[-1])


def draw_matrix(ax, tn, fp, fn, tp, title, max_rate=1.0):
    """2x2 confusion matrix, shaded by the share of each actual class (row-normalised)."""
    counts = np.array([[tn, fp], [fn, tp]])
    rates = counts / counts.sum(axis=1, keepdims=True)
    ax.imshow(rates, cmap=BLUES, vmin=0, vmax=max_rate)
    for (r, c), n in np.ndenumerate(counts):
        light_cell = rates[r, c] < 0.55
        color = INK if light_cell else SURFACE
        ax.text(c, r - 0.08, f"{n:,}", ha="center", va="center", fontsize=22, fontweight="bold", color=color)
        ax.text(c, r + 0.2, f"{rates[r, c]:.1%} of {'legitimate' if r == 0 else 'phishing'}",
                ha="center", va="center", fontsize=11, color=color)
    ax.set_xticks([0, 1], ["Legitimate", "Phishing"])
    ax.set_yticks([0, 1], ["Legitimate", "Phishing"])
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.tick_params(length=0)
    ax.set_title(title, fontsize=13, color=INK, pad=10, loc="left")
    for spine in ax.spines.values():
        spine.set_visible(False)
    # 2px surface gaps between the cells
    for x in (0.5,):
        ax.axvline(x, color=SURFACE, lw=3)
        ax.axhline(x, color=SURFACE, lw=3)


def figure_holdout() -> Path:
    tn, fp, fn, tp = holdout_counts()
    recall, precision = tp / (tp + fn), tp / (tp + fp)
    fpr, acc = fp / (fp + tn), (tp + tn) / (tp + tn + fp + fn)
    fig, ax = plt.subplots(figsize=(10, 8.4), facecolor=SURFACE)
    fig.subplots_adjust(left=0.2, right=0.92, top=0.8, bottom=0.17)
    draw_matrix(ax, tn, fp, fn, tp, f"DistilBERT on {tp + tn + fp + fn:,} emails from a source it never saw (CEAS_08)")
    fig.text(0.04, 0.95, f"The model catches {recall:.1%} of phishing,", fontsize=19, fontweight="bold", va="top")
    fig.text(0.04, 0.90, f"with {fpr:.1%} false alarms on legitimate email", fontsize=19, fontweight="bold", va="top")
    fig.text(0.04, 0.06, f"Accuracy {acc:.1%}  ·  Precision {precision:.1%}  ·  Recall {recall:.1%}", fontsize=12,
             color=INK_MUTED)
    fig.text(0.04, 0.03, "Kaggle Phishing Email Dataset; whole-source holdout, so no corpus style can leak into the test",
             fontsize=11, color=INK_MUTED)
    path = OUT / "confusion_holdout.png"
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return path


def demo_counts():
    os.environ.setdefault("LLM_LIVE", "0")
    from app.detection import message_from_sim
    from app.schemas import Severity
    from app.scoring.analyze import analyze
    from app.simulation.seed import load_emails

    ml, system = np.zeros((2, 2), int), np.zeros((2, 2), int)
    for sim in load_emails():
        if sim.scenario.label not in ("legitimate", "phishing"):
            continue
        actual = int(sim.scenario.label == "phishing")
        a = analyze(message_from_sim(sim))
        ml[actual, int((a.ml_confidence or 0) >= 0.5)] += 1
        system[actual, int(a.risk >= Severity.MEDIUM)] += 1
    return ml, system


def figure_demo() -> Path:
    ml, system = demo_counts()
    fig, axes = plt.subplots(1, 2, figsize=(14, 7.4), facecolor=SURFACE)
    fig.subplots_adjust(left=0.1, right=0.97, top=0.78, bottom=0.17, wspace=0.35)
    draw_matrix(axes[0], *ml.ravel(), "Text classifier alone")
    draw_matrix(axes[1], *system.ravel(), "Full system: rules + text classifier")
    n = int(ml.sum())
    fig.text(0.03, 0.95, f"On the {n} demo emails, the rules catch what the text model misses",
             fontsize=19, fontweight="bold", va="top")
    fig.text(0.03, 0.885, f"{int(ml.trace())}/{n} correct with the text model alone, "
             f"{int(system.trace())}/{n} with the full system", fontsize=14, color=INK_MUTED, va="top")
    fig.text(0.03, 0.05, "Text model flags at 50% probability; the system flags at risk MEDIUM or above.",
             fontsize=11, color=INK_MUTED)
    fig.text(0.03, 0.02, "The text model reads the wording; the detection rules read sender, domains and links. "
             "Demo emails are never used for training.", fontsize=11, color=INK_MUTED)
    path = OUT / "demo_ml_vs_system.png"
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return path


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for p in (figure_holdout(), figure_demo()):
        print("saved", p)
