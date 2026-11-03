import pandas as pd

from boatoz.plot import scatter

scatter(pd.read_csv("data/sample_races.csv"), "output/motor-scatter.png")
