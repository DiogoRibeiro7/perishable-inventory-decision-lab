import pandas as pd

from perishable_lab.forecasting.conformal import ConformalIntervalCalibrator


def test_conformal_calibration_expands_interval() -> None:
    target = pd.Series([0.0, 3.0, 8.0, 5.0])
    predictions = pd.DataFrame({"q10": [1.0, 2.0, 3.0, 4.0], "q90": [2.0, 4.0, 6.0, 6.0]})

    calibrator = ConformalIntervalCalibrator.fit(
        target, predictions, "q10", "q90", miscoverage=0.2
    )
    transformed = calibrator.transform(predictions)

    assert calibrator.adjustment >= 0.0
    assert (transformed["q10"] <= predictions["q10"]).all()
    assert (transformed["q90"] >= predictions["q90"]).all()
