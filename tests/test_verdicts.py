"""Tests for src/verdicts.py. Hand-made small tables for every branch; test seeds 201+ only."""

from pathlib import Path

import pandas as pd
import pytest

from src import experiments, verdicts
from src.verdicts import INCONCLUSIVE, NOT_SUPPORTED, SUPPORTED

SEEDS = [201, 202, 203]
MODELS = {"A": "sequential", "B": "prefunded", "C": "atomic"}


# ------------------------------------------------------------ table builders

def make_rows(experiment: str, condition: str, *, failure=0.01, delay=60, multiplier=1.0,
              **per_model: dict[str, list[float]]) -> list[dict]:
    """Rows of one cell. per_model maps a metric name to {"A": [...per seed...], "B": [...], "C": [...]}."""
    rows = []
    for model_key, model in MODELS.items():
        for i, seed in enumerate(SEEDS):
            row = {"experiment": experiment, "condition": condition, "model": model, "seed": seed,
                   "failure_probability": failure, "delay_seconds": delay, "jpy_multiplier": multiplier,
                   "n_partial_insufficient_funds": 0, "principal_exposure_usd": 0.0,
                   "peak_liquidity_proxy_usd": 0.0, "success_rate": 1.0}
            for metric, values in per_model.items():
                if model_key in values:
                    row[metric] = values[model_key][i]
            rows.append(row)
    return rows


def frame(*cell_rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([r for rows in cell_rows for r in rows])


def verdict_of(table: pd.DataFrame, hypothesis: str, level: str = "overall") -> str:
    selected = table[(table["hypothesis"] == hypothesis) & (table["level"] == level)]
    assert len(selected) == 1
    return selected["verdict"].iloc[0]


def note_of(table: pd.DataFrame, hypothesis: str, level: str) -> str:
    return table[(table["hypothesis"] == hypothesis) & (table["level"] == level)]["note"].iloc[0]


# ------------------------------------------------------------ paired_verdict

def test_paired_all_predicted_sign_is_supported():
    assert verdicts.paired_verdict([1.0, 2.0, 3.0], +1) == SUPPORTED
    assert verdicts.paired_verdict([-1.0, -2.0, -3.0], -1) == SUPPORTED


def test_paired_mixed_signs_is_inconclusive():
    assert verdicts.paired_verdict([1.0, -2.0, 3.0], +1) == INCONCLUSIVE


def test_paired_some_zero_seeds_is_inconclusive():
    assert verdicts.paired_verdict([1.0, 0.0, 3.0], +1) == INCONCLUSIVE


def test_paired_all_zero_is_not_supported():
    assert verdicts.paired_verdict([0.0, 0.0, 0.0], +1) == NOT_SUPPORTED


def test_paired_opposite_sign_in_every_seed_is_not_supported():
    assert verdicts.paired_verdict([-1.0, -2.0, -3.0], +1) == NOT_SUPPORTED
    assert verdicts.paired_verdict([1.0, 2.0, 3.0], -1) == NOT_SUPPORTED


def test_paired_mean_zero_with_mixed_signs_is_inconclusive():
    assert verdicts.paired_verdict([1.0, -1.0, 0.0], +1) == INCONCLUSIVE


def test_paired_empty_is_inconclusive():
    assert verdicts.paired_verdict([], +1) == INCONCLUSIVE


def test_paired_non_directional():
    assert verdicts.paired_verdict([1.0, 2.0], None) == SUPPORTED
    assert verdicts.paired_verdict([-1.0, -2.0], None) == SUPPORTED  # no "opposite" case
    assert verdicts.paired_verdict([1.0, -2.0], None) == INCONCLUSIVE
    assert verdicts.paired_verdict([0.0, 0.0], None) == NOT_SUPPORTED
    assert verdicts.paired_verdict([0.0, 1.0], None) == INCONCLUSIVE


def test_clean_removes_float_noise_but_keeps_real_cents():
    assert verdicts.clean([1e-7, -3e-8, 0.01, -0.0]) == [0.0, 0.0, 0.01, 0.0]
    assert verdicts.sign_counts(verdicts.clean([1e-7, 0.01, -0.01])) == (1, 1, 1)


# ------------------------------------------------------------ H1b

def h1b_frame(levels: dict[float, dict[str, list[float]]]) -> pd.DataFrame:
    """levels: multiplier -> {"partial": A partial counts, "a": A exposure, "b": B exposure}."""
    cells = [make_rows("exp3_liquidity", "jpy_1", multiplier=1.0)]
    for multiplier, v in levels.items():
        cells.append(make_rows("exp3_liquidity", f"jpy_{multiplier:g}", multiplier=multiplier,
                               n_partial_insufficient_funds={"A": v["partial"]},
                               principal_exposure_usd={"A": v["a"], "B": v["b"]}))
    return frame(*cells)


def test_h1b_supported_when_b_lower_at_every_active_level():
    runs = h1b_frame({0.5: {"partial": [1, 2, 1], "a": [10, 20, 30], "b": [5, 5, 5]},
                      0.25: {"partial": [3, 3, 3], "a": [10, 20, 30], "b": [0, 0, 0]}})
    table = verdicts.h1b_rows(runs)
    out = pd.DataFrame(table)
    assert verdict_of(out, "H1b") == SUPPORTED
    assert set(out[out["level"] != "overall"]["role"]) == {"decides"}


def test_h1b_no_active_level_is_inconclusive_untestable():
    runs = h1b_frame({0.5: {"partial": [0, 0, 0], "a": [10, 20, 30], "b": [5, 5, 5]},
                      0.25: {"partial": [1, 0, 1], "a": [10, 20, 30], "b": [5, 5, 5]}})  # not in EVERY seed
    out = pd.DataFrame(verdicts.h1b_rows(runs))
    assert verdict_of(out, "H1b") == INCONCLUSIVE
    assert "untestable under the chosen grid" in note_of(out, "H1b", "overall")
    assert (out[out["level"] != "overall"]["verdict"] == "").all()


def test_h1b_mix_of_active_and_inactive_levels_counts_only_active():
    runs = h1b_frame({0.5: {"partial": [0, 0, 0], "a": [10, 20, 30], "b": [50, 50, 50]},  # inactive, B higher
                      0.25: {"partial": [2, 2, 2], "a": [10, 20, 30], "b": [5, 5, 5]}})  # active, supported
    out = pd.DataFrame(verdicts.h1b_rows(runs))
    assert verdict_of(out, "H1b") == SUPPORTED
    inactive = out[out["level"] == "jpy_0.5"].iloc[0]
    assert inactive["role"] == "descriptive" and inactive["verdict"] == ""
    assert "not informative" in inactive["note"]


def test_h1b_not_supported_when_b_equal_or_higher_everywhere():
    runs = h1b_frame({0.5: {"partial": [1, 1, 1], "a": [10, 20, 30], "b": [10, 20, 30]},  # identical
                      0.25: {"partial": [1, 1, 1], "a": [10, 20, 30], "b": [10, 25, 40]}})  # equal or higher
    out = pd.DataFrame(verdicts.h1b_rows(runs))
    assert verdict_of(out, "H1b") == NOT_SUPPORTED


def test_h1b_inconclusive_when_levels_disagree_or_mixed():
    runs = h1b_frame({0.5: {"partial": [1, 1, 1], "a": [10, 20, 30], "b": [5, 5, 5]},  # supported
                      0.25: {"partial": [1, 1, 1], "a": [10, 20, 30], "b": [10, 20, 30]}})  # identical
    assert verdict_of(pd.DataFrame(verdicts.h1b_rows(runs)), "H1b") == INCONCLUSIVE
    mixed = h1b_frame({0.5: {"partial": [1, 1, 1], "a": [10, 20, 30], "b": [5, 25, 5]}})
    assert verdict_of(pd.DataFrame(verdicts.h1b_rows(mixed)), "H1b") == INCONCLUSIVE


# ------------------------------------------------------------ H2

def h2_frame(a_by_delay: dict[int, list[float]], b_by_delay: dict[int, list[float]]) -> pd.DataFrame:
    """Peak proxy per delay. 0 and 300 are exp4_delay cells; 60 lives in exp4_failure (shared)."""
    cells = [
        make_rows("exp4_delay", "delay_0", delay=0, peak_liquidity_proxy_usd={"A": a_by_delay[0], "B": b_by_delay[0]}),
        make_rows("exp4_delay", "delay_300", delay=300,
                  peak_liquidity_proxy_usd={"A": a_by_delay[300], "B": b_by_delay[300]}),
        make_rows("exp4_failure", "failure_0.01", delay=60,
                  peak_liquidity_proxy_usd={"A": a_by_delay[60], "B": b_by_delay[60]}),
    ]
    return frame(*cells)


def test_h2_supported_and_finds_shared_60s_cell():
    runs = h2_frame({0: [100, 100, 100], 60: [100, 100, 100], 300: [100, 100, 100]},
                    {0: [100, 100, 100], 60: [110, 110, 110], 300: [150, 160, 170]})
    out = pd.DataFrame(verdicts.h2_rows(runs))
    assert verdict_of(out, "H2") == SUPPORTED
    sixty = out[out["level"] == "gap_delay_60"].iloc[0]  # read from exp4_failure/failure_0.01
    assert sixty["mean_diff"] == 10 and sixty["role"] == "descriptive"


def test_h2_not_supported_when_gap_never_changes():
    runs = h2_frame({d: [100, 100, 100] for d in (0, 60, 300)}, {d: [120, 130, 140] for d in (0, 60, 300)})
    assert verdict_of(pd.DataFrame(verdicts.h2_rows(runs)), "H2") == NOT_SUPPORTED


def test_h2_not_supported_when_gap_shrinks_in_every_seed():
    runs = h2_frame({d: [100, 100, 100] for d in (0, 60, 300)},
                    {0: [150, 150, 150], 60: [140, 140, 140], 300: [120, 130, 140]})
    assert verdict_of(pd.DataFrame(verdicts.h2_rows(runs)), "H2") == NOT_SUPPORTED


def test_h2_inconclusive_when_mixed():
    runs = h2_frame({d: [100, 100, 100] for d in (0, 60, 300)},
                    {0: [100, 100, 100], 60: [100, 100, 100], 300: [150, 90, 100]})
    assert verdict_of(pd.DataFrame(verdicts.h2_rows(runs)), "H2") == INCONCLUSIVE


# ------------------------------------------------------------ H4a

def h4a_frame(success: dict[float, dict[str, list[float]]]) -> pd.DataFrame:
    """success: multiplier -> {"A": rates, "C": rates}; multiplier 1.0 is the baseline."""
    return frame(*[make_rows("exp3_liquidity", f"jpy_{m:g}", multiplier=m, success_rate=v)
                   for m, v in success.items()])


BASE = {"A": [1.0, 1.0, 1.0], "B": [1.0, 1.0, 1.0], "C": [1.0, 1.0, 1.0]}


def test_h4a_supported_same_sign_at_highest_stress_no_reversal():
    # change_A - change_C: A loses more success (negative) at both stress levels.
    runs = h4a_frame({1.0: BASE,
                      0.5: {"A": [0.9] * 3, "C": [0.95] * 3},
                      0.25: {"A": [0.5, 0.6, 0.5], "C": [0.8] * 3}})
    out = pd.DataFrame(verdicts.h4a_rows(runs))
    assert verdict_of(out, "H4a") == SUPPORTED
    assert "negative" in note_of(out, "H4a", "overall")
    assert out[out["level"] == "jpy_0.5"]["role"].iloc[0] == "direction_check"
    assert out[out["level"] == "jpy_0.25"]["role"].iloc[0] == "decides"


def test_h4a_not_supported_when_a_and_c_identical_at_highest_stress():
    runs = h4a_frame({1.0: BASE,
                      0.5: {"A": [0.9] * 3, "C": [0.95] * 3},  # a difference at a milder level does not matter
                      0.25: {"A": [0.7] * 3, "C": [0.7] * 3}})
    assert verdict_of(pd.DataFrame(verdicts.h4a_rows(runs)), "H4a") == NOT_SUPPORTED


def test_h4a_inconclusive_when_signs_mixed_at_highest_stress():
    runs = h4a_frame({1.0: BASE, 0.25: {"A": [0.5, 0.9, 0.5], "C": [0.7, 0.7, 0.7]}})
    assert verdict_of(pd.DataFrame(verdicts.h4a_rows(runs)), "H4a") == INCONCLUSIVE


def test_h4a_reversal_at_milder_level_is_inconclusive():
    runs = h4a_frame({1.0: BASE,
                      0.5: {"A": [1.0] * 3, "C": [0.9] * 3},  # A minus C positive: opposite of the top level
                      0.25: {"A": [0.5] * 3, "C": [0.8] * 3}})
    out = pd.DataFrame(verdicts.h4a_rows(runs))
    assert verdict_of(out, "H4a") == INCONCLUSIVE
    assert "reversal" in note_of(out, "H4a", "overall")


def test_h4a_mean_exactly_zero_at_milder_level_is_not_a_reversal():
    runs = h4a_frame({1.0: BASE,
                      0.5: {"A": [0.9, 1.0, 0.95], "C": [1.0, 0.9, 0.95]},  # diffs -0.1, +0.1, 0 -> mean 0
                      0.25: {"A": [0.5] * 3, "C": [0.8] * 3}})
    out = pd.DataFrame(verdicts.h4a_rows(runs))
    assert verdict_of(out, "H4a") == SUPPORTED
    assert "not a reversal" in note_of(out, "H4a", "jpy_0.5")


def test_h4a_highest_stress_is_the_lowest_multiplier_whatever_the_row_order():
    runs = h4a_frame({0.25: {"A": [0.5] * 3, "C": [0.8] * 3}, 1.0: BASE, 0.5: {"A": [0.9] * 3, "C": [0.95] * 3}})
    out = pd.DataFrame(verdicts.h4a_rows(runs))
    assert out[out["role"] == "decides"]["level"].tolist() == ["jpy_0.25"]


# ------------------------------------------------------------ H4b

def h4b_frame(exposure: dict[int, dict[str, list[float]]], partial: list[int]) -> pd.DataFrame:
    """exposure: delay -> {"A": ..., "B": ...}; partial: A's insufficient_funds partial per seed (all delays)."""
    return frame(*[make_rows("exp4_h4b", f"h4b_delay_{d}", delay=d, multiplier=0.1,
                             principal_exposure_usd=v, n_partial_insufficient_funds={"A": partial})
                   for d, v in exposure.items()])


def test_h4b_untestable_without_a_partial_insufficient_funds():
    runs = h4b_frame({0: {"A": [0] * 3, "B": [0] * 3}, 60: {"A": [5] * 3, "B": [0] * 3},
                      300: {"A": [9] * 3, "B": [0] * 3}}, partial=[0, 0, 0])
    out = pd.DataFrame(verdicts.h4b_rows(runs))
    assert verdict_of(out, "H4b") == INCONCLUSIVE
    assert "untestable" in note_of(out, "H4b", "overall")
    assert verdict_of(out, "H4b", "h4b_cells") == INCONCLUSIVE
    assert set(out[out["level"].isin(["delay_300", "delay_60"])]["verdict"]) == {""}  # not decided


def test_h4b_active_check_needs_only_some_seed():
    runs = h4b_frame({0: {"A": [0] * 3, "B": [0] * 3}, 60: {"A": [5] * 3, "B": [0] * 3},
                      300: {"A": [9, 8, 7], "B": [0] * 3}}, partial=[0, 1, 0])
    out = pd.DataFrame(verdicts.h4b_rows(runs))
    assert verdict_of(out, "H4b", "h4b_cells") == ""  # check passed
    assert verdict_of(out, "H4b") == SUPPORTED  # A change - B change positive in every seed at 300 s


def test_h4b_not_supported_when_a_and_b_changes_are_identical_at_300s():
    runs = h4b_frame({0: {"A": [1, 2, 3], "B": [1, 2, 3]}, 60: {"A": [4, 4, 4], "B": [1, 2, 3]},
                      300: {"A": [6, 7, 8], "B": [6, 7, 8]}}, partial=[1, 1, 1])
    assert verdict_of(pd.DataFrame(verdicts.h4b_rows(runs)), "H4b") == NOT_SUPPORTED


def test_h4b_reversal_at_60s_is_inconclusive():
    runs = h4b_frame({0: {"A": [0] * 3, "B": [0] * 3}, 60: {"A": [0] * 3, "B": [10] * 3},
                      300: {"A": [9] * 3, "B": [0] * 3}}, partial=[1, 1, 1])
    out = pd.DataFrame(verdicts.h4b_rows(runs))
    assert verdict_of(out, "H4b") == INCONCLUSIVE
    assert out[out["level"] == "delay_60"]["role"].iloc[0] == "direction_check"


def test_h4b_mixed_signs_at_300s_is_inconclusive():
    runs = h4b_frame({0: {"A": [0] * 3, "B": [0] * 3}, 60: {"A": [0] * 3, "B": [0] * 3},
                      300: {"A": [9, 0, 9], "B": [0, 5, 0]}}, partial=[1, 1, 1])
    assert verdict_of(pd.DataFrame(verdicts.h4b_rows(runs)), "H4b") == INCONCLUSIVE


def test_h4b_without_cells_is_inconclusive():
    out = pd.DataFrame(verdicts.h4b_rows(make_frame_without_h4b()))
    assert verdict_of(out, "H4b") == INCONCLUSIVE


def make_frame_without_h4b() -> pd.DataFrame:
    return frame(make_rows("exp3_liquidity", "jpy_1"))


# ------------------------------------------------------------ H1a

def test_h1a_is_descriptive_without_verdict():
    cells = [make_rows("exp4_failure", f"failure_{p:g}", failure=p,
                       principal_exposure_usd={"A": [p * 100 + i for i in range(3)], "B": [p * 100] * 3})
             for p in (0.0, 0.01, 0.05)]
    out = pd.DataFrame(verdicts.h1a_rows(frame(*cells)))
    assert (out["verdict"] == "").all()
    assert len(out) == 3 * 2 + 1
    a_5 = out[(out["level"] == "failure_0.05") & (out["model"] == "sequential")].iloc[0]
    assert (a_5["value_mean"], a_5["value_min"], a_5["value_max"]) == (6.0, 5.0, 7.0)


# ------------------------------------------------------------ table, files, integration

def test_columns_and_allowed_verdicts_on_a_hand_made_table():
    runs = full_runs()
    table = verdicts.build_verdicts(runs)
    assert list(table.columns) == verdicts.COLUMNS
    overall = table[table["role"] == "overall"]
    assert overall["hypothesis"].tolist() == ["H1a", "H1b", "H2", "H4a", "H4b"]
    assert set(overall["verdict"]) <= {"", *verdicts.VERDICTS}
    assert set(table["role"]) <= {"decides", "direction_check", "descriptive", "active_check", "overall"}


def test_verdicts_main_refuses_overwrite_and_missing_input(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        verdicts.main(results_dir=tmp_path)
    (tmp_path / "verdicts.csv").write_text("x\n")
    with pytest.raises(FileExistsError):
        verdicts.main(results_dir=tmp_path)
    assert (tmp_path / "verdicts.csv").read_text() == "x\n"


def test_verdicts_cli_exit_codes(monkeypatch):
    monkeypatch.setattr(verdicts, "main", lambda **kw: (_ for _ in ()).throw(FileExistsError("x")))
    assert verdicts.cli([]) == 1
    seen = {}
    monkeypatch.setattr(verdicts, "main", lambda **kw: seen.update(kw))
    assert verdicts.cli(["--force"]) == 0
    assert seen == {"force": True}


def test_integration_stress_run_then_verdicts(tmp_path, monkeypatch):
    """Run the real stress runner on 2 test seeds, then the verdicts on its output."""
    monkeypatch.setattr(experiments, "git_version", lambda: "abc123")
    pd.DataFrame([{"status": "ok", "ample_reached": True, "reference_usd": 100_000_000,
                   "reference_jpy": 15_000_000_000, "lower_multipliers": "0.09375 0.0625 0.03125 0.0125",
                   "h4b_multiplier": 0.09375, "h4b_testable": True}]).to_csv(tmp_path / "calibration.csv", index=False)
    experiments.main(results_dir=tmp_path, seeds=[201, 202], count=100)
    experiments.main_stress(results_dir=tmp_path, seeds=[201, 202], count=100)
    table = verdicts.main(results_dir=tmp_path)
    written = pd.read_csv(tmp_path / "verdicts.csv", keep_default_na=False)
    assert len(written) == len(table)
    assert set(written["verdict"]) <= {"", "supported", "not supported", "inconclusive"}
    overall = written[written["role"] == "overall"]
    assert overall["hypothesis"].tolist() == ["H1a", "H1b", "H2", "H4a", "H4b"]
    assert overall[overall["hypothesis"] != "H1a"]["verdict"].isin(verdicts.VERDICTS).all()
    assert (written["n_seeds"].replace("", 2).astype(int).isin([0, 2])).all()


# ====================================================================== review fixes

def h4a_two_levels(top_a, top_c, mild_a, mild_c, base=1.0):
    """H4a frame with baseline `base` for A and C, a highest-stress level 0.25 and a milder level 0.5."""
    flat = {"A": [base] * 3, "B": [base] * 3, "C": [base] * 3}
    return h4a_frame({1.0: flat, 0.5: {"A": mild_a, "C": mild_c}, 0.25: {"A": top_a, "C": top_c}})


# ---- exact zero mean

def test_mean_sign_and_mean_of_are_exact_for_float_residue():
    diffs = verdicts.clean([0.1, 0.2, -0.3])
    assert sum(diffs) / 3 != 0  # the plain float mean really has a residue
    assert verdicts.mean_sign(diffs) == 0
    assert verdicts.mean_of(diffs) == 0.0 and str(verdicts.mean_of(diffs)) == "0.0"
    grid = verdicts.clean([0.002, 0.004, -0.006])
    assert verdicts.mean_sign(grid) == 0 and verdicts.mean_of(grid) == 0.0
    assert verdicts.mean_sign(verdicts.clean([0.01, -0.02])) == -1
    assert verdicts.mean_of(verdicts.clean([0.002, 0.004])) == 0.003
    assert verdicts.mean_of([]) != verdicts.mean_of([])  # NaN


def test_paired_verdict_with_float_residue_zero_sum_is_inconclusive():
    for predicted in (+1, -1, None):
        assert verdicts.paired_verdict(verdicts.clean([0.1, 0.2, -0.3]), predicted) == INCONCLUSIVE


def test_random_zero_sum_sets_always_have_mean_sign_zero():
    import random

    rng = random.Random(7)  # local generator, not simulation randomness
    for _ in range(300):
        values = [rng.randint(-40, 40) * 0.002 for _ in range(5)]
        values.append(-sum(round(v / 0.002) for v in values) * 0.002)
        assert verdicts.mean_sign(verdicts.clean(values)) == 0


@pytest.mark.parametrize("mild_a, mild_c", [
    ([1.25, 0.75, 1.0], [1.0] * 3),  # exact zero-sum (+0.25, -0.25, 0)
    ([1.1, 1.2, 0.7], [1.0] * 3),  # float residue (0.1, 0.2, -0.3)
    ([1.002, 1.004, 0.994], [1.0] * 3),  # success-rate grid (+0.002, +0.004, -0.006)
])
@pytest.mark.parametrize("top_sign", [+1, -1])
def test_h4a_zero_mean_at_milder_level_is_not_a_reversal_for_either_top_sign(mild_a, mild_c, top_sign):
    # A minus C at the highest stress: +0.2 (A loses less) or -0.2 (A loses more).
    top_a, top_c = ([1.0] * 3, [0.8] * 3) if top_sign > 0 else ([0.8] * 3, [1.0] * 3)
    out = pd.DataFrame(verdicts.h4a_rows(h4a_two_levels(top_a, top_c, mild_a, mild_c)))
    assert verdict_of(out, "H4a") == SUPPORTED
    assert "not a reversal" in note_of(out, "H4a", "jpy_0.5")
    assert out[out["level"] == "jpy_0.5"]["mean_diff"].iloc[0] == 0.0


def test_h4a_real_reversal_still_detected_with_positive_top():
    out = pd.DataFrame(verdicts.h4a_rows(h4a_two_levels([1.0] * 3, [0.8] * 3, [0.8] * 3, [1.0] * 3)))
    assert verdict_of(out, "H4a") == INCONCLUSIVE and "reversal" in note_of(out, "H4a", "overall")


# ---- H4b direction pin

def test_h4b_delay_300_diff_is_change_a_minus_change_b():
    zero = {"A": [0] * 3, "B": [0] * 3}
    runs = h4b_frame({0: zero, 60: zero, 300: {"A": [9, 8, 7], "B": [1, 1, 1]}}, [1, 1, 1])
    out = pd.DataFrame(verdicts.h4b_rows(runs))
    row300 = out[out["level"] == "delay_300"].iloc[0]
    assert row300["mean_diff"] == 7.0  # (9-1, 8-1, 7-1) mean = 7: A minus B, positive when A's exposure grows more
    swapped = h4b_frame({0: zero, 60: zero, 300: {"A": [1, 1, 1], "B": [9, 8, 7]}}, [1, 1, 1])
    assert pd.DataFrame(verdicts.h4b_rows(swapped)).query("level == 'delay_300'")["mean_diff"].iloc[0] == -7.0


# ---- ample violation, provenance

def full_runs(commit: str = "abc123") -> pd.DataFrame:
    """A small input with every experiment, ample_cell, n_insufficient_funds and git_commit columns."""
    runs = frame(
        h1b_frame({0.5: {"partial": [1, 1, 1], "a": [10, 20, 30], "b": [5, 5, 5]}}).to_dict("records"),
        h2_frame({d: [100] * 3 for d in (0, 60, 300)}, {0: [100] * 3, 60: [100] * 3, 300: [150] * 3}).to_dict("records"),
        h4a_frame({0.25: {"A": [0.5] * 3, "C": [0.8] * 3}}).to_dict("records"),
        h4b_frame({0: {"A": [0] * 3, "B": [0] * 3}, 60: {"A": [0] * 3, "B": [0] * 3},
                   300: {"A": [9] * 3, "B": [0] * 3}}, [1, 1, 1]).to_dict("records"),
        make_rows("exp4_failure", "failure_0", failure=0.0),
    )
    runs["ample_cell"] = ~runs["experiment"].eq("exp4_h4b") & runs["jpy_multiplier"].eq(1.0)
    runs["n_insufficient_funds"] = 0
    runs["git_commit"] = commit
    return runs


def set_insufficient(runs: pd.DataFrame, condition: str, value: int = 2) -> pd.DataFrame:
    out = runs.copy()
    out.loc[out["condition"] == condition, "n_insufficient_funds"] = value
    return out


def overall_of(table: pd.DataFrame, hypothesis: str) -> pd.Series:
    return table[(table["hypothesis"] == hypothesis) & (table["role"] == "overall")].iloc[0]


def test_clean_input_has_verdicts_and_no_ample_check_row():
    table = verdicts.build_verdicts(full_runs())
    assert "ample_check" not in set(table["hypothesis"])
    assert overall_of(table, "H1b")["verdict"] == SUPPORTED and overall_of(table, "H2")["verdict"] == SUPPORTED


def test_ample_violation_withholds_every_verdict(capsys):
    table = verdicts.build_verdicts(set_insufficient(full_runs(), "delay_300"))
    assert "WARNING: ample violated" in capsys.readouterr().out
    for hypothesis in ("H1a", "H1b", "H2", "H4a", "H4b"):
        assert overall_of(table, hypothesis)["verdict"] == ""
        assert overall_of(table, hypothesis)["note"] == verdicts.AMPLE_WITHHELD_NOTE
        rows = table[table["hypothesis"] == hypothesis]
        assert (rows[rows["role"] == "decides"]["verdict"] == "").all()
    assert (table["verdict"] == "").all()  # nothing at all is decided
    check = table[table["hypothesis"] == "ample_check"]
    assert len(check) == 1 and "delay_300" in check["note"].iloc[0] and check["verdict"].iloc[0] == ""


def test_ample_violation_in_the_jpy_1_reference_withholds_too(capsys):
    table = verdicts.build_verdicts(set_insufficient(full_runs(), "jpy_1"))
    assert overall_of(table, "H4a")["verdict"] == "" and overall_of(table, "H1b")["verdict"] == ""


def test_insufficient_funds_in_a_non_ample_cell_is_not_an_ample_violation():
    table = verdicts.build_verdicts(set_insufficient(full_runs(), "jpy_0.5"))
    assert "ample_check" not in set(table["hypothesis"])
    assert overall_of(table, "H1b")["verdict"] == SUPPORTED


def test_ample_violations_helper_requires_columns_and_handles_string_flags():
    for column in ("ample_cell", "n_insufficient_funds"):
        with pytest.raises(ValueError, match=column):
            verdicts.ample_violations(full_runs().drop(columns=[column]))
    with pytest.raises(ValueError, match="ample_cell"):
        verdicts.build_verdicts(full_runs().drop(columns=["ample_cell"]))
    runs = set_insufficient(full_runs(), "delay_0")
    runs["ample_cell"] = runs["ample_cell"].astype(str)  # as read back from CSV text
    assert len(verdicts.ample_violations(runs)) == 9  # 3 models x 3 seeds


def test_provenance_columns_and_seed_warning(capsys):
    table = verdicts.build_verdicts(full_runs("deadbee"))
    assert set(table["git_commit"]) == {"deadbee"} and set(table["seeds"]) == {"201-203"}
    assert "not exactly 1-30" in capsys.readouterr().out
    check = table[table["hypothesis"] == "input_check"].iloc[0]
    assert "not exactly 1-30" in check["note"] and "201-203" in check["note"]


def test_exactly_main_seeds_gives_no_warning(capsys):
    base = full_runs()
    base = base[base["seed"] == 201]  # one seed copied to seeds 1-30
    runs = pd.concat([base.assign(seed=s) for s in range(1, 31)], ignore_index=True)
    table = verdicts.build_verdicts(runs)
    assert "WARNING" not in capsys.readouterr().out
    assert set(table["seeds"]) == {"1-30"}
    assert table[table["hypothesis"] == "input_check"]["note"].iloc[0] == "seeds are exactly 1-30"


def test_more_than_one_git_commit_is_refused(tmp_path):
    runs = full_runs()
    runs.loc[runs.index[0], "git_commit"] = "other"
    with pytest.raises(ValueError, match="more than one git_commit"):
        verdicts.build_verdicts(runs)
    runs.to_csv(tmp_path / "stress_run_metrics.csv", index=False)
    with pytest.raises(ValueError, match="git_commit"):
        verdicts.main(results_dir=tmp_path)
    assert not (tmp_path / "verdicts.csv").exists()


def test_seeds_text():
    assert verdicts.seeds_text([3, 1, 2]) == "1-3"
    assert verdicts.seeds_text([1, 3]) == "1,3"


def test_dirty_git_commit_gives_warning_and_note_but_no_refusal(capsys):
    table = verdicts.build_verdicts(full_runs("abc123-dirty"))
    assert "dirty" in capsys.readouterr().out
    assert "dirty" in table[table["hypothesis"] == "input_check"]["note"].iloc[0]
    assert overall_of(table, "H1b")["verdict"] == SUPPORTED
    clean = verdicts.build_verdicts(full_runs("abc123"))
    assert "dirty" not in clean[clean["hypothesis"] == "input_check"]["note"].iloc[0]


# ====================================================================== H3 (Day 13)
# L*, range rule and h3_rows on hand-made tables; seeds 201+ only.

GRID = [0.25, 0.5, 1.0]  # small grid: rank 0 = 0.25, 1 = 0.5, 2 = 1, 3 = not reached


def test_lstar_exact_95_percent_boundary():
    assert verdicts.lstar({1.0: (95, 100)}) == (0, "1")  # 95/100 qualifies
    assert verdicts.lstar({1.0: (94, 100)}) == (1, "not_reached")  # 94/100 does not


def test_lstar_all_levels_qualify_gives_lowest_level():
    levels = {1.0: (100, 100), 0.5: (97, 100), 0.25: (95, 100)}
    assert verdicts.lstar(levels) == (0, "0.25")


def test_lstar_non_monotone_is_above_the_failing_level():
    # 0.25 qualifies, but 0.5 fails, so L* is the top level 1 (not 0.25).
    levels = {1.0: (100, 100), 0.5: (50, 100), 0.25: (100, 100)}
    assert verdicts.lstar(levels) == (2, "1")


def test_lstar_top_level_fails_is_not_reached():
    levels = {1.0: (90, 100), 0.5: (100, 100), 0.25: (100, 100)}
    assert verdicts.lstar(levels) == (3, "not_reached")


def test_lstar_text_uses_the_multiplier():
    assert verdicts.lstar({1.0: (100, 100), 0.0625: (100, 100)})[1] == "0.0625"


def rv(low: list[int], high: list[int]) -> tuple[str, str]:
    """range_verdict on a 5-level grid: lowest rank 0, not reached rank 5."""
    seeds = range(201, 201 + len(low))
    return verdicts.range_verdict(dict(zip(seeds, low)), dict(zip(seeds, high)), 0, 5)


def test_range_censored_at_lowest_level_is_inconclusive():
    assert rv([2, 0, 2], [3, 3, 3]) == (INCONCLUSIVE, "censored")
    assert rv([2, 2, 2], [3, 0, 3]) == (INCONCLUSIVE, "censored")


def test_range_censored_not_reached_is_inconclusive():
    assert rv([2, 2, 2], [4, 5, 4]) == (INCONCLUSIVE, "censored")


def test_range_censored_beats_otherwise_supported_and_identical():
    assert rv([1, 1, 1], [0, 3, 3])[0] == INCONCLUSIVE  # disjoint, but one seed censored
    assert rv([5, 5, 5], [5, 5, 5])[0] == INCONCLUSIVE  # identical, but censored: never not supported


def test_range_touching_is_inconclusive():
    assert rv([1, 2, 1], [2, 3, 3])[0] == INCONCLUSIVE  # [1,2] and [2,3] touch


def test_range_disjoint_is_supported_in_both_directions():
    assert rv([1, 1, 2], [3, 4, 3])[0] == SUPPORTED
    assert rv([3, 4, 3], [1, 1, 2])[0] == SUPPORTED


def test_range_identical_per_seed_is_not_supported():
    assert rv([1, 2, 3], [1, 2, 3])[0] == NOT_SUPPORTED


def test_range_same_multiset_but_different_per_seed_is_inconclusive():
    assert rv([1, 2, 3], [3, 2, 1])[0] == INCONCLUSIVE


def test_range_mismatched_seed_sets_raise():
    with pytest.raises(ValueError, match="same seeds"):
        verdicts.range_verdict({201: 1, 202: 2}, {201: 1, 203: 2}, 0, 5)


def h3_frame(ranks: dict[tuple[str, str], list[int]] | None = None, default: int = 2) -> pd.DataFrame:
    """Runs table for the 6 cells x 3 models x 3 seeds on GRID. `ranks` sets L* rank per cell and seed."""
    ranks = ranks or {}
    cells = [("baseline", "baseline"), ("volume", "100"), ("volume", "1000"),
             ("banks", "5"), ("banks", "10"), ("arrival", "burst")]  # fmt: skip
    rows = []
    for factor, level in cells:
        for model in MODELS.values():
            for i, seed in enumerate(SEEDS):
                rank = ranks.get((factor, level), [default] * len(SEEDS))[i]
                for index, m in enumerate(GRID):
                    rows.append({"factor": factor, "factor_level": level, "model": model, "seed": seed,
                                 "jpy_multiplier": m, "n_total": 100, "n_settled": 100 if index >= rank else 0,
                                 "ample_cell": m == 1.0, "n_insufficient_funds": 0, "git_commit": "abc123"})
    return pd.DataFrame(rows)


def test_lstar_table_columns_and_rows():
    table = verdicts.lstar_table(h3_frame({("banks", "10"): [1, 2, 3]}))
    assert list(table.columns) == verdicts.LSTAR_COLUMNS
    assert len(table) == 6 * 3 * len(SEEDS)
    part = table[(table["level"] == "10") & (table["model"] == "atomic")].sort_values("seed")
    assert part["lstar"].tolist() == ["0.5", "1", "not_reached"]
    assert part["not_reached"].tolist() == [False, False, True]
    assert table[(table["level"] == "baseline")]["censored_low"].eq(False).all()


def test_lstar_table_missing_grid_level_is_an_error():
    runs = h3_frame()
    runs = runs.drop(runs[(runs["factor"] == "volume") & (runs["factor_level"] == "100")
                          & (runs["model"] == "atomic") & (runs["seed"] == 201)
                          & (runs["jpy_multiplier"] == 0.5)].index)
    with pytest.raises(ValueError, match="grid levels missing"):
        verdicts.lstar_table(runs)


def test_h3_rows_has_nine_rows_with_factor_and_model():
    rows = verdicts.h3_rows(h3_frame())
    assert len(rows) == 9
    assert [(r["factor"], r["model"]) for r in rows] == [
        (f, m) for f in ("volume", "banks", "arrival") for m in ("sequential", "prefunded", "atomic")]
    assert all(r["hypothesis"] == "H3" and r["n_seeds"] == 3 for r in rows)


def h3_by_factor(rows: list[dict]) -> dict[str, dict]:
    return {r["factor"]: r for r in rows if r["model"] == "atomic"}


def test_h3_low_high_cell_mapping_banks_only_differs():
    # Only banks 10 differs from the baseline cell (2 banks): L* rank 1 vs 2 in every seed (disjoint, uncensored).
    # The 5-bank cell is set to something else to prove it is not used.
    rows = verdicts.h3_rows(h3_frame({("banks", "10"): [1, 1, 1], ("banks", "5"): [2, 2, 2]}, default=2))
    by = h3_by_factor(rows)
    assert by["banks"]["verdict"] == SUPPORTED
    assert (by["banks"]["low_level"], by["banks"]["high_level"]) == ("2", "10")
    assert (by["banks"]["low_min"], by["banks"]["high_max"]) == ("1", "0.5")
    assert by["volume"]["verdict"] == NOT_SUPPORTED and by["arrival"]["verdict"] == NOT_SUPPORTED
    assert by["banks"]["n_seeds_equal"] == 0 and by["volume"]["n_seeds_equal"] == 3


def test_h3_low_high_cell_mapping_volume_and_arrival():
    ranks = {("volume", "100"): [2, 2, 2], ("volume", "1000"): [1, 1, 1],
             ("arrival", "burst"): [1, 1, 1], ("baseline", "baseline"): [2, 2, 2]}  # fmt: skip
    by = h3_by_factor(verdicts.h3_rows(h3_frame(ranks)))
    assert by["volume"]["verdict"] == SUPPORTED
    assert (by["volume"]["low_level"], by["volume"]["high_level"]) == ("100", "1000")
    assert by["arrival"]["verdict"] == SUPPORTED
    assert (by["arrival"]["low_level"], by["arrival"]["high_level"]) == ("sequential", "burst")
    assert by["banks"]["verdict"] == NOT_SUPPORTED  # banks 10 stays at default rank 2 = baseline rank


def test_h3_censored_row_is_flagged():
    rows = verdicts.h3_rows(h3_frame({("volume", "1000"): [0, 1, 1]}))
    row = h3_by_factor(rows)["volume"]
    assert row["verdict"] == INCONCLUSIVE and row["censored"] is True and row["note"] == "censored"


def test_h3_ample_violation_withholds_every_verdict():
    runs = h3_frame({("banks", "10"): [1, 1, 1]})
    runs.loc[(runs["jpy_multiplier"] == 1.0) & (runs["factor"] == "volume"), "n_insufficient_funds"] = 1
    rows = verdicts.h3_rows(runs)
    assert len(rows) == 9
    assert all(r["verdict"] == "" and r["note"] == verdicts.AMPLE_WITHHELD_NOTE for r in rows)


def test_build_h3_provenance_and_seed_warning(capsys):
    table = verdicts.build_h3(h3_frame())
    assert list(table.columns) == verdicts.H3_COLUMNS
    assert (table["git_commit"] == "abc123").all() and (table["seeds"] == "201-203").all()
    assert "not exactly 1-30" in capsys.readouterr().out
    assert table[table["hypothesis"] == "input_check"]["note"].iloc[0].startswith("WARNING")


def test_build_h3_dirty_commit_warning(capsys):
    runs = h3_frame()
    runs["git_commit"] = "abc123-dirty"
    table = verdicts.build_h3(runs)
    assert "dirty" in capsys.readouterr().out
    assert "dirty" in table[table["hypothesis"] == "input_check"]["note"].iloc[0]


def test_h3_main_writes_files_and_refuses_overwrite(tmp_path):
    h3_frame().to_csv(tmp_path / "sensitivity_run_metrics.csv", index=False)
    verdicts.main_h3(results_dir=tmp_path)
    assert (tmp_path / "lstar_by_seed.csv").exists() and (tmp_path / "h3_verdicts.csv").exists()
    with pytest.raises(FileExistsError):
        verdicts.main_h3(results_dir=tmp_path)
    verdicts.main_h3(results_dir=tmp_path, force=True)


def test_h3_main_missing_input(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        verdicts.main_h3(results_dir=tmp_path)


def test_cli_h3_subcommand_and_day12_behaviour_unchanged(monkeypatch):
    seen = {}
    monkeypatch.setattr(verdicts, "main_h3", lambda **kw: seen.update(h3=kw))
    monkeypatch.setattr(verdicts, "main", lambda **kw: seen.update(old=kw))
    assert verdicts.cli(["h3", "--force"]) == 0
    assert verdicts.cli(["--force"]) == 0
    assert verdicts.cli([]) == 0
    assert seen == {"h3": {"force": True}, "old": {"force": False}}
    monkeypatch.setattr(verdicts, "main_h3", lambda **kw: (_ for _ in ()).throw(FileExistsError("x")))
    assert verdicts.cli(["h3"]) == 1


def test_lstar_rejects_non_positive_n_total():
    with pytest.raises(ValueError, match="n_total"):
        verdicts.lstar({1.0: (0, 0), 0.5: (10, 10)})
    with pytest.raises(ValueError, match="n_total"):
        verdicts.lstar({1.0: (10, 10), 0.5: (0, 0)})


def test_lstar_ignores_mapping_order():
    levels = {1.0: (100, 100), 0.5: (50, 100), 0.25: (100, 100), 0.125: (100, 100)}
    expected = verdicts.lstar(levels)
    assert expected == (3, "1")
    assert verdicts.lstar(dict(sorted(levels.items()))) == expected  # ascending
    assert verdicts.lstar(dict(sorted(levels.items(), reverse=True))) == expected  # descending
    shuffled = {k: levels[k] for k in (0.25, 1.0, 0.125, 0.5)}
    assert verdicts.lstar(shuffled) == expected


@pytest.mark.parametrize("factor, level", [("baseline", "baseline"), ("volume", "100"), ("volume", "1000"),
                                           ("banks", "10"), ("arrival", "burst")])
def test_h3_rows_raises_when_a_needed_cell_is_missing(factor, level):
    runs = h3_frame()
    runs = runs[~((runs["factor"] == factor) & (runs["factor_level"] == level))]
    with pytest.raises(ValueError, match="missing or has no seeds"):
        verdicts.h3_rows(runs)


def test_h3_rows_does_not_need_the_five_bank_cell():
    runs = h3_frame()
    runs = runs[~((runs["factor"] == "banks") & (runs["factor_level"] == "5"))]
    assert len(verdicts.h3_rows(runs)) == 9
