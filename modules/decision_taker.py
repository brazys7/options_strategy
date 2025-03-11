def take_decision(recommendation):
    if not isinstance(recommendation, dict):
        return "SKIP"

    avg_volume_bool = recommendation.get("avg_volume", False)
    iv30_rv30_bool = recommendation.get("iv30_rv30", False)
    ts_slope_bool = recommendation.get("ts_slope_0_45", False)

    iv30_rv30_value = recommendation.get("iv30_rv30_value", 0)
    mispriced_expected_move = recommendation.get("mispriced_expected_move", 1)
    iv_percentile = recommendation.get("iv_percentile", 100)

    if avg_volume_bool and iv30_rv30_bool and ts_slope_bool:
        return "RECOMMEND"
    elif ts_slope_bool and (
        (avg_volume_bool and not iv30_rv30_bool)
        or (iv30_rv30_bool and not avg_volume_bool)
    ):
        return "CONSIDER"
    elif mispriced_expected_move < 0.8 and iv_percentile < 25 and iv30_rv30_value < 1.0:
        return "RECOMMEND_BUY"
    else:
        return "SKIP"
