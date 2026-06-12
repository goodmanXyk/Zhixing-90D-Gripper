import minimalmodbus
import time
from flask import Flask, jsonify
import threading
from flask import render_template

# todo flask框架搭建
app = Flask(__name__)
# todo 线程锁
lock = threading.Lock()


# todo 前端页面
@app.route('/')
def index():
    return render_template('index.html')


# todo 默认夹爪开闭位置
Gripper_open = 0
Gripper_close = 9000

# todo 寄存器地址
ENABLE = 0x0100
POSITION_HIGH_8 = 0x0102
POSITION_LOW_8 = 0x0103
SPEED = 0x0104
FORCE = 0x0105
MOTION_TRIGGER = 0x0108
STATUS = 0x0401
REAL_POSITION_HIGH = 0x0414
REAL_POSITION_LOW = 0x0415
FORCE_REACH = 0x0008

# todo 创建 minimalmodbus 串口对象
instrument = minimalmodbus.Instrument('COM3', 1)  # COM3, 从站1
instrument.serial.baudrate = 115200
instrument.serial.bytesize = 8
instrument.serial.parity = 'N'
instrument.serial.stopbits = 1
instrument.serial.timeout = 1


# todo 上使能
def Gripper_enable():
    instrument.write_register(ENABLE, 1, functioncode=6)
    time.sleep(2)
    print("上使能完成")


# todo 下使能
def Gripper_disable():
    instrument.write_register(ENABLE, 0, functioncode=6)
    print("下使能完成")


# todo 读取使能寄存器地址
def get_enabled_status():
    status = instrument.read_register(ENABLE)
    print(f"寄存器地址 0x{ENABLE:04X} 当前值: {status} (二进制: {bin(status)})")
    return bool(status)


# todo 设置速度
def set_speed(speed=100):
    instrument.write_register(SPEED, speed, functioncode=6)
    print(f"速度设置{speed}成功")


# todo 设置力度
def set_force(force=100):
    instrument.write_register(FORCE, force, functioncode=6)
    print(f"设置力度{force}成功")


# todo 指定夹爪位置设置
def set_position(position):
    position = max(0, min(65535, int(position)))
    instrument.write_long(POSITION_HIGH_8, position)


# todo 获取
def get_gripper_current_position():
    try:
        # 读取低位寄存器
        position = instrument.read_register(REAL_POSITION_LOW, 0)
        print(f"夹爪当前位置: {position}")
        return position
    except Exception as e:
        print(f"读取夹爪当前位置失败: {e}")
        return None


# todo 触发运动
def trigger_motion(timeout=5):
    start_time = time.time()
    while True:
        status = get_enabled_status()
        if status:
            print("使能状态正常，可以触发运动")
            instrument.write_register(MOTION_TRIGGER, 1, functioncode=6)
            print("运动已触发")
            return True
        elif (time.time() - start_time) > timeout:
            print("超时")
            return False
        time.sleep(0.5)


# todo 读取力矩到达状态
def read_force():
    try:
        status = instrument.read_register(STATUS, 0)
        force_reach = bool(status & FORCE_REACH)
        print(f"力矩到达结果: {force_reach} (寄存器值: {status}, 二进制: {bin(status)})")
        return force_reach
    except Exception as e:
        print(f"读取力矩状态失败: {e}")
        return False


# todo 移动到指定位置
def move_to_position(position, check_force=False, timeout=60):
    set_position(position)
    if not trigger_motion():
        print("夹爪未上使能或超时导致无法运动")
        return False

    start_time = time.time()
    if check_force:
        # todo 只在闭合时判断力矩
        while True:
            if read_force():
                print(f"力矩到达，夹取成功")
                break
            if (time.time() - start_time) > timeout:
                print(f"力矩检测超时，夹取可能失败")
                break
            time.sleep(0.1)
    else:
        # todo 打开夹爪不检测力矩，直接等待运动完成
        time.sleep(0.5)
    return True


# todo 初始化夹爪
def Gripper_init():
    Gripper_enable()
    set_speed(100)
    set_force(100)
    move_to_position(Gripper_close, check_force=False)
    move_to_position(Gripper_open, check_force=False)


# todo 夹爪开闭动作
def Gripper_action(action):
    action = action.lower()
    if action == "init":
        Gripper_init()
    elif action == "open":
        move_to_position(Gripper_open, check_force=False)
    # todo 测试使用时我们调用简单的close，不做力矩的判断
    elif action == "close":
        move_to_position(Gripper_close, check_force=False)
    # todo 夹取物体时调用这个grasp_close
    elif action == "grasp_close":
        move_to_position(Gripper_close, check_force=True)
    else:
        print("执行指令有误")


# todo http接口调用
@app.route('/gripper/init', methods=['POST'])
def gripper_init():
    with lock:
        try:
            Gripper_action("init")
            return jsonify({"success": True, "message": "夹爪初始化完成"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

@app.route('/gripper/open', methods=['POST'])
def gripper_open():
    with lock:
        try:
            Gripper_action("open")
            return jsonify({"success": True, "message": "夹爪已打开"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

@app.route('/gripper/close', methods=['POST'])
def gripper_close():
    with lock:
        try:
            Gripper_action("close")
            return jsonify({"success": True, "message": "夹爪已关闭"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

@app.route('/gripper/grasp', methods=['POST'])
def gripper_grasp():
    with lock:
        try:
            Gripper_action("grasp_close")
            return jsonify({"success": True, "message": "夹爪已夹持"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})


if __name__ == '__main__':
    print("系统启动，正在初始化夹爪...")
    Gripper_init()
    print("夹爪初始化完成，可以访问前端")
    app.run(host='0.0.0.0', port=5000)
