#!/usr/bin/env python3

import sys
from typing import List

from loguru import logger
import numpy as np
import pandas as pd


def concat_excel(filenames: List[str]):
    dfs = []

    for filename in filenames:
        logger.info(f"Processing file {filename}")
        df = pd.read_excel(filename, skiprows=[1], index_col=0)
        df.drop_duplicates(inplace=True)

        dfs.append(df)

    df_concat = pd.concat(dfs, axis=1)

    return df_concat


if __name__ == "__main__":

    outfile = sys.argv[1]
    args = sys.argv[2:]

    logger.debug(f"Args: {args}")
    df_concat = concat_excel(args)

    df_concat.reset_index(inplace=True)

    df_concat.rename(columns={df_concat.columns[0]: "TIMESTAMP"}, inplace=True)
    df_concat.replace("", np.nan, inplace=True)
    df_concat.dropna(axis=1, how="all", inplace=True)
    df_concat.dropna(inplace=True)
    blank_row = pd.DataFrame([[""] * len(df_concat.columns)], columns=df_concat.columns)
    df_concat = pd.concat([blank_row, df_concat.iloc[:]]).reset_index(drop=True)
    logger.debug(f"df_concat: {df_concat=}")
    logger.info(f"Saving the file to: {outfile}")
    df_concat.to_excel(outfile, index=False)
