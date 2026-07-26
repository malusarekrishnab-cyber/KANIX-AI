import time
import queue
import threading
import numpy as np
import sounddevice as sd

class VADMic:
    def __init__(self, sample_rate=16000, threshold=500, silence_duration=1.5):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.silence_duration = silence_duration
        self.audio_queue = queue.Queue()
        
        self._cooldown_until = 0.0
        self._cooldown_lock = threading.Lock()
        
    def start_cooldown(self, duration: float):
        """Ignore audio for the specified duration."""
        with self._cooldown_lock:
            self._cooldown_until = time.time() + duration
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break

    def is_in_cooldown(self) -> bool:
        with self._cooldown_lock:
            return time.time() < self._cooldown_until

    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_in_cooldown():
            return
            
        rms = np.sqrt(np.mean(indata**2)) * 32768
        if rms > self.threshold:
            self.audio_queue.put((indata.copy(), True)) 
        else:
            self.audio_queue.put((indata.copy(), False))

    async def listen(self) -> bytes:
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
                
        audio_buffer = []
        is_speaking = False
        silence_start_time = None
        
        stream = sd.InputStream(
            samplerate=self.sample_rate, 
            channels=1, 
            callback=self._audio_callback
        )
        
        with stream:
            while True:
                if self.is_in_cooldown():
                    time.sleep(0.1)
                    continue
                    
                try:
                    data, has_speech = self.audio_queue.get(timeout=0.1)
                    
                    if has_speech:
                        is_speaking = True
                        silence_start_time = None
                        audio_buffer.append(data)
                    elif is_speaking:
                        audio_buffer.append(data)
                        if silence_start_time is None:
                            silence_start_time = time.time()
                        elif time.time() - silence_start_time > self.silence_duration:
                            break
                            
                except queue.Empty:
                    pass
        
        if not audio_buffer:
            return b""
            
        self.start_cooldown(0.5) # Auto mini-cooldown after capturing
            
        audio_data = np.concatenate(audio_buffer)
        audio_data_int16 = (audio_data * 32767).astype(np.int16)
        return audio_data_int16.tobytes()