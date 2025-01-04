import serial
import wave
import numpy as np
import time
import threading
import queue

BUFFER_SIZE = 64  # Match ESP32's buffer size defined in the Arduino code

class ESP32AudioInterface:
    def __init__(self, port, baudrate=115200):
        """Initialize the ESP32 audio interface."""
        self.serial = serial.Serial(port, baudrate)
        self.recording = False
        self.playing = False
        self.audio_queue = queue.Queue()
        time.sleep(2)  # Wait for ESP32 to initialize
        
    def start_recording(self, duration_ms, filename=None):
        """Start recording audio from the ESP32's microphone."""
        if self.recording:
            print("Already recording!")
            return
            
        # Clear any existing data
        self.serial.reset_input_buffer()
        
        print("Sending record command...")
        self.serial.write(f"REC {duration_ms}\n".encode())
        self.serial.flush()
        
        # Wait for command confirmation
        while True:
            line = self.serial.readline()
            try:
                if b"###CMD_REC_OK###" in line:
                    break
            except UnicodeDecodeError:
                continue
        
        # Start recording thread
        self.recording = True
        self.record_thread = threading.Thread(
            target=self._record_thread,
            args=(duration_ms, filename)
        )
        self.record_thread.start()
        
    def _record_thread(self, duration_ms, filename):
        """Background thread to handle recording."""
        audio_data = bytearray()
        start_time = time.time()
        timeout = (duration_ms / 1000) + 1
        
        # Wait for start marker
        while self.recording:
            line = self.serial.readline()
            try:
                if b"###START_AUDIO###" in line:
                    break
            except UnicodeDecodeError:
                continue
        
        # Read audio data
        print("Recording audio data...")
        while self.recording and (time.time() - start_time) < timeout:
            if self.serial.in_waiting:
                chunk = self.serial.read(self.serial.in_waiting)
                try:
                    if b"###END_AUDIO###" in chunk:
                        end_pos = chunk.find(b"###END_AUDIO###")
                        audio_data.extend(chunk[:end_pos])
                        break
                    else:
                        audio_data.extend(chunk)
                except:
                    audio_data.extend(chunk)
        
        self.recording = False
        
        # Ensure we have an even number of bytes for 16-bit samples
        if len(audio_data) % 2 != 0:
            audio_data = audio_data[:-1]
        
        if len(audio_data) == 0:
            print("No audio data received!")
            return
        
        print(f"Received {len(audio_data)} bytes of audio data")
        
        if filename:
            try:
                # Convert to numpy array for processing
                samples = np.frombuffer(audio_data, dtype=np.int16)
                
                # Save to WAV file
                with wave.open(filename, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(8000)
                    wav_file.writeframes(samples.tobytes())
                print(f"Saved {len(samples)} samples to {filename}")
            except Exception as e:
                print(f"Error saving audio file: {e}")
        else:
            self.audio_queue.put(np.frombuffer(audio_data, dtype=np.int16))
    
    def start_playback(self, data):
        """Start playing audio through the ESP32's speaker."""
        # Stop any existing playback
        self.stop_playback()
        time.sleep(0.2)  # Give time for cleanup
        
        if isinstance(data, str):
            print(f"Loading WAV file: {data}")
            with wave.open(data, 'rb') as wav_file:
                data = wav_file.readframes(wav_file.getnframes())
        elif isinstance(data, np.ndarray):
            data = data.tobytes()
        
        # Clear any existing data
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()
        
        print("Sending PLAY command...")
        self.serial.write(b"PLAY\n")
        self.serial.flush()
        
        # Wait for command confirmation with timeout
        start_time = time.time()
        while True:
            if time.time() - start_time > 5:
                self.stop_playback()
                raise TimeoutError("No response to PLAY command")
            
            if self.serial.in_waiting:
                line = self.serial.readline()
                try:
                    decoded = line.decode().strip()
                    print(f"Received: {decoded}")
                    if "###CMD_PLAY_OK###" in decoded:
                        break
                    elif "Playback stopped" in decoded:
                        # ESP32 stopped previous playback
                        continue
                except UnicodeDecodeError:
                    continue
        
        # Wait for ready signal with timeout
        start_time = time.time()
        while True:
            if time.time() - start_time > 5:
                raise TimeoutError("No READY_FOR_AUDIO received")
            
            if self.serial.in_waiting:
                line = self.serial.readline()
                try:
                    decoded = line.decode().strip()
                    print(f"Received: {decoded}")
                    if "###READY_FOR_AUDIO###" in decoded:
                        break
                except UnicodeDecodeError:
                    continue
        
        # Send audio data in chunks
        print(f"Sending {len(data)} bytes of audio data...")
        chunk_size = 1024
        bytes_sent = 0
        
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            self.serial.write(chunk)
            self.serial.flush()
            bytes_sent += len(chunk)
            
            if bytes_sent % (chunk_size * 10) == 0:
                print(f"Sent {bytes_sent}/{len(data)} bytes")
            
            # Small delay to prevent buffer overflow
            time.sleep(0.001)
        
        print("Finished sending audio data")
        self.playing = False
    
    def stop_recording(self):
        """Stop recording."""
        if self.recording:
            self.recording = False
            self.serial.write(b"STOP_REC\n")
            self.serial.flush()
            self.record_thread.join()
    
    def stop_playback(self):
        """Stop playback."""
        if self.playing:
            print("Stopping playback...")
            self.playing = False
            self.serial.write(b"STOP_PLAY\n")
            self.serial.flush()
            
            # Wait for stop confirmation
            start_time = time.time()
            while time.time() - start_time < 1:  # 1 second timeout
                if self.serial.in_waiting:
                    try:
                        line = self.serial.readline().decode().strip()
                        if "Playback stopped" in line:
                            break
                    except:
                        pass
            
            # Clear any remaining data
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            time.sleep(0.1)
    
    def close(self):
        """Close the serial connection."""
        self.stop_playback()
        if hasattr(self, 'serial'):
            self.serial.close()
    
    def test_speaker(self, wav_file):
        """Simple speaker test routine."""
        print(f"\nTesting speaker with {wav_file}...")
        
        try:
            # Load and resample the WAV file if needed
            with wave.open(wav_file, 'rb') as wav:
                print(f"WAV file details:")
                print(f"- Channels: {wav.getnchannels()}")
                print(f"- Sample width: {wav.getsampwidth()} bytes")
                print(f"- Frame rate: {wav.getframerate()} Hz")
                print(f"- Number of frames: {wav.getnframes()}")
                print(f"- Duration: {wav.getnframes() / wav.getframerate():.2f} seconds")
                
                # Read the entire file
                data = wav.readframes(wav.getnframes())
                
                # If sample rate doesn't match, we need to resample
                if wav.getframerate() != 44100:
                    print(f"Resampling from {wav.getframerate()}Hz to 44100Hz")
                    import numpy as np
                    from scipy import signal
                    
                    # Convert bytes to numpy array
                    samples = np.frombuffer(data, dtype=np.int16)
                    
                    # Resample
                    samples_44k = signal.resample(samples, int(len(samples) * 44100 / wav.getframerate()))
                    
                    # Convert back to bytes
                    data = samples_44k.astype(np.int16).tobytes()
            
            # Reset serial connection
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            print("\nSending PLAY command...")
            self.serial.write(b"PLAY\n")
            self.serial.flush()
            
            # Wait for ready signal with timeout
            start_time = time.time()
            while True:
                if time.time() - start_time > 5:
                    print("Timeout waiting for ESP32 ready signal")
                    return
                    
                if self.serial.in_waiting:
                    line = self.serial.readline()
                    try:
                        decoded = line.decode().strip()
                        print(f"ESP32: {decoded}")
                        if "###READY_FOR_AUDIO###" in decoded:
                            break
                    except UnicodeDecodeError:
                        continue
            
            # Send audio data in chunks
            chunk_size = BUFFER_SIZE * 2  # Match ESP32's buffer size
            total_bytes = len(data)
            bytes_sent = 0
            
            print(f"\nSending {total_bytes} bytes of audio data...")
            
            while bytes_sent < total_bytes:
                # Send a chunk
                chunk = data[bytes_sent:bytes_sent + chunk_size]
                self.serial.write(chunk)
                self.serial.flush()
                
                # Update progress every ~10%
                bytes_sent += len(chunk)
                if bytes_sent % (total_bytes // 10) == 0:
                    print(f"Progress: {bytes_sent}/{total_bytes} bytes ({(bytes_sent/total_bytes)*100:.1f}%)")
                
                # Small delay to prevent buffer overflow
                time.sleep(0.001)
            
            print("Finished sending audio data")
            
            # Wait for playback completion
            print("Waiting for playback to complete...")
            self.serial.write(b"STOP_PLAY\n")
            self.serial.flush()
            
        except Exception as e:
            print(f"Error during playback: {e}")
            self.serial.write(b"STOP_PLAY\n")
            self.serial.flush()
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

    def test_audio_modes(self, wav_file):
        """Test different audio output methods."""
        print("\nTesting three audio modes...")

        # 3. ESP32-generated tone
        print("\n3. Testing ESP32-generated tone...")
        self.serial.write(b"GENERATE_TONE\n")
        
        if self._wait_for_ready():
            time.sleep(1)
        
        self.serial.write(b"STOP\n")

        # 1. WAV file test (1 second)
        print("\n1. Testing WAV playback...")
        with wave.open(wav_file, 'rb') as wav:
            # Read only first second
            frames_to_read = wav.getframerate()
            data = wav.readframes(frames_to_read)
            
        self.serial.write(b"PLAY_WAV\n")
        self.serial.flush()
        if self._wait_for_ready():
            self.serial.write(data)
            time.sleep(1)
        self.serial.write(b"STOP\n")
        
        # 2. Python-generated tone
        print("\n2. Testing Python-generated tone...")
        freq = 440  # A4 note
        duration = 1  # seconds
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration))
        tone = (32767 * np.sin(2 * np.pi * freq * t)).astype(np.int16)
        
        self.serial.write(b"PLAY_TONE\n")
        self.serial.flush()
        if self._wait_for_ready():
            self.serial.write(tone.tobytes())
            time.sleep(1)
        self.serial.write(b"STOP\n")
        

    def _wait_for_ready(self):
        """Wait for ESP32 ready signal."""
        start_time = time.time()
        while time.time() - start_time < 4:
            if self.serial.in_waiting:
                response = self.serial.readline()   
                if b"READY" in response:
                    print(f"ESP32: {response}")
                    return True
        print("Timeout waiting for ESP32")
        return False

    def play_wav_file(self, filename):
        print(f"\nTesting speaker with {filename}...")
        
        # Load and print WAV file details
        with wave.open(filename, 'rb') as wav_file:
            print("WAV file details:")
            print(f"- Channels: {wav_file.getnchannels()}")
            print(f"- Sample width: {wav_file.getsampwidth()} bytes")
            print(f"- Frame rate: {wav_file.getframerate()} Hz")
            print(f"- Number of frames: {wav_file.getnframes()}")
            print(f"- Duration: {wav_file.getnframes() / wav_file.getframerate():.2f} seconds")
            
            # Read the entire file
            audio_data = wav_file.readframes(wav_file.getnframes())
            
            # Convert to numpy array for resampling
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Resample if needed
            if wav_file.getframerate() != 44100:
                print(f"Resampling from {wav_file.getframerate()}Hz to 44100Hz")
                audio_array = resample(audio_array, int(len(audio_array) * 44100 / wav_file.getframerate()))
            
            # Clear any existing data and reset buffers
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            print("\nSending PLAY command...")
            self.serial.write(b'PLAY\n')
            self.serial.flush()
            
            # Wait for ready signal with timeout
            ready_received = False
            start_time = time.time()
            while time.time() - start_time < 5:
                if self.serial.in_waiting:
                    response = self.serial.readline().decode().strip()
                    print(f"ESP32: {response}")  # More explicit debug output
                    if "READY" in response:
                        ready_received = True
                        break
                time.sleep(0.1)
            
            if not ready_received:
                print("Timeout waiting for ESP32 ready signal")
                return
            
            # Send audio data
            print("Sending audio data...")
            chunk_size = 1024  # Send data in chunks
            for i in range(0, len(audio_array), chunk_size):
                chunk = audio_array[i:i + chunk_size]
                self.serial.write(chunk.tobytes())
                self.serial.flush()  # Ensure data is sent
                
                # Add a small delay to prevent buffer overflow
                time.sleep(0.001)
                
                # Print progress
                if i % (chunk_size * 10) == 0:
                    print(f"Progress: {i/len(audio_array)*100:.1f}%")
            
            # Send STOP command
            print("\nSending STOP command...")
            self.serial.write(b'STOP\n')
            self.serial.flush()

    def test_basic_send(self, wav_file):
        # 2. Python-generated tone
        print("\n2. Testing Python-generated tone...")
        freq = 440  # A4 note
        duration = 1  # seconds
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration))
        tone = (32767 * np.sin(2 * np.pi * freq * t)).astype(np.int16)
        
        self.serial.write(tone.tobytes())
        

# Example usage
if __name__ == "__main__":
    # Replace with your ESP32's serial port
    esp32 = ESP32AudioInterface('/dev/tty.usbserial-0001')
    
    try:
        # Test the speaker
        esp32.test_basic_send("CantinaBand60.wav")
        
    finally:
        esp32.close()