def take_decision(recommendation):
    if not isinstance(recommendation, dict):
        return "SKIP"
    
    avg_volume_bool    = recommendation.get('avg_volume', False)
    iv30_rv30_bool     = recommendation.get('iv30_rv30', False)
    ts_slope_bool      = recommendation.get('ts_slope_0_45', False)

    if avg_volume_bool and iv30_rv30_bool and ts_slope_bool:
        return "RECOMMEND"
    else:
        return "SKIP"