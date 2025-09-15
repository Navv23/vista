import polars as pl
from datetime import datetime
from typing import Dict, Any, List, Optional
from vista.io.file_reader import FileReader

class GenerateMetrics:
    def __init__(self, file_path: str, file_type: str):
        self.file_path = file_path
        self.file_reader = FileReader(file_path, file_type)
        self.df_lazy = self.file_reader.read(lazy=True)
        self.df_full: Optional[pl.DataFrame] = None
        self.report: Dict[str, Any] = {}

    def _get_df_full(self):
        if self.df_full is None:
            self.df_full = self.df_lazy.collect()
        return self.df_full

    def _get_numeric_stats(self) -> List[Dict[str, Any]]:
        numeric_stats = []
        numeric_cols = [col for col, dtype in self.df_full.schema.items() if dtype.is_numeric()]
        
        if not numeric_cols:
            return numeric_stats
        
        df_num = self.df_full.select(numeric_cols)
        
        for col in numeric_cols:
            stats = {'column': col,
                     'null_count': df_num[col].is_null().sum(),
                     'mean': df_num[col].mean(),
                     'stddev': df_num[col].std(),
                     'min': df_num[col].min(),
                     'max': df_num[col].max(),
                     'median': df_num[col].median(),
                     'skew': df_num[col].skew(),
                     'kurtosis': df_num[col].kurtosis()}
            numeric_stats.append(stats)
            
        return numeric_stats
        
    def _get_text_stats(self) -> List[Dict[str, Any]]:
        text_stats = []
        text_cols = [col for col, dtype in self.df_full.schema.items() if isinstance(dtype, (pl.Utf8, pl.Categorical))]
        
        if not text_cols:
            return text_stats
            
        for col in text_cols:
            df_col = self.df_full.select(pl.col(col))
            
            stats = {'column': col,
                     'null_count': df_col[col].is_null().sum(),
                     'distinct_count': df_col[col].n_unique(),
                     'min_length': df_col[col].str.len_chars().min(),
                     'max_length': df_col[col].str.len_chars().max(),
                     'most_occurred': df_col.group_by(col).agg(pl.len().alias('count')).sort('count', descending=True).head(1).select(pl.col(col)).item()}
            text_stats.append(stats)
            
        return text_stats
        
    def _outlier_analysis(self) -> List[Dict[str, Any]]:
        outlier_data = []
        numeric_cols = [col for col, dtype in self.df_full.schema.items() if dtype.is_numeric()]
        
        if not numeric_cols:
            return outlier_data
            
        for col in numeric_cols:
            q1 = self.df_full[col].quantile(0.25)
            q3 = self.df_full[col].quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outliers = self.df_full.filter(
                (pl.col(col) < lower_bound) | (pl.col(col) > upper_bound)
            ).select(pl.col(col)).to_series()
            
            if outliers.len() > 0:
                outlier_data.append({
                    'column': col,
                    'num_outliers': outliers.len(),
                    'min_outlier': outliers.min(),
                    'max_outlier': outliers.max(),
                })
        return outlier_data

    def _get_duplicate_stats(self) -> Dict[str, Any]:
        df = self._get_df_full()
        total_rows = df.height
        duplicate_rows_df = df.group_by(df.columns).agg(pl.len().alias('count')).filter(pl.col('count') > 1)
        total_duplicates = duplicate_rows_df['count'].sum() - duplicate_rows_df.height
        duplicate_percentage = (total_duplicates / total_rows) * 100 if total_rows > 0 else 0
        return {'total_duplicates': total_duplicates,
                'duplicate_percentage': duplicate_percentage}

    def _get_missing_stats(self) -> Dict[str, Any]:
        df = self._get_df_full()
        total_cells = df.height * df.width
        missing_per_col = {col: df[col].is_null().sum() for col in df.columns}
        total_missing = sum(missing_per_col.values())
        missing_percentage = (total_missing / total_cells) * 100 if total_cells > 0 else 0
        return {'total_missing_cells': total_missing,
                'missing_percentage': missing_percentage,
                'missing_per_column': missing_per_col}

    def _get_cardinality_stats(self) -> Dict[str, Any]:
        df = self._get_df_full()
        unique_rows = df.unique().height
        cardinality_per_col = {col: df[col].n_unique() for col in df.columns}
        return {'unique_rows': unique_rows,
                'cardinality_per_column': cardinality_per_col}
        
    def _get_value_counts(self) -> Dict[str, List[Dict[str, Any]]]:
        value_counts = {}
        non_numeric_cols = [col for col, dtype in self.df_full.schema.items() if not dtype.is_numeric()]
        
        for col in non_numeric_cols:
            vc = self.df_full.group_by(col).agg(pl.len().alias('count')).sort('count', descending=True).head(5)
            value_counts[col] = vc.to_dicts()
            
        return value_counts

    def _generate_overview_metrics(self):
        self.report['Information'] = {'Csv file name': self.file_path.split('/')[-1],
                                      'Date of Generation': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        self.report['Data Shape'] = {'total row count': self.df_full.height,
                                     'total col count': self.df_full.width,
                                     'Data Insights': {
                                         'duplicates': self._get_duplicate_stats(),
                                         'missing_values': self._get_missing_stats(),
                                         'cardinality': self._get_cardinality_stats()}}
    
    def _generate_column_metrics(self):
        self.report['Data Types'] = [{'column': k, 'dtype': str(v)} for k, v in self.df_full.schema.items()]
        self.report['Numeric Column Statistics'] = self._get_numeric_stats()
        self.report['Text Column Statistics'] = self._get_text_stats()
    
    def _generate_additional_metrics(self):
        self.report['Sample Data'] = self.df_full.head(15).to_dicts()
        self.report['Outlier Analysis'] = self._outlier_analysis()
        self.report['Value Counts'] = self._get_value_counts()

    def generate_report(self):
        self._get_df_full()
        self._generate_overview_metrics()
        self._generate_column_metrics()
        self._generate_additional_metrics()
        return self.report