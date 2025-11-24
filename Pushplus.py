import hashlib
from datetime import datetime
import json
import requests
import argparse
import logging
import random

import random
# 配置日志
logger = logging.getLogger(__name__)

# 默认参数值
DEFAULT_PUSHPULS_TOKEN = ''
DEFAULT_CHANNEL = 'mail'


class PushPlusNotifier:
    """PushPlus消息推送类 - 支持群组推送"""

    def __init__(self, token=DEFAULT_PUSHPULS_TOKEN, channel=DEFAULT_CHANNEL, topic=''):
        self.token = token
        self.channel = channel
        self.topic = topic  # 群组编码/话题编码
        self.base_url = 'https://www.pushplus.plus/send'
        self.last_content_hash = None

    def generate_variation_content(self, base_content):
        """生成有变化的推送内容，避免重复检测"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        current_time = datetime.now().strftime('%H:%M:%S')
        random_suffix = random.randint(1000, 9999)
        # 定义 current_time 变量

        # 多种变化模板
        variation_templates = [
            "\n\n—— 自动监控系统 {time}",
            "\n\n[更新于 {time}]",
            "\n\n⏰ 监控时间: {time}",
            "\n\n🔔 系统提醒 {time}",
            "\n\n📊 编号: {random} | 时间: {time}",
            "\n\n💡 提醒时间: {time}",
            "\n\n⚡ 电力监控 {time}",
            "\n\n🏠 房间监控 {time}"
        ]

        template = random.choice(variation_templates)
        variation = template.format(time=timestamp, random=random_suffix)
        varied_content = base_content + variation

        return varied_content

    def pushplus_notify(self, title, content):
        """发送PushPlus通知，支持群组推送"""
        today = datetime.now().strftime('%Y-%m-%d')
        full_title = f"{title} {today}"
        varied_content = self.generate_variation_content(content)

        # 基础数据
        data = {
            "token": self.token,
            "title": full_title,
            "content": varied_content,
            "template": "html",
            "channel": self.channel
        }

        # 添加群组推送参数
        if self.topic:
            data["topic"] = self.topic  # 群组/话题编码
            logger.info(f"启用群组推送，群组编码: {self.topic}")

        try:
            logger.info(f"开始推送消息: 渠道={self.channel}, 群组={self.topic or '个人'}, token={self.token[:8]}...")

            headers = {'Content-Type': 'application/json'}
            response = requests.post(self.base_url, json=data, headers=headers, timeout=10)

            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('code') == 200:
                    logger.info("推送成功")
                    return True
                else:
                    error_msg = response_data.get('msg', '未知错误')
                    logger.error(f"推送失败: {error_msg}")
                    
                    # 如果是topic错误，尝试不使用topic发送
                    if "topic" in error_msg.lower():
                        logger.info("尝试不使用群组编码发送...")
                        data.pop("topic", None)
                        response = requests.post(self.base_url, json=data, headers=headers, timeout=10)
                        if response.status_code == 200:
                            response_data = response.json()
                            if response_data.get('code') == 200:
                                logger.info("个人推送成功")
                                return True
                    
                    return False
            else:
                logger.error(f"推送失败，HTTP状态码: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"推送过程中出错: {str(e)}")
            return False


# 便捷函数，保持向后兼容
def pushplus_notify(title, content, token=DEFAULT_PUSHPULS_TOKEN, channel=DEFAULT_CHANNEL):
    """
    发送PushPlus通知的便捷函数

    Args:
        title (str): 通知标题
        content (str): 通知内容
        token (str): PushPlus token，默认为预定义值
        channel (str): 推送渠道，默认为'mail'
    """
    notifier = PushPlusNotifier(token, channel)
    return notifier.pushplus_notify(title, content)





# 命令行接口
def main():
    parser = argparse.ArgumentParser(description='PushPlus消息推送')
    parser.add_argument('--title', required=True, help='通知标题')
    parser.add_argument('--content', required=True, help='通知内容')
    parser.add_argument('--token', default=DEFAULT_PUSHPULS_TOKEN, help='PushPlus token')
    parser.add_argument('--channel', default=DEFAULT_CHANNEL, help='推送渠道')

    args = parser.parse_args()

    # 使用便捷函数
    result = pushplus_notify(
        title=args.title,
        content=args.content,
        token=args.token,
        channel=args.channel
    )

    if result:
        print("消息推送完成")
    else:
        print("消息推送失败")

if __name__ == "__main__":
    main()
