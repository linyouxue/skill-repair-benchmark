import numpy as np

file_path = '/root/data/BG.ACR..DP.0215954.npz'
data = np.load(file_path)
for k in data.files:
    if k != 'data':
        print(k, data[k])
