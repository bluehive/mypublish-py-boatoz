import pandas as pd

from boatoz.analysis import summarize

print(summarize(pd.read_csv("data/sample_races.csv")))
