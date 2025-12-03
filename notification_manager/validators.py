"""
数据验证和输入过滤模块
"""
import re
from urllib.parse import urlparse
from flask import request
from functools import wraps

class ValidationError(Exception):
    """验证错误异常"""
    pass

class InputValidator:
    """输入验证器"""
    
    @staticmethod
    def validate_username(username):
        """验证用户名"""
        if not username or len(username) < 3:
            raise ValidationError("用户名至少需要3个字符")
        if len(username) > 20:
            raise ValidationError("用户名不能超过20个字符")
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError("用户名只能包含字母、数字和下划线")
        return True
    
    @staticmethod
    def validate_email(email):
        """验证邮箱"""
        if not email:
            raise ValidationError("邮箱不能为空")
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValidationError("邮箱格式不正确")
        return True
    
    @staticmethod
    def validate_password(password):
        """验证密码"""
        if not password or len(password) < 6:
            raise ValidationError("密码至少需要6个字符")
        if len(password) > 128:
            raise ValidationError("密码不能超过128个字符")
        return True
    
    @staticmethod
    def validate_webhook_url(url):
        """验证Webhook URL"""
        if not url:
            raise ValidationError("Webhook URL不能为空")
        
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValidationError("URL格式不正确")
            if parsed.scheme not in ['http', 'https']:
                raise ValidationError("URL必须使用http或https协议")
        except Exception:
            raise ValidationError("URL格式不正确")
        
        return True
    
    @staticmethod
    def validate_platform_name(name):
        """验证平台名称"""
        if not name or len(name.strip()) < 1:
            raise ValidationError("平台名称不能为空")
        if len(name) > 100:
            raise ValidationError("平台名称不能超过100个字符")
        return True
    
    @staticmethod
    def validate_message_content(content):
        """验证消息内容"""
        if not content or len(content.strip()) < 1:
            raise ValidationError("消息内容不能为空")
        if len(content) > 4000:
            raise ValidationError("消息内容不能超过4000个字符")
        return True
    
    @staticmethod
    def validate_template_name(name):
        """验证模板名称"""
        if not name or len(name.strip()) < 1:
            raise ValidationError("模板名称不能为空")
        if len(name) > 100:
            raise ValidationError("模板名称不能超过100个字符")
        return True
    
    @staticmethod
    def sanitize_html(text):
        """清理HTML标签"""
        if not text:
            return text
        # 简单的HTML标签清理
        clean_text = re.sub(r'<[^>]+>', '', text)
        return clean_text.strip()
    
    @staticmethod
    def validate_json_variables(variables_json):
        """验证JSON变量格式"""
        if not variables_json:
            return True
        
        try:
            import json
            variables = json.loads(variables_json)
            if not isinstance(variables, list):
                raise ValidationError("变量必须是数组格式")
            
            for var in variables:
                if not isinstance(var, dict):
                    raise ValidationError("变量项必须是对象格式")
                if 'name' not in var:
                    raise ValidationError("变量必须包含name字段")
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var['name']):
                    raise ValidationError(f"变量名 '{var['name']}' 格式不正确")
        except json.JSONDecodeError:
            raise ValidationError("变量JSON格式不正确")
        
        return True

def validate_request_data(required_fields=None, optional_fields=None):
    """请求数据验证装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return {'error': '请求必须是JSON格式'}, 400
            
            data = request.get_json()
            if not data:
                return {'error': '请求数据不能为空'}, 400
            
            # 检查必需字段
            if required_fields:
                for field in required_fields:
                    if field not in data:
                        return {'error': f'缺少必需字段: {field}'}, 400
            
            # 检查未知字段
            allowed_fields = set(required_fields or []) | set(optional_fields or [])
            unknown_fields = set(data.keys()) - allowed_fields
            if unknown_fields:
                return {'error': f'未知字段: {", ".join(unknown_fields)}'}, 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def rate_limit_by_user(max_requests=100, window=3600):
    """用户级别的限流装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 这里可以实现Redis-based的限流逻辑
            # 暂时跳过实现，返回原函数
            return f(*args, **kwargs)
        return decorated_function
    return decorator
