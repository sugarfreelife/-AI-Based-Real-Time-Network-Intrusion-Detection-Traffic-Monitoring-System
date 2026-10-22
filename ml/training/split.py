"""Deterministic capture-group-separated train/validation/test splits."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.model_selection import GroupShuffleSplit

from ml.data.loader import DatasetBundle, DatasetValidationError


@dataclass(frozen=True, slots=True)
class DatasetSplit:
    train_indices: np.ndarray
    validation_indices: np.ndarray
    test_indices: np.ndarray
    train_group_count: int
    validation_group_count: int
    test_group_count: int


def split_by_capture_group(
    dataset: DatasetBundle,
    *,
    test_fraction: float = 0.2,
    validation_fraction: float = 0.2,
    random_seed: int = 42,
) -> DatasetSplit:
    if not 0 < test_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("split fractions must be between 0 and 1")
    if test_fraction + validation_fraction >= 1:
        raise ValueError("train, validation, and test fractions must leave a non-empty train split")
    if random_seed < 0:
        raise ValueError("random_seed must be non-negative")
    all_groups = dataset.capture_groups.to_numpy()
    unique_group_count = dataset.summary.capture_group_count
    if unique_group_count < 5:
        raise DatasetValidationError(
            f"at least 5 independent capture groups are required; found {unique_group_count}"
        )

    test_splitter = GroupShuffleSplit(n_splits=1, test_size=test_fraction, random_state=random_seed)
    train_validation_indices, test_indices = next(
        test_splitter.split(dataset.features, dataset.labels, groups=all_groups)
    )
    relative_validation_fraction = validation_fraction / (1.0 - test_fraction)
    validation_splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=relative_validation_fraction,
        random_state=random_seed + 1,
    )
    train_relative_indices, validation_relative_indices = next(
        validation_splitter.split(
            dataset.features.iloc[train_validation_indices],
            dataset.labels.iloc[train_validation_indices],
            groups=all_groups[train_validation_indices],
        )
    )
    train_indices = train_validation_indices[train_relative_indices]
    validation_indices = train_validation_indices[validation_relative_indices]

    train_groups = set(all_groups[train_indices])
    validation_groups = set(all_groups[validation_indices])
    test_groups = set(all_groups[test_indices])
    if train_groups & validation_groups or train_groups & test_groups or validation_groups & test_groups:
        raise DatasetValidationError("capture groups overlap across train, validation, and test splits")

    all_classes = set(dataset.labels.astype(str))
    for split_name, indices in (
        ("train", train_indices),
        ("validation", validation_indices),
        ("test", test_indices),
    ):
        present = set(dataset.labels.iloc[indices].astype(str))
        missing = sorted(all_classes - present)
        if missing:
            raise DatasetValidationError(
                f"{split_name} split is missing classes {missing}; add independent capture groups per class"
            )

    return DatasetSplit(
        train_indices=np.sort(train_indices),
        validation_indices=np.sort(validation_indices),
        test_indices=np.sort(test_indices),
        train_group_count=len(train_groups),
        validation_group_count=len(validation_groups),
        test_group_count=len(test_groups),
    )
