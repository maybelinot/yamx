

# YAMX

extend your YAML configuration with jinja2 expressions

---

## Usage

### Create

Create your first config with template syntax

```yaml
# starship.yml

type: Exploration vessel
{% if features["speed_improved"] %}
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
  {% if features["new_missiles_weapon"] %}
  - damage: 100
    fire_rate: 0.1
    ammo_capacity: 10
    name: Missiles
  {% endif %}
```

### Resolve

Resolve jinja logic configuration with `YAMX().resolve`

```python
from yamx import YAMX
import json

with open("starship.yml") as fp:
  raw_config = fp.read()

yamx = YAMX()
context = {
  "features": {
    "speed_improved": True,
    "new_missiles_weapon": False,
  }
}
raw_starship = yamx.resolve(raw_config, context)
starship_data = json.loads(raw_starship)

assert starship["speed"] == 50
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
