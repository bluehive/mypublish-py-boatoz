import pandas as pd

from boatoz.analysis import recent_races

print(recent_races(pd.read_csv("data/sample_races.csv"), 5))
