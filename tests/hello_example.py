#!/usr/bin/env python3
"""examples from the readme."""

from importproxy import (
    register,
    object_resolver,
    synthetic_module,
    proxy_module,
    chain_resolvers,
    dict_resolver,
)
import pathlib
import math

print("import-proxy examples")
print("=" * 20)

# example 1: proxy any object's attributes as a module
print("\n1. object proxying:")


class ApiClient:
    def get_user(self, id):
        return f"user {id}"

    def get_posts(self):
        return ["post1", "post2"]


client = ApiClient()
register("api", object_resolver(client))

from api import get_user, get_posts

print(f"   get_user(123) = {get_user(123)}")
print(f"   get_posts() = {get_posts()}")

# example 2: create synthetic modules from dictionaries
print("\n2. synthetic modules:")

math_funcs = {"double": lambda x: x * 2, "square": lambda x: x**2, "PI": 3.14159}

register("mymath", synthetic_module(math_funcs))

from mymath import double, PI

print(f"   double(5) = {double(5)}")
print(f"   PI = {PI}")

# example 3: proxy real modules with custom names
print("\n3. module aliasing:")

register("paths", proxy_module(pathlib))

from paths import Path

p = Path("/tmp/test")
print(f"   Path('/tmp/test') = {p}")
print(f"   type: {type(p)}")

# example 4: chain multiple sources together
print("\n4. resolver chaining:")

custom = {"triple": lambda x: x * 3}

register(
    "math_2",
    chain_resolvers(
        dict_resolver(custom),  # try custom first
        proxy_module(math),  # fall back to real math
    ),
)

from math_2 import triple, sin

print(f"   triple(4) = {triple(4)} (custom)")
print(f"   sin(0) = {sin(0)} (from math)")

print("\nok!")
