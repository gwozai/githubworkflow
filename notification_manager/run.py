#!/usr/bin/env python3
"""
通知管理系统启动脚本
"""

from app import app, db

if __name__ == '__main__':
    # 创建数据库表
    with app.app_context():
        db.create_all()
        print("数据库初始化完成！")
    
    print("🧍‍♂️ 通知管理系统启动中...")
    print("访问地址: http://localhost:5555")
    print("按 Ctrl+C 停止服务")
    
    # 启动应用
    app.run(debug=True, host='0.0.0.0', port=5555)
