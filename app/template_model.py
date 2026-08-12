from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ColumnRule:
    name: str
    delete: bool
    is_id: bool = False


@dataclass
class Template:
    name: str
    columns: list[ColumnRule] = field(default_factory=list)

    @property
    def id_column(self) -> str | None:
        for col in self.columns:
            if col.is_id:
                return col.name
        return None

    @property
    def kept_columns(self) -> list[str]:
        # the ID column always survives to the output, even if marked for deletion,
        # since anonymized reporting depends on it being there to cross-reference rows
        return [c.name for c in self.columns if not c.delete or c.is_id]

    def to_dict(self) -> dict:
        return {"name": self.name, "columns": [asdict(c) for c in self.columns]}

    @classmethod
    def from_dict(cls, data: dict) -> Template:
        return cls(name=data["name"], columns=[ColumnRule(**c) for c in data["columns"]])

    def save(self, store_dir: Path) -> Path:
        store_dir = Path(store_dir)
        store_dir.mkdir(parents=True, exist_ok=True)
        path = store_dir / f"{self.name}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> Template:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def load_all(cls, store_dir: Path) -> list[Template]:
        store_dir = Path(store_dir)
        if not store_dir.exists():
            return []
        return [cls.load(p) for p in sorted(store_dir.glob("*.json"))]
