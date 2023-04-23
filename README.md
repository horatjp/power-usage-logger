# power-usage-logger

power-usage-loggerは電力消費情報をリアルタイムで収集しログをとるプログラムです。  
Wi-SUNモジュールとして RL7023 Stick-D/IPS を使用します。  
このプログラムはLinux環境で動作し、Python 3.9以上が必要です。  


## インストール方法

このリポジトリをクローンまたはダウンロードします。

```bash
git clone https://github.com/horatjp/power-usage-logger
```

```bash
cd power-usage-logger
```

必要なPythonパッケージをインストールします。

```bash
pip install -r requirements.txt
```

### 電力メーター情報発信サービス（Bルートサービス）

電力メーター情報発信サービス（Bルートサービス）の認証IDとパスワードを設定します。

```bash
mv .env.example .env
```

`vi .env`
```ini.:.env
BROUTE_ID=
BROUTE_PASSWORD=
```

### デバイス管理

```bash
sudo vi /etc/udev/rules.d/99-RL7023Stick.rules
```

```ini
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6015", MODE="0666", SYMLINK+="RL7023Stick"
```

反映

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```


## 使い方

```bash
src/power_usage_logger.py
```

`logs/power_usage.log` にログが出力されていきます。

例
```
2023-04-22 09:56:19: 瞬時電力計測値:1256W 積算電力量計測値:26861.4kWh
2023-04-22 09:57:19: 瞬時電力計測値:1276W 積算電力量計測値:26861.4kWh
2023-04-22 09:58:20: 瞬時電力計測値:1264W 積算電力量計測値:26861.4kWh
2023-04-22 09:59:19: 瞬時電力計測値:1284W 積算電力量計測値:26861.5kWh
2023-04-22 10:00:19: 瞬時電力計測値:1324W 積算電力量計測値:26861.5kWh
2023-04-22 10:01:19: 瞬時電力計測値:1268W 積算電力量計測値:26861.5kWh
2023-04-22 10:02:20: 瞬時電力計測値:1284W 積算電力量計測値:26861.5kWh
2023-04-22 10:02:37: 定時積算電力量:26861.5kWh(2023-04-22 10:00:00) 定時積算電力量(逆方向):2.1kWh(2023-04-22 10:00:00)
2023-04-22 10:03:20: 瞬時電力計測値:1260W 積算電力量計測値:26861.5kWh
2023-04-22 10:04:19: 瞬時電力計測値:1320W 積算電力量計測値:26861.6kWh
2023-04-22 10:05:19: 瞬時電力計測値:856W 積算電力量計測値:26861.6kWh
2023-04-22 10:06:20: 瞬時電力計測値:900W 積算電力量計測値:26861.6kWh
```


### 永続化

以下の手順で、power_usage_logger.pyが常にバックグラウンドで実行されるように設定できます。  
これにより、システムが再起動された場合でも、プログラムが自動的に再起動されます。

```bash
crontab -e
```

```
*/10 * * * * ps ax | grep -v grep | grep -q power_usage_logger.py || cd [プロジェクトのパス] && src/power_usage_logger.py &
```

## その他

Zabbixによる電力使用量のモニタリング「RL7023 Stick-D/IPS」 – Debian Linuxによる自宅サーバ
https://blog.horat.jp/a/479
