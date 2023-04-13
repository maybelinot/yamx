

# YAMJinX

extend your YAML configuration with Jinja conditional expressions

---

## How to use

Current version is useful only for linting of existing configs

1. Define configuration with conditional block

    ```yaml
    config:
      app2: 2
      # {% if defines.get("ENABLED") %}
      enabled: true
      # {% else %}
      enabled: false
      # {% endif %}
      app1: 1
    ```
2. Load configuration with YAMJinX and dump it to string

    ```python
    from yamjinx import YAMJinX

    yamjinx = YAMJinX(sort_keys=True)

    with open("data.yaml") as f:
        data = yamjinx.load(f)

    data_raw = yamjinx.dump_to_string(data)
    print(data_raw)
    ```
    ```yaml
    ### stdout ###
    config:
      app1: 1
      app2: 2
      # {% if defines.get("ENABLED") %}
      enabled: true
      # {% else %}
      enabled: false
      # {% endif %}
    ```


## Testing

```bash
pytest tests
```
