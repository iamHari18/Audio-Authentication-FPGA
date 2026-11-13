import librosa
import numpy as np
import sounddevice as sd
import serial
import time
import matplotlib.pyplot as plt

# --- 1. CONFIGURATION ---
REFERENCE_FILE = "rtm.wav"   # Recorded reference passphrase: "Open the door"
DURATION = 3                 # 3-second recording window
SAMPLE_RATE = 16000
FPGA_PORT = 'COM4'           # Serial port of the FPGA (PROG/UART)
THRESHOLD = 3.8              # DTW dissimilarity threshold

# --- 2. SETUP SERIAL (FPGA) ---
try:
    ser = serial.Serial(FPGA_PORT, 9600, timeout=1)
    time.sleep(2)
    print(f"Connected to FPGA on {FPGA_PORT}")
except Exception as e:
    print(f"WARNING: Could not connect to FPGA: {e}")
    ser = None


def record_audio(duration, fs):
    print("---------------------------------------")
    print(f"LISTENING...SAY:'OPEN THE DOOR' ({duration}s)")
    print("---------------------------------------")
    myrecording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='float32')
    sd.wait()
    print("         DONE RECORDING.")
    return myrecording.flatten(), fs


def prep_audio(y, sr):
    y_trimmed, _ = librosa.effects.trim(y, top_db=20)
    y_norm = librosa.util.normalize(y_trimmed)
    return y_norm


def extract_features(y, sr):
    # n_fft=400 creates a 25ms window to identify pitch texture
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, n_fft=400, hop_length=160)
    mfcc = mfcc[1:]
    mfcc = (mfcc - np.mean(mfcc, axis=1, keepdims=True)) / (np.std(mfcc, axis=1, keepdims=True) + 1e-6)

    # --- PITCH CALCULATION ---
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr, fmin=75, fmax=400)
    index = magnitudes.argmax()
    pitch_val = pitches.flatten()[index]
    return mfcc, pitch_val


# --- 3. MAIN EXECUTION ---
try:
    y_ref, sr_ref = librosa.load(REFERENCE_FILE, sr=SAMPLE_RATE)
    y_ref = prep_audio(y_ref, sr_ref)
    feat_ref, pitch_ref = extract_features(y_ref, sr_ref)

    input("Press Enter to start recording...")
    y_live, sr_live = record_audio(DURATION, SAMPLE_RATE)
    y_live = prep_audio(y_live, sr_live)
    feat_live, pitch_live = extract_features(y_live, sr_live)

    # DTW comparison
    D, wp = librosa.sequence.dtw(feat_ref, feat_live, metric='euclidean')
    dist = D[-1, -1] / wp.shape[0]

    print("=" * 40)
    print(f"Dissimilarity Score: {dist:.4f}")
    print(f"Average Pitch: {pitch_live:.2f} Hz")
    print("=" * 40)

    if dist < THRESHOLD:
        print("RESULT: MATCH DETECTED! -> UNLOCKING")
        if ser:
            ser.write(b'1')
            ser.flush()
    else:
        print("RESULT: NO MATCH -> LOCKING")
        if ser:
            ser.write(b'0')
            ser.flush()

    # --- FULL CROSS-CORRELATION ---
    # Use MFCC mean vectors for meaningful comparison
    ref_vec = np.mean(feat_ref, axis=1)
    live_vec = np.mean(feat_live, axis=1)

    correlation = np.correlate(ref_vec, live_vec, mode='full')
    lags = np.arange(-len(live_vec) + 1, len(ref_vec))

    plt.figure(figsize=(10, 4))
    plt.plot(lags, correlation, color='r')
    plt.title(f'Full Audio Cross-Correlation\nLive Pitch: {pitch_live:.2f} Hz ')
    plt.xlabel('Time Lag (seconds)')
    plt.ylabel('Amplitude')
    plt.grid(True)
    plt.show()

    time.sleep(0.5)
    if ser:
        ser.close()

except Exception as e:
    print(f"Error: {e}")
    if ser:
        ser.close()
