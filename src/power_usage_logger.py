#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import configparser
import logging.config
import logging

from dotenv import load_dotenv
from wi_sun_module_broute import WiSunModuleBroute


def power_usage_logging(data):
    """
    使用電力ログ出力
    """

    message = ""

    for value in data:
        message += " {0}:{1}{2}".format(value["name"], value["power"], value["unit"])

        if "time" in value:
            message += "({0})".format(value["time"])

    if message:
        log = logging.getLogger("power_usage")
        log.info(message)


# メインプログラム
if __name__ == "__main__":
    # ディレクトリ移動
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # 環境変数
    load_dotenv()
    broute_id = os.getenv("BROUTE_ID")
    broute_password = os.getenv("BROUTE_PASSWORD")

    # コンフィグ
    config = configparser.ConfigParser()
    config.read("../config/config.ini")

    # ロガー
    logging.config.fileConfig("../config/logging.ini")
    logger = logging.getLogger("main")

    wi_sun_module_broute = WiSunModuleBroute(
        config.get("serial_port", "device"),
        config.get("serial_port", "baudRate"),
        broute_id,
        broute_password,
        logger,
    )

    try:
        wi_sun_module_broute.serial_open()

        while True:
            wi_sun_module_broute.connect_smart_meter()
            wi_sun_module_broute.send_start_smart_meter()

            # 受信ループ
            while True:
                try:
                    data = wi_sun_module_broute.recieve_smart_meter()

                    if data is None:
                        break

                    power_usage_logging(data)

                except Exception as e:
                    logger.error(e)
                    break

            wi_sun_module_broute.send_end_smart_meter()
            wi_sun_module_broute.close_smart_meter()

            # スマートメータ再接続待機
            logger.info("スマートメータ再接続待機")
            time.sleep(10)

    except Exception as e:
        logger.error(e)

    finally:
        wi_sun_module_broute.serial_close()
