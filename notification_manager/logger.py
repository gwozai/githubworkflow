"""
日志系统配置
"""
import logging
import logging.handlers
import os
from datetime import datetime
import json

class JSONFormatter(logging.Formatter):
    """JSON格式的日志格式化器"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # 添加异常信息
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # 添加自定义字段
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'platform_type'):
            log_entry['platform_type'] = record.platform_type
        
        return json.dumps(log_entry, ensure_ascii=False)

def setup_logging(app):
    """设置应用日志"""
    
    # 创建日志目录
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 设置日志级别
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
    
    # 创建根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 清除现有的处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器（按日期轮转）
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(log_dir, 'app.log'),
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)
    
    # 错误日志文件处理器
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(log_dir, 'error.log'),
        when='midnight',
        interval=1,
        backupCount=90,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)
    
    # API访问日志
    api_logger = logging.getLogger('api')
    api_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(log_dir, 'api.log'),
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    api_handler.setFormatter(JSONFormatter())
    api_logger.addHandler(api_handler)
    api_logger.setLevel(logging.INFO)
    
    # 通知发送日志
    notification_logger = logging.getLogger('notification')
    notification_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(log_dir, 'notification.log'),
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    notification_handler.setFormatter(JSONFormatter())
    notification_logger.addHandler(notification_handler)
    notification_logger.setLevel(logging.INFO)
    
    # 设置第三方库的日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    app.logger.info("日志系统初始化完成")

class LoggerMixin:
    """日志混入类"""
    
    @property
    def logger(self):
        return logging.getLogger(self.__class__.__name__)

def log_api_request(logger_name='api'):
    """API请求日志装饰器"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            logger = logging.getLogger(logger_name)
            
            # 记录请求开始
            start_time = datetime.utcnow()
            logger.info(
                "API请求开始",
                extra={
                    'method': request.method,
                    'url': request.url,
                    'remote_addr': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'start_time': start_time.isoformat()
                }
            )
            
            try:
                result = f(*args, **kwargs)
                
                # 记录请求成功
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                logger.info(
                    "API请求成功",
                    extra={
                        'method': request.method,
                        'url': request.url,
                        'duration': duration,
                        'status': 'success'
                    }
                )
                
                return result
                
            except Exception as e:
                # 记录请求失败
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                logger.error(
                    f"API请求失败: {str(e)}",
                    extra={
                        'method': request.method,
                        'url': request.url,
                        'duration': duration,
                        'status': 'error',
                        'error': str(e)
                    },
                    exc_info=True
                )
                raise
                
        return decorated_function
    return decorator

def log_notification_send(platform_type, user_id):
    """通知发送日志"""
    logger = logging.getLogger('notification')
    
    def decorator(f):
        def decorated_function(*args, **kwargs):
            start_time = datetime.utcnow()
            
            try:
                result = f(*args, **kwargs)
                
                # 记录发送结果
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                logger.info(
                    "通知发送完成",
                    extra={
                        'user_id': user_id,
                        'platform_type': platform_type,
                        'duration': duration,
                        'success': result.get('success', False),
                        'status_code': result.get('status_code'),
                        'response': result.get('response', '')[:200]  # 限制响应长度
                    }
                )
                
                return result
                
            except Exception as e:
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                logger.error(
                    f"通知发送失败: {str(e)}",
                    extra={
                        'user_id': user_id,
                        'platform_type': platform_type,
                        'duration': duration,
                        'error': str(e)
                    },
                    exc_info=True
                )
                raise
                
        return decorated_function
    return decorator
