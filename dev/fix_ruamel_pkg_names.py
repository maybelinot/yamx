#!/usr/bin/env python3

"""
Workaround for poetry install to be able to install ruamel.yaml library
and at same time we can still keep using pip-compile and output requirement txt files
"""

import sys

TO_BE_REPLACED = {
    "ruamel-yaml-string": "ruamel.yaml.string",
    "ruamel-yaml-clib": "ruamel.yaml.clib",
    "ruamel-yaml": "ruamel.yaml",
}


def replace_in_file(file_path: str):
    with open(file_path) as f:
        content = f.read()

    for value_to_be_replaced, new_value in TO_BE_REPLACED.items():
        content = content.replace(value_to_be_replaced, new_value)

    with open(file_path, "w") as f:
        f.write(content)


def main(path: str):
    replace_in_file(path)


if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            raise Exception("Missing path namespace argument.")

        main(sys.argv[1])
    except Exception as e:
        print(str(e))
        sys.exit(1)
