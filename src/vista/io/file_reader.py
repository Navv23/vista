import polars as pl
from typing import Optional, Union, Dict, Any

class FileReader:
    def __init__(self, file_path: str, file_type: str, read_options: Optional[Dict[str, Any]] = None):
        self.file_path = file_path
        self.file_type = file_type.lower()
        self.schema = None
        self.columns = None
        self.width = None
        self.height = None
        self.read_options = read_options if read_options is not None else {}
    
    def _get_dimensions(self, lazy_frame: pl.LazyFrame) -> tuple:
        '''
        Retrieve the dimensions (width and height) of the lazy frame.
        '''
        if self.width is None or self.height is None:
            dimensions = lazy_frame.select(pl.len()).collect().item()
            self.height = dimensions
            self.width = len(lazy_frame.collect_schema().names())
        return self.width, self.height
    
    def _get_columns(self, lazy_frame: pl.LazyFrame) -> list:
        '''
        Retrieve the column names for the lazy frame.
        '''
        if self.columns is None:
            self.columns = lazy_frame.collect_schema().names()
        return self.columns
    
    def _get_schema(self, lazy_frame: pl.LazyFrame) -> Dict[str, pl.DataType]:
        '''
        Retrieve the schema for the lazy frame.
        '''
        if self.schema is None:
            self.schema = lazy_frame.collect_schema()
        return self.schema

    def scan_lazy(self) -> Union[pl.DataFrame, pl.LazyFrame]:
        '''
        Scans the lazy frame based on file type.
        '''
        if self.file_type == 'csv':
            lazy_frame =  pl.scan_csv(self.file_path, **self.read_options)
        elif self.file_type == 'parquet':
            lazy_frame = pl.scan_parquet(self.file_path, **self.read_options)
        else:
            raise ValueError(f"Unsupported file type: {self.file_type}")
        
        self._get_schema(lazy_frame=lazy_frame)
        self._get_columns(lazy_frame=lazy_frame)
        self._get_dimensions(lazy_frame=lazy_frame)
        return lazy_frame
