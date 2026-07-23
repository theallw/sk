"""
优化打包脚本 v4.0
功能：
- 自动检查 Python 环境
- 自动安装/更新依赖
- 生成详细打包日志 (build.log)
- 多种打包策略回退
- 针对原始代码路径问题进行自动修复
"""

import os
import sys
import subprocess
import shutil
import time
import logging
from pathlib import Path
from datetime import datetime

# ==================== 日志配置 ====================
LOG_FILE = Path(os.getcwd()) / f"build_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==================== 辅助函数 ====================

def print_separator(title=""):
    line = "=" * 70
    logger.info(line)
    if title:
        logger.info(f"  {title}")
        logger.info(line)

def get_current_dir():
    """获取当前工作目录（兼容Thonny）"""
    return Path(os.getcwd())

def run_command(cmd, capture=True, shell=True):
    """执行命令并返回结果，同时记录日志"""
    logger.info(f"执行命令: {cmd}")
    try:
        if capture:
            result = subprocess.run(cmd, capture_output=True, text=True, shell=shell, timeout=300)
            if result.stdout:
                logger.debug(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                logger.debug(f"STDERR:\n{result.stderr}")
            return result
        else:
            return subprocess.run(cmd, shell=shell, timeout=300)
    except subprocess.TimeoutExpired:
        logger.error("命令执行超时")
        return None
    except Exception as e:
        logger.error(f"执行命令异常: {e}")
        return None

# ==================== 环境检查 ====================

def check_environment():
    """检查 Python 和 pip 环境"""
    print_separator("环境检查")
    logger.info(f"Python 版本: {sys.version}")
    logger.info(f"Python 路径: {sys.executable}")
    logger.info(f"工作目录: {os.getcwd()}")
    logger.info(f"操作系统: {sys.platform}")

    # 检查 pip
    result = run_command([sys.executable, '-m', 'pip', '--version'])
    if result and result.returncode == 0:
        logger.info(f"pip 版本: {result.stdout.strip()}")
    else:
        logger.warning("pip 命令异常，请确保 pip 可用")

    # 检查是否有管理员权限（Windows）
    if sys.platform == 'win32':
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            logger.info(f"管理员权限: {'是' if is_admin else '否（建议以管理员身份运行）'}")
        except:
            pass

def check_pyinstaller():
    """检查 PyInstaller 是否可用"""
    print_separator("检查 PyInstaller")
    try:
        import PyInstaller
        logger.info("✅ PyInstaller 已安装（导入成功）")
        return True
    except ImportError:
        logger.warning("❌ PyInstaller 未安装（导入失败）")

    # 尝试命令行检查
    result = run_command(['pyinstaller', '--version'])
    if result and result.returncode == 0:
        logger.info(f"✅ PyInstaller 命令行可用，版本: {result.stdout.strip()}")
        return True

    logger.error("PyInstaller 不可用，需要安装")
    return False

# ==================== 安装依赖 ====================

def install_pyinstaller():
    """多策略安装 PyInstaller"""
    print_separator("安装 PyInstaller")
    strategies = [
        ([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], "升级 pip"),
        ([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], "普通安装"),
        ([sys.executable, '-m', 'pip', 'install', 'pyinstaller', '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple'], "清华镜像"),
        ([sys.executable, '-m', 'pip', 'install', 'pyinstaller', '--no-cache-dir'], "无缓存安装"),
        ([sys.executable, '-m', 'pip', 'install', 'pyinstaller==6.3.0'], "指定版本 6.3.0"),
    ]

    for cmd, desc in strategies:
        logger.info(f"尝试: {desc}")
        result = run_command(cmd)
        if result and result.returncode == 0:
            logger.info(f"✅ {desc} 成功")
            # 验证安装
            if check_pyinstaller():
                return True
        else:
            logger.warning(f"❌ {desc} 失败")

    logger.error("所有安装策略均失败，请手动安装：pip install pyinstaller")
    return False

# ==================== 修复原始代码路径 ====================

def patch_source_code(source_file):
    """自动修复原始代码中的硬编码路径，改为动态获取"""
    print_separator("检查并修复源代码路径问题")
    
    with open(source_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查是否存在硬编码路径
    if r'C:\Users\Administrator\Downloads' in content:
        logger.warning("检测到硬编码路径，将自动修复为动态路径")
        # 替换为动态获取方式
        # 注意：这里简单替换，实际可能需要更精细处理
        # 我们添加一段代码来动态获取目录
        new_content = content.replace(
            r'input_file = Path(r"C:\Users\Administrator\Downloads\sk.md")',
            r'input_file = Path(os.path.dirname(os.path.abspath(__file__))) / "sk.md"'
        ).replace(
            r'output_file = Path(r"C:\Users\Administrator\Downloads\nav.html")',
            r'output_file = Path(os.path.dirname(os.path.abspath(__file__))) / "nav.html"'
        )
        # 同时添加导入 os
        if 'import os' not in new_content:
            new_content = 'import os\n' + new_content

        # 写入备份
        backup = source_file.with_suffix('.py.bak')
        shutil.copy(source_file, backup)
        logger.info(f"已备份原文件为 {backup}")

        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        logger.info("✅ 路径已修复，将使用当前目录下的 sk.md 和 nav.html")
        return True
    else:
        logger.info("未发现硬编码路径，无需修复")
        return False

# ==================== 打包执行 ====================

def build_exe(target_file, output_name):
    """执行打包，并记录详细日志"""
    print_separator("开始打包")
    current_dir = get_current_dir()

    # 清理旧的构建文件
    for d in ['build', 'dist']:
        dpath = current_dir / d
        if dpath.exists():
            shutil.rmtree(dpath)
            logger.info(f"已删除旧目录: {d}")

    # 构建 PyInstaller 命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--console',
        f'--name={output_name}',
        '--hidden-import=bs4',
        '--hidden-import=bs4.builder._htmlparser',
        '--hidden-import=chardet',
        '--hidden-import=requests',
        '--hidden-import=requests.packages.urllib3',
        '--hidden-import=concurrent.futures',
        '--workpath', str(current_dir / 'build'),
        '--distpath', str(current_dir / 'dist'),
        '--log-level=DEBUG',   # 输出详细日志
        str(target_file)
    ]

    logger.info("执行打包命令:")
    logger.info(' '.join(cmd))

    # 运行打包，捕获输出
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=600)
        # 记录完整输出
        if result.stdout:
            logger.debug("STDOUT:\n" + result.stdout)
        if result.stderr:
            logger.debug("STDERR:\n" + result.stderr)

        if result.returncode == 0:
            logger.info("✅ 打包命令执行成功")
            exe_file = current_dir / 'dist' / f"{output_name}.exe"
            if exe_file.exists():
                size = exe_file.stat().st_size / (1024 * 1024)
                logger.info(f"📦 生成文件: {exe_file} (大小: {size:.2f} MB)")
                return True
            else:
                logger.error("打包成功但未找到生成的 exe 文件")
                return False
        else:
            logger.error(f"打包失败，返回码: {result.returncode}")
            # 尝试从输出中提取关键错误信息
            error_lines = [line for line in (result.stderr or '').split('\n') if 'Error' in line or 'error' in line]
            if error_lines:
                logger.error("关键错误信息:")
                for line in error_lines[:5]:
                    logger.error(f"  {line}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("打包超时（超过10分钟）")
        return False
    except Exception as e:
        logger.error(f"打包过程异常: {e}")
        return False

# ==================== 主函数 ====================

def main():
    print_separator("优化打包工具 v4.0")
    logger.info(f"日志文件: {LOG_FILE}")

    # 1. 环境检查
    check_environment()

    # 2. 检查并安装 PyInstaller
    if not check_pyinstaller():
        if not install_pyinstaller():
            logger.error("PyInstaller 安装失败，无法继续")
            input("按 Enter 退出...")
            return

    # 3. 查找目标文件
    current_dir = get_current_dir()
    py_files = []
    for f in current_dir.glob("*.py"):
        if f.name not in ['build_optimized.py', 'build.py', '打包.py', 'setup.py']:
            py_files.append(f)

    if not py_files:
        logger.error("当前目录下没有找到 Python 文件")
        input("按 Enter 退出...")
        return

    logger.info(f"找到 {len(py_files)} 个 Python 文件:")
    for i, f in enumerate(py_files, 1):
        logger.info(f"  {i}. {f.name}")

    # 自动选择第一个或让用户选择
    if len(py_files) == 1:
        target = py_files[0]
        logger.info(f"自动选择: {target.name}")
    else:
        try:
            choice = input(f"请选择要打包的文件 (1-{len(py_files)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(py_files):
                target = py_files[idx]
            else:
                target = py_files[0]
                logger.warning("无效选择，使用第一个文件")
        except:
            target = py_files[0]
            logger.warning("输入错误，使用第一个文件")

    logger.info(f"目标文件: {target}")

    # 4. 修复源代码路径问题
    patch_source_code(target)

    # 5. 设置输出名称
    default_name = target.stem
    output_name = input(f"输出文件名 (默认 {default_name}): ").strip()
    if not output_name:
        output_name = default_name

    # 6. 开始打包
    success = build_exe(target, output_name)

    # 7. 结果处理
    if success:
        print_separator("打包成功")
        logger.info(f"🎉 打包完成！EXE 文件位于: {current_dir / 'dist'}")
        # 自动打开文件夹
        try:
            os.startfile(str(current_dir / 'dist'))
            logger.info("已自动打开输出文件夹")
        except:
            pass
    else:
        print_separator("打包失败")
        logger.error("❌ 打包失败，请检查上述日志信息")
        logger.info(f"完整日志已保存到: {LOG_FILE}")

    input("\n按 Enter 退出...")

if __name__ == "__main__":
    main()