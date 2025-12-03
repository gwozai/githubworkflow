from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
import requests
import json
import uuid
import time
import hmac
import hashlib
import base64
import urllib.parse
from abc import ABC, abstractmethod
import logging
import secrets
from functools import wraps
import redis
import pickle

from config import get_config
from logger import setup_logging

app = Flask(__name__)
config_class = get_config()
app.config.from_object(config_class)

# Redis配置
app.config['REDIS_HOST'] = '106.12.107.176'
app.config['REDIS_PORT'] = 16379
app.config['REDIS_DB'] = 0
app.config['REDIS_PASSWORD'] = None  # 如果有密码请设置

# 会话配置（使用Redis存储会话）
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'notification_manager:'

# 初始化Redis连接
try:
    redis_client = redis.Redis(
        host=app.config['REDIS_HOST'],
        port=app.config['REDIS_PORT'],
        db=app.config['REDIS_DB'],
        password=app.config['REDIS_PASSWORD'],
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5
    )
    # 测试连接
    redis_client.ping()
    print("✅ Redis连接成功！")
    
    # 配置会话Redis连接
    app.config['SESSION_REDIS'] = redis_client
    
except Exception as e:
    print(f"❌ Redis连接失败: {e}")
    redis_client = None

# 缓存管理器
class CacheManager:
    """Redis缓存管理器"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.enabled = redis_client is not None
    
    def get(self, key):
        """获取缓存"""
        if not self.enabled:
            return None
        try:
            data = self.redis.get(key)
            if data:
                return pickle.loads(data.encode('latin1'))
            return None
        except Exception as e:
            app.logger.warning(f"缓存获取失败 {key}: {e}")
            return None
    
    def set(self, key, value, expire=3600):
        """设置缓存"""
        if not self.enabled:
            return False
        try:
            data = pickle.dumps(value).decode('latin1')
            return self.redis.setex(key, expire, data)
        except Exception as e:
            app.logger.warning(f"缓存设置失败 {key}: {e}")
            return False
    
    def delete(self, key):
        """删除缓存"""
        if not self.enabled:
            return False
        try:
            return self.redis.delete(key)
        except Exception as e:
            app.logger.warning(f"缓存删除失败 {key}: {e}")
            return False
    
    def exists(self, key):
        """检查缓存是否存在"""
        if not self.enabled:
            return False
        try:
            return self.redis.exists(key)
        except Exception as e:
            app.logger.warning(f"缓存检查失败 {key}: {e}")
            return False
    
    def clear_pattern(self, pattern):
        """清除匹配模式的缓存"""
        if not self.enabled:
            return False
        try:
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
            return True
        except Exception as e:
            app.logger.warning(f"缓存模式清除失败 {pattern}: {e}")
            return False

# 初始化缓存管理器
cache = CacheManager(redis_client)

# 添加自定义Jinja2过滤器
@app.template_filter('from_json')
def from_json_filter(value):
    """将JSON字符串转换为Python对象"""
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 数据库模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    api_token = db.Column(db.String(64), unique=True)
    token_expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    platforms = db.relationship('NotificationPlatform', backref='user', lazy=True)
    
    def generate_api_token(self, expires_in=365*24*3600):  # 默认1年过期
        """生成API Token"""
        self.api_token = secrets.token_urlsafe(32)
        self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        return self.api_token
    
    def verify_api_token(self):
        """验证API Token是否有效"""
        if not self.api_token or not self.token_expires_at:
            return False
        return datetime.utcnow() < self.token_expires_at and self.is_active

# 带缓存的Token验证函数
def verify_token_with_cache(token):
    """使用缓存验证API Token"""
    if not token:
        return None
    
    # 先从缓存中查找
    cache_key = f"api_token:{token}"
    cached_user = cache.get(cache_key)
    
    if cached_user is not None:
        # 缓存命中，直接返回
        return cached_user if cached_user else None
    
    # 缓存未命中，从数据库查询
    user = User.query.filter_by(api_token=token).first()
    
    if user and user.verify_api_token():
        # Token有效，缓存用户信息（缓存15分钟）
        cache.set(cache_key, user, expire=900)
        return user
    else:
        # Token无效，缓存空结果（缓存5分钟避免频繁查询）
        cache.set(cache_key, False, expire=300)
        return None

def invalidate_token_cache(token):
    """使Token缓存失效"""
    if token:
        cache_key = f"api_token:{token}"
        cache.delete(cache_key)

class NotificationPlatform(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    platform_type = db.Column(db.String(50), nullable=False)  # feishu, flomo, etc.
    webhook_url = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class NotificationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    platform_id = db.Column(db.Integer, db.ForeignKey('notification_platform.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # success, failed, pending
    response_code = db.Column(db.Integer)
    error_message = db.Column(db.Text)
    batch_id = db.Column(db.String(50))  # 批量发送ID
    template_id = db.Column(db.Integer, db.ForeignKey('message_template.id'))
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

# 新增消息模板表
class MessageTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)  # JSON格式的多平台内容
    variables = db.Column(db.Text)  # JSON格式的变量定义
    category = db.Column(db.String(50), default='custom')
    is_public = db.Column(db.Boolean, default=False)
    usage_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系
    user = db.relationship('User', backref='templates')
    logs = db.relationship('NotificationLog', backref='template')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# API认证装饰器
def require_api_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # 从Header获取token
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid authorization header format'}), 401
        
        # 从JSON body获取token (兼容旧版本)
        elif request.is_json and 'token' in request.get_json():
            token = request.get_json()['token']
        
        if not token:
            return jsonify({'error': 'Missing API token'}), 401
        
        # 验证token
        user = User.query.filter_by(api_token=token).first()
        if not user or not user.verify_api_token():
            return jsonify({'error': 'Invalid or expired API token'}), 401
        
        # 将用户信息传递给视图函数
        return f(user, *args, **kwargs)
    
    return decorated_function

# 通知机器人基类
class NotificationBot(ABC):
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    @abstractmethod
    def send_message(self, message):
        pass

class FeishuBot(NotificationBot):
    def send_message(self, message, mentions=None):
        headers = {"Content-Type": "application/json"}
        content = {"text": message}
        if mentions:
            content["text"] = f"<at user_id=\"{mentions}\">{message}</at>"
        payload = {"msg_type": "text", "content": content}
        
        try:
            response = requests.post(self.webhook_url, headers=headers, data=json.dumps(payload))
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'response': response.text
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 0,
                'response': str(e)
            }

class FlomoBot(NotificationBot):
    def send_message(self, message):
        headers = {"Content-Type": "application/json"}
        data = {"content": message}
        
        try:
            response = requests.post(self.webhook_url, headers=headers, data=json.dumps(data))
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'response': response.text
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 0,
                'response': str(e)
            }

class DingTalkBot(NotificationBot):
    def __init__(self, webhook_url, secret=None):
        super().__init__(webhook_url)
        self.secret = secret
    
    def _generate_sign(self, timestamp):
        """生成钉钉签名"""
        if not self.secret:
            return None
        
        string_to_sign = f'{timestamp}\n{self.secret}'
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return sign
    
    def send_message(self, message, msg_type='text', at_mobiles=None, at_all=False):
        """发送钉钉消息"""
        timestamp = str(round(time.time() * 1000))
        sign = self._generate_sign(timestamp)
        
        url = self.webhook_url
        if sign:
            url += f'&timestamp={timestamp}&sign={sign}'
        
        payload = {
            'msgtype': msg_type,
            msg_type: {'content': message}
        }
        
        # 添加@功能
        if at_mobiles or at_all:
            payload['at'] = {
                'atMobiles': at_mobiles or [],
                'isAtAll': at_all
            }
        
        try:
            response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
            result = response.json()
            
            return {
                'success': result.get('errcode') == 0,
                'status_code': response.status_code,
                'response': result.get('errmsg', response.text)
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 0,
                'response': str(e)
            }
    
    def send_markdown(self, title, content):
        """发送Markdown消息"""
        payload = {
            'msgtype': 'markdown',
            'markdown': {
                'title': title,
                'text': content
            }
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload, headers={'Content-Type': 'application/json'})
            result = response.json()
            
            return {
                'success': result.get('errcode') == 0,
                'status_code': response.status_code,
                'response': result.get('errmsg', response.text)
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 0,
                'response': str(e)
            }

class WeworkBot(NotificationBot):
    """企业微信机器人"""
    def send_message(self, message, msg_type='text', mentioned_list=None):
        """发送企业微信消息"""
        payload = {
            'msgtype': msg_type,
            msg_type: {'content': message}
        }
        
        # 添加@功能
        if mentioned_list:
            payload[msg_type]['mentioned_list'] = mentioned_list
        
        try:
            response = requests.post(
                self.webhook_url, 
                json=payload, 
                headers={'Content-Type': 'application/json'}
            )
            result = response.json()
            
            return {
                'success': result.get('errcode') == 0,
                'status_code': response.status_code,
                'response': result.get('errmsg', response.text)
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 0,
                'response': str(e)
            }
    
    def send_markdown(self, content):
        """发送Markdown消息"""
        payload = {
            'msgtype': 'markdown',
            'markdown': {'content': content}
        }
        
        try:
            response = requests.post(
                self.webhook_url, 
                json=payload, 
                headers={'Content-Type': 'application/json'}
            )
            result = response.json()
            
            return {
                'success': result.get('errcode') == 0,
                'status_code': response.status_code,
                'response': result.get('errmsg', response.text)
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 0,
                'response': str(e)
            }

class TelegramBot(NotificationBot):
    """Telegram机器人"""
    def __init__(self, webhook_url):
        # webhook_url格式: bot_token:chat_id
        super().__init__(webhook_url)
        parts = webhook_url.split(':')
        if len(parts) >= 2:
            self.bot_token = ':'.join(parts[:-1])
            self.chat_id = parts[-1]
        else:
            self.bot_token = webhook_url
            self.chat_id = None
    
    def send_message(self, message, parse_mode='HTML'):
        """发送Telegram消息"""
        if not self.chat_id:
            return {
                'success': False,
                'status_code': 0,
                'response': 'Invalid webhook format. Use: bot_token:chat_id'
            }
        
        url = f'https://api.telegram.org/bot{self.bot_token}/sendMessage'
        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': parse_mode
        }
        
        try:
            response = requests.post(url, json=payload)
            result = response.json()
            
            return {
                'success': result.get('ok', False),
                'status_code': response.status_code,
                'response': result.get('description', response.text)
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 0,
                'response': str(e)
            }

class EmailBot(NotificationBot):
    """邮件通知"""
    def __init__(self, webhook_url):
        # webhook_url格式: smtp_host:port:username:password:to_email
        super().__init__(webhook_url)
        parts = webhook_url.split(':')
        if len(parts) >= 5:
            self.smtp_host = parts[0]
            self.smtp_port = int(parts[1])
            self.username = parts[2]
            self.password = parts[3]
            self.to_email = ':'.join(parts[4:])  # 处理邮箱中可能的冒号
        else:
            self.smtp_host = None
    
    def send_message(self, message, subject='通知消息'):
        """发送邮件"""
        if not self.smtp_host:
            return {
                'success': False,
                'status_code': 0,
                'response': 'Invalid config. Use: smtp_host:port:username:password:to_email'
            }
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = self.to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(message, 'plain', 'utf-8'))
            
            server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            server.login(self.username, self.password)
            server.sendmail(self.username, self.to_email, msg.as_string())
            server.quit()
            
            return {
                'success': True,
                'status_code': 200,
                'response': 'Email sent successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 0,
                'response': str(e)
            }

class WebhookBot(NotificationBot):
    """通用Webhook"""
    def send_message(self, message):
        """发送到通用Webhook"""
        payload = {
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'notification_manager'
        }
        
        try:
            response = requests.post(
                self.webhook_url, 
                json=payload, 
                headers={'Content-Type': 'application/json'}
            )
            
            return {
                'success': response.status_code in [200, 201, 204],
                'status_code': response.status_code,
                'response': response.text[:500] if response.text else 'OK'
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 0,
                'response': str(e)
            }

# Bot工厂函数
def get_bot(platform_type, webhook_url):
    """根据平台类型获取对应的Bot实例"""
    bots = {
        'feishu': FeishuBot,
        'flomo': FlomoBot,
        'dingtalk': DingTalkBot,
        'wework': WeworkBot,
        'telegram': TelegramBot,
        'email': EmailBot,
        'webhook': WebhookBot
    }
    
    bot_class = bots.get(platform_type.lower())
    if bot_class:
        return bot_class(webhook_url)
    return None

# 路由
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('用户名已存在')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('邮箱已被注册')
            return render_template('register.html')
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功！请登录')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # 尝试从缓存获取统计数据
    cache_key = f"user_stats:{current_user.id}"
    cached_stats = cache.get(cache_key)
    
    if cached_stats:
        # 缓存命中，使用缓存的统计数据
        stats = cached_stats
        app.logger.info(f"Dashboard stats cache hit for user {current_user.id}")
    else:
        # 缓存未命中，从数据库查询
        platforms = NotificationPlatform.query.filter_by(user_id=current_user.id).all()
        total_platforms = len(platforms)
        success_count = NotificationLog.query.filter_by(user_id=current_user.id, status='success').count()
        failed_count = NotificationLog.query.filter_by(user_id=current_user.id, status='failed').count()
        total_count = success_count + failed_count
        
        stats = {
            'total_platforms': total_platforms,
            'success_count': success_count,
            'failed_count': failed_count,
            'total_count': total_count
        }
        
        # 缓存统计数据（缓存5分钟）
        cache.set(cache_key, stats, expire=300)
        app.logger.info(f"Dashboard stats cached for user {current_user.id}")
    
    # 最近日志不缓存，保持实时性
    recent_logs = NotificationLog.query.filter_by(user_id=current_user.id).order_by(NotificationLog.sent_at.desc()).limit(10).all()
    platforms = NotificationPlatform.query.filter_by(user_id=current_user.id).all()
    
    # 如果用户没有API Token，自动生成一个
    if not current_user.api_token:
        current_user.generate_api_token()
        db.session.commit()
    
    return render_template('dashboard.html', platforms=platforms, logs=recent_logs, stats=stats)

def invalidate_user_stats_cache(user_id):
    """使用户统计缓存失效"""
    cache_key = f"user_stats:{user_id}"
    cache.delete(cache_key)

# API Token管理
@app.route('/api_token')
@login_required
def api_token_page():
    return render_template('api_token.html')

@app.route('/api_token/generate', methods=['POST'])
@login_required
def generate_api_token():
    try:
        token = current_user.generate_api_token()
        db.session.commit()
        return jsonify({
            'success': True, 
            'token': token,
            'expires_at': current_user.token_expires_at.isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api_token/revoke', methods=['POST'])
@login_required
def revoke_api_token():
    try:
        current_user.api_token = None
        current_user.token_expires_at = None
        db.session.commit()
        return jsonify({'success': True, 'message': 'API Token已撤销'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/platforms')
@login_required
def platforms():
    platforms = NotificationPlatform.query.filter_by(user_id=current_user.id).all()
    return render_template('platforms.html', platforms=platforms)

@app.route('/add_platform', methods=['GET', 'POST'])
@login_required
def add_platform():
    if request.method == 'POST':
        name = request.form['name']
        platform_type = request.form['platform_type']
        webhook_url = request.form['webhook_url']
        
        platform = NotificationPlatform(
            user_id=current_user.id,
            name=name,
            platform_type=platform_type,
            webhook_url=webhook_url
        )
        db.session.add(platform)
        db.session.commit()
        
        flash('平台添加成功！')
        return redirect(url_for('platforms'))
    
    return render_template('add_platform.html')

@app.route('/edit_platform/<int:platform_id>', methods=['GET', 'POST'])
@login_required
def edit_platform(platform_id):
    platform = NotificationPlatform.query.filter_by(id=platform_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        platform.name = request.form['name']
        platform.platform_type = request.form['platform_type']
        platform.webhook_url = request.form['webhook_url']
        platform.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash('平台更新成功！')
        return redirect(url_for('platforms'))
    
    return render_template('edit_platform.html', platform=platform)

@app.route('/delete_platform/<int:platform_id>', methods=['POST'])
@login_required
def delete_platform(platform_id):
    platform = NotificationPlatform.query.filter_by(id=platform_id, user_id=current_user.id).first_or_404()
    db.session.delete(platform)
    db.session.commit()
    flash('平台删除成功！')
    return redirect(url_for('platforms'))

@app.route('/test_platform/<int:platform_id>', methods=['POST'])
@login_required
def test_platform(platform_id):
    platform = NotificationPlatform.query.filter_by(id=platform_id, user_id=current_user.id).first_or_404()
    
    test_message = "这是一条测试消息 🧍‍♂️"
    
    if platform.platform_type == 'feishu':
        bot = FeishuBot(platform.webhook_url)
        result = bot.send_message(test_message)
    elif platform.platform_type == 'flomo':
        bot = FlomoBot(platform.webhook_url)
        result = bot.send_message(test_message)
    elif platform.platform_type == 'dingtalk':
        bot = DingTalkBot(platform.webhook_url)
        result = bot.send_message(test_message)
    else:
        return jsonify({'error': '不支持的平台类型'})
    
    # 记录日志
    log = NotificationLog(
        user_id=current_user.id,
        platform_id=platform.id,
        message=test_message,
        status='success' if result['success'] else 'failed',
        response_code=result['status_code'],
        error_message=result['response'] if not result['success'] else None
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify(result)

# API 路由
@app.route('/api/send', methods=['POST'])
def api_send():
    data = request.get_json()
    
    # 支持Header和Body两种认证方式
    token = None
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]  # 移除 "Bearer " 前缀
    elif data and 'token' in data:
        token = data['token']
    
    if not data or 'message' not in data:
        return jsonify({'error': '缺少必要参数'}), 400
    
    if not token:
        return jsonify({'error': '缺少认证Token'}), 401
    
    # 使用缓存验证Token
    user = verify_token_with_cache(token)
    if not user:
        return jsonify({'error': '无效的token'}), 401
    
    message = data['message']
    platform_name = data.get('platform', None)
    
    # 获取用户的平台
    if platform_name:
        platforms = NotificationPlatform.query.filter_by(
            user_id=user.id, 
            name=platform_name, 
            is_active=True
        ).all()
    else:
        platforms = NotificationPlatform.query.filter_by(
            user_id=user.id, 
            is_active=True
        ).all()
    
    if not platforms:
        return jsonify({'error': '没有找到可用的通知平台'}), 404
    
    results = []
    for platform in platforms:
        if platform.platform_type == 'feishu':
            bot = FeishuBot(platform.webhook_url)
        elif platform.platform_type == 'flomo':
            bot = FlomoBot(platform.webhook_url)
        elif platform.platform_type == 'dingtalk':
            bot = DingTalkBot(platform.webhook_url)
        else:
            continue
        
        result = bot.send_message(message)
        
        # 记录日志
        log = NotificationLog(
            user_id=user.id,
            platform_id=platform.id,
            message=message,
            status='success' if result['success'] else 'failed',
            response_code=result['status_code'],
            error_message=result['response'] if not result['success'] else None
        )
        db.session.add(log)
        
        results.append({
            'platform': platform.name,
            'success': result['success'],
            'status_code': result['status_code']
        })
    
    db.session.commit()
    
    # 发送完成后，使用户统计缓存失效
    invalidate_user_stats_cache(user.id)
    
    return jsonify({
        'message': '通知发送完成',
        'results': results
    })

# 消息模板路由
@app.route('/templates')
@login_required
def templates():
    user_templates = MessageTemplate.query.filter_by(user_id=current_user.id).all()
    public_templates = MessageTemplate.query.filter_by(is_public=True).limit(10).all()
    return render_template('templates.html', 
                         user_templates=user_templates,
                         public_templates=public_templates)

@app.route('/templates/create', methods=['GET', 'POST'])
@login_required
def create_template():
    if request.method == 'POST':
        template = MessageTemplate(
            user_id=current_user.id,
            name=request.form['name'],
            description=request.form.get('description', ''),
            content=request.form['content'],
            variables=request.form.get('variables', '[]'),
            category=request.form.get('category', 'custom')
        )
        db.session.add(template)
        db.session.commit()
        flash('模板创建成功！')
        return redirect(url_for('templates'))
    return render_template('create_template.html')

@app.route('/templates/edit/<int:template_id>', methods=['GET', 'POST'])
@login_required
def edit_template(template_id):
    template = MessageTemplate.query.filter_by(id=template_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        template.name = request.form['name']
        template.description = request.form.get('description', '')
        template.content = request.form['content']
        template.variables = request.form.get('variables', '[]')
        template.category = request.form.get('category', 'custom')
        template.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('模板更新成功！')
        return redirect(url_for('templates'))
    
    return render_template('edit_template.html', template=template)

@app.route('/templates/delete/<int:template_id>', methods=['POST'])
@login_required
def delete_template(template_id):
    template = MessageTemplate.query.filter_by(id=template_id, user_id=current_user.id).first_or_404()
    db.session.delete(template)
    db.session.commit()
    flash('模板删除成功！')
    return redirect(url_for('templates'))

@app.route('/api/send_template', methods=['POST'])
def api_send_template():
    data = request.get_json()
    
    # 支持Header和Body两种认证方式
    token = None
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]  # 移除 "Bearer " 前缀
    elif data and 'token' in data:
        token = data['token']
    
    if not data or 'template_id' not in data:
        return jsonify({'error': '缺少必要参数'}), 400
    
    if not token:
        return jsonify({'error': '缺少认证Token'}), 401
    
    # 使用缓存验证Token
    user = verify_token_with_cache(token)
    if not user:
        return jsonify({'error': '无效的token'}), 401
    
    template = MessageTemplate.query.get(data['template_id'])
    if not template:
        return jsonify({'error': '模板不存在'}), 404
    
    # 检查权限
    if template.user_id != user.id and not template.is_public:
        return jsonify({'error': '无权限使用此模板'}), 403
    
    # 渲染模板内容
    variables = data.get('variables', {})
    try:
        rendered_content = template.content
        for key, value in variables.items():
            rendered_content = rendered_content.replace(f'{{{{{key}}}}}', str(value))
    except Exception as e:
        return jsonify({'error': f'模板渲染失败: {str(e)}'}), 400
    
    # 获取目标平台
    platform_name = data.get('platform')
    if platform_name:
        platforms = NotificationPlatform.query.filter_by(
            user_id=user.id, 
            name=platform_name, 
            is_active=True
        ).all()
    else:
        platforms = NotificationPlatform.query.filter_by(
            user_id=user.id, 
            is_active=True
        ).all()
    
    if not platforms:
        return jsonify({'error': '没有找到可用的通知平台'}), 404
    
    results = []
    for platform in platforms:
        if platform.platform_type == 'feishu':
            bot = FeishuBot(platform.webhook_url)
        elif platform.platform_type == 'flomo':
            bot = FlomoBot(platform.webhook_url)
        elif platform.platform_type == 'dingtalk':
            bot = DingTalkBot(platform.webhook_url)
        else:
            continue
        
        result = bot.send_message(rendered_content)
        
        # 记录日志
        log = NotificationLog(
            user_id=user.id,
            platform_id=platform.id,
            template_id=template.id,
            message=rendered_content,
            status='success' if result['success'] else 'failed',
            response_code=result['status_code'],
            error_message=result['response'] if not result['success'] else None
        )
        db.session.add(log)
        
        results.append({
            'platform': platform.name,
            'success': result['success'],
            'status_code': result['status_code']
        })
    
    # 更新模板使用次数
    template.usage_count += 1
    db.session.commit()
    
    return jsonify({
        'message': '模板消息发送完成',
        'template': template.name,
        'results': results
    })

# 获取模板详情API
@app.route('/api/template/<int:template_id>')
@login_required
def api_get_template(template_id):
    template = MessageTemplate.query.filter_by(
        id=template_id, 
        user_id=current_user.id
    ).first()
    
    if not template:
        return jsonify({'error': '模板不存在'}), 404
    
    return jsonify({
        'id': template.id,
        'name': template.name,
        'description': template.description,
        'content': template.content,
        'variables': json.loads(template.variables) if template.variables else [],
        'category': template.category,
        'usage_count': template.usage_count,
        'created_at': template.created_at.isoformat()
    })



# 复制公共模板API
@app.route('/api/copy_template/<int:template_id>', methods=['POST'])
@login_required
def api_copy_template(template_id):
    # 获取公共模板
    public_template = MessageTemplate.query.filter_by(
        id=template_id, 
        is_public=True
    ).first()
    
    if not public_template:
        return jsonify({'error': '公共模板不存在'}), 404
    
    # 检查用户是否已经复制过这个模板
    existing = MessageTemplate.query.filter_by(
        user_id=current_user.id,
        name=f"{public_template.name} (复制)"
    ).first()
    
    if existing:
        return jsonify({'error': '您已经复制过这个模板'}), 400
    
    # 创建副本
    new_template = MessageTemplate(
        user_id=current_user.id,
        name=f"{public_template.name} (复制)",
        description=public_template.description,
        content=public_template.content,
        variables=public_template.variables,
        category=public_template.category
    )
    
    db.session.add(new_template)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '模板复制成功'})

@app.route('/api/recent_logs')
@login_required
def api_recent_logs():
    logs = NotificationLog.query.filter_by(user_id=current_user.id)\
                              .order_by(NotificationLog.sent_at.desc())\
                              .limit(10).all()
    return jsonify({
        'logs': [{
            'id': log.id,
            'message': log.message,
            'status': log.status,
            'error_message': log.error_message,
            'sent_at': log.sent_at.strftime('%m-%d %H:%M')
        } for log in logs]
    })

if __name__ == '__main__':
    # 设置日志
    setup_logging(app)
    
    with app.app_context():
        db.create_all()
        app.logger.info("数据库初始化完成！")
    
    app.logger.info("🧍‍♂️ 通知管理系统启动中...")
    app.logger.info(f"访问地址: http://localhost:5555")
    app.logger.info("按 Ctrl+C 停止服务")
    
    app.run(host='0.0.0.0', port=5555, debug=app.config.get('DEBUG', False))
