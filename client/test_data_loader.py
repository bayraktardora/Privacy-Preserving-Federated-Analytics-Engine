import sys
import os
import numpy as np
import pandas as pd
import pytest
import warnings

# Add parent directory setup
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock minimal environmental constraints needed for client imports
os.environ["NODE_ID"] = "test_node"
from main import DataLoader


@pytest.fixture
def temp_csv(tmp_path):
    """Fixture to generate temporary CSV file paths."""
    return tmp_path / "test_data.csv"


def test_no_file_keeps_fallback():
    """Case: No file exists -> should return synthetic data loop fallback array."""
    loader = DataLoader("non_existent_file.csv")
    data = loader.load()
    
    assert isinstance(data, np.ndarray)
    assert len(data) == 20  # Synthetic fallback creates 20 elements


def test_empty_csv_returns_empty_list_and_warning(temp_csv):
    """Case: Empty CSV -> returns empty array + triggers warning."""
    # Create an empty file with no columns/data
    temp_csv.write_text("")
    loader = DataLoader(str(temp_csv))
    
    with pytest.warns(UserWarning, match="is empty"):
        data = loader.load()
        
    assert isinstance(data, np.ndarray)
    assert len(data) == 0


def test_nan_rows_drop_strategy(temp_csv, monkeypatch):
    """Case: NaN entries present -> drop strategy cleans them out completely."""
    monkeypatch.setenv("MISSING_VALUE_STRATEGY", "drop")
    
    # Setup test file containing strings and missing items mixed with valid numeric items
    temp_csv.write_text("values\n10.5\nNaN\ntext_garbage\n30.5")
    loader = DataLoader(str(temp_csv))
    
    data = loader.load()
    # Should cleanly filter down to just [10.5, 30.5]
    assert np.array_equal(data, np.array([10.5, 30.5]))


def test_nan_rows_fill_mean_strategy(temp_csv, monkeypatch):
    """Case: NaN entries present -> fill_mean calculates and targets open holes."""
    monkeypatch.setenv("MISSING_VALUE_STRATEGY", "fill_mean")
    
    # 10.0 + 30.0 = 40.0 -> Mean should equal 20.0. The two bad rows must become 20.0
    temp_csv.write_text("values\n10.0\nNaN\ntext_garbage\n30.0")
    loader = DataLoader(str(temp_csv))
    
    data = loader.load()
    expected = np.array([10.0, 20.0, 20.0, 30.0])
    assert np.array_equal(data, expected)


if __name__ == "__main__":
    # Allows running file directly without explicit pytest call setups
    pytest.main([__file__])