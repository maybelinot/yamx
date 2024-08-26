## Logical Sorting

To apply logical sorting to your YAML file, you can use the function `sort_logical(obj, config)`. The config parameter in this function is defined by SORT_CONFIG, which determines the sorting order for keys and values within the YAML content. By using SORT_CONFIG, you can ensure your YAML data is organized according to specific rules and preferences.

### Structure of SORT_CONFIG

- **Keys**: The keys in `SORT_CONFIG` are tuples that represent the path to a key in the YAML file. For example, a key like `("key1", "key2")` targets a nested key `key2` under `key1`.

- **Values**: The values are dictionaries that define the sorting order for either dictionaries or lists located under the specified key path.

### Sorting Dictionaries

For dictionary elements, the `key_order` specifies the order in which keys should appear.

#### Example 1: Sorting Dictionary Keys

Given the configuration:
```python
SORT_CONFIG = {
    ("key1", "key2"): {
        "key_order": ["key3", "key4"]
    }
}
```

The resulting YAML configuration will sort the keys `key3` and `key4` under `key1 > key2`:

```yaml
key1:
  key2:
    key3: ...
    key4: ...
```

### Sorting Lists

Lists are denoted by the `[]` symbol in the key tuple, indicating that the sorting rules apply to a list under the specified path.

#### Example 2: Sorting Lists

Given the configuration:
```python
SORT_CONFIG = {
    ("key1", "[]"): {
        "key_order": ["key3", "key4"]
    }
}
```

The resulting YAML configuration will sort dictionary items inside a list under `key1` by the keys `key3` and `key4`:

```yaml
key1:
  - key3: ...
    key4: ...
```

### Advanced Sorting for Lists

For sorting list elements, use `item_order` to define the sorting criteria. The `item_order` can contain strings or tuples, where tuples represent nested keys within dictionary elements.

#### Example 3: Advanced Sorting for Lists

Given the configuration:
```python
SORT_CONFIG = {
    ("key1",): {
        "item_order": [
            {"key": "key2"},
            {"key": ("key3", "value")}
        ]
    }
}
```

Here, items under the list at `key1` will be sorted:
1. First by the value of `key2`.
2. Then by the value under `key2 > value`.

The resulting YAML configuration will look like:

```yaml
key1:
  - key2: 1
    key3:
      value: 3
  - key2: 1
    key3:
      value: 4
  - key2: 2
    key3:
      value: 1
  - key2: 2
    key3:
      value: 2
```

### Special Notes

- If a dictionary is represented by a toggled group, the first key of the "if" body is used to represent the order of the entire group.
- `item_order` is used exclusively for defining the order of items in a list, allowing for complex nested sorting based on multiple criteria.

By configuring `SORT_CONFIG` appropriately, you can ensure your YAML files are consistently and predictably ordered according to your specific needs.
