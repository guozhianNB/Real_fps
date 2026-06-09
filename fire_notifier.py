"""
开火事件实时通知模块（UDP 本地广播）。

设计思路：
  JSON 轮询适合传递"状态"（分数、目标列表、模式），
  但开火是"事件"，需要立即通知 UI，不应被轮询周期拖慢。

方案：
  主程序开火时通过 UDP 发一个数据包到 127.0.0.1:8099，
  UI 后台线程监听该端口，收到后立即触发动画。

用法（主程序）：
    from fire_notifier import send_fire

    send_fire(hit_zone="head", score_delta=50)

用法（UI）：
    from fire_notifier import FireListener

    def on_fire(event):
        print(f"开火！{event['hit_zone']} +{event['score_delta']}")

    listener = FireListener(callback=on_fire)
    listener.start()
"""

import socket
import json
import threading
import time

FIRE_PORT = 8099
FIRE_ADDR = ("127.0.0.1", FIRE_PORT)
RELOAD_DONE_PORT = 8098
RELOAD_DONE_ADDR = ("127.0.0.1", RELOAD_DONE_PORT)

# ======================
# 发送端（主程序使用）
# ======================

_fire_sock = None

def _get_sock():
    global _fire_sock
    if _fire_sock is None:
        _fire_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return _fire_sock

def send_fire(hit_zone="", score_delta=0, event_type="fire", gun="ak"):
    """发送开火事件（UDP，不阻塞，fire-and-forget）。
    
    参数：
        hit_zone: "head" / "body" / ""
        score_delta: 本次得分
        event_type: 事件类型
        gun: 枪械名（用于 UI 播放对应音效）
    """
    msg = json.dumps({
        "event": event_type,
        "hit_zone": hit_zone,
        "score_delta": score_delta,
        "gun": gun,
        "timestamp": time.time(),
    })
    sock = _get_sock()
    try:
        sock.sendto(msg.encode(), FIRE_ADDR)
    except Exception as e:
        print(f"[fire] UDP 发送失败: {e}")

def send_kill(hit_zone="", score_delta=0, target_id=0, target_name="", gun="ak"):
    """发送击杀事件。"""
    msg = json.dumps({
        "event": "kill",
        "hit_zone": hit_zone,
        "score_delta": score_delta,
        "target_id": target_id,
        "target_name": target_name,
        "gun": gun,
        "timestamp": time.time(),
    })
    try:
        _get_sock().sendto(msg.encode(), FIRE_ADDR)
    except Exception as e:
        print(f"[fire] UDP kill 发送失败: {e}")

def close_sender():
    """关闭发送端 socket。"""
    global _fire_sock
    if _fire_sock:
        try:
            _fire_sock.close()
        except Exception as e:
            print(f"[fire] 关闭 socket 失败: {e}")
        _fire_sock = None


# ======================
# 接收端（UI 使用）
# ======================

class FireListener:
    """UDP 开火事件监听器（在后台线程运行）。
    
    用法：
        def on_fire(event):
            print(f"开火！{event}")

        listener = FireListener(callback=on_fire)
        listener.start()
        # ... 程序结束后
        listener.stop()
    """

    def __init__(self, callback=None):
        """
        参数：
            callback: 收到事件时调用的函数，参数为事件 dict
        """
        self.callback = callback
        self._running = False
        self._thread = None

    def start(self):
        """启动监听线程。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止监听线程。"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _listen_loop(self):
        """后台监听循环。"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(FIRE_ADDR)
        sock.settimeout(0.5)  # 每 0.5s 醒来检查一次 running 标志

        while self._running:
            try:
                data, _ = sock.recvfrom(4096)
                event = json.loads(data.decode())
                if self.callback:
                    self.callback(event)
            except socket.timeout:
                continue
            except json.JSONDecodeError:
                pass  # 格式异常包直接忽略
            except Exception as e:
                print(f"[fire] 监听异常: {e}")

        sock.close()


# ======================
# 换弹完成 → 发送端（UI 使用）
# ======================

_reload_sock = None

def _get_reload_sock():
    global _reload_sock
    if _reload_sock is None:
        _reload_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return _reload_sock

def send_reload_done():
    """UI 通知主程序：换弹动画播放完毕。"""
    msg = json.dumps({"event": "reload_done", "timestamp": time.time()})
    try:
        _get_reload_sock().sendto(msg.encode(), RELOAD_DONE_ADDR)
    except Exception as e:
        print(f"[fire] reload_done 发送失败: {e}")

def close_reload_sender():
    global _reload_sock
    if _reload_sock:
        try:
            _reload_sock.close()
        except Exception as e:
            print(f"[fire] 关闭 reload socket 失败: {e}")
        _reload_sock = None


# ======================
# 换弹完成 → 接收端（主程序使用）
# ======================

class ReloadDoneListener:
    """监听 UI 发回的换弹完成信号。"""

    def __init__(self, callback=None):
        self.callback = callback
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _listen(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(RELOAD_DONE_ADDR)
        sock.settimeout(0.5)
        while self._running:
            try:
                data, _ = sock.recvfrom(4096)
                event = json.loads(data.decode())
                if self.callback:
                    self.callback(event)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[fire] ReloadDoneListener 异常: {e}")
        sock.close()


# ======================
# 独立测试
# ======================

if __name__ == "__main__":
    print("=== fire_notifier 测试 ===")
    print("将在后台监听，请在另一个终端运行：")
    print('  python -c "from fire_notifier import send_fire; send_fire(\'head\', 50)"')
    print()

    def test_callback(event):
        print(f"[收到] {event['event']} | "
              f"部位: {event['hit_zone']} | "
              f"得分: +{event['score_delta']}")

    listener = FireListener(callback=test_callback)
    listener.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止")
    finally:
        listener.stop()
