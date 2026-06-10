#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Markdown书签转HTML书签工具
将Markdown格式的书签文件转换为浏览器可识别的HTML书签文件
"""

import re
import os
import chardet

def detect_encoding(file_path):
    """
    检测文件编码
    
    Args:
        file_path (str): 文件路径
        
    Returns:
        str: 检测到的编码名称
        
    Raises:
        Exception: 无法识别编码时抛出异常
    """
    encodings = ['gbk', 'gb2312', 'utf-8', 'ansi', 'gb18030']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read()
            return encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    # 使用chardet自动检测
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        encoding = result.get('encoding', 'utf-8')
        if encoding.lower() == 'gb2312':
            encoding = 'gbk'
        return encoding

def markdown_bookmarks_to_html(md_file_path, html_file_path):
    """
    将Markdown格式的书签文件转换为HTML书签文件
    
    Args:
        md_file_path (str): Markdown书签文件路径
        html_file_path (str): 输出HTML书签文件路径
        
    Raises:
        Exception: 文件读取或转换失败时抛出异常
    """
    # 检测文件编码
    try:
        used_encoding = detect_encoding(md_file_path)
        print(f"正在使用编码: {used_encoding}")
        
        with open(md_file_path, 'r', encoding=used_encoding) as f:
            lines = f.readlines()
    except Exception as e:
        raise Exception(f"无法读取文件: {e}")
    
    # HTML书签文件头部
    html_lines = [
        '<!DOCTYPE NETSCAPE-Bookmark-file-1>',
        '<!-- This is an automatically generated file -->',
        '<!-- It will be read and overwritten. Do Not Edit! -->',
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        '<TITLE>Bookmarks</TITLE>',
        '<H1>Bookmarks</H1>',
        '<DL><p>'
    ]
    
    stack = []  # 用于跟踪标题层级
    
    for line in lines:
        line = line.rstrip()
        
        # 处理Markdown标题（##, ###等）
        if line.startswith('#'):
            match = re.match(r'^#+', line)
            if match:
                level = len(match.group())
                title = line.lstrip('#').strip()
                
                # 关闭当前层级以下的DL标签
                while len(stack) >= level:
                    html_lines.append('</DL><p>')
                    stack.pop()
                
                # 添加新层级
                html_lines.append(f'<DT><H3>{title}</H3>')
                html_lines.append('<DL><p>')
                stack.append(level)
        
        # 处理Markdown链接格式：- [文本](URL)
        elif line.strip().startswith('- ['):
            match = re.search(r'- \[(.*?)\]\((.*?)\)', line)
            if match:
                text = match.group(1)
                url = match.group(2)
                # 只保留有效的URL协议
                if url.startswith(('http://', 'https://', 'chrome://', 'edge://')):
                    html_lines.append(f'<DT><A HREF="{url}">{text}</A>')
        
        # 处理特殊区块（如代码块）
        elif line.strip() == '```Plain Text':
            html_lines.append('<DT><H3>Hosts配置</H3><DL><p>')
        elif line.strip() == '```':
            html_lines.append('</DL><p>')
    
    # 关闭所有未闭合的DL标签
    while stack:
        html_lines.append('</DL><p>')
        stack.pop()
    
    html_lines.append('</DL><p>')
    
    # 写入HTML文件
    try:
        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_lines))
        print(f"转换完成！文件保存至: {html_file_path}")
    except Exception as e:
        raise Exception(f"无法写入文件: {e}")

def main():
    """
    主函数：处理默认桌面路径的sk.md文件
    """
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    input_file = os.path.join(desktop, "sk.md")
    output_file = os.path.join(desktop, "bookmarks.html")
    
    if os.path.exists(input_file):
        print(f"找到输入文件: {input_file}")
        try:
            markdown_bookmarks_to_html(input_file, output_file)
        except Exception as e:
            print(f"转换失败: {e}")
    else:
        print(f"未找到输入文件: {input_file}")
        print("请确保桌面上存在 sk.md 文件")

if __name__ == "__main__":
    main()
