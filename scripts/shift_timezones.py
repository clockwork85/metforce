import os
import sys

import pandas as pd
from openpyxl import load_workbook
def read_units_row(file_path: str) -> pd.DataFrame:
    """
    Read the units row from an Excel file.

    Parameters
    ----------
    file_path : str
        The path to the Excel file.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the units row.
    """
    return pd.read_excel(file_path, nrows=1, engine='openpyxl')


def write_excel_with_two_headers(df: pd.DataFrame, units_df: pd.DataFrame, output_file_path: str, sheet_name: str = 'Sheet1') -> None:
    """
    Write a DataFrame to an Excel file with two rows of headers.
    If the Excel file already exists, the function will append the DataFrame to a new sheet.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to write.
    units_df : pd.DataFrame
        The DataFrame containing the units row.
    output_file_path : str
        The path to the output Excel file.
    sheet_name : str, optional
        The name of the sheet where the DataFrame will be written. Default is 'Sheet1'.
    """

    # Get rid of the timezone in the TIMESTAMP column
    df['TIMESTAMP'] = df['TIMESTAMP'].dt.tz_localize(None)

    print(f'{df=}')

    # Write the DataFrame to Excel
    df.to_excel(output_file_path, index=False, sheet_name=sheet_name)

def read_and_convert_time_zone(file_path: str, original_time_zone: str) -> pd.DataFrame:
    """
    Read an Excel file and convert the time zone of the TIMESTAMP column to UTC.

    Parameters
    ----------
    file_path : str
        The path to the Excel file.
    original_time_zone : str
        The original time zone in which the TIMESTAMP is set.

    Returns
    -------
    pd.DataFrame
        A DataFrame with the TIMESTAMP column converted to UTC.
    """

    # Read the Excel file into a DataFrame, skipping the row containing units
    df = pd.read_excel(file_path, skiprows=[1])

    # Convert the 'TIMESTAMP' column to a pandas datetime object
    df['TIMESTAMP'] = pd.to_datetime(df['TIMESTAMP'])

    # Set the time zone for the 'TIMESTAMP' column to its original time zone
    df['TIMESTAMP'] = df['TIMESTAMP'].dt.tz_localize(original_time_zone)

    # Convert the time zone to UTC
    df['TIMESTAMP'] = df['TIMESTAMP'].dt.tz_convert('UTC')

    return df

if __name__ == '__main__':

    file_path = sys.argv[1]
    original_time_zone = sys.argv[2]

    basename = file_path.split('/')[-1].split('.')[0]
    output_file_path = f"{basename}_UTC.xlsx"

    if os.path.isfile(output_file_path):
        os.remove(output_file_path)

    met_unit_row = read_units_row(file_path)

    converted_df = read_and_convert_time_zone(file_path, original_time_zone)

    write_excel_with_two_headers(converted_df, met_unit_row, output_file_path)