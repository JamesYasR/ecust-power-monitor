import threading
import time
import sqlite3
import json
import os
from urllib.parse import urlparse, parse_qs
from flask import Flask, render_template, request, jsonify, url_for
from flask_apscheduler import APScheduler
from datetime import datetime, timedelta
import logging
from ElectricityQuery import ElectricityQuery  # 电量查询模块
from Pushplus import PushPlusNotifier  # 推送模块 - 修正类名

# 初始化Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# 初始化调度器
scheduler = APScheduler()
scheduler.init_app(app)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局变量，用于存储当前定时任务
current_scheduler_job = None
# 推送频率控制
LAST_PUSH_TIME = {}  # 记录每个房间最后一次推送的时间
PUSH_COOLDOWN = 50  # 冷却时间（单位：秒）
# 默认配置
# 默认配置
DEFAULT_CONFIG = {
    'threshold': 20.0,
    'query_interval': 30,
    'electricity_params': {
        'url': '',
        'html_encode': 'utf-8',
        'timeout': 15
    },
    'push_params': {
        'token': '',
        'channel': ['mail'],
        'topic': ''  # 群组/话题编码
    }
}

# 校区和楼栋映射
AREA_MAPPING = {'2': '奉贤校区', '3': '徐汇校区'}
BUILDING_MAPPING = {'3': '3号楼'}


def init_db():
    """初始化数据库 - 支持多房间数据隔离"""
    conn = sqlite3.connect('electricity.db')
    c = conn.cursor()

    # 创建电费数据表，增加room_identifier字段用于区分不同房间
    c.execute('''CREATE TABLE IF NOT EXISTS electricity_data
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  timestamp DATETIME, 
                  balance REAL,
                  room_identifier TEXT,  -- 房间唯一标识符
                  area_id TEXT,
                  build_id TEXT,
                  room_id TEXT)''')

    # 创建配置表
    c.execute('''CREATE TABLE IF NOT EXISTS app_config
                 (id INTEGER PRIMARY KEY, 
                  config_data TEXT)''')

    conn.commit()

    # 插入默认配置
    c.execute("SELECT COUNT(*) FROM app_config WHERE id = 1")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO app_config (id, config_data) VALUES (1, ?)",
                  (json.dumps(DEFAULT_CONFIG),))
    conn.commit()
    conn.close()


def get_config():
    """获取当前配置"""
    conn = sqlite3.connect('electricity.db')
    c = conn.cursor()
    c.execute("SELECT config_data FROM app_config WHERE id = 1")
    result = c.fetchone()
    conn.close()
    return json.loads(result[0]) if result else DEFAULT_CONFIG


def save_config(config):
    """保存配置"""
    conn = sqlite3.connect('electricity.db')
    c = conn.cursor()
    c.execute("UPDATE app_config SET config_data = ? WHERE id = 1",
              (json.dumps(config),))
    conn.commit()
    conn.close()

    # 配置保存后，重新设置定时任务
    setup_scheduler()


def parse_room_info(url):
    """从URL解析房间信息"""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        area_id = params.get('areaid', [''])[0]
        build_id = params.get('buildid', [''])[0]
        room_id = params.get('roomid', [''])[0]

        area_name = AREA_MAPPING.get(area_id, f"校区{area_id}")
        building_name = BUILDING_MAPPING.get(build_id, f"{build_id}号楼")

        return f"{area_name}{building_name}{room_id}室", area_id, build_id, room_id
    except Exception as e:
        logger.error(f"解析房间信息失败: {e}")
        return "未知房间", "", "", ""


def get_room_identifier(url):
    """从URL生成房间唯一标识符"""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        area_id = params.get('areaid', [''])[0]
        build_id = params.get('buildid', [''])[0]
        room_id = params.get('roomid', [''])[0]

        return f"area{area_id}_build{build_id}_room{room_id}", area_id, build_id, room_id
    except Exception as e:
        logger.error(f"生成房间标识符失败: {e}")
        return "unknown", "", "", ""


def save_electricity_data(balance, url):
    """保存电量数据到数据库，按房间隔离"""
    room_identifier, area_id, build_id, room_id = get_room_identifier(url)

    conn = sqlite3.connect('electricity.db')
    c = conn.cursor()
    c.execute('''INSERT INTO electricity_data 
                 (timestamp, balance, room_identifier, area_id, build_id, room_id) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (datetime.now(), float(balance), room_identifier, area_id, build_id, room_id))
    conn.commit()
    conn.close()

    logger.info(f"保存电量数据: 房间{room_identifier} - {balance}度")


def get_electricity_history(days=30, room_identifier=None):
    """获取电量历史数据，支持按房间筛选"""
    conn = sqlite3.connect('electricity.db')
    c = conn.cursor()
    start_date = datetime.now() - timedelta(days=days)

    if room_identifier:
        # 获取特定房间的数据
        c.execute('''SELECT timestamp, balance FROM electricity_data 
                     WHERE timestamp > ? AND room_identifier = ? 
                     ORDER BY timestamp''',
                  (start_date, room_identifier))
    else:
        # 获取所有房间的数据（向后兼容）
        c.execute('''SELECT timestamp, balance FROM electricity_data 
                     WHERE timestamp > ? ORDER BY timestamp''',
                  (start_date,))

    data = c.fetchall()
    conn.close()
    return [{'timestamp': row[0], 'balance': float(row[1])} for row in data]


def get_current_room_data():
    """获取当前配置房间的数据"""
    config = get_config()
    current_url = config['electricity_params']['url']
    room_identifier, _, _, _ = get_room_identifier(current_url)

    return get_electricity_history(30, room_identifier)


def send_multichannel_notify(title, content, push_params, room_identifier=""):
    """
    向多个渠道发送推送消息，支持群组推送
    """
    try:
        # 频率控制
        current_time = time.time()
        if room_identifier and current_time - LAST_PUSH_TIME[room_identifier] < PUSH_COOLDOWN:
            logger.info(f"房间 {room_identifier} 在冷却期内，跳过推送")
            return True

        results = []
        channels = push_params.get('channel', [])
        token = push_params.get('token', '')
        topic = push_params.get('topic', '')  # 获取群组编码

        if not channels:
            logger.warning("未设置推送渠道")
            return False

        if not token or token == 'your-token-here':
            logger.error("PushPlus token未配置或为默认值")
            return False

        logger.info(f"开始推送消息，渠道: {channels}, 群组: {topic or '个人'}, token: {token[:8]}...")

        for channel in channels:
            try:
                # 创建推送实例，传入群组编码
                push = PushPlusNotifier(token=token, channel=channel, topic=topic)

                # 发送消息
                result = push.pushplus_notify(title, content)
                results.append(result)

                if result:
                    logger.info(f"向渠道 {channel} 发送通知成功")
                    if room_identifier:
                        LAST_PUSH_TIME[room_identifier] = current_time
                else:
                    logger.error(f"向渠道 {channel} 发送通知失败")

            except Exception as e:
                logger.error(f"向渠道 {channel} 发送通知异常: {str(e)}")
                results.append(False)

        success_count = sum(results)
        logger.info(f"推送完成: {success_count}/{len(channels)} 个渠道成功")

        return any(results)

    except Exception as e:
        logger.error(f"多渠道推送失败: {str(e)}")
        return False




def electricity_query_task():
    """定时查询电量任务，防止重复执行"""
    # 获取任务锁，防止重复执行
    try:
        with app.app_context():
            config = get_config()
            params = config['electricity_params']
            query_interval = config.get('query_interval', 30)

            logger.info(f"执行定时电量查询，间隔: {query_interval}分钟")

            balance = ElectricityQuery(**params).query()
            if balance is not None:
                save_electricity_data(balance, params['url'])
                logger.info(f"定时任务 - 电量查询成功: {balance}度")

                # 检查阈值并发送通知
                threshold = config.get('threshold', 20.0)
                if float(balance) < threshold:
                    room_info = parse_room_info(params['url'])[0]
                    push_params = config['push_params']
                    title = "电量告急"
                    content = f"{room_info}现在还剩电量：{balance}度，请及时充值"

                    # 使用多渠道推送
                    send_multichannel_notify(title, content, push_params)
            else:
                logger.error("定时任务 - 电量查询失败")

    except Exception as e:
        logger.error(f"定时任务执行失败: {e}")


# 在app.py中修改调度器设置
def setup_scheduler():
    """设置或更新定时任务"""
    global current_scheduler_job

    try:
        # 移除现有的定时任务
        if current_scheduler_job:
            scheduler.remove_job(current_scheduler_job)
            logger.info("移除现有定时任务")

        # 获取当前配置的查询间隔
        config = get_config()
        query_interval = config.get('query_interval', 30)  # 默认30分钟

        # 确保间隔至少为5分钟，避免频率过高
        if query_interval < 1:
            query_interval = 1
            logger.warning(f"查询间隔过短，已调整为{query_interval}分钟")

        # 添加新的定时任务，使用唯一ID
        current_scheduler_job = scheduler.add_job(
            func=electricity_query_task,
            trigger='interval',
            minutes=query_interval,
            id='electricity_query',
            name='electricity_query_task',
            replace_existing=True,
            max_instances=1  # 确保只有一个实例运行
        )

        logger.info(f"设置定时任务成功，间隔: {query_interval}分钟")

    except Exception as e:
        logger.error(f"设置定时任务失败: {e}")
# 路由定义
@app.route('/')
def index():
    """主页面 - 显示当前配置房间的数据"""
    config = get_config()
    room_info, _, _, _ = parse_room_info(config['electricity_params']['url'])

    # 获取当前房间的历史数据
    history_data = get_current_room_data()
    current_balance = history_data[-1]['balance'] if history_data else 0

    return render_template('index.html',
                           room_info=room_info,
                           history_data=json.dumps(history_data),
                           current_balance=current_balance)


@app.route('/api/test-push', methods=['POST'])
def api_test_push():
    """测试推送功能 - 支持群组推送测试"""
    try:
        config = get_config()
        push_params = config['push_params']

        title = "测试推送"
        content = "这是一条测试消息，用于验证推送功能是否正常工作"
        
        # 添加房间标识符（使用默认房间）
        room_identifier, _, _, _ = get_room_identifier(config['electricity_params']['url'])

        result = send_multichannel_notify(title, content, push_params, room_identifier)

        # 根据是否设置了群组编码，返回不同的消息
        topic = push_params.get('topic', '')
        if topic:
            message = f'推送测试成功，请检查群组所有成员是否收到消息（群组编码: {topic}）'
        else:
            message = '推送测试成功，请检查个人是否收到消息（未设置群组编码）'

        if result:
            return jsonify({
                'status': 'success',
                'message': message
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '推送测试失败，请检查配置和日志'
            }), 500

    except Exception as e:
        logger.error(f"推送测试失败: {e}")
        return jsonify({
            'status': 'error',
            'message': f'推送测试异常: {str(e)}'
        }), 500


@app.route('/api/history')
def api_history():
    """API接口：获取历史数据，支持房间筛选"""
    range_type = request.args.get('range', 'month')
    room_identifier = request.args.get('room', None)

    if range_type == 'week':
        days = 7
    elif range_type == 'day':
        days = 1
    else:  # month
        days = 30

    # 如果没有指定房间，使用当前配置的房间
    if not room_identifier:
        config = get_config()
        current_url = config['electricity_params']['url']
        room_identifier, _, _, _ = get_room_identifier(current_url)

    data = get_electricity_history(days, room_identifier)
    return jsonify(data)


@app.route('/api/room-info')
def api_room_info():
    """API接口：获取当前配置的房间信息"""
    try:
        config = get_config()
        current_url = config['electricity_params']['url']
        room_name, area_id, build_id, room_id = parse_room_info(current_url)

        return jsonify({
            'name': room_name,
            'url': current_url,
            'area_id': area_id,
            'build_id': build_id,
            'room_id': room_id
        })
    except Exception as e:
        logger.error(f"获取房间信息失败: {e}")
        return jsonify({
            'name': '未知房间',
            'url': '',
            'area_id': '',
            'build_id': '',
            'room_id': ''
        }), 500


@app.route('/api/measure', methods=['POST'])
def api_measure():
    """API接口：立即测量电量"""
    try:
        config = get_config()
        params = config['electricity_params']

        # 执行电量查询
        balance = ElectricityQuery(**params).query()
        if balance is not None:
            # 保存数据（自动按房间隔离）
            save_electricity_data(balance, params['url'])
            logger.info(f"手动测量成功: {balance}度")

            # 检查阈值并发送通知
            threshold = config.get('threshold', 20.0)
            if float(balance) < threshold:
                room_info = parse_room_info(params['url'])[0]
                push_params = config['push_params']

                title = "电量告急"
                content = f"{room_info}现在还剩电量：{balance}度，请及时充值"

                # 使用多渠道推送
                send_multichannel_notify(title, content, push_params)
                logger.info("低电量通知已发送")

            # 返回最新数据
            latest_data = {
                'timestamp': datetime.now().isoformat(),
                'balance': float(balance),
                'room_identifier': get_room_identifier(params['url'])[0]
            }

            return jsonify({
                'status': 'success',
                'message': f'测量成功: {balance}度',
                'data': latest_data
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '电量查询失败'
            }), 500

    except Exception as e:
        logger.error(f"手动测量失败: {e}")
        return jsonify({
            'status': 'error',
            'message': f'测量失败: {str(e)}'
        }), 500


@app.route('/config', methods=['GET', 'POST'])
def config():
    """配置页面"""
    config_data = get_config()

    if request.method == 'POST':
        # 获取推送渠道
        push_channels = request.form.getlist('push_channels')
        valid_channels = []
        for channel in push_channels:
            if ',' in channel:
                valid_channels.extend([ch.strip() for ch in channel.split(',')])
            else:
                valid_channels.append(channel)
        valid_channels = list(set([ch for ch in valid_channels if ch in ['wechat', 'mail', 'sms']]))

        # 获取群组编码
        topic = request.form.get('topic', '').strip()

        # 更新配置
        new_config = {
            'threshold': float(request.form.get('threshold', 20)),
            'query_interval': int(request.form.get('query_interval', 30)),
            'electricity_params': {
                'url': request.form.get('electricity_url', ''),
                'html_encode': request.form.get('html_encode', 'utf-8'),
                'timeout': int(request.form.get('timeout', 15))
            },
            'push_params': {
                'token': request.form.get('push_token', ''),
                'channel': valid_channels,
                'topic': topic  # 保存群组编码
            }
        }

        # 保存配置
        save_config(new_config)
        return jsonify({'status': 'success', 'message': '配置已保存'})

    return render_template('config.html', config=config_data)

@app.route('/config/reset', methods=['POST'])
def reset_config():
    """重置为默认配置"""
    save_config(DEFAULT_CONFIG)
    return jsonify({'status': 'success', 'message': '已恢复默认配置'})


if __name__ == '__main__':
    # 初始化数据库
    init_db()

    # 设置定时任务
    setup_scheduler()

    # 启动调度器
    scheduler.start()

    # 启动应用
    app.run(host='0.0.0.0', port=8080, debug=True,use_reloader=False)