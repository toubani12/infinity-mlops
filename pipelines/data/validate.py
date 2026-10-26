from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from data.schema import AMOUNT, RAW_COLUMNS, TARGET


@dataclass(frozen=True)
class Issue:
    check: str
    message: str
    columns: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    rows: int
    frauds: int
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def fraud_rate(self) -> float:
        return self.frauds / self.rows if self.rows else 0.0

    def to_dict(self) -> dict:
        return asdict(self) | {"ok": self.ok, "fraud_rate": self.fraud_rate}


class DataValidationError(ValueError):
    def __init__(self, report: ValidationReport) -> None:
        super().__init__("; ".join(issue.message for issue in report.errors))
        self.report = report


def _numeric(df: pd.DataFrame, column: str) -> bool:
    return is_numeric_dtype(df[column]) and not is_bool_dtype(df[column])


def _check_values(df: pd.DataFrame, numeric: list[str], errors: list[Issue]) -> None:
    nulls = [c for c in numeric if df[c].isna().any()]
    if nulls:
        errors.append(Issue("missing_values", f"missing values in {', '.join(nulls)}", nulls))
    infinite = [c for c in numeric if np.isinf(df[c].to_numpy(dtype=float)).any()]
    if infinite:
        errors.append(
            Issue("infinite_values", f"infinite values in {', '.join(infinite)}", infinite)
        )
    if AMOUNT in numeric and (df[AMOUNT] < 0).any():
        count = int((df[AMOUNT] < 0).sum())
        errors.append(Issue("negative_amount", f"{count} rows with negative amount", [AMOUNT]))
    if TARGET in numeric:
        invalid = df[TARGET].notna() & ~df[TARGET].isin([0, 1])
        if invalid.any():
            message = f"{int(invalid.sum())} rows with class outside {{0, 1}}"
            errors.append(Issue("invalid_class", message, [TARGET]))


def validate(df: pd.DataFrame, *, strict: bool = True) -> ValidationReport:
    """Check the normalized (lowercase) frame; raise DataValidationError on errors if strict."""
    errors: list[Issue] = []
    warnings: list[Issue] = []

    missing = [c for c in RAW_COLUMNS if c not in df.columns]
    if missing:
        errors.append(Issue("columns", f"missing columns: {', '.join(missing)}", missing))
    extra = [c for c in df.columns if c not in RAW_COLUMNS]
    if extra:
        warnings.append(Issue("columns", f"unexpected columns ignored: {', '.join(extra)}", extra))

    present = [c for c in RAW_COLUMNS if c in df.columns]
    non_numeric = [c for c in present if not _numeric(df, c)]
    if non_numeric:
        message = f"non-numeric dtype for {', '.join(non_numeric)}"
        errors.append(Issue("dtypes", message, non_numeric))
    if df.empty:
        errors.append(Issue("rows", "dataset is empty"))

    numeric = [c for c in present if c not in non_numeric]
    _check_values(df, numeric, errors)

    duplicates = int(df.duplicated(subset=present).sum()) if present else 0
    if duplicates:
        warnings.append(Issue("duplicates", f"{duplicates} duplicated rows"))
    frauds = int((df[TARGET] == 1).sum()) if TARGET in numeric else 0
    if TARGET in numeric and frauds == 0 and not df.empty:
        warnings.append(Issue("class_balance", "no fraud rows", [TARGET]))

    report = ValidationReport(rows=len(df), frauds=frauds, errors=errors, warnings=warnings)
    if strict and errors:
        raise DataValidationError(report)
    return report
