# 使用官方的Python slim镜像作为基础，兼顾体积与兼容性
FROM python:3.11-slim

# 设置环境变量，防止Python输出缓冲，确保日志实时输出
ENV PYTHONUNBUFFERED=1

# 设置容器内的工作目录
WORKDIR /app

# 1. 首先只复制依赖列表文件（这一步可充分利用Docker的构建缓存）
COPY requirements.txt .

# 2. 安装项目依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 3. 将应用程序代码复制到容器中
COPY . .

# 创建数据目录并确保权限正确
RUN mkdir -p /app/data && chmod 755 /app/data

# 创建一个非root用户来运行应用，增强安全性
RUN groupadd -r apprunner && useradd -r -g apprunner apprunner
# 将应用目录的所有权交给新创建的用户
RUN chown -R apprunner:apprunner /app
# 同时确保数据目录对apprunner可写
RUN chown -R apprunner:apprunner /app/data

USER apprunner

# 暴露Flask应用运行的端口
EXPOSE 8080

# 设置容器启动时运行的命令
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "app:app"]