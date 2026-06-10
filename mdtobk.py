import re
import os
#pip install chardet
def markdown_bookmarks_to_html(md_file_path, html_file_path):
    """
    将Markdown格式的书签文件转换为HTML书签文件
    """
    # 尝试多种编码读取文件
    encodings = ['gbk', 'gb2312', 'utf-8', 'ansi', 'gb18030']
    lines = None
    used_encoding = None
    
    for enc in encodings:
        try:
            with open(md_file_path, 'r', encoding=enc) as f:
                lines = f.readlines()
            used_encoding = enc
            break
        except:
            continue
    
    if lines is None:
        raise Exception("无法识别文件编码，请检查文件")
    
    print(f"?? 使用编码: {used_encoding}")
    
    html_lines = []
    html_lines.append('<!DOCTYPE NETSCAPE-Bookmark-file-1>')
    html_lines.append('<!-- This is an automatically generated file -->')
    html_lines.append('<!-- It will be read and overwritten. Do Not Edit! -->')
    html_lines.append('<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">')
    html_lines.append('<TITLE>Bookmarks</TITLE>')
    html_lines.append('<H1>Bookmarks</H1>')
    html_lines.append('<DL><p>')
    
    stack = []
    
    for line in lines:
        line = line.rstrip()
        
        if line.startswith('##'):
            match = re.match(r'^#+', line)
            if match:
                level = len(match.group())
                title = line.lstrip('#').strip()
                
                while len(stack) >= level:
                    html_lines.append('</DL><p>')
                    stack.pop()
                
                html_lines.append(f'<DT><H3>{title}</H3>')
                html_lines.append('<DL><p>')
                stack.append(level)
        
        elif line.strip().startswith('- ['):
            match = re.search(r'- \[(.*?)\]\((.*?)\)', line)
            if match:
                text = match.group(1)
                url = match.group(2)
                if url.startswith(('http://', 'https://', 'chrome://', 'edge://')):
                    html_lines.append(f'<DT><A HREF="{url}">{text}</A>')
        
        elif line.strip() == '```Plain Text':
            html_lines.append('<DT><H3>Hosts配置</H3><DL><p>')
        elif line.strip() == '```':
            html_lines.append('</DL><p>')
    
    while stack:
        html_lines.append('</DL><p>')
        stack.pop()
    
    html_lines.append('</DL><p>')
    
    with open(html_file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_lines))
    
    print(f"? 转换完成！保存到: {html_file_path}")

if __name__ == "__main__":
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    input_file = os.path.join(desktop, "sk.md")
    output_file = os.path.join(desktop, "bookmarks.html")
    
    if os.path.exists(input_file):
        print(f"?? 找到文件: {input_file}")
        markdown_bookmarks_to_html(input_file, output_file)
    else:
        print(f"? 找不到文件: {input_file}")