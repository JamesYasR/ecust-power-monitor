# ecust-power-monitor
**自动抓取华理宿舍剩余电量数据并在低电量发出提醒（邮箱微信短信）**

**可视化前端，可视化配置,可docker部署或者本地运行**

**支持切换不同寝室，数据分隔存储互不影响**

2025.11.24 新增快捷支付功能，修复了主页title显示的问题，修复了容器内时区不对的问题

：设置默认充值金额，点击主页的充电按钮，后端会把付款链接直接发送到微信上，点击即可

但是如果你短时间内没有登陆过信息办的电费缴费系统，那么可能打不开链接...请点击右边的“信管中心”按钮，进入公众号，点击“微门户”-“电费充值"，点击“电费充值"之后就可以退出了，在一段时间内你就可以直接使用快捷支付按钮一键充值了
![Screenshot_20251124_170227_com tencent mm](https://github.com/user-attachments/assets/3d7c7d6b-8c4d-40b9-b012-2de4acc063a8)

0.前端使用注意事项

```
所有可调参数都在前端的配置界面里面
第一次构建的时候url,pushplus的token和群组码都是空着的，所以网页会报错是正常的
自己填好了以后就可以使用了
#######################重要######################
如果修改了检测间隔时间（单位是分钟），docker需要重启一下才能生效，本地运行建议也重启一下
#######################重要######################
url:
进入华理信管中心电费充值-选择好校区，楼号，寝室以后，进入电量查询界面（能看到剩了多少度电的地方）
然后右上角点击，链接分享，得到的链接就是url
pushplus：
是一家公司提供的api，需要自己注册填写信息拿到token（强隐私信息，注意不要外泄）
如果想发到多人，需要让你的室友也注册，你建立群组，获得群组码（这个是自定义的）
在前端如果群组码是空的，那么默认发给你自己
发送邮箱和微信（公众号消息）是免费的，选择短信需要你自己买积分（一条一毛钱）
```

1.本地部署

直接运行app.py，开在本地8080端口

python环境已经提供在requirements.txt里面

2.docker部署

直接使用镜像部署(compose)

```
services:
  eecust-power-monitor:
    build: .
    image: crpi-kp4alpljgmcdwnr9.cn-hangzhou.personal.cr.aliyuncs.com/jamesyasr/ecust-power-monitor:1.0
    ports:
      - "8080:8080"
    volumes:
      - /your/path/data:/app/data  # 持久化数据库
    environment:
      - PYTHONUNBUFFERED=1
      - DATA_DIR=/app/data  # 明确设置数据目录
    restart: always
    container_name: ecust-power-monitor
    # 确保数据目录权限
    command: python app.py
```



如果你自己修改了程序，请使用docker compose编译镜像并部署，进入工作目录以后

```
sudo docker compose build --no-cache
```

如果数据库db文件不能正常生成是因为文件夹权限问题：

```sudo mkdir -p /your/docker/path/data
然后
sudo chown -R 1000:1000 /your/docker/path/data 
#这里的1000是容器中的apprunner的uid，我的是999，具体查询方法如下：
sudo docker exec <容器名称> id
最后给权限：
sudo chmod 755 /your/docker/path/data
检查你自己建立的data目录下有没有db文件生成,若有则解决了
```


<img width="2290" height="1223" alt="image" src="https://github.com/user-attachments/assets/d694039c-4598-4294-86c2-8601f0ac9e44" />
<img width="1808" height="1054" alt="image" src="https://github.com/user-attachments/assets/2aa099c1-4b4c-4320-8f19-1c6aa0373d54" />

