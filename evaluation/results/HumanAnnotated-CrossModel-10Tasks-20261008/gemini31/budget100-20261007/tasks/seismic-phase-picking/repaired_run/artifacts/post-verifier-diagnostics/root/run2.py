import os
import glob
import numpy as np
import pandas as pd
import obspy
import seisbench.models as sbm
from tqdm import tqdm
import logging
logging.getLogger("obspy").setLevel(logging.ERROR)

data_dir = '/root/data/'
result_file = '/root/results2.csv'

files = glob.glob(os.path.join(data_dir, '*.npz'))
print(f"Found {len(files)} files.")

# Try EQTransformer
model = sbm.EQTransformer.from_pretrained("original")

results = []

for file_path in tqdm(files):
    file_name = os.path.basename(file_path)
    data = np.load(file_path)
    
    waveform = data['data']
    dt = float(data['dt'])
    channels = str(data['channels']).split(',')
    
    # Standardize data to have zero mean and unit variance per channel
    # This is better than arbitrary scaling
    waveform_std = []
    for c in range(waveform.shape[1] if waveform.shape == (12000, 3) else waveform.shape[0]):
        c_data = waveform[:, c] if waveform.shape == (12000, 3) else waveform[c, :]
        c_data = (c_data - np.mean(c_data)) / (np.std(c_data) + 1e-10)
        waveform_std.append(c_data)
        
    waveform = np.array(waveform_std)
    
    traces = []
    for i, channel in enumerate(channels):
        tr = obspy.Trace(data=waveform[i])
        tr.stats.sampling_rate = 1.0 / dt
        tr.stats.channel = channel
        traces.append(tr)
        
    stream = obspy.Stream(traces)
    
    input_t0 = stream[0].stats.starttime
    input_dt = stream[0].stats.delta
    input_npts = stream[0].stats.npts
    
    outputs = model.classify(stream)
    
    for pick in outputs.picks:
        pick_idx = round((pick.peak_time - input_t0) / input_dt)
        if 0 <= pick_idx < input_npts:
            results.append({
                'file_name': file_name,
                'phase': pick.phase,
                'pick_idx': pick_idx
            })

df = pd.DataFrame(results)
df.to_csv(result_file, index=False)
print(f"Saved results to {result_file}")
