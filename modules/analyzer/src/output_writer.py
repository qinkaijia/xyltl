from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from models import FinalStatus


class OutputWriter:
    def __init__(self, output_path: Union[str, Path]) -> None:
        self.output_path = Path(output_path)

    def write(self, final_status: FinalStatus) -> Path:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as file:
            json.dump(final_status.to_dict(), file, ensure_ascii=False, indent=2)
            file.write("\n")
        return self.output_path
