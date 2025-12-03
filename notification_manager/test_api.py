#!/usr/bin/env python3
"""
API测试脚本
用于测试通知管理系统的API功能
"""

import requests
import json

# 配置
BASE_URL = "http://localhost:5555"
TEST_TOKEN = "testuser"  # 替换为你的用户名
TEST_MESSAGE = "这是一条API测试消息 🧍‍♂️"

def test_send_notification():
    """测试发送通知API"""
    url = f"{BASE_URL}/api/send"
    
    payload = {
        "token": TEST_TOKEN,
        "message": TEST_MESSAGE
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print(f"发送测试通知到: {url}")
        print(f"消息内容: {TEST_MESSAGE}")
        print("-" * 50)
        
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 通知发送成功!")
            print(f"发送结果: {result}")
        else:
            print("❌ 通知发送失败!")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def test_send_to_specific_platform():
    """测试发送到指定平台"""
    url = f"{BASE_URL}/api/send"
    
    payload = {
        "token": TEST_TOKEN,
        "message": "发送到指定平台的测试消息 🧍‍♂️",
        "platform": "我的飞书机器人"  # 替换为你的平台名称
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print(f"发送测试通知到指定平台: {url}")
        print(f"平台名称: {payload['platform']}")
        print(f"消息内容: {payload['message']}")
        print("-" * 50)
        
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 通知发送成功!")
            print(f"发送结果: {result}")
        else:
            print("❌ 通知发送失败!")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")

if __name__ == "__main__":
    print("🧍‍♂️ 通知管理系统 API 测试")
    print("=" * 50)
    
    print("\n1. 测试发送通知到所有平台:")
    test_send_notification()
    
    print("\n2. 测试发送通知到指定平台:")
    test_send_to_specific_platform()
    
    print("\n测试完成!")
    print("\n使用说明:")
    print("1. 确保应用正在运行 (python run.py)")
    print("2. 修改 TEST_TOKEN 为你的用户名")
    print("3. 在系统中配置好通知平台")
    print("4. 运行此脚本进行测试")
