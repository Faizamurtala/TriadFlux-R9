import numpy as np, pandas as pd, os

rng=np.random.default_rng(7)
n=9000
idx=pd.date_range("2025-01-01", periods=n, freq="15min")
reg=np.repeat([0,1,2,1], [2200,2200,2200,2400])[:n]
ret=np.zeros(n)
for i in range(n):
    if reg[i]==0: drift,vol=0.00008,0.002
    elif reg[i]==1: drift,vol=0.0,0.0012
    else: drift,vol=0.0,0.005
    ret[i]=drift+vol*rng.normal()
price=100*np.exp(np.cumsum(ret))
close=price
open_=np.r_[price[0],price[:-1]]
spread=np.abs(rng.normal(0,0.0015,n))*price
high=np.maximum(open_,close)+spread
low=np.minimum(open_,close)-spread
volume=np.exp(rng.normal(10,0.35,n))
df=pd.DataFrame({"timestamp":idx,"open":open_,"high":high,"low":low,"close":close,"volume":volume})
os.makedirs("data",exist_ok=True)
df.to_csv("data/sample_ohlcv.csv",index=False)
print("Wrote data/sample_ohlcv.csv")
