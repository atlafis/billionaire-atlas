from billionaires.sources import monthly_sample


def test_monthly_sample_keeps_last_day_of_each_month_and_skips_junk():
    days = ["2020-01-03", "2020-01-19", "2020-02-29", "latest", "2020-02-01"]
    assert monthly_sample(days) == ["2020-01-19", "2020-02-29"]
