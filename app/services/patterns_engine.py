from pathlib import Path
import yaml

def parse_yaml(text: str) -> dict:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("Pattern YAML must define a mapping/object")
    if "name" not in data:
        raise ValueError("Pattern YAML must include a 'name' field")
    # Normalize optional extensions
    data.setdefault('version', '1.0')
    data.setdefault('type', 'template_image')
    data.setdefault('scoring', {})
    if isinstance(data['scoring'], dict):
        data['scoring'].setdefault('threshold_alert', 0.7)
    return data

def load_patterns_from_dir(path: Path):
    items = []
    if not path.exists():
        return items
    for p in path.glob('*.yml'):
        items.append(parse_yaml(p.read_text(encoding='utf-8')))
    for p in path.glob('*.yaml'):
        items.append(parse_yaml(p.read_text(encoding='utf-8')))
    return items
