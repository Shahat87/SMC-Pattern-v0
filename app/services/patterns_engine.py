from pathlib import Path
import yaml

def parse_yaml(text: str) -> dict:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("Pattern YAML must define a mapping/object")
    if "name" not in data:
        raise ValueError("Pattern YAML must include a 'name' field")
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