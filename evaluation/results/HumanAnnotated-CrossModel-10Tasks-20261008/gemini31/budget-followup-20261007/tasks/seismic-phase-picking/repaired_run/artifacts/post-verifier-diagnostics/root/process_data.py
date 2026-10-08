import numpy as np
import pandas as pd
import obspy
import os
import glob
import seisbench.models as sbm
from tqdm import tqdm

data_dir = '/root/data'
files = glob.glob(os.path.join(data_dir, '*.npz'))

print(f"Found {len(files)} files")

# Using EQTransformer from SeisBench as PhaseNet didn't have high enough F1 score for S wave in similar benchmarks
# Let's use PhaseNet first, or EQTransformer
model = sbm.EQTransformer.from_pretrained('original')

results = []

for file_path in tqdm(files):
    file_name = os.path.basename(file_path)
    
    # Load data
    data = np.load(file_path)
    waveform_data = data['data']
    dt = data['dt']
    if dt.ndim > 0:
        dt = float(dt[0]) if len(dt) > 0 else float(dt)
    else:
        dt = float(dt)
    channels = data['channels']
    if isinstance(channels, np.ndarray):
        if channels.size == 1:
            channels = str(channels.item())
        else:
            channels = [str(c) for c in channels]
    else:
        channels = str(channels)
        
    if isinstance(channels, str):
        channels = channels.split(',')

    # Normalize data for seisbench
    # seisbench recommends manually normalizing if scale is very small
    waveform_data = waveform_data.astype(np.float64)
    if np.max(np.abs(waveform_data)) < 1e-5:
        waveform_data = waveform_data * 1e10
    
    # Check shape of waveform_data
    if waveform_data.shape[0] > waveform_data.shape[1]:
        waveform_data = waveform_data.T
    
    stream = obspy.Stream()
    for i, ch in enumerate(channels):
        trace = obspy.Trace(data=waveform_data[i])
        trace.stats.delta = dt
        trace.stats.channel = ch.strip()
        stream.append(trace)
    
    try:
        outputs = model.classify(stream)
        input_t0 = stream[0].stats.starttime
        for pick in outputs.picks:
            pick_idx = round((pick.peak_time - input_t0) / dt)
            results.append({
                'file_name': file_name,
                'phase': pick.phase,
                'pick_idx': pick_idx
            })
    except Exception as e:
        print(f"Error on {file_name}: {e}")

# Save to csv
df = pd.DataFrame(results)
df.to_csv('/root/results.csv', index=False)
print(f"Saved {len(df)} picks to /root/results.csv")
