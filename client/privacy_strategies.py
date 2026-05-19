import numpy as np
from abc import ABC, abstractmethod


class PrivacyStrategy(ABC):
    """
    Abstract base class for differential privacy strategies.
    All strategies must implement the apply() method.
    """

    def __init__(self, epsilon: float):
        if epsilon <= 0:
            raise ValueError("Epsilon must be positive (epsilon > 0)")
        self.epsilon = epsilon

    @abstractmethod
    def apply(self, value: float, sensitivity: float = 1.0) -> float:
        """Apply noise to a value to achieve differential privacy."""
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(epsilon={self.epsilon})"


class LaplaceStrategy(PrivacyStrategy):
    """
    Laplace Mechanism for differential privacy.

    Adds Laplace-distributed noise scaled to sensitivity / epsilon.
    Best for numerical queries (counts, sums, averages).

    Privacy guarantee: epsilon-DP
    """

    def __init__(self, epsilon: float):
        super().__init__(epsilon)

    def apply(self, value: float, sensitivity: float = 1.0) -> float:
        """
        Add Laplace noise to value.

        Args:
            value: The true numeric value to protect.
            sensitivity: L1 sensitivity of the query (default 1.0).

        Returns:
            Noisy value with epsilon-DP guarantee.
        """
        scale = sensitivity / self.epsilon
        noise = np.random.laplace(loc=0.0, scale=scale)
        return value + noise

    def apply_batch(self, values: list[float], sensitivity: float = 1.0) -> list[float]:
        """Apply Laplace noise to a list of values."""
        return [self.apply(v, sensitivity) for v in values]


class GaussianStrategy(PrivacyStrategy):
    """
    Gaussian Mechanism for differential privacy.

    Adds Gaussian-distributed noise scaled to sensitivity / epsilon.
    Provides (epsilon, delta)-DP — slightly weaker but often more
    practical for machine learning workloads.

    Privacy guarantee: (epsilon, delta)-DP
    """

    def __init__(self, epsilon: float, delta: float = 1e-5):
        super().__init__(epsilon)
        if not (0 < delta < 1):
            raise ValueError("Delta must be between 0 and 1 (exclusive)")
        self.delta = delta

    def _compute_sigma(self, sensitivity: float) -> float:
        """
        Compute Gaussian noise standard deviation using the analytic formula.
        sigma = sensitivity * sqrt(2 * ln(1.25 / delta)) / epsilon
        """
        sigma = sensitivity * (np.sqrt(2 * np.log(1.25 / self.delta)) / self.epsilon)
        return sigma

    def apply(self, value: float, sensitivity: float = 1.0) -> float:
        """
        Add Gaussian noise to value.

        Args:
            value: The true numeric value to protect.
            sensitivity: L2 sensitivity of the query (default 1.0).

        Returns:
            Noisy value with (epsilon, delta)-DP guarantee.
        """
        sigma = self._compute_sigma(sensitivity)
        noise = np.random.normal(loc=0.0, scale=sigma)
        return value + noise

    def apply_batch(self, values: list[float], sensitivity: float = 1.0) -> list[float]:
        """Apply Gaussian noise to a list of values."""
        return [self.apply(v, sensitivity) for v in values]

    def __repr__(self):
        return f"GaussianStrategy(epsilon={self.epsilon}, delta={self.delta})"


class PrivacyStrategyFactory:
    """
    Factory to create the appropriate privacy strategy by name.

    Usage:
        strategy = PrivacyStrategyFactory.create("laplace", epsilon=0.5)
        noisy_value = strategy.apply(42.0)
    """

    @staticmethod
    def create(strategy_name: str, epsilon: float, **kwargs) -> PrivacyStrategy:
        strategies = {
            "laplace": LaplaceStrategy,
            "gaussian": GaussianStrategy,
        }
        name = strategy_name.lower()
        if name not in strategies:
            raise ValueError(
                f"Unknown strategy '{strategy_name}'. "
                f"Available: {list(strategies.keys())}"
            )
        return strategies[name](epsilon=epsilon, **kwargs)
