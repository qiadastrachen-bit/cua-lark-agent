#!/usr/bin/env python3
"""
上传 Demo 视频到 GitHub Release
使用方法: python upload_videos_to_release.py <github_token>
"""

import sys
import json
import requests

REPO_OWNER = "qiadastrachen-bit"
REPO_NAME = "cua-lark-agent"
RELEASE_TAG = "v2.0-m2-submission"

VIDEOS = [
    "videos/陈锦彤.mp4",
    "videos/一些小计划.mp4",
    "videos/日历.mp4",
]

def create_release(token):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "tag_name": RELEASE_TAG,
        "name": "M2 复赛提交 - Demo 视频",
        "body": """## Larker M2 复赛 Demo 视频

### E2E 测试演示（通过率 100%）

| 用例 | 搜索词 | 视频 |
|------|--------|------|
| TC001 - 搜索联系人 | 陈锦彤 | 陈锦彤.mp4 |
| TC002 - 搜索文档 | 一些小计划 | 一些小计划.mp4 |
| TC003 - 搜索功能 | 日历 | 日历.mp4 |

**运行环境**: Windows 11, 飞书桌面端
**录制方式**: mss 截帧 + cv2.VideoWriter 合成 (10fps)
**提交日期**: 2026-05-07""",
        "draft": False,
        "prerelease": False,
    }
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()["upload_url"]

def upload_asset(upload_url, token, file_path):
    import os
    filename = os.path.basename(file_path)
    url = upload_url.replace("{?name,label}", f"?name={filename}")
    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "video/mp4",
        "Accept": "application/vnd.github.v3+json",
    }
    with open(file_path, "rb") as f:
        resp = requests.post(url, headers=headers, data=f)
    resp.raise_for_status()
    print(f"✅ 上传成功: {filename}")
    return resp.json()["browser_download_url"]

def main():
    if len(sys.argv) < 2:
        print("用法: python upload_videos_to_release.py <github_token>")
        sys.exit(1)

    token = sys.argv[1]
    print("📦 创建 Release...")
    upload_url = create_release(token)
    print(f"✅ Release 创建成功: {upload_url}")

    for video in VIDEOS:
        print(f"📤 上传 {video}...")
        url = upload_asset(upload_url, token, video)
        print(f"🔗 下载链接: {url}")

    print("\n🎉 全部完成！")
    print(f"📋 Release 页面: https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/tag/{RELEASE_TAG}")

if __name__ == "__main__":
    main()
