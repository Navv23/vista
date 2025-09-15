import polars as pl
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepInFrame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from typing import Dict, Any, List, Optional

class PDFWriter:
    def __init__(self, filename: str):
        self.filename = filename
        self.doc = SimpleDocTemplate(self.filename, pagesize=letter,
                                     leftMargin=72, rightMargin=72, topMargin=72, bottomMargin=72)
        self.styles = getSampleStyleSheet()
        self.story = []
        
        self.styles['Normal'].fontSize = 10
        self.styles['Normal'].fontName = 'Helvetica'

        self.styles.add(ParagraphStyle(name='ReportTitle', fontSize=28, spaceAfter=24, alignment=1, fontName='Helvetica-Bold', textColor=colors.HexColor('#2C3E50')))
        self.styles.add(ParagraphStyle(name='SectionTitle', fontSize=18, spaceAfter=12, alignment=0, fontName='Helvetica-Bold', textColor=colors.HexColor('#34495E')))
        self.styles.add(ParagraphStyle(name='SubSection', fontSize=14, spaceAfter=8, alignment=0, fontName='Helvetica-Oblique', textColor=colors.HexColor('#7F8C8D')))
        self.styles.add(ParagraphStyle(name='TableCaption', fontSize=10, spaceAfter=6, alignment=0, fontName='Helvetica-Oblique', textColor=colors.HexColor('#95A5A6')))

    def _add_section_title(self, text: str):
        self.story.append(Spacer(1, 24))
        self.story.append(Paragraph(text, self.styles['SectionTitle']))
        self.story.append(Spacer(1, 12))

    def _add_subsection_title(self, text: str):
        self.story.append(Spacer(1, 12))
        self.story.append(Paragraph(text, self.styles['SubSection']))
        self.story.append(Spacer(1, 6))

    def _add_table(self, data: List[List[Any]], caption: str = ""):
        if not data or not data[0]:
            return
            
        num_cols = len(data[0])
        col_widths = [self.doc.width / num_cols] * num_cols

        table_style = TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#EAEAEA')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ECF0F1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9F9F9')])
        ])
        
        wrapped_data = []
        for row in data:
            wrapped_row = [Paragraph(str(cell), self.styles['Normal']) for cell in row]
            wrapped_data.append(wrapped_row)

        t = Table(wrapped_data, col_widths)
        t.setStyle(table_style)
        
        if caption:
            self.story.append(Paragraph(caption, self.styles['TableCaption']))

        self.story.append(t)
        self.story.append(Spacer(1, 18))

    def _add_report_overview(self, report: Dict[str, Any]):
        self._add_section_title("1. Report Overview")
        info_data = [
            ["File Name:", report['Information']['Csv file name']],
            ["Date of Generation:", report['Information']['Date of Generation']]
        ]
        self._add_table(info_data)
        self.story.append(Spacer(1, 12))

    def _add_data_shape_and_insights(self, report: Dict[str, Any]):
        self._add_section_title("2. Data Shape")
        shape_data = [
            ["Total Rows:", f"{report['Data Shape']['total row count']:,}"],
            ["Total Columns:", f"{report['Data Shape']['total col count']:,}"]
        ]
        self._add_table(shape_data)
        self._add_subsection_title("Data Insights")
        duplicate_data = [
            ["Total Duplicates:", f"{report['Data Shape']['Data Insights']['duplicates']['total_duplicates']:,}"],
            ["Duplicate Percentage:", f"{report['Data Shape']['Data Insights']['duplicates']['duplicate_percentage']:.2f}%"]
        ]
        self._add_table(duplicate_data, "Summary of duplicate rows.")
        missing_data = [
            ["Total Missing Cells:", f"{report['Data Shape']['Data Insights']['missing_values']['total_missing_cells']:,}"],
            ["Missing Percentage:", f"{report['Data Shape']['Data Insights']['missing_values']['missing_percentage']:.2f}%"]
        ]
        self._add_table(missing_data, "Summary of missing values.")
        cardinality_data = [
            ["Unique Rows:", f"{report['Data Shape']['Data Insights']['cardinality']['unique_rows']:,}"]
        ]
        self._add_table(cardinality_data, "Total number of unique rows.")
        self.story.append(PageBreak())

    def _add_column_metrics(self, report: Dict[str, Any]):
        self._add_section_title("3. Data Types and Column Metrics")
        self._add_subsection_title("3.1 Data Types")
        dtype_data = [["Column Name", "Data Type"]]
        for item in report['Data Types']:
            dtype_data.append([item['column'], item['dtype']])
        self._add_table(dtype_data)
        self.story.append(Spacer(1, 12))
        
        if report['Numeric Column Statistics']:
            self._add_subsection_title("3.2 Numeric Column Statistics")
            numeric_headers = ["Column", "Nulls", "Mean", "Std Dev", "Min", "Max", "Median"]
            numeric_data = [numeric_headers]
            for stats in report['Numeric Column Statistics']:
                numeric_data.append([
                    stats['column'],
                    f"{stats['null_count']:,}",
                    f"{stats['mean']:.2f}",
                    f"{stats['stddev']:.2f}",
                    f"{stats['min']:.2f}",
                    f"{stats['max']:.2f}",
                    f"{stats['median']:.2f}"
                ])
            self._add_table(numeric_data)
            self.story.append(Spacer(1, 12))

        if report['Text Column Statistics']:
            self._add_subsection_title("3.3 Text Column Statistics")
            text_headers = ["Column", "Nulls", "Distinct Count", "Min Length", "Max Length", "Most Occurred"]
            text_data = [text_headers]
            for stats in report['Text Column Statistics']:
                text_data.append([
                    stats['column'],
                    f"{stats['null_count']:,}",
                    f"{stats['distinct_count']:,}",
                    stats['min_length'],
                    stats['max_length'],
                    stats['most_occurred']
                ])
            self._add_table(text_data)
            self.story.append(Spacer(1, 12))
        self.story.append(PageBreak())

    def _add_outlier_analysis(self, report: Dict[str, Any]):
        if report['Outlier Analysis']:
            self._add_section_title("4. Outlier Analysis")
            outlier_headers = ["Column", "Num Outliers", "Min Outlier Value", "Max Outlier Value"]
            outlier_data = [outlier_headers]
            for stats in report['Outlier Analysis']:
                outlier_data.append([
                    stats['column'],
                    f"{stats['num_outliers']:,}",
                    f"{stats['min_outlier']:.2f}",
                    f"{stats['max_outlier']:.2f}"
                ])
            self._add_table(outlier_data)
            self.story.append(Spacer(1, 12))

    def _add_sample_data(self, report: Dict[str, Any]):
        if report['Sample Data']:
            self._add_section_title("5. Sample Data")
            sample_data_table = [["Column Name", "First 3 Values"]]
            columns = list(report['Sample Data'][0].keys())
            for col in columns:
                values = [str(row.get(col, '')) for row in report['Sample Data'][:3]]
                formatted_values = ", ".join(values)
                sample_data_table.append([col, formatted_values])
            self._add_table(sample_data_table)
            self.story.append(Spacer(1, 12))

    def _add_value_counts(self, report: Dict[str, Any]):
        if report['Value Counts']:
            self.story.append(PageBreak())
            self._add_section_title("6. Value Counts per Column")
            for column, counts in report['Value Counts'].items():
                self.story.append(Spacer(1, 12))
                self._add_subsection_title(f"Top 5 Values for '{column}'")
                value_counts_data = [["Value", "Count"]]
                for item in counts:
                    value = item.get(column, '')
                    count = item.get('count', 0)
                    value_counts_data.append([value, f"{count:,}"])
                self._add_table(value_counts_data)
                
    def write_report(self, report: Dict[str, Any]):
        self.story.append(Paragraph("VISTA Data Quality Report", self.styles['ReportTitle']))
        self.story.append(Spacer(1, 24))
        self._add_report_overview(report)
        self._add_data_shape_and_insights(report)
        self._add_column_metrics(report)
        self._add_outlier_analysis(report)
        self._add_sample_data(report)
        self._add_value_counts(report)
        self.doc.build(self.story)