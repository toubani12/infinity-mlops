import numpy as np
import pytest

from data.validate import DataValidationError, validate


def checks(report) -> set[str]:
    return {issue.check for issue in report.errors}


def test_valid_frame_passes(frame) -> None:
    report = validate(frame)
    assert report.ok
    assert report.rows == 4_000
    assert report.frauds == 120
    assert report.to_dict()["fraud_rate"] == pytest.approx(0.03)


def test_missing_column_is_an_error(frame) -> None:
    with pytest.raises(DataValidationError) as raised:
        validate(frame.drop(columns=["v14"]))
    assert raised.value.report.errors[0].columns == ["v14"]


def test_missing_v_values_are_reported(frame) -> None:
    frame.loc[3, "v7"] = np.nan
    report = validate(frame, strict=False)
    assert checks(report) == {"missing_values"}
    assert report.errors[0].columns == ["v7"]


def test_negative_amount_and_bad_class(frame) -> None:
    frame.loc[0, "amount"] = -1.0
    frame.loc[1, "class"] = 2
    assert checks(validate(frame, strict=False)) == {"negative_amount", "invalid_class"}


def test_non_numeric_and_infinite(frame) -> None:
    frame["v3"] = frame["v3"].astype(str)
    frame.loc[0, "v5"] = np.inf
    assert checks(validate(frame, strict=False)) == {"dtypes", "infinite_values"}


def test_warnings_do_not_fail(frame) -> None:
    frame["extra"] = 1
    duplicated = frame.iloc[[0, 0]]
    report = validate(duplicated.assign(**{"class": 0}))
    assert report.ok
    assert {w.check for w in report.warnings} == {"columns", "duplicates", "class_balance"}


def test_empty_frame(frame) -> None:
    assert "rows" in checks(validate(frame.iloc[0:0], strict=False))
