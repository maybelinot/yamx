

# YAMX

extend your YAML configuration with jinja2 expressions

---

## Usage

### Create

Create your first config with template syntax

```yaml
# starship.yml

type: Exploration vessel
{% if toggles.speed_improved %}
speed: 50
max_speed: 100
{% else %}
max_speed: 35
speed: 20
{% endif %}
name: Starship Enterprise

weapons:
  - name: Laser Blaster
    fire_rate: 2.0
    damage: 20
    ammo_capacity: 50
  {% if toggles.new_missiles_weapon %}
  - damage: 100
    fire_rate: 0.1
    ammo_capacity: 10
    name: Missiles
  {% endif %}
```

### Extra functionality


Some parts of the library don't have general support yet and available only as set of `extra` tools to work with specific format of conditions such as

`defines.get("FEATURE_FLAG")`

`toggles.FEATURE_FLAG`

`toggles.get("FEATURE_FLAG")`

`toggles["FEATURE_FLAG"]`

`config_flags.NAME`

`config_flags.get("NAME")`

`config_flags["NAME"]`

Operations `not` and `and` are supported for them.

#### Extract toggle names used in config


```python
from yamx import YAMX
from yamx.extra import extract_toggles

yamx = YAMX()

with open("starship.yml") as fp:
  data = yamx.load(fp)


toggles = extract_toggles(data)

assert toggles == {"speed_improved", "new_missiles_weapon"}
```

#### Resolve jinja logic configuration with `yamx.extra.resolve_toggles`

```python
from immutables import Map

from yamx import YAMX
from yamx.extra import resolve_toggles, ResolvingContext

yamx = YAMX()

with open("starship.yml") as fp:
  data = yamx.load(fp)


context = {
  "toggles": ResolvingContext({
    "speed_improved":True,
    "new_missiles_weapon":False,
  })
}
resolved_data = resolve_toggles(data, context)

assert resolved_data["speed"] == 50
```

### Format

Format file structure and sort attribute keys with `sort_keys`

```python
from yamx import YAMX

yamx = YAMX(sort_keys=True)

with open("data.yaml") as f:
    data = yamx.load(f)

data_raw = yamx.dump_to_string(data)
print(data_raw)
```

```yaml
name: Starship Enterprise
type: Exploration vessel
{% if features["speed_improved"] %}
speed: 50
max_speed: 100
{% else %}
speed: 20
max_speed: 35
{% endif %}

weapons:
  - name: Laser Blaster
    damage: 20
    fire_rate: 2.0
    ammo_capacity: 50
  {% if features["new_missiles_weapon"] %}
  - name: Missiles
    damage: 100
    fire_rate: 0.1
    ammo_capacity: 10
  {% endif %}
```

## Development

### Linter

run linter with
```bash
make lint
```


## Testing

run tests with
```bash
make test
```
