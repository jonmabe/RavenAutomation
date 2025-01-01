import serial
import time
from typing import Optional, Tuple

class BottangoDriver:
    BAUD_RATE = 115200

    def __init__(self, port: str = '/dev/tty.usbserial-0001'):
        """Initialize the driver with a serial connection"""
        self.serial = serial.Serial(
            port=port,
            baudrate=self.BAUD_RATE,
            timeout=1
        )
        self.connected = False
        self._initialize_connection()

    def _initialize_connection(self):
        """Initialize connection with Bottango"""
        print("Initializing connection...")
        
        # Wait for serial connection to stabilize
        time.sleep(2)
        
        while not self.connected:
            success = self._handle_connection_sequence()
            if not success:
                print("Connection sequence failed, retrying in 2 seconds...")
                time.sleep(2)

    def _handle_connection_sequence(self) -> bool:
        """Handle the boot and handshake sequence"""
        # Wait for BOOT message
        boot_received = False
        print("Waiting for BOOT message...")
        
        # Try to get BOOT message for up to 5 seconds
        start_time = time.time()
        while time.time() - start_time < 5:
            response = self._read_response()
            if response:
                print(f"Received: {response}")
                if "BOOT" in response:
                    boot_received = True
                    break
            time.sleep(0.1)
        
        if not boot_received:
            return False

        # Send handshake request and wait for response
        print("Sending handshake request...")
        success = self._send_command_and_wait(
            command="hRQ,144\n",
            expected_response="btngoHSK",
            timeout=5
        )
        
        if success:
            # Wait for OK after handshake
            if self._wait_for_ok():
                print("Handshake successful!")
                self.connected = True
                return True
        
        print("Handshake failed!")
        return False

    def _send_command_and_wait(
        self, 
        command: str, 
        expected_response: str, 
        timeout: int = 5
    ) -> bool:
        """
        Send a command and wait for expected response
        Returns True if expected response received, False otherwise
        """
        self._send_command(command)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self._read_response()
            if response:
                print(f"Received: {response}")
                if expected_response in response:
                    return True
            time.sleep(0.1)
        
        return False

    def _wait_for_ok(self, timeout: int = 5) -> bool:
        """Wait for OK response from Bottango"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self._read_response()
            if response:
                #print(f"Received: {response}")
                if "OK" in response:
                    return True
            time.sleep(0.01)
        print("Timeout waiting for OK")
        return False

    def _send_command(self, command: str):
        """Send a command to Bottango"""
        #print(f"Sending: {command.strip()}")
        self.serial.write(command.encode())
        self.serial.flush()

    def _send_command_with_ok(self, command: str) -> bool:
        """Send a command and wait for OK response"""
        self._send_command(command)
        return self._wait_for_ok()

    def _read_response(self) -> str:
        """Read response from Bottango"""
        try:
            if self.serial.in_waiting:
                response = self.serial.readline().decode().strip()
                return response
            return ""
        except Exception as e:
            print(f"Error reading response: {e}")
            return ""

    def __del__(self):
        """Cleanup when object is destroyed"""
        if hasattr(self, 'serial') and self.serial.is_open:
            self.serial.close()

    def initialize_servos(self):
        """Initialize the servos"""
        commands = [
            "rSVPin,12,1275,1725,3000,1500\n",
            "rSVPin,14,850,2100,3000,1760\n",
            "rSVPin,27,1450,1700,3000,1700\n",
            "rSVPin,13,1500,2000,3000,2000\n"
        ]
        
        for cmd in commands:
            if not self._send_command_with_ok(cmd):
                print(f"Failed to initialize servo with command: {cmd.strip()}")
                return False
        return True

    def set_mouth(self, position: float):
        """Set mouth position (0.0 to 1.0)"""
        position = max(0.0, min(1.0, position))  # Clamp between 0 and 1
        bottango_position = int(position * 8192)
        return self._send_command_with_ok(f"sCI,27,{bottango_position}\n")

    def set_head_rotation(self, position: float):
        """Set head rotation (0.0 to 1.0)"""
        position = max(0.0, min(1.0, position))  # Clamp between 0 and 1
        bottango_position = int(position * 8192)
        return self._send_command_with_ok(f"sCI,12,{bottango_position}\n")

    def set_head_tilt(self, position: float):
        """Set head tilt (0.0 to 1.0)"""
        position = max(0.0, min(1.0, position))  # Clamp between 0 and 1
        bottango_position = int(position * 8192)
        return self._send_command_with_ok(f"sCI,14,{bottango_position}\n")

    def set_wing(self, position: float):
        """Set wing position (0.0 to 1.0)"""
        position = max(0.0, min(1.0, position))  # Clamp between 0 and 1
        bottango_position = int(position * 8192)
        return self._send_command_with_ok(f"sCI,13,{bottango_position}\n")

    def test_servos(self):
        """Test the servos with normalized positions"""
        test_positions = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 0.0]
        
        print("Testing mouth...")
        for pos in test_positions:
            if not self.set_mouth(pos):
                print(f"Failed to set mouth to position {pos}")
                return False
            time.sleep(0.5)
            
        print("Testing head rotation...")
        for pos in test_positions:
            if not self.set_head_rotation(pos):
                print(f"Failed to set head rotation to position {pos}")
                return False
            time.sleep(0.5)
            
        print("Testing head tilt...")
        for pos in test_positions:
            if not self.set_head_tilt(pos):
                print(f"Failed to set head tilt to position {pos}")
                return False
            time.sleep(0.5)
            
        print("Testing wing...")
        for pos in test_positions:
            if not self.set_wing(pos):
                print(f"Failed to set wing to position {pos}")
                return False
            time.sleep(0.5)

        return True

    def set_motor_curve(
        self,
        pin: int,
        start_time_ms: int,
        duration_ms: int,
        start_pos_raw: int,      # 0-8192
        start_tangent_x: int,
        start_tangent_y_raw: int,  # 0-8192
        end_pos_raw: int,        # 0-8192
        end_tangent_x: int,
        end_tangent_y_raw: int,  # 0-8192
    ) -> bool:
        """
        Set a motor curve for smooth movement using raw Bottango values (0-8192)
        """
        command = f"sC,{pin},{start_time_ms},{duration_ms},{start_pos_raw}," \
                 f"{start_tangent_x},{start_tangent_y_raw},{end_pos_raw}," \
                 f"{end_tangent_x},{end_tangent_y_raw}\n"
        #print(command)
        return self._send_command_with_ok(command)

    def test_mouth_curve(self):
        """Test mouth movement using curve command"""
        print("Testing mouth curve movement...")
        
        # sC,27,0,5033,8192,1258,-548,8192,-666,4457
        success = self.set_motor_curve(
            pin=27,                # Mouth servo pin
            start_time_ms=0,       # Start immediately
            duration_ms=5033,      # Duration
            start_pos_raw=8192,    # Start fully open
            start_tangent_x=1258,  
            start_tangent_y_raw=-548,
            end_pos_raw=8192,      # End position
            end_tangent_x=-666,
            end_tangent_y_raw=4457
        )

        if success:
            print("Mouth curve test completed successfully")
            time.sleep(5.1)  # Wait for movement to complete
            # Return to closed position
            self.set_mouth(0.0)
            time.sleep(0.5)
            self.set_mouth(1.0)
        else:
            print("Mouth curve test failed")
        
        return success

    def test_manually(self):
        """Test manually setting the mouth position"""
        print("Testing manually setting the mouth position...")
        self.set_mouth(0.0)
        time.sleep(0.5)
        self.set_mouth(0.5)
        time.sleep(0.5)
        self.set_mouth(1.0)
        time.sleep(0.5)
        self.set_mouth(0.0)

if __name__ == "__main__":
    driver = BottangoDriver()
    if driver.initialize_servos():
        print("Servos initialized successfully")
        driver.test_manually()
