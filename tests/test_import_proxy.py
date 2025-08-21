"""Tests for import proxy functionality."""

import sys
import pytest
import os
import math
from importproxy import (
    register,
    unregister,
    object_resolver,
    dict_resolver,
    proxy_module,
    synthetic_module,
    chain_resolvers,
)


class DummyObject:
    """Test object for proxy testing."""

    def __init__(self):
        self.Jax = "test_jax_value"
        self.other_attr = 42
        self.nested = {"key": "value"}


def test_basic_object_proxy():
    """Test basic object attribute proxying."""
    test_obj = DummyObject()

    # register the proxy
    register("funny", object_resolver(test_obj))

    # import and test
    from funny import Jax

    assert Jax == "test_jax_value"

    from funny import other_attr

    assert other_attr == 42

    # clean up
    unregister("funny")


def test_object_attribute_import():
    """Test from funny import Silly -> myobj.Silly."""

    class MyObj:
        def __init__(self):
            self.Silly = "works perfectly"

    myobj = MyObj()
    register("funny", object_resolver(myobj))

    from funny import Silly

    assert Silly == "works perfectly"

    unregister("funny")


def test_dict_resolver():
    """Test dictionary-based resolver."""
    test_dict = {"Jax": "dict_jax_value", "number": 123, "list_item": [1, 2, 3]}

    register("testdict", dict_resolver(test_dict))

    from testdict import Jax, number, list_item

    assert Jax == "dict_jax_value"
    assert number == 123
    assert list_item == [1, 2, 3]

    unregister("testdict")


def test_custom_resolver():
    """Test custom resolver function."""

    def custom_resolver(module_name, attr_name):
        if attr_name == "special":
            return f"special_value_from_{module_name}"
        elif attr_name == "multiply":
            return lambda x: x * 2
        else:
            raise AttributeError(f"No attribute {attr_name}")

    register("custom", custom_resolver)

    from custom import special, multiply

    assert special == "special_value_from_custom"
    assert multiply(5) == 10

    unregister("custom")


def test_attribute_error():
    """Test that AttributeError is raised for missing attributes."""
    test_dict = {"existing": "value"}
    register("errortest", dict_resolver(test_dict))

    # import the module first, then try to access missing attribute
    import errortest

    with pytest.raises(AttributeError):
        _ = errortest.nonexistent

    unregister("errortest")


def test_multiple_registrations():
    """Test multiple simultaneous proxy registrations."""
    obj1 = DummyObject()
    obj1.value = "obj1"

    obj2 = DummyObject()
    obj2.value = "obj2"

    register("proxy1", object_resolver(obj1))
    register("proxy2", object_resolver(obj2))

    from proxy1 import value as value1
    from proxy2 import value as value2

    assert value1 == "obj1"
    assert value2 == "obj2"

    unregister("proxy1")
    unregister("proxy2")


def test_unregister():
    """Test that unregistering works properly."""
    test_obj = DummyObject()
    register("temp", object_resolver(test_obj))

    # should work
    from temp import Jax

    assert Jax == "test_jax_value"

    # unregister
    unregister("temp")

    # should fail now
    with pytest.raises(ModuleNotFoundError):
        import temp


def test_module_cleanup():
    """Test that modules are properly cleaned up from sys.modules."""
    test_obj = DummyObject()
    register("cleanup_test", object_resolver(test_obj))

    from cleanup_test import Jax

    assert "cleanup_test" in sys.modules

    unregister("cleanup_test")
    assert "cleanup_test" not in sys.modules


def test_nested_attribute_access():
    """Test accessing nested attributes through the proxy."""
    test_obj = DummyObject()
    register("nested_test", object_resolver(test_obj))

    from nested_test import nested

    assert nested == {"key": "value"}
    assert nested["key"] == "value"

    unregister("nested_test")


def test_proxy_module():
    """Test proxying real Python modules."""
    register("myos", proxy_module(os))

    import myos
    from myos import getcwd, path

    assert myos.getcwd() == os.getcwd()
    assert path.join("a", "b") == os.path.join("a", "b")
    assert myos.name == os.name

    unregister("myos")


def test_proxy_pathlib():
    """Test proxying pathlib module."""
    import pathlib

    register("mypath", proxy_module(pathlib))

    from mypath import Path, PurePath

    # test basic functionality
    p = Path("/tmp/test")
    assert str(p) == "/tmp/test"
    assert isinstance(p, pathlib.Path)

    # test that we get the real classes
    assert Path is pathlib.Path
    assert PurePath is pathlib.PurePath

    unregister("mypath")


def test_proxy_missing_attribute():
    """Test that missing attributes raise proper errors."""
    register("empty_os", proxy_module(os))

    import empty_os

    with pytest.raises(AttributeError, match="has no attribute 'nonexistent'"):
        _ = empty_os.nonexistent

    unregister("empty_os")


def test_reregistration():
    """Test that reregistering works properly."""
    obj1 = DummyObject()
    obj1.value = "first"

    obj2 = DummyObject()
    obj2.value = "second"

    # register first
    register("changing", object_resolver(obj1))
    from changing import value as v1

    assert v1 == "first"

    # reregister with different object
    register("changing", object_resolver(obj2))
    from changing import value as v2

    assert v2 == "second"

    unregister("changing")


def test_dir_functionality():
    """Test __dir__ support for tab completion."""
    attrs = {"func1": lambda: 1, "func2": lambda: 2, "CONSTANT": 42}
    register("dirtest", synthetic_module(attrs))

    import dirtest

    dir_result = dir(dirtest)

    assert "func1" in dir_result
    assert "func2" in dir_result
    assert "CONSTANT" in dir_result
    assert "__name__" in dir_result

    unregister("dirtest")


def test_resolver_exceptions():
    """Test that non-AttributeError exceptions propagate."""

    def buggy_resolver(module_name, attr_name):
        if attr_name == "crash":
            raise ValueError("intentional crash")
        elif attr_name == "works":
            return "success"
        raise AttributeError("not found")

    register("buggy", buggy_resolver)

    import buggy

    assert buggy.works == "success"

    with pytest.raises(ValueError, match="intentional crash"):
        _ = buggy.crash

    with pytest.raises(AttributeError):
        _ = buggy.missing

    unregister("buggy")


def test_synthetic_module():
    """Test synthetic modules from dictionaries."""
    attrs = {"PI": 3.14159, "add": lambda a, b: a + b, "version": "1.0.0"}

    register("calculator", synthetic_module(attrs))

    import calculator
    from calculator import add, PI

    assert calculator.PI == 3.14159
    assert add(5, 3) == 8
    assert calculator.version == "1.0.0"

    unregister("calculator")


def test_chain_resolvers():
    """Test chaining multiple resolvers."""
    custom_attrs = {
        "double": lambda x: x * 2,
        "triple": lambda x: x * 3,
    }

    register(
        "combo_math",
        chain_resolvers(
            synthetic_module(custom_attrs),  # try custom first
            proxy_module(math),  # fall back to math module
        ),
    )

    import combo_math
    from combo_math import pi, sqrt, double

    assert combo_math.pi == math.pi  # from math module
    assert sqrt(25) == 5.0  # from math module
    assert double(21) == 42  # from custom attrs

    unregister("combo_math")


def test_package_support():
    """Test package with submodules."""
    # register main package
    register(
        "mypkg",
        synthetic_module(
            {"VERSION": "2.0.0", "main_func": lambda: "hello from main"},
            is_package=True,
        ),
    )

    # register submodule
    register(
        "mypkg.utils",
        synthetic_module({"helper": lambda x: f"processed: {x}", "CONSTANT": 42}),
    )

    import mypkg
    from mypkg import main_func
    from mypkg.utils import helper, CONSTANT

    assert mypkg.VERSION == "2.0.0"
    assert main_func() == "hello from main"
    assert helper("test") == "processed: test"
    assert CONSTANT == 42

    unregister("mypkg.utils")
    unregister("mypkg")
