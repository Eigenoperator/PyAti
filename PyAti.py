import socket
import struct
import time


class ATISensor:
    def __init__(self, ip, counts_per_force, counts_per_torque, tcp_port=49151, udp_port=49152, timeout=2.0):
        self.tcp_port = tcp_port
        self.addr = (ip, udp_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.command = struct.pack('>HHHH', 0x1234, 2, 0, 1)
        self.counts_per_force = counts_per_force # Default counts per force unit
        self.counts_per_torque = counts_per_torque  # Default counts per torque unit
        self.timeout = timeout

    def read_raw_counts(self):
        self.sock.sendto(self.command, self.addr)
        data, _ = self.sock.recvfrom(36)
        if len(data) != 36:
            raise RuntimeError("Invalid ATI response length")
        return list(struct.unpack('>6i', data[12:36]))

    def read_ft(self):
        raw_counts = self.read_raw_counts()
        # Convert raw counts to forces and torques
        fx = raw_counts[0] / self.counts_per_force
        fy = raw_counts[1] / self.counts_per_force  
        fz = raw_counts[2] / self.counts_per_force
        tx = raw_counts[3] / self.counts_per_torque
        ty = raw_counts[4] / self.counts_per_torque
        tz = raw_counts[5] / self.counts_per_torque
        # print(f"Raw counts: {raw_counts}, Forces: ({fx}, {fy}, {fz}), Torques: ({tx}, {ty}, {tz})")
        return fx, fy, fz, tx, ty, tz
    

    def bias_current_value(self):
        """
        Use ATI RDT command 0x42 to tell the device to treat current reading as zero.
        """
        BIAS_CMD = struct.pack('>HHHH', 0x1234, 0x0042, 0, 0)
        try:
            self.sock.sendto(BIAS_CMD, self.addr)
            print("[Bias] Sent software bias command to ATI device.")
        except Exception as e:
            print(f"[Bias Error] {e}")

    def close(self):
        self.sock.close()
    
    def read_calibration_info(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.timeout)
            sock.connect((self.ip, self.tcp_port))

            cmd = struct.pack('>B19x', 1)
            sock.sendall(cmd)

            response = self.recv_all(sock, 24)
            if len(response) != 24:
                raise RuntimeError(f"Invalid response length: {len(response)}")

            # 解析
            header, force_unit, torque_unit, cpf, cpt, *scale_factors = struct.unpack('>HBBII6H', response)
            if header != 0x1234:
                raise RuntimeError(f"Invalid header: {hex(header)}")

            return {
                "force_unit_code": force_unit,
                "torque_unit_code": torque_unit,
                "counts_per_force": cpf,
                "counts_per_torque": cpt,
                "scale_factors": scale_factors
            }
    
    def describe_units(self, code, is_force=True):
        force_units = {
            1: 'Pound', 2: 'Newton', 3: 'Kilopound', 4: 'Kilonewton', 5: 'Kilogram', 6: 'Gram'
        }
        torque_units = {
            1: 'Pound-inch', 2: 'Pound-foot', 3: 'Newton-meter', 4: 'Newton-millimeter',
            5: 'Kilogram-centimeter', 6: 'Kilonewton-meter'
        }
        return force_units.get(code, 'Unknown') if is_force else torque_units.get(code, 'Unknown')
        
    def print_calibration_info(self):
        info = self.read_calibration_info()
        print("=== Calibration Info ===")
        print(f"Force Unit: {self.describe_units(info['force_unit_code'], is_force=True)}")
        print(f"Torque Unit: {self.describe_units(info['torque_unit_code'], is_force=False)}")
        print(f"Counts Per Force: {info['counts_per_force']}")
        print(f"Counts Per Torque: {info['counts_per_torque']}")
        print(f"Scale Factors: {info['scale_factors']}")

    @staticmethod
    def recv_all(sock, length):
        data = b''
        while len(data) < length:
            packet = sock.recv(length - len(data))
            if not packet:
                break
            data += packet
        return data


if __name__ == "__main__":
    ati = ATISensor()

    ati.bias_current_value() 
    for _ in range(10):
        try:
            data = ati.read_ft()
            print(data)
        except RuntimeError as e:
            print(f"Error: {e}")
        time.sleep(0.1)
