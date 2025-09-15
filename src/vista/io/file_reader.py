import polars as pl
from typing import Optional, Union, Dict, Any

class FileReader:
    def __init__(self, file_path: str, file_type: str, read_options: Optional[Dict[str, Any]] = None):
        self.file_path = file_path
        self.file_type = file_type.lower()
        self.read_options = read_options if read_options is not None else {}

    def read(self, lazy: bool = False) -> Union[pl.DataFrame, pl.LazyFrame]:
        if self.file_type == 'csv':
            if lazy:
                return pl.scan_csv(self.file_path, **self.read_options)
            else:
                return pl.read_csv(self.file_path, **self.read_options)
        elif self.file_type == 'parquet':
            if lazy:
                return pl.scan_parquet(self.file_path, **self.read_options)
            else:
                return pl.read_parquet(self.file_path, **self.read_options)
        elif self.file_type == 'json':
            if lazy:
                raise NotImplementedError("Lazy reading is not supported for JSON files.")
            else:
                return pl.read_json(self.file_path, **self.read_options)
        else:
            raise ValueError(f"Unsupported file type: {self.file_type}")

    def read_in_batches(self, batch_size: int):
        if self.file_type == 'csv':
            return pl.read_csv_batched(self.file_path, **self.read_options)
        else:
            raise NotImplementedError(f"Batch reading is not supported for {self.file_type} files.")