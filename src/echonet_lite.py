import struct
import binascii


class EchonetLite:
    PROTOCOL_TYPE = 0x10

    class Format:
        FORMAT1 = 0x81
        FORMAT2 = 0x82

    class Service:
        WRITE_NO_RESPONSE = 0x60
        WRITE = 0x61
        READ = 0x62
        NOTIFY = 0x62
        WRITE_READ = 0x6E

    class Device:
        HOUSING = 0x02
        MANAGEMENT = 0x05

        class Housing:
            LOW_VOLTAGE_SMART_METER = 0x88

        class Management:
            CONTROLLER = 0xFF

    class Property:
        class LowVoltageSmartMeter:
            STATUS = 0x80
            CUMULATIVE_ENERGY_DIGITS = 0xD7  # 積算電力量有効桁数
            CUMULATIVE_ENERGY_NORMAL = 0xE0  # 積算電力量計測値(正方向計測値)
            CUMULATIVE_ENERGY_REVERSE = 0xE3  # 積算電力量計測値(逆方向計測値)
            CUMULATIVE_ENERGY_UNIT = 0xE1  # 積算電力量単位(正方向、逆方向計測値)
            INSTANTANEOUS_POWER = 0xE7  # 瞬時電力計測値
            INSTANTANEOUS_CURRENT = 0xE8  # 瞬時電流計測値
            CUMULATIVE_ENERGY_FIXED_TIME_NORMAL = 0xEA  # 定時積算電力量計測値(正方向計測値)
            CUMULATIVE_ENERGY_FIXED_TIME_REVERSE = 0xEB  # 定時積算電力量計測値(逆方向計測値)

    ENERGY_UNIT = 0.1  # 積算電力量単位

    @staticmethod
    def create_power_request_command():
        """
        電力量をリクエストするECHONET Liteパケットを作成
        """

        seoj = EchonetLite.create_object_id(EchonetLite.Device.MANAGEMENT, EchonetLite.Device.Management.CONTROLLER)

        deoj = EchonetLite.create_object_id(
            EchonetLite.Device.HOUSING, EchonetLite.Device.Housing.LOW_VOLTAGE_SMART_METER
        )

        properties = [
            {
                "EPC": EchonetLite.Property.LowVoltageSmartMeter.CUMULATIVE_ENERGY_UNIT,
                "PDC": 0,
            },
            {
                "EPC": EchonetLite.Property.LowVoltageSmartMeter.CUMULATIVE_ENERGY_NORMAL,
                "PDC": 0,
            },
            {
                "EPC": EchonetLite.Property.LowVoltageSmartMeter.INSTANTANEOUS_POWER,
                "PDC": 0,
            },
        ]

        return EchonetLite.create_packet(seoj, deoj, EchonetLite.Service.READ, properties)

    @staticmethod
    def create_object_id(object_group, object_code, instance_code=0x1):
        return (object_group << 16) | (object_code << 8) | instance_code

    def create_packet(seoj, deoj, service, properties, tid=1):
        edata = EchonetLite.build_edata(seoj, deoj, service, properties)
        return EchonetLite.build_frame(edata, tid)

    @staticmethod
    def build_edata(seoj, deoj, service, properties):
        seoj_data = struct.pack(">I", seoj)[1:]
        deoj_data = struct.pack(">I", deoj)[1:]

        service_data = struct.pack("B", service)
        opc_data = struct.pack("B", len(properties))

        edata = seoj_data + deoj_data + service_data + opc_data

        for prop in properties:
            prop_data = EchonetLite.build_property(prop["EPC"], prop["PDC"], prop.get("EDT"))
            edata += prop_data

        return edata

    @staticmethod
    def build_frame(edata, tid=1):
        return (
            struct.pack("2B", EchonetLite.PROTOCOL_TYPE, EchonetLite.Format.FORMAT1) + struct.pack(">H", tid) + edata
        )

    @staticmethod
    def build_property(epc, pdc, edt=None):
        epc_data = struct.pack("B", epc)
        pdc_data = struct.pack("B", pdc)
        edt_data = edt if edt is not None else b""

        return epc_data + pdc_data + edt_data

    @staticmethod
    def parse_packet(packet):
        frame = {}

        # ヘッダ情報をパース
        frame["PROTOCOL_TYPE"] = packet[0]
        frame["FORMAT"] = packet[1]
        frame["TID"] = packet[2:4]

        if frame["FORMAT"] == EchonetLite.Format.FORMAT1:
            frame["EDATA"] = EchonetLite.parse_edata(packet[4:])

        # ヘッダの妥当性を確認
        EchonetLite.validate_header(frame)

        return frame

    @staticmethod
    def validate_header(frame):
        """
        ECHONET Liteフレームのヘッダが有効であることを検証
        """

        # プロトコルタイプが正しくない場合は例外をスロー
        if frame["PROTOCOL_TYPE"] != EchonetLite.PROTOCOL_TYPE:
            raise Exception(f"Invalid PROTOCOL_TYPE: {frame['PROTOCOL_TYPE']}")

        # フォーマットが正しくない場合は例外をスロー
        if (frame["FORMAT"] != EchonetLite.Format.FORMAT1) and (frame["FORMAT"] != EchonetLite.Format.FORMAT2):
            raise Exception(f"Invalid FORMAT: {frame['FORMAT']}")

    @staticmethod
    def parse_edata(packet):
        """
        ECHONET LiteパケットのEDATA部分を解析
        """

        data = {}
        data["SEOJ"] = packet[0:3]
        data["DEOJ"] = packet[3:6]
        data["ESV"] = packet[6]
        data["OPC"] = packet[7]

        properties = []
        packet = packet[8:]
        for i in range(data["OPC"]):
            prop = {}
            prop["EPC"] = packet[0]
            prop["PDC"] = packet[1]

            if prop["PDC"] == 0:
                prop["EDT"] = None
            else:
                prop["EDT"] = packet[2 : (2 + prop["PDC"])]

            properties.append(prop)

            packet = packet[(2 + prop["PDC"]) :]

        data["properties"] = properties

        return data

    @staticmethod
    def parse_properties(frame):
        data = []

        result = EchonetLite.parse_instantaneous_power(frame)
        if result:
            data.append(result)

        result = EchonetLite.parse_cumulative_energy_normal(frame)
        if result:
            data.append(result)

        result = EchonetLite.parse_cumulative_energy_reverse(frame)
        if result:
            data.append(result)

        result = EchonetLite.parse_cumulative_energy_fixed_time_normal(frame)
        if result:
            data.append(result)

        result = EchonetLite.parse_cumulative_energy_fixed_time_reverse(frame)
        if result:
            data.append(result)

        return data

    @staticmethod
    def parse_instantaneous_power(frame):
        """
        ECHONET Liteフレームから瞬時電力量を取得
        """

        data = None

        property = EchonetLite.find_property(frame, EchonetLite.Property.LowVoltageSmartMeter.INSTANTANEOUS_POWER)

        if property is None:
            return None

        power = int.from_bytes(property["EDT"], "big")

        data = {"name": "瞬時電力計測値", "power": power, "unit": "W"}

        return data

    @staticmethod
    def parse_cumulative_energy_unit(frame):
        """
        ECHONET Liteフレームから積算電力量単位を取得
        """

        data = EchonetLite.ENERGY_UNIT

        property = EchonetLite.find_property(frame, EchonetLite.Property.LowVoltageSmartMeter.CUMULATIVE_ENERGY_UNIT)

        if property is None:
            return data

        # 積算電力量単位
        units = {
            0x00: 1,
            0x01: 0.1,
            0x02: 0.01,
            0x03: 0.001,
            0x04: 0.0001,
            0x0A: 10,
            0x0B: 100,
            0x0C: 1000,
            0x0D: 10000,
        }

        if property["EDT"] in units:
            data = units[property["EDT"]]

        return data

    @staticmethod
    def parse_cumulative_energy_normal(frame):
        """
        ECHONET Liteフレームから積算電力量を取得
        """

        data = None

        property = EchonetLite.find_property(frame, EchonetLite.Property.LowVoltageSmartMeter.CUMULATIVE_ENERGY_NORMAL)

        if property is None:
            return None

        power = round(int.from_bytes(property["EDT"], "big") * EchonetLite.parse_cumulative_energy_unit(frame), 1)

        data = {"name": "積算電力量計測値", "power": power, "unit": "kWh"}

        return data

    @staticmethod
    def parse_cumulative_energy_reverse(frame):
        """
        ECHONET Liteフレームから積算電力量(逆方向)を取得
        """

        data = None

        property = EchonetLite.find_property(
            frame, EchonetLite.Property.LowVoltageSmartMeter.CUMULATIVE_ENERGY_REVERSE
        )

        if property is None:
            return None

        power = round(int.from_bytes(property["EDT"], "big") * EchonetLite.parse_cumulative_energy_unit(frame), 1)

        data = {"name": "積算電力量計測値(逆方向)", "power": power, "unit": "kWh"}

        return data

    @staticmethod
    def parse_cumulative_energy_fixed_time_normal(frame):
        """
        ECHONET Liteフレームから定時積算電力量を取得
        """

        data = None

        property = EchonetLite.find_property(
            frame, EchonetLite.Property.LowVoltageSmartMeter.CUMULATIVE_ENERGY_FIXED_TIME_NORMAL
        )

        if property is None:
            return None

        year = int(binascii.b2a_hex(property["EDT"][0:2]), 16)
        month = int(binascii.b2a_hex(property["EDT"][2:3]), 16)
        day = int(binascii.b2a_hex(property["EDT"][3:4]), 16)

        hour = int(binascii.b2a_hex(property["EDT"][4:5]), 16)
        min = int(binascii.b2a_hex(property["EDT"][5:6]), 16)
        sec = int(binascii.b2a_hex(property["EDT"][6:7]), 16)

        power = round(
            int(binascii.b2a_hex(property["EDT"][7:]), 16) * EchonetLite.parse_cumulative_energy_unit(frame), 1
        )

        timeStr = EchonetLite.format_timestamp(year, month, day, hour, min, sec)

        data = {"name": "定時積算電力量", "power": power, "unit": "kWh", "time": timeStr}

        return data

    @staticmethod
    def parse_cumulative_energy_fixed_time_reverse(frame):
        """
        ECHONET Liteフレームから定時積算電力量(逆方向)を取得
        """

        data = None

        property = EchonetLite.find_property(
            frame, EchonetLite.Property.LowVoltageSmartMeter.CUMULATIVE_ENERGY_FIXED_TIME_REVERSE
        )

        if property is None:
            return None

        year = int(binascii.b2a_hex(property["EDT"][0:2]), 16)
        month = int(binascii.b2a_hex(property["EDT"][2:3]), 16)
        day = int(binascii.b2a_hex(property["EDT"][3:4]), 16)

        hour = int(binascii.b2a_hex(property["EDT"][4:5]), 16)
        min = int(binascii.b2a_hex(property["EDT"][5:6]), 16)
        sec = int(binascii.b2a_hex(property["EDT"][6:7]), 16)

        power = round(
            int(binascii.b2a_hex(property["EDT"][7:]), 16) * EchonetLite.parse_cumulative_energy_unit(frame), 1
        )

        time_str = EchonetLite.format_timestamp(year, month, day, hour, min, sec)

        data = {"name": "定時積算電力量(逆方向)", "power": power, "unit": "kWh", "time": time_str}

        return data

    @staticmethod
    def find_property(frame, epc):
        """
        ECHONET Liteフレームから特定のプロパティを検索
        """

        # プロパティを検索
        for prop in frame["EDATA"]["properties"]:
            if prop["EPC"] == epc:
                return prop

        return None

    @staticmethod
    def format_timestamp(year, month, day, hour, minute, second):
        return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
