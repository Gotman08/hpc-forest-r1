"""Plot saved measured-trial counts and common final speedups; no new experiments."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def main():
    study = Path(__file__).resolve().parents[1]
    results = study / "results"
    summary = read(results / "exploration-comparison.json")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none"})
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True, sharey="row")
    labels = {"gemm_cpu": "GEMM CPU", "blackscholes": "Black–Scholes"}
    for row, case in enumerate(("gemm_cpu", "blackscholes")):
        for col, condition in enumerate(("off", "corrected")):
            ax = axes[row, col]
            old = read(study / "baseline-r3" / f"{case}-{condition}-curve.json")["rows"]
            ax.plot([r["charged_seconds"] / 60 for r in old],
                    [r["correct_measured_trials"] for r in old],
                    "--", color="#7b818a", label="R3 antérieur", linewidth=1.8)
            for repeat, color in ((1, "#147d92"), (2, "#a35317")):
                rows = read(results / f"{case}-r{repeat}-{condition}-curve.json")["rows"]
                ax.plot([r["charged_seconds"] / 60 for r in rows],
                        [r["correct_measured_trials"] for r in rows],
                        "o-", color=color, label=f"Nouveau — répétition {repeat}", linewidth=2)
            ax.set_title(labels[case] + (" · sans TabPFN" if condition == "off" else " · avec TabPFN"))
            ax.set_xticks((15, 30, 45, 60, 75, 90))
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            ax.set_ylim(bottom=0)
            ax.grid(axis="y", alpha=.2)
            if col == 0:
                ax.set_ylabel("Essais corrects réellement mesurés")
            if row == 1:
                ax.set_xlabel("Temps imputé au budget (minutes)")
    handles, legend = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, legend, loc="lower center", ncols=3, bbox_to_anchor=(.5, .045), frameon=False)
    fig.suptitle("Forest · progression des essais à budget égal", fontsize=17, weight="bold")
    fig.text(.5, .018, "Hors combinaisons et confirmation finale. R3 : référence historique descriptive, une recherche par condition.",
             ha="center", fontsize=9, color="#555b65")
    fig.tight_layout(rect=(0, .1, 1, .95))
    for suffix in ("svg", "png"):
        fig.savefig(results / ("measured-trials." + suffix), dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, case in zip(axes, ("gemm_cpu", "blackscholes")):
        for repeat, marker, offset in ((1, "o", -.06), (2, "s", .06)):
            pair = {r["condition"]: r for r in summary["arms"] if r["case"] == case and r["repeat"] == repeat}
            for x, metric in enumerate(("registered_speedup", "reserved_speedup")):
                for condition, dx, color in (("off", -.14, "#147d92"), ("corrected", .14, "#a35317")):
                    value = pair[condition][metric]
                    ax.scatter([x + dx + offset], [value], color=color, marker=marker, s=65,
                               label=("Sans TabPFN" if condition == "off" else "Avec TabPFN") + f" · r{repeat}" if x == 0 else None)
        ax.set_title(labels[case])
        ax.set_xticks((0, 1), ("Entrées enregistrées", "Entrées réservées"))
        ax.set_ylabel("Accélération par rapport au code initial (×)")
        ax.grid(axis="y", alpha=.2)
        ax.set_ylim(bottom=0)
        ax.set_xlim(-.5, 1.5)
    handles, legend = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend, loc="lower center", ncols=4, bbox_to_anchor=(.5, .045), frameon=False)
    fig.suptitle("Codes livrés · remesure sur une allocation ROMEO commune", fontsize=15, weight="bold")
    fig.text(.5, .015, "Deux répétitions de recherche : résultat descriptif, sans preuve de supériorité générale du conseiller.",
             ha="center", fontsize=9, color="#555b65")
    fig.tight_layout(rect=(0, .13, 1, .93))
    for suffix in ("svg", "png"):
        fig.savefig(results / ("final-speedups." + suffix), dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
