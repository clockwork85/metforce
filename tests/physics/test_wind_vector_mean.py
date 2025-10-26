import numpy as np
import pytest


from metforce.physics.wind import vector_mean_from_samples


def _angle_close(a: int, b: int, atol: int =1e-6) -> bool:
    d = (a - b + 180.0) % 360.0 - 180.0
    return np.all(np.abs(d) <= atol)

def test_vector_mean_wraparound_basic():
    # Three samples in one bin: 350, 10, 20 deg at 5 m/s
    s = np.array([5.0, 5.0, 5.0])
    th = np.array([350.0, 10.0, 20.0])
    spd, deg = vector_mean_from_samples(s, th)
    assert spd == pytest.approx(4.883, rel=1e-3, abs=1e-3)
    assert _angle_close(deg, 6.7, atol=1e-2)

def test_vector_mean_uniform_direction_equals_scalar():
    s = np.array([3.0, 4.0, 5.0])
    th = np.array([90.0, 90.0, 90.0])
    spd, deg = vector_mean_from_samples(s, th)
    # vector speed is mean of components -> equals arithmetic mean if all headings same
    assert spd == pytest.approx(s.mean(), rel=1e-12)
    assert _angle_close(deg, 90.0)

def test_calm_direction_nan_when_below_threshold():
    s = np.array([0.05, 0.05, 0.05])  # m/s, tiny
    th = np.array([0.0, 120.0, 240.0])
    spd, deg = vector_mean_from_samples(s, th, calm_threshold_mps=0.2)
    assert spd < 0.2
    assert np.isnan(deg)