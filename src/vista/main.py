import polars as pl
import sys
import argparse
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.append(str(project_root))

from vista.core.metrics import GenerateMetrics
from vista.io.report_generator import PDFWriter

def main():
    parser = argparse.ArgumentParser(description="Generate a data quality report for a given file.")
    parser.add_argument('--file_path',
                        type=str,
                        help="The path to the input data file (e.g., /path/to/data.csv)")
    
    parser.add_argument('--file_type',
                        type=str,
                        default='csv',
                        help="The type of the input file (e.g., csv, parquet). Defaults to 'csv'.")
    
    parser.add_argument('--output_path',
                        type=str,
                        default='vista_report.pdf',
                        help="The path where the output PDF report will be saved. Defaults to 'vista_report.pdf'.")
    
    args = parser.parse_args()

    try:
        profiler = GenerateMetrics(file_path=args.file_path, 
                                   file_type=args.file_type)
        report = profiler.generate_report()
        
        pdf_writer = PDFWriter(args.output_path)
        pdf_writer.write_report(report)
        
        print(f"Data profiling complete! Report saved to '{args.output_path}'.")

    except FileNotFoundError:
        print(f"Error: The file '{args.file_path}' was not found. Please check the file path.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()