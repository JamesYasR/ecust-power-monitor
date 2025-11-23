import requests
import logging
import argparse
from bs4 import BeautifulSoup
import re
import datetime

# 默认参数值
DEFAULT_HTML_ENCODE = 'utf-8'
DEFAULT_URL = 'https://yktyd.ecust.edu.cn/epay/wxpage/wanxiao/eleresult?sysid=1&roomid=103&areaid=2&buildid=3'
DEFAULT_AGENT_WECHAT = 'Mozilla/5.0 (Linux; Android 10; MI 9 Build/QKQ1.190825.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/78.0.3904.62 XWEB/2797 MMWEBSDK/20220101 Mobile Safari/537.36 MMWEBID/8070 MicroMessenger/8.0.20.2100(0x28001451) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64'
DEFAULT_AGENT_AND10 = 'Mozilla/5.0 (Linux; Android 10; MI 9 Build/QKQ1.190825.002; wv) AppleWebKit/537.36'
DEFAULT_REFERER = 'https://yktyd.ecust.edu.cn/'


# 配置日志
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


logger = setup_logging()


class ElectricityQuery:
    """电费查询类"""

    def __init__(self, html_encode=DEFAULT_HTML_ENCODE, url=DEFAULT_URL,
                 agent_wechat=DEFAULT_AGENT_WECHAT, agent_and10=DEFAULT_AGENT_AND10,
                 referer=DEFAULT_REFERER,
                 timeout=15):
        self.html_encode = html_encode
        self.url = url
        self.agent_wechat = agent_wechat
        self.agent_and10 = agent_and10
        self.referer = referer
        self.timeout = timeout

    def get_electricity_fixed(self):
        """针对具体HTML结构优化的电费查询函数"""
        headers = {
            'User-Agent': self.agent_wechat,
            'Referer': self.referer
        }

        try:
            logger.info("开始查询电量信息...")
            response = requests.get(self.url, headers=headers, timeout=self.timeout)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                logger.error(f"请求失败，状态码: {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            # 方法1：直接提取包含电量的div文本
            remaining_label = soup.find('label', class_='weui-label', string='剩余电量')
            if remaining_label:
                parent_div = remaining_label.find_parent('div', class_='weui-cell')
                if parent_div:
                    value_div = parent_div.find('div')
                    if value_div and value_div.text.strip():
                        balance_text = value_div.text.strip()
                        logger.info(f"通过方法1找到电量文本: '{balance_text}'")
                        balance_match = re.search(r'([\d.]+)', balance_text)
                        if balance_match:
                            balance = balance_match.group(1)
                            logger.info(f"解析成功！剩余电量: {balance}度")
                            return balance

            # 方法2：提取input标签的left-degree属性
            input_element = soup.find('input', {'id': 'roomdef'})
            if input_element and input_element.get('left-degree'):
                balance = input_element.get('left-degree')
                logger.info(f"通过方法2找到电量: {balance}度")
                return balance

            # 方法3：通过CSS选择器直接定位
            cells = soup.select('.weui-cell')
            for cell in cells:
                if '剩余电量' in cell.get_text():
                    value_div = cell.select_one('div')
                    if value_div:
                        balance_text = value_div.get_text(strip=True)
                        balance_match = re.search(r'([\d.]+)', balance_text)
                        if balance_match:
                            balance = balance_match.group(1)
                            logger.info(f"通过方法3找到电量: {balance}度")
                            return balance

            logger.error("所有解析方法都失败")
            return None

        except Exception as e:
            logger.error(f"发生错误: {str(e)}")
            return None

    def get_electricity_simple(self):
        """简化版本，直接使用正则表达式从HTML文本提取"""
        headers = {
            'User-Agent': self.agent_and10
        }

        try:
            response = requests.get(self.url, headers=headers, timeout=self.timeout)
            response.encoding = self.html_encode

            # 方法4：直接使用正则表达式搜索
            left_degree_match = re.search(r'left-degree="([\d.]+)"', response.text)
            if left_degree_match:
                return left_degree_match.group(1)

            # 方法5：搜索数字+度的模式
            degree_match = re.search(r'(\d+\.?\d*)\s*度', response.text)
            if degree_match:
                return degree_match.group(1)

            return None

        except Exception as e:
            logger.error(f"简化版本错误: {e}")
            return None

    def query(self):
        """执行电费查询"""
        logger.info("开始电费查询...")
        logger.info(f"使用URL: {self.url}")

        # 先尝试完整解析
        balance = self.get_electricity_fixed()

        if not balance:
            # 如果失败，尝试简化版本
            logger.info("完整解析失败，尝试简化版本...")
            balance = self.get_electricity_simple()

        return balance

    def save_result(self, balance, output_file='electricity_result.txt'):
        """保存结果到文件"""
        try:
            with open(output_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"{timestamp} - 剩余电量: {balance}度\n")
            logger.info(f"结果已保存到 {output_file}")
            return True
        except Exception as e:
            logger.error(f"保存文件失败: {e}")
            return False

    def save_debug_info(self, debug_file='debug_final.html'):
        """保存调试信息"""
        try:
            response = requests.get(
                self.url,
                headers={'User-Agent': self.agent_and10},
                timeout=self.timeout
            )
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.info(f"调试信息已保存到 {debug_file}")
            return True
        except Exception as e:
            logger.error(f"保存调试信息失败: {e}")
            return False


# 便捷函数，用于直接调用
def query_electricity(url=DEFAULT_URL, **kwargs):
    """便捷的电费查询函数"""
    query = ElectricityQuery(url=url, **kwargs)
    return query.query()


# 命令行接口
def main():
    """命令行主函数"""
    parser = argparse.ArgumentParser(description='电费查询脚本')

    parser.add_argument('--html-encode', type=str, default=DEFAULT_HTML_ENCODE,
                        help=f'网页编码 (默认: {DEFAULT_HTML_ENCODE})')
    parser.add_argument('--url', type=str, default=DEFAULT_URL,
                        help=f'查询URL (默认: {DEFAULT_URL})')
    parser.add_argument('--agent-wechat', type=str, default=DEFAULT_AGENT_WECHAT,
                        help=f'微信User-Agent')
    parser.add_argument('--agent-and10', type=str, default=DEFAULT_AGENT_AND10,
                        help=f'安卓10 User-Agent')
    parser.add_argument('--referer', type=str, default=DEFAULT_REFERER,
                        help=f'Referer头 (默认: {DEFAULT_REFERER})')
    parser.add_argument('--output-file', type=str, default='electricity_result.txt',
                        help='结果输出文件 (默认: electricity_result.txt)')
    parser.add_argument('--debug-file', type=str, default='debug_final.html',
                        help='调试信息文件 (默认: debug_final.html)')
    parser.add_argument('--timeout', type=int, default=15,
                        help='请求超时时间(秒) (默认: 15)')

    args = parser.parse_args()

    # 创建查询实例
    query = ElectricityQuery(
        html_encode=args.html_encode,
        url=args.url,
        agent_wechat=args.agent_wechat,
        agent_and10=args.agent_and10,
        referer=args.referer,
        timeout=args.timeout
    )

    # 执行查询
    balance = query.query()

    if balance:
        print(f"✅ 查询成功！剩余电量: {balance}度")
        query.save_result(balance, args.output_file)
    else:
        print("❌ 查询失败")
        query.save_debug_info(args.debug_file)


if __name__ == "__main__":
    main()