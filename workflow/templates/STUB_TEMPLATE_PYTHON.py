"""
Stub Implementation Template - Python

Purpose: Create minimal interface definitions to unblock parallel agent work.
When to use: When Agent B needs to call code that Agent A hasn't finished yet.

Instructions:
1. Copy this template
2. Define the interface (function signatures, class methods)
3. Raise NotImplementedError in all methods
4. Add clear TODO comments indicating what needs implementation
5. Document expected behavior in docstrings
"""

from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod


class StubClass(ABC):
    """
    [STUB] Brief description of what this class does.

    TODO: Full implementation required by [Agent Name/Phase]
    Dependencies: [List any dependencies]
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the stub.

        Args:
            config: Configuration dictionary (format TBD)
        """
        self.config = config or {}
        # Add minimal initialization needed for type checking

    @abstractmethod
    def primary_method(self, param1: str, param2: int) -> Dict[str, Any]:
        """
        [STUB] Brief description of what this method should do.

        Args:
            param1: Description of param1
            param2: Description of param2

        Returns:
            Dictionary containing:
                - key1: Description
                - key2: Description

        Raises:
            NotImplementedError: This is a stub

        TODO: Implement by [Agent/Phase]
        Expected behavior: [Describe expected behavior]
        """
        raise NotImplementedError("Stub: primary_method not yet implemented")

    def helper_method(self, data: List[Any]) -> bool:
        """
        [STUB] Brief description.

        Args:
            data: Input data

        Returns:
            Success status

        TODO: Implement by [Agent/Phase]
        """
        raise NotImplementedError("Stub: helper_method not yet implemented")


def stub_function(input_data: Any, options: Optional[Dict] = None) -> Any:
    """
    [STUB] Brief description of what this function does.

    Args:
        input_data: Description
        options: Optional configuration

    Returns:
        Description of return value

    Raises:
        NotImplementedError: This is a stub

    TODO: Implement by [Agent/Phase]

    Example usage:
        >>> result = stub_function({"key": "value"})
        >>> # Expected result format: {...}
    """
    raise NotImplementedError("Stub: stub_function not yet implemented")


# Type aliases for better documentation
StubInputType = Dict[str, Any]
StubOutputType = Dict[str, Any]


# Constants that define the interface contract
STUB_VERSION = "0.1.0"
EXPECTED_INPUT_SCHEMA = {
    "field1": "string",
    "field2": "integer",
    # Add expected fields
}
EXPECTED_OUTPUT_SCHEMA = {
    "result": "string",
    "metadata": "object",
    # Add expected output fields
}


if __name__ == "__main__":
    # Minimal test to verify stub can be imported
    print("[STUB] This module is a stub and not fully implemented")
    print(f"Version: {STUB_VERSION}")
    print("TODO: Replace with actual implementation")
