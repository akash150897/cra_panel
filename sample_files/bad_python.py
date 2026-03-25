# Sample Python file with intentional violations for testing
from os.path import *          # PY001: wildcard import
import json                    # PY007: unused import

SECRET_KEY = "my-super-secret-key-12345"   # PY009 + COM001: hardcoded secret
DATABASE_URL = "postgres://admin:password123@localhost/db"

def getUserData(id, name):     # PY006: camelCase, PY005: missing type hints
    print("Fetching user:", id)  # PY003: print instead of logging
    try:
        result = eval(f"get_user({id})")  # PY004: eval usage
        return result
    except:                    # PY002: bare except
        pass

def process():
    # TODO: implement this later   # COM002: TODO comment
    debugger                        # COM003: debug statement
    pass
