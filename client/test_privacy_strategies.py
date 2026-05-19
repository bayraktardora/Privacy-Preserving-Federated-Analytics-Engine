import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from privacy_strategies import LaplaceStrategy, GaussianStrategy, PrivacyStrategyFactory


def test_laplace_output_differs_from_input():
    strategy = LaplaceStrategy(epsilon=1.0)
    original = 50.0
    noisy = strategy.apply(original)
    assert noisy != original, "Noisy output should differ from original"


def test_gaussian_output_differs_from_input():
    strategy = GaussianStrategy(epsilon=1.0, delta=1e-5)
    original = 50.0
    noisy = strategy.apply(original)
    assert noisy != original, "Noisy output should differ from original"


def test_noise_increases_as_epsilon_decreases():
    """Lower epsilon = more privacy = more noise."""
    import statistics
    value = 100.0
    samples = 200

    high_privacy = LaplaceStrategy(epsilon=0.01)   # çok gürültü
    low_privacy  = LaplaceStrategy(epsilon=10.0)   # az gürültü

    high_noise = [abs(high_privacy.apply(value) - value) for _ in range(samples)]
    low_noise  = [abs(low_privacy.apply(value) - value)  for _ in range(samples)]

    assert statistics.mean(high_noise) > statistics.mean(low_noise), \
        "High privacy (low epsilon) should produce more noise"


def test_factory_creates_correct_strategy():
    laplace  = PrivacyStrategyFactory.create("laplace", epsilon=0.5)
    gaussian = PrivacyStrategyFactory.create("gaussian", epsilon=0.5, delta=1e-5)
    assert isinstance(laplace,  LaplaceStrategy)
    assert isinstance(gaussian, GaussianStrategy)


def test_invalid_epsilon_raises():
    try:
        LaplaceStrategy(epsilon=-1.0)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    test_laplace_output_differs_from_input()
    test_gaussian_output_differs_from_input()
    test_noise_increases_as_epsilon_decreases()
    test_factory_creates_correct_strategy()
    test_invalid_epsilon_raises()
    print("All tests passed ✅")
