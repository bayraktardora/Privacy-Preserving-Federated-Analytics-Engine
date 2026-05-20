import sys
import os
import numpy as np
import statistics

# Ensure the local directory is in the path so it can find privacy_strategies
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from privacy_strategies import (
    LaplaceStrategy, 
    GaussianStrategy, 
    PrivacyMechanismFactory,
    IPrivacyMechanism
)


def test_laplace_output_differs_from_input():
    strategy = LaplaceStrategy(epsilon=1.0)
    original = np.array([50.0, 60.0, 70.0])
    noisy = strategy.apply_noise(original)
    
    assert noisy.shape == original.shape, "Output shape must match input shape"
    assert not np.array_equal(noisy, original), "Noisy output array should differ from original"


def test_gaussian_output_differs_from_input():
    strategy = GaussianStrategy(epsilon=1.0, delta=1e-5)
    original = np.array([50.0, 60.0, 70.0])
    noisy = strategy.apply_noise(original)
    
    assert noisy.shape == original.shape, "Output shape must match input shape"
    assert not np.array_equal(noisy, original), "Noisy output array should differ from original"


def test_noise_increases_as_epsilon_decreases():
    """Lower epsilon = more privacy = more noise variance."""
    value_array = np.full((500,), 100.0)  # 500 test samples inside a vectorized array

    high_privacy = LaplaceStrategy(epsilon=0.01)   # Low epsilon -> Lots of noise
    low_privacy  = LaplaceStrategy(epsilon=10.0)   # High epsilon -> Barely any noise

    high_noise_elements = np.abs(high_privacy.apply_noise(value_array) - value_array)
    low_noise_elements = np.abs(low_privacy.apply_noise(value_array) - value_array)

    assert np.mean(high_noise_elements) > np.mean(low_noise_elements), \
        "High privacy (low epsilon) should produce a significantly higher mean absolute noise displacement"


def test_factory_creates_correct_strategy():
    laplace  = PrivacyMechanismFactory.create("laplace", epsilon=0.5)
    gaussian = PrivacyMechanismFactory.create("gaussian", epsilon=0.5, delta=1e-5)
    
    assert isinstance(laplace,  LaplaceStrategy)
    assert isinstance(gaussian, GaussianStrategy)
    assert isinstance(laplace,  IPrivacyMechanism)


def test_invalid_epsilon_raises():
    try:
        LaplaceStrategy(epsilon=-1.0)
        assert False, "Should have raised ValueError for negative epsilon"
    except ValueError:
        pass


if __name__ == "__main__":
    test_laplace_output_differs_from_input()
    test_gaussian_output_differs_from_input()
    test_noise_increases_as_epsilon_decreases()
    test_factory_creates_correct_strategy()
    test_invalid_epsilon_raises()
    print("All strategy tests passed perfectly with NumPy optimization! ✅")