import urllib.parse
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class WechatMsgGenerator:
    def __init__(self, url: str):
        self.url = url
        self.params = self._parse_url()

    def _parse_url(self) -> Dict[str, Any]:
        """解析URL参数并返回参数字典"""
        parsed_url = urllib.parse.urlparse(self.url)
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # 提取参数值
        params = {}
        params['roomid'] = query_params.get('roomid', [''])[0]  # 房间号
        params['areaid'] = query_params.get('areaid', [''])[0]  # 校区ID
        params['buildid'] = query_params.get('buildid', [''])[0]  # 楼号
        params['amount'] = query_params.get('amount', [''])[0]  # 金额

        # 校区名称映射
        area_map = {'2': '奉贤', '3': '徐汇'}
        params['area_name'] = area_map.get(params['areaid'], '未知校区')

        return params

    def generate_title(self) -> str:
        """生成标题，格式如'奉贤3号楼103电费100元'"""
        params = self.params
        # 处理金额显示，如果是整数则显示整数，否则保留两位小数
        try:
            amount = float(params['amount'])
            if amount.is_integer():
                amount_str = str(int(amount))
            else:
                amount_str = f"{amount:.2f}"
        except (ValueError, TypeError):
            amount_str = params['amount']

        title = f"{params['area_name']}{params['buildid']}号楼{params['roomid']}电费{amount_str}元"
        return title

    def generate_html(self) -> str:
        """生成HTML文本，使用提供的模板并填充URL"""
        # HTML模板
        html_template = """<!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>华东理工大学一卡通缴费</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            }

            body {
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 15px;
            }

            .container {
                background: white;
                border-radius: 12px;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
                width: 100%;
                max-width: 360px;
                padding: 25px 20px;
                text-align: center;
            }

            h1 {
                color: #2c3e50;
                margin-bottom: 15px;
                font-weight: 600;
                font-size: 20px;
            }

            .description {
                color: #7f8c8d;
                margin-bottom: 20px;
                line-height: 1.5;
                font-size: 14px;
            }

            .link-container {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 20px;
                border: 1px solid #e9ecef;
                word-break: break-all;
            }

            .link {
                color: #3498db;
                text-decoration: none;
                font-size: 13px;
                line-height: 1.4;
                transition: color 0.2s;
            }

            .link:hover {
                color: #2980b9;
                text-decoration: underline;
            }

            .buttons {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
            }

            .btn {
                flex: 1;
                background: #3498db;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 6px;
                font-size: 15px;
                cursor: pointer;
                transition: all 0.2s;
                text-decoration: none;
                text-align: center;
            }

            .btn:hover {
                background: #2980b9;
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }

            /* 新增：信管中心按钮样式 */
            .btn-info {
                background: #5cb85c; /* 饱和度较低的绿色 */
                opacity: 0.9; /* 稍微降低不透明度 */
            }

            .btn-info:hover {
                background: #4cae4c; /* 悬停时稍深的绿色 */
            }

            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                background: #2ecc71;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
                transform: translateX(150%);
                transition: transform 0.3s ease;
                z-index: 1000;
                font-size: 14px;
            }

            .notification.show {
                transform: translateX(0);
            }

            .footer {
                margin-top: 20px;
                color: #95a5a6;
                font-size: 12px;
                line-height: 1.5;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>华东理工大学一卡通缴费</h1>
            <p class="description">若打不开先登录华信</p>

            <div class="link-container">
                <a href="{url}" 
                   class="link" 
                   target="_blank" 
                   id="payment-link">
                    {url}
                </a>
            </div>

            <div class="buttons">
                <a href="{url}" 
                   class="btn" 
                   target="_blank">
                    立即缴费
                </a>
                <!-- 新增：信管中心按钮 -->
                <a href="https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=MzUyMDY2NzQ0MA==&scene=124#wechat_redirect" 
                   class="btn btn-info" 
                   target="_blank">
                    信管中心
                </a>
            </div>

            <div class="footer">
                <p>此项目由不知名的某室长开源</p>
                <p>华东理工大学信息化办公室 提供技术支持</p>
            </div>
        </div>
    </body>
    </html>"""

        # 使用传入的URL替换模板中的占位符
        html_content = html_template.replace("{url}", self.url)
        return html_content


def generate_recharge_url(query_url, amount):
    """
    根据查询URL和充值金额生成充值URL

    Args:
        query_url: 查询电费的URL
        amount: 充值金额

    Returns:
        充值URL字符串
    """
    try:
        # 解析查询URL获取参数
        parsed = urllib.parse.urlparse(query_url)
        params = urllib.parse.parse_qs(parsed.query)

        # 提取必要参数
        sysid = params.get('sysid', ['1'])[0]  # 默认1
        roomid = params.get('roomid', [''])[0]
        areaid = params.get('areaid', [''])[0]
        buildid = params.get('buildid', [''])[0]

        # 构建充值URL
        recharge_params = {
            'sysid': sysid,
            'roomid': roomid,
            'areaid': areaid,
            'buildid': buildid,
            'amount': amount,
            'rest': 'undefined'
        }

        recharge_url = "https://yktyd.ecust.edu.cn/epay/wxpage/wanxiao/elepaybill"
        recharge_full_url = recharge_url + '?' + urllib.parse.urlencode(recharge_params)

        logger.info(f"生成充值URL: {recharge_full_url}")
        return recharge_full_url

    except Exception as e:
        logger.error(f"生成充值URL失败: {e}")
        return None