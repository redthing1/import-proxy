
# import-proxy

a simple way to proxy imports in python

# usage

proxy any object's attributes as a module:

```py
from importproxy import register, object_resolver

class ApiClient:
    def get_user(self, id): return f"user {id}"
    def get_posts(self): return ["post1", "post2"]

client = ApiClient()
register('api', object_resolver(client))

from api import get_user, get_posts
print(get_user(123))  # user 123
```

create synthetic modules from dictionaries:

```py
from importproxy import register, synthetic_module

math_funcs = {
    'double': lambda x: x * 2,
    'square': lambda x: x ** 2,
    'PI': 3.14159
}

register('mymath', synthetic_module(math_funcs))

from mymath import double, PI
print(double(5))  # 10
```

proxy real modules with custom names:

```py
from importproxy import register, proxy_module
import pathlib

register('paths', proxy_module(pathlib))

from paths import Path
p = Path('/tmp/test')
```

chain multiple sources together:

```py
from importproxy import register, chain_resolvers, dict_resolver, proxy_module
import math

custom = {'triple': lambda x: x * 3}

register('math_2', chain_resolvers(
    dict_resolver(custom),    # try custom first
    proxy_module(math)        # fall back to real math
))

from math_2 import triple, sin
print(triple(4))  # 12 (custom)
print(sin(0))     # 0.0 (from math)
```

# why does this exist?

i was tired of having to `Thing = something.Thing` when working with rpyc remote objects. now i can just `from something import Thing` and have my scripts work unmodified

yes, it's a massive hack, but it's funny, it amuses me
