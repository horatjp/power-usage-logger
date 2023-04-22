import serial
import serial.tools.list_ports
import time
import binascii
import threading

from echonet_lite import EchonetLite


class WiSunModuleBroute:
    def __init__(self, device, baudrate, id, password, logger, retry_scan=5):
        self.device = device
        self.baudrate = baudrate
        self.id = id
        self.password = password
        self.logger = logger
        self.retry_scan = retry_scan

        self.serial = None
        self.ip_v6_address = None

        self.event = threading.Event()

    def serial_open(self):
        self.logger.info("シリアルポートオープン")
        self.serial = serial.Serial()
        self.serial.port = self.device
        self.serial.baudrate = self.baudrate
        self.serial.open()

        if not self.serial.is_open:
            raise Exception("シリアルポートオープンエラー")

    def serial_close(self):
        self.logger.info("シリアルポートクローズ")
        if self.serial is not None:
            self.serial.close()
            self.serial = None

    def serial_write(self, command, data=None):
        if data:
            command = command.encode() + data
        else:
            command = (command + "\r\n").encode()

        self.logger.debug(command)
        self.serial.write(command)

    def serial_read(self):
        response = ""

        while True:
            line = self.serial.readline().decode("utf-8")

            if not line:
                continue
            response += line
            if line.endswith("\r\n"):
                break

        self.logger.debug(response.rstrip())
        return response.rstrip()

    def serial_command(self, command, data=None):
        self.serial_write(command, data)
        return self.serial_read()

    def connect_smart_meter(self):
        self.logger.info("スマートメータ接続開始")

        self.serial_command("SKSREG SFE 0")

        # Bルート認証パスワード設定
        self.serial_command("SKSETPWD C " + self.password)

        # Bルート認証ID設定
        self.serial_command("SKSETRBID " + self.id)

        # 受信データ
        scan_response = {}

        # アクティブスキャン
        for i in range(self.retry_scan):
            self.logger.info("アクティブスキャン開始")

            # デバイススキャン(2はアクティブスキャン, 6は間隔)
            self.serial_command("SKSCAN 2 FFFFFFFF 6")

            while True:
                response = self.serial_read()

                if response.startswith("EVENT 20"):
                    while True:
                        response = self.serial_read()

                        if response.startswith("EPANDESC"):
                            continue
                        elif response.startswith("  "):
                            cols = response.strip().split(":")
                            scan_response[cols[0]] = cols[1]
                        else:
                            break

                    break

                elif response.startswith("EVENT 22"):
                    break

            # Channelが取得出来ていたら終了
            if "Channel" in scan_response:
                break

            self.logger.info("アクティブスキャン待機")
            time.sleep(60)

        # Channel取得確認
        if "Channel" not in scan_response:
            raise Exception("Channel取得エラー")

        self.logger.info(scan_response)

        # スキャン結果からChannelを設定。
        self.serial_command("SKSREG S2 {0}".format(scan_response["Channel"]))

        # スキャン結果からPan IDを設定
        self.serial_command("SKSREG S3 {0}".format(scan_response["Pan ID"]))

        # MACアドレス(64bit)をIPV6リンクローカルアドレスに変換
        ip_v6_address = self.serial_command("SKLL64 {0}".format(scan_response["Addr"]))

        # IPv6アドレス取得確認
        if ip_v6_address is None:
            raise Exception("IPv6アドレス取得エラー")

        self.logger.info("IPv6アドレス:" + ip_v6_address)

        # 接続シーケンス開始
        self.logger.info("接続シーケンス開始")
        self.serial_command("SKJOIN {0}".format(ip_v6_address))

        # 接続待ち
        while True:
            response = self.serial_read()

            if response.startswith("EVENT 24"):
                self.logger.info("PANAによる接続過程でエラーが発生")
                break
            elif response.startswith("EVENT 25"):
                self.logger.info("PANAによる接続が完了")
                self.ip_v6_address = ip_v6_address
                break

    def close_smart_meter(self):
        self.logger.info("スマートメータ接続終了")

    def send_start_smart_meter(self):
        self.logger.info("スマートメータコマンド送信開始")

        self.thread = threading.Thread(target=self.send_smart_meter)
        self.thread.daemon = True
        self.thread.start()

    def send_end_smart_meter(self):
        self.logger.info("スマートメータコマンド送信終了")

        self.event.set()
        self.thread.join()
        self.event.clear()

    def send_smart_meter(self):
        power_request_command = EchonetLite.create_power_request_command()

        while not self.event.wait(0):
            self.logger.debug("ECHONET Lite Frame: {0}".format(repr(power_request_command)))

            command = "SKSENDTO 1 {0} 0E1A 1 {1:04X} ".format(self.ip_v6_address, len(power_request_command))

            self.serial_write(command, power_request_command)

            time.sleep(60)

    def recieve_smart_meter(self):
        # 受信ループ
        while True:
            response = self.serial_read()

            if response.startswith("ERXUDP"):  # 自端末宛てのUDP受信
                cols = response.split(" ")  # スマートメータからの受信データ解析

                frame_str = cols[8]  # UDP受信データ部分

                frame = binascii.a2b_hex(frame_str)  # 文字列16進数を変換

                self.logger.debug("ECHONET Lite Frame: {0}".format(frame))

                frame_obj = EchonetLite.parse_packet(frame)

                data = EchonetLite.parse_properties(frame_obj)

                return data

            # 接続相手からセッション終了要求を受信
            elif response.startswith("EVENT 26"):
                self.logger.info("接続相手からセッション終了要求を受信")

            # PANA セッションの終了に成功した
            elif response.startswith("EVENT 27"):
                self.logger.info("PANA セッションの終了に成功した")

                break

            # PANA セッションの終了要求に対する応答がなくタイムアウトした（セッションは終了）
            elif response.startswith("EVENT 28"):
                self.logger.info("PANA セッションの終了要求に対する応答がなくタイムアウトした（セッションは終了）")

                break

            # セッションのライフタイムが経過して期限切れになった
            elif response.startswith("EVENT 29"):
                self.logger.info("セッションのライフタイムが経過して期限切れになった")

                break

        self.logger.info("受信終了")

        return None
