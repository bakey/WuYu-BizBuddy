from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RetrieverConfig:
    pg_dsn: str = (
        "postgresql://postgres:"
        "cc4872ac7d93535a275b4c43822faca3"
        "@127.0.0.1:5440/gufei_vec"
    )
    model_path: str = "/data/models/bge-m3_20250912_235519m"
    device: str = "cpu"

    default_k: int = 10
    default_probes: int = 5
    preview_chars: int = 500

    rerank_model_path: str = ""
    mmr_lambda: float = 0.7
    rerank_top_k: int = 5

    cluster_centroids_path: str = "/data/gufei_vec/cluster_centroids.npy"
    cluster_labels_path: str = "/data/gufei_vec/cluster_labels.parquet"
    cluster_route_top_n: int = 3

    valid_subdirs: tuple[str, ...] = (
        "html_md",
        "pt_md",
        "arxiv_markdown",
        "MDS_md",
        "chemrxiv_md",
    )

    subdir_aliases: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "all": (
                "html_md",
                "pt_md",
                "arxiv_markdown",
                "MDS_md",
                "chemrxiv_md",
            ),
            "industrial": (
                "arxiv_markdown",
                "MDS_md",
                "chemrxiv_md",
            ),
            "policy": ("html_md", "pt_md"),
        }
    )
