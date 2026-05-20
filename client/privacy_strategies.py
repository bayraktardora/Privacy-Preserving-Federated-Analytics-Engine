import numpy as np
from abc import ABC, abstractmethod


class IPrivacyMechanism(ABC):
    """
    Abstract base class for differential privacy mechanisms.
    All mechanisms must implement the vectorized apply_noise() method.
    "I" prefix symbolizes that this class isn't used directly, implementations inherit it.
    """

    def __init__(self, epsilon: float):
        if epsilon <= 0:
            raise ValueError("Epsilon must be positive (epsilon > 0)")
        self.epsilon = epsilon

    @abstractmethod
    def apply_noise(self, data: np.ndarray, sensitivity: float = 1.0) -> np.ndarray:
        """
        Apply noise to an entire NumPy array to achieve differential privacy efficiently.
        
        Args:
            data: NumPy array of true numeric values to protect.
            sensitivity: Sensitivity of the query.
            
        Returns:
            A NumPy array containing the noisy values.
        """
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(epsilon={self.epsilon})"


class LaplaceStrategy(IPrivacyMechanism):
    """
    Laplace Mechanism for differential privacy.
    Adds Laplace-distributed noise scaled to sensitivity / epsilon.
    Optimized to handle entire NumPy arrays natively.
    Privacy guarantee: epsilon-DP
    """

    def __init__(self, epsilon: float):
        super().__init__(epsilon)

    def apply_noise(self, data: np.ndarray, sensitivity: float = 1.0) -> np.ndarray:
        scale = sensitivity / self.epsilon
        # Vectorized noise generation matching the shape of incoming data
        noise = np.random.laplace(loc=0.0, scale=scale, size=data.shape)
        return data + noise


class GaussianStrategy(IPrivacyMechanism):
    """
    Gaussian Mechanism for differential privacy.
    Adds Gaussian-distributed noise scaled to sensitivity / epsilon.
    Provides (epsilon, delta)-DP guarantee.
    """

    def __init__(self, epsilon: float, delta: float = 1e-5):
        super().__init__(epsilon)
        if not (0 < delta < 1):
            raise ValueError("Delta must be between 0 and 1 (exclusive)")
        self.delta = delta

    def _compute_sigma(self, sensitivity: float) -> float:
        """sigma = sensitivity * sqrt(2 * ln(1.25 / delta)) / epsilon"""
        return sensitivity * (np.sqrt(2 * np.log(1.25 / self.delta)) / self.epsilon)

    def apply_noise(self, data: np.ndarray, sensitivity: float = 1.0) -> np.ndarray:
        sigma = self._compute_sigma(sensitivity)
        # Vectorized noise generation matching the shape of incoming data
        noise = np.random.normal(loc=0.0, scale=sigma, size=data.shape)
        return data + noise

    def __repr__(self):
        return f"GaussianStrategy(epsilon={self.epsilon}, delta={self.delta})"


class PrivacyMechanismFactory:
    """
    Factory to create the appropriate privacy mechanism by name.

    Usage:
        mechanism = PrivacyMechanismFactory.create("laplace", epsilon=0.5)
        noisy_data = mechanism.apply_noise(np.array([10.0, 20.0, 30.0]))
    """

    @staticmethod
    def create(strategy_name: str, epsilon: float, **kwargs) -> IPrivacyMechanism:
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