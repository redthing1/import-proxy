"""
Import proxy library for Python.

Create proxy modules that dynamically resolve imports with custom resolver functions.
"""

import sys
import types
import importlib.abc
import importlib.machinery
from typing import Callable, Any, Optional, Dict, List


class ProxyModule(types.ModuleType):
    """Module that uses __getattr__ for dynamic attribute resolution."""

    def __init__(self, name: str, resolver: Callable[[str, str], Any]):
        super().__init__(name)
        self.__name__ = name
        self.__package__ = name.rsplit(".", 1)[0] if "." in name else None
        self._resolver = resolver

        # determine if this module should be treated as a package
        try:
            path_info = resolver(name, "__path__")
            if path_info is not None:
                self.__path__ = path_info if isinstance(path_info, list) else []
        except AttributeError:
            pass

    def __getattr__(self, name: str) -> Any:
        """PEP 562 module-level __getattr__ for dynamic resolution."""
        try:
            return self._resolver(self.__name__, name)
        except AttributeError:
            # attempt to resolve as submodule
            submodule_name = f"{self.__name__}.{name}"
            if submodule_name in _registry:
                try:
                    submodule = __import__(submodule_name, fromlist=[""])
                    return submodule
                except ImportError:
                    pass

            raise AttributeError(f"module '{self.__name__}' has no attribute '{name}'")

    def __dir__(self) -> List[str]:
        """Return available attributes for tab completion."""
        attrs = []

        try:
            resolver_dir = self._resolver(self.__name__, "__dir__")
            if callable(resolver_dir):
                attrs.extend(resolver_dir())
            elif isinstance(resolver_dir, (list, tuple)):
                attrs.extend(resolver_dir)
        except AttributeError:
            pass

        attrs.extend(["__name__", "__package__"])
        if hasattr(self, "__path__"):
            attrs.append("__path__")

        return sorted(set(attrs))


class ProxyLoader(importlib.abc.Loader):
    """Loader implementation for proxy modules."""

    def __init__(self, resolver: Callable[[str, str], Any]):
        self.resolver = resolver

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ProxyModule:
        return ProxyModule(spec.name, self.resolver)

    def exec_module(self, module: ProxyModule) -> None:
        pass


class ProxyFinder(importlib.abc.MetaPathFinder):
    """Meta path finder for intercepting and resolving proxy imports."""

    def find_spec(
        self,
        fullname: str,
        path: Optional[List[str]],
        target: Optional[types.ModuleType] = None,
    ) -> Optional[importlib.machinery.ModuleSpec]:
        if fullname in _registry:
            resolver = _registry[fullname]
            loader = ProxyLoader(resolver)

            spec = importlib.machinery.ModuleSpec(fullname, loader)
            spec.origin = "proxy"

            # determine package configuration
            try:
                path_info = resolver(fullname, "__path__")
                if path_info is not None:
                    spec.submodule_search_locations = (
                        path_info if isinstance(path_info, list) else []
                    )
            except AttributeError:
                spec.submodule_search_locations = None

            return spec

        return None


# module registry and finder state
_registry: Dict[str, Callable[[str, str], Any]] = {}
_finder: Optional[ProxyFinder] = None


def _ensure_installed():
    """Ensure the meta path finder is installed in sys.meta_path."""
    global _finder
    if _finder is None:
        _finder = ProxyFinder()
        sys.meta_path.insert(0, _finder)


def register(module_name: str, resolver: Callable[[str, str], Any]):
    """Register a module with a resolver function.

    Args:
        module_name: Name of module to proxy (e.g., 'funny')
        resolver: Function that takes (module_name, attr_name) and returns value

    Example:
        >>> thing = SomeObject()
        >>> register('funny', lambda mod, attr: getattr(thing, attr))
        >>> from funny import Jax  # returns thing.Jax
    """
    _ensure_installed()
    _registry[module_name] = resolver

    # remove any cached module to force re-import
    if module_name in sys.modules:
        del sys.modules[module_name]


def unregister(module_name: str):
    """Unregister a proxy module.

    Args:
        module_name: Name of the module to unregister
    """
    if module_name in _registry:
        del _registry[module_name]

    if module_name in sys.modules:
        del sys.modules[module_name]


# built-in resolver functions


def object_resolver(obj: Any) -> Callable[[str, str], Any]:
    """Create resolver that proxies to an object's attributes.

    Args:
        obj: Object whose attributes will be accessible via import

    Returns:
        Resolver function that delegates to getattr(obj, attr_name)
    """

    def resolver(module_name: str, attr_name: str):
        return getattr(obj, attr_name)

    return resolver


def dict_resolver(mapping: Dict[str, Any]) -> Callable[[str, str], Any]:
    """Create resolver that looks up attributes in a dictionary.

    Args:
        mapping: Dictionary of attribute names to values

    Returns:
        Resolver function that looks up attributes in the mapping
    """

    def resolver(module_name: str, attr_name: str):
        if attr_name == "__dir__":
            return lambda: list(mapping.keys())
        elif attr_name in mapping:
            return mapping[attr_name]
        else:
            raise AttributeError(
                f"module '{module_name}' has no attribute '{attr_name}'"
            )

    return resolver


def proxy_module(module: types.ModuleType) -> Callable[[str, str], Any]:
    """Create resolver that proxies to a real Python module.

    Args:
        module: Python module to proxy

    Returns:
        Resolver function that delegates to the target module
    """

    def resolver(module_name: str, attr_name: str):
        if attr_name == "__path__":
            return getattr(module, "__path__", None)
        elif attr_name == "__dir__":
            return lambda: dir(module)
        elif hasattr(module, attr_name):
            return getattr(module, attr_name)
        else:
            raise AttributeError(
                f"module '{module.__name__}' has no attribute '{attr_name}'"
            )

    return resolver


def synthetic_module(
    attrs: Dict[str, Any], is_package: bool = False
) -> Callable[[str, str], Any]:
    """Create resolver from a dictionary of attributes.

    Args:
        attrs: Dictionary of attribute names to values
        is_package: Whether the synthetic module should be treated as a package

    Returns:
        Resolver function for a synthetic module
    """

    def resolver(module_name: str, attr_name: str):
        if attr_name == "__path__":
            return [] if is_package else None
        elif attr_name == "__dir__":
            return lambda: list(attrs.keys())
        elif attr_name in attrs:
            return attrs[attr_name]
        else:
            raise AttributeError(
                f"module '{module_name}' has no attribute '{attr_name}'"
            )

    return resolver


def chain_resolvers(*resolvers: Callable[[str, str], Any]) -> Callable[[str, str], Any]:
    """Create resolver that tries multiple resolvers in order.

    Args:
        *resolvers: Resolver functions to try in order

    Returns:
        Resolver that tries each resolver until one succeeds
    """

    def resolver(module_name: str, attr_name: str):
        for r in resolvers:
            try:
                return r(module_name, attr_name)
            except AttributeError:
                continue
        raise AttributeError(f"module '{module_name}' has no attribute '{attr_name}'")

    return resolver
