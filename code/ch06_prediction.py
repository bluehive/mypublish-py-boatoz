import pandas as pd

from boatoz.model import evaluate

print(evaluate(pd.read_csv("data/sample_races.csv")))
