import polars as pl
from datetime import datetime
from typing import Dict, Any, List
from vista.io.file_reader import FileReader
from vista.settings import STREAMING_ENGINE

class GenerateMetrics:
    def __init__(self, file_path: str, file_type: str):
        '''
        Initializes the GenerateMetrics class with file path and type.
        '''
        self.file_path = file_path
        self.file_reader = FileReader(file_path, file_type)
        self.df_lazy = self.file_reader.scan_lazy()
        self.report: Dict[str, Any] = {}

    def _get_numeric_stats(self, lazy_frame: pl.LazyFrame) -> List[Dict[str, Any]]:
        '''
        Calculates summary statistics for all numeric columns in a single lazy pass.
        '''
        numeric_cols = [col for col, dtype in self.file_reader.schema.items() if dtype.is_numeric()]
        if not numeric_cols:
            return []

        exprs = []
        for col in numeric_cols:
            exprs.extend([pl.col(col).null_count().alias(f"{col}_null_count"),
                          pl.col(col).mean().alias(f"{col}_mean"),
                          pl.col(col).std().alias(f"{col}_std"),
                          pl.col(col).min().alias(f"{col}_min"),
                          pl.col(col).max().alias(f"{col}_max"),
                          pl.col(col).median().alias(f"{col}_median"),
                          pl.col(col).skew().alias(f"{col}_skew"),
                          pl.col(col).kurtosis().alias(f"{col}_kurtosis")])

        result = lazy_frame.select(exprs).collect(engine=STREAMING_ENGINE).row(0, named=True)

        return [{"column": col,
                 "null_count": result[f"{col}_null_count"],
                 "mean": result[f"{col}_mean"],
                 "stddev": result[f"{col}_std"],
                 "min": result[f"{col}_min"],
                 "max": result[f"{col}_max"],
                 "median": result[f"{col}_median"],
                 "skew": result[f"{col}_skew"],
                 "kurtosis": result[f"{col}_kurtosis"]} for col in numeric_cols]

    def _get_text_stats(self, lazy_frame: pl.LazyFrame) -> List[Dict[str, Any]]:
        '''
        Calculates descriptive statistics for string and categorical columns.
        '''
        text_cols = [col for col, dtype in self.file_reader.schema.items()
                     if dtype in (pl.String, pl.Categorical)]
        
        if not text_cols:
            return []

        exprs = []
        for col in text_cols:
            exprs.extend([pl.col(col).null_count().alias(f"{col}_null_count"),
                          pl.col(col).n_unique().alias(f"{col}_distinct"),
                          pl.col(col).str.len_chars().min().alias(f"{col}_min_len"),
                          pl.col(col).str.len_chars().max().alias(f"{col}_max_len"),
                          pl.col(col).mode().first().alias(f"{col}_mode")])

        results = lazy_frame.select(exprs).collect(engine=STREAMING_ENGINE).row(0, named=True)

        return [{"column": col,
                 "null_count": results[f"{col}_null_count"],
                 "distinct_count": results[f"{col}_distinct"],
                 "min_length": results[f"{col}_min_len"],
                 "max_length": results[f"{col}_max_len"],
                 "most_occurred": results[f"{col}_mode"]} for col in text_cols]

    def _outlier_analysis(self, lazy_frame: pl.LazyFrame) -> List[Dict[str, Any]]:
        '''
        Identifies outliers using the IQR method, minimizing data collection.
        '''
        numeric_cols = [col for col, dtype in self.file_reader.schema.items() if dtype.is_numeric()]
        if not numeric_cols:
            return []

        bounds_exprs = []
        for col in numeric_cols:
            bounds_exprs.extend([pl.col(col).quantile(0.25).alias(f"{col}_q1"),
                                 pl.col(col).quantile(0.75).alias(f"{col}_q3")])
        
        bounds = lazy_frame.select(bounds_exprs).collect(engine=STREAMING_ENGINE).row(0, named=True)
        outlier_data = []

        for col in numeric_cols:
            q1, q3 = bounds[f"{col}_q1"], bounds[f"{col}_q3"]
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr

            outliers = (lazy_frame.filter((pl.col(col) < lower) | (pl.col(col) > upper))
                        .select(pl.col(col))
                        .collect(engine=STREAMING_ENGINE)
                        .to_series())

            if not outliers.is_empty():
                outlier_data.append({'column': col,
                                     'num_outliers': len(outliers),
                                     'min_outlier': outliers.min(),
                                     'max_outlier': outliers.max()})
        return outlier_data

    def _get_duplicate_stats(self, lazy_frame: pl.LazyFrame) -> Dict[str, Any]:
        '''
        Calculates duplicate row counts using lazy aggregation.
        '''
        total_rows = self.file_reader.height
        if total_rows == 0:
            return {'total_duplicates': 0, 'duplicate_percentage': 0}

        dupe_count = (lazy_frame.group_by(self.file_reader.columns)
                      .agg(pl.len().alias('count'))
                      .filter(pl.col('count') > 1)
                      .select((pl.col('count') - 1).sum())
                      .collect(engine=STREAMING_ENGINE)
                      .item()) or 0
        
        return {'total_duplicates': dupe_count,
                'duplicate_percentage': (dupe_count / total_rows) * 100}

    def _get_missing_stats(self, lazy_frame: pl.LazyFrame) -> Dict[str, Any]:
        '''
        Computes missing value statistics for the entire dataset.
        '''
        cols = self.file_reader.columns
        result = lazy_frame.select([pl.col(c).null_count() for c in cols]).collect(engine=STREAMING_ENGINE)
        missing_per_col = result.row(0, named=True)
        total_missing = sum(missing_per_col.values())
        total_cells = self.file_reader.height * self.file_reader.width

        return {"total_missing_cells": total_missing,
                "missing_percentage": (total_missing / total_cells) * 100 if total_cells > 0 else 0,
                "missing_per_column": missing_per_col}

    def _get_cardinality_stats(self, lazy_frame: pl.LazyFrame) -> Dict[str, Any]:
        '''
        Calculates unique value counts per column.
        '''
        result = lazy_frame.select([pl.col(c).n_unique() for c in self.file_reader.columns]).collect(engine=STREAMING_ENGINE)
        return {"unique_rows": self.file_reader.height,
                "cardinality_per_column": result.row(0, named=True)}

    def _get_value_counts(self, lazy_frame: pl.LazyFrame) -> Dict[str, List[Dict[str, Any]]]:
        '''
        Retrieves top 5 value distributions for non-numeric columns.
        '''
        non_num = [c for c, d in self.file_reader.schema.items() if not d.is_numeric()]
        return {col: (lazy_frame.select(col).group_by(col).agg(pl.len().alias("count"))
                .sort("count", descending=True).head(5).collect(engine=STREAMING_ENGINE).to_dicts())
                for col in non_num}

    def _generate_overview_metrics(self, lazy_frame: pl.LazyFrame):
        '''
        Generates high-level file information and data shape metrics.
        '''
        self.report['Information'] = {'Csv file name': self.file_path.split('/')[-1],
                                      'Date of Generation': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self.report['Data Shape'] = {'total row count': self.file_reader.height,
                                     'total col count': self.file_reader.width,
                                     'Data Insights': {'duplicates': self._get_duplicate_stats(lazy_frame),
                                                       'missing_values': self._get_missing_stats(lazy_frame),
                                                       'cardinality': self._get_cardinality_stats(lazy_frame)}}

    def _generate_column_metrics(self, lazy_frame: pl.LazyFrame):
        '''
        Generates detailed statistics for numeric and text columns.
        '''
        self.report['Data Types'] = [{'column': k, 'dtype': str(v)} for k, v in self.file_reader.schema.items()]
        self.report['Numeric Column Statistics'] = self._get_numeric_stats(lazy_frame)
        self.report['Text Column Statistics'] = self._get_text_stats(lazy_frame)

    def _generate_additional_metrics(self, lazy_frame: pl.LazyFrame):
        '''
        Generates sample data rows, outlier data, and value counts.
        '''
        self.report['Sample Data'] = lazy_frame.head(15).collect(engine=STREAMING_ENGINE).to_dicts()
        self.report['Outlier Analysis'] = self._outlier_analysis(lazy_frame)
        self.report['Value Counts'] = self._get_value_counts(lazy_frame)

    def generate_report(self) -> Dict[str, Any]:
        '''
        Executes the full metrics generation pipeline and returns the report.
        '''
        self._generate_overview_metrics(self.df_lazy)
        self._generate_column_metrics(self.df_lazy)
        self._generate_additional_metrics(self.df_lazy)
        return self.report