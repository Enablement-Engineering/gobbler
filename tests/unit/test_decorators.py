"""Unit tests for MCP tool decorators.

Tests the error handling decorator functionality used across all MCP tools.
"""

import inspect
import logging

import httpx
import pytest

from gobbler_mcp.decorators import handle_tool_errors


class TestHandleToolErrorsDecorator:
    """Tests for the handle_tool_errors decorator."""

    @pytest.mark.asyncio
    async def test_successful_execution_returns_result(self):
        """Test that successful function execution returns the result unchanged."""

        @handle_tool_errors(operation_name="test operation")
        async def successful_func():
            return "success result"

        result = await successful_func()
        assert result == "success result"

    @pytest.mark.asyncio
    async def test_successful_execution_with_args(self):
        """Test that arguments are passed through correctly."""

        @handle_tool_errors(operation_name="test operation")
        async def func_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = await func_with_args("x", "y", c="z")
        assert result == "x-y-z"

    @pytest.mark.asyncio
    async def test_httpx_connect_error_handling(self):
        """Test httpx.ConnectError is caught and returns error message."""

        @handle_tool_errors(operation_name="fetch data")
        async def raise_connect_error():
            msg = "Connection refused"
            raise httpx.ConnectError(msg)

        result = await raise_connect_error()
        assert "Connection failed" in result
        assert "Connection refused" in result

    @pytest.mark.asyncio
    async def test_httpx_connect_error_with_service_name(self):
        """Test ConnectError includes service name hint when provided."""

        @handle_tool_errors(operation_name="fetch data", service_name="Docker")
        async def raise_connect_error():
            msg = "Connection refused"
            raise httpx.ConnectError(msg)

        result = await raise_connect_error()
        assert "Connection failed" in result
        assert "Is Docker running?" in result

    @pytest.mark.asyncio
    async def test_httpx_connect_error_without_service_name(self):
        """Test ConnectError does not include service hint when not provided."""

        @handle_tool_errors(operation_name="fetch data")
        async def raise_connect_error():
            msg = "Connection refused"
            raise httpx.ConnectError(msg)

        result = await raise_connect_error()
        assert "Connection failed" in result
        assert "Is " not in result or "running?" not in result

    @pytest.mark.asyncio
    async def test_value_error_handling(self):
        """Test ValueError is caught and returns the error message."""

        @handle_tool_errors(operation_name="validate input")
        async def raise_value_error():
            msg = "Invalid input: expected positive number"
            raise ValueError(msg)

        result = await raise_value_error()
        assert result == "Invalid input: expected positive number"

    @pytest.mark.asyncio
    async def test_file_not_found_error_handling(self):
        """Test FileNotFoundError is caught and returns error message."""

        @handle_tool_errors(operation_name="read file")
        async def raise_file_not_found():
            msg = "config.yml"
            raise FileNotFoundError(msg)

        result = await raise_file_not_found()
        assert "Error: File not found" in result
        assert "config.yml" in result

    @pytest.mark.asyncio
    async def test_generic_exception_handling(self):
        """Test generic Exception is caught and returns error message."""

        @handle_tool_errors(operation_name="process data")
        async def raise_generic_exception():
            msg = "Something went wrong"
            raise RuntimeError(msg)

        result = await raise_generic_exception()
        assert "Failed to process data" in result
        assert "Something went wrong" in result

    @pytest.mark.asyncio
    async def test_runtime_error_handling(self):
        """Test RuntimeError is caught as generic exception."""

        @handle_tool_errors(operation_name="execute task")
        async def raise_runtime_error():
            msg = "Runtime failure"
            raise RuntimeError(msg)

        result = await raise_runtime_error()
        assert "Failed to execute task" in result
        assert "Runtime failure" in result

    @pytest.mark.asyncio
    async def test_type_error_handling(self):
        """Test TypeError is caught as generic exception."""

        @handle_tool_errors(operation_name="call function")
        async def raise_type_error():
            msg = "Expected string, got int"
            raise TypeError(msg)

        result = await raise_type_error()
        assert "Failed to call function" in result
        assert "Expected string, got int" in result


class TestDecoratorFunctionSignature:
    """Tests for decorator signature preservation."""

    def test_preserves_function_name(self):
        """Test that the decorator preserves the original function name."""

        @handle_tool_errors(operation_name="test")
        async def my_special_function():
            pass

        assert my_special_function.__name__ == "my_special_function"

    def test_preserves_function_docstring(self):
        """Test that the decorator preserves the original docstring."""

        @handle_tool_errors(operation_name="test")
        async def documented_function():
            """This is a detailed docstring."""

        assert documented_function.__doc__ == "This is a detailed docstring."

    def test_preserves_function_module(self):
        """Test that the decorator preserves the original module."""

        @handle_tool_errors(operation_name="test")
        async def module_function():
            pass

        assert module_function.__module__ == __name__

    def test_function_remains_async(self):
        """Test that decorated function remains a coroutine function."""

        @handle_tool_errors(operation_name="test")
        async def async_function():
            return "result"

        assert inspect.iscoroutinefunction(async_function)


class TestDecoratorLogging:
    """Tests for decorator logging behavior."""

    @pytest.mark.asyncio
    async def test_connect_error_logs_error(self, caplog):
        """Test that connection errors are logged at error level."""

        @handle_tool_errors(operation_name="connect to service")
        async def raise_connect_error():
            msg = "Connection refused"
            raise httpx.ConnectError(msg)

        with caplog.at_level(logging.ERROR, logger="gobbler_mcp.decorators"):
            await raise_connect_error()

        assert "Connection error in connect to service" in caplog.text

    @pytest.mark.asyncio
    async def test_value_error_logs_warning(self, caplog):
        """Test that validation errors are logged at warning level."""

        @handle_tool_errors(operation_name="validate data")
        async def raise_value_error():
            msg = "Invalid value"
            raise ValueError(msg)

        with caplog.at_level(logging.WARNING, logger="gobbler_mcp.decorators"):
            await raise_value_error()

        assert "Validation error in validate data" in caplog.text

    @pytest.mark.asyncio
    async def test_file_not_found_logs_error(self, caplog):
        """Test that file not found errors are logged at error level."""

        @handle_tool_errors(operation_name="load config")
        async def raise_file_not_found():
            msg = "missing.txt"
            raise FileNotFoundError(msg)

        with caplog.at_level(logging.ERROR, logger="gobbler_mcp.decorators"):
            await raise_file_not_found()

        assert "File not found in load config" in caplog.text

    @pytest.mark.asyncio
    async def test_generic_exception_logs_error_with_traceback(self, caplog):
        """Test that generic exceptions are logged at error level with traceback."""

        @handle_tool_errors(operation_name="run operation")
        async def raise_generic():
            msg = "Unexpected failure"
            raise RuntimeError(msg)

        with caplog.at_level(logging.ERROR, logger="gobbler_mcp.decorators"):
            await raise_generic()

        assert "Unexpected error in run operation" in caplog.text


class TestDecoratorEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_empty_string_result(self):
        """Test that empty string result is returned correctly."""

        @handle_tool_errors(operation_name="test")
        async def return_empty():
            return ""

        result = await return_empty()
        assert result == ""

    @pytest.mark.asyncio
    async def test_none_result(self):
        """Test that None result is returned correctly."""

        @handle_tool_errors(operation_name="test")
        async def return_none():
            return None

        result = await return_none()
        assert result is None

    @pytest.mark.asyncio
    async def test_multiline_result(self):
        """Test that multiline string result is returned correctly."""

        @handle_tool_errors(operation_name="test")
        async def return_multiline():
            return "line1\nline2\nline3"

        result = await return_multiline()
        assert result == "line1\nline2\nline3"

    @pytest.mark.asyncio
    async def test_unicode_in_error_message(self):
        """Test that unicode characters in error messages are handled."""

        @handle_tool_errors(operation_name="test unicode")
        async def raise_unicode_error():
            msg = "错误: invalid input"
            raise ValueError(msg)

        result = await raise_unicode_error()
        assert "错误" in result

    @pytest.mark.asyncio
    async def test_long_operation_name(self):
        """Test decorator works with long operation names."""
        long_name = "a" * 200

        @handle_tool_errors(operation_name=long_name)
        async def raise_exception():
            msg = "test error"
            raise RuntimeError(msg)

        result = await raise_exception()
        assert f"Failed to {long_name}" in result

    @pytest.mark.asyncio
    async def test_special_characters_in_operation_name(self):
        """Test decorator handles special characters in operation name."""

        @handle_tool_errors(operation_name="fetch user's data (test)")
        async def raise_exception():
            msg = "failed"
            raise RuntimeError(msg)

        result = await raise_exception()
        assert "Failed to fetch user's data (test)" in result

    @pytest.mark.asyncio
    async def test_nested_decorator_calls(self):
        """Test that multiple decorated functions can call each other."""

        @handle_tool_errors(operation_name="inner operation")
        async def inner_func():
            return "inner result"

        @handle_tool_errors(operation_name="outer operation")
        async def outer_func():
            inner_result = await inner_func()
            return f"outer: {inner_result}"

        result = await outer_func()
        assert result == "outer: inner result"

    @pytest.mark.asyncio
    async def test_kwargs_only_function(self):
        """Test decorator works with kwargs-only function."""

        @handle_tool_errors(operation_name="test")
        async def kwargs_only(*, name, value):
            return f"{name}={value}"

        result = await kwargs_only(name="key", value="val")
        assert result == "key=val"

    @pytest.mark.asyncio
    async def test_mixed_args_kwargs(self):
        """Test decorator works with mixed positional and keyword args."""

        @handle_tool_errors(operation_name="test")
        async def mixed_func(a, b, *args, **kwargs):
            return f"{a}-{b}-{args}-{kwargs}"

        result = await mixed_func(1, 2, 3, 4, x=5, y=6)
        assert "1-2-(3, 4)" in result
        assert "'x': 5" in result
        assert "'y': 6" in result


class TestDecoratorWithRealExceptions:
    """Tests using realistic exception scenarios."""

    @pytest.mark.asyncio
    async def test_file_permission_error(self):
        """Test PermissionError is handled as generic exception."""

        @handle_tool_errors(operation_name="write file")
        async def raise_permission_error():
            msg = "Access denied to /etc/passwd"
            raise PermissionError(msg)

        result = await raise_permission_error()
        assert "Failed to write file" in result
        assert "Access denied" in result

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """Test TimeoutError is handled as generic exception."""

        @handle_tool_errors(operation_name="fetch API", service_name="external API")
        async def raise_timeout():
            msg = "Request timed out after 30s"
            raise TimeoutError(msg)

        result = await raise_timeout()
        assert "Failed to fetch API" in result
        assert "timed out" in result

    @pytest.mark.asyncio
    async def test_key_error_handling(self):
        """Test KeyError is handled as generic exception."""

        @handle_tool_errors(operation_name="parse response")
        async def raise_key_error():
            msg = "missing_field"
            raise KeyError(msg)

        result = await raise_key_error()
        assert "Failed to parse response" in result
        assert "missing_field" in result

    @pytest.mark.asyncio
    async def test_os_error_handling(self):
        """Test OSError is handled as generic exception."""

        @handle_tool_errors(operation_name="access disk")
        async def raise_os_error():
            msg = "Disk full"
            raise OSError(msg)

        result = await raise_os_error()
        assert "Failed to access disk" in result
        assert "Disk full" in result
