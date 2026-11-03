"""画面のない環境でも保存できる散布図。"""

from pathlib import Path


def scatter(frame, output):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    clean = frame[["motor_rate", "rank"]].dropna()
    clean = clean[clean["rank"].between(1, 6)]
    if clean.empty:
        raise ValueError("描画できるデータがありません")
    fig, ax = plt.subplots()
    ax.scatter(clean["motor_rate"], clean["rank"], alpha=0.5)
    ax.set(xlabel="Motor top-two rate (0–1)", ylabel="Finish rank", yticks=range(1, 7))
    ax.invert_yaxis()
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=150, bbox_inches="tight")
    plt.close(fig)
