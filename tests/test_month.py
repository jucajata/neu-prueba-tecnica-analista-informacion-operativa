from datetime import datetime

import pytest

from app.schemas import month_period


def test_month_is_a_half_open_range():
    period = month_period("2023-09")
    assert period.start == datetime(2023, 9, 1)
    assert period.end == datetime(2023, 10, 1)


def test_december_rolls_over_to_next_year():
    period = month_period("2023-12")
    assert period.start == datetime(2023, 12, 1)
    assert period.end == datetime(2024, 1, 1)


@pytest.mark.parametrize("value", ["2023-13", "2023-00", "2023-9", "23-09", "2023/09", "", "abc", "9999-12"])
def test_invalid_months_are_rejected(value):
    with pytest.raises(ValueError):
        month_period(value)
