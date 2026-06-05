#!/usr/bin/env python
"""
Alembic 自动初始化脚本
一键配置数据库迁移环境，自动从项目配置读取数据库连接

使用方法:
    python init_alembic.py [--no-confirm]  # 跳过确认直接保存
    python init_alembic.py [--dry-run]     # 预览模式，不实际创建文件
"""
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

# 全局 logger，稍后根据参数配置
logger = logging.getLogger(__name__)


def setup_logging(save_log: bool = False, log_dir: str = "logs") -> Optional[Path]:
    """
    配置日志系统

    Args:
        save_log: 是否保存日志到文件
        log_dir: 日志文件保存目录

    Returns:
        日志文件路径（如果保存）或 None
    """
    # 基础格式
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # 清除现有的 handlers
    logger.handlers.clear()
    logger.setLevel(logging.INFO)

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(log_format, date_format)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 如果需要保存日志
    log_file = None
    if save_log:
        try:
            # 创建日志目录
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)

            # 生成日志文件名（带时间戳）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = log_path / f"init_alembic_{timestamp}.log"

            # 文件输出
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)  # 文件记录更详细的日志
            file_formatter = logging.Formatter(log_format, date_format)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            logger.info(f"日志将保存到: {log_file}")
        except Exception as e:
            logger.warning(f"无法创建日志文件: {e}")
            return None

    return log_file


def get_project_config() -> Optional[Dict]:
    """获取项目配置"""
    try:
        from listening_ripples.config import settings
        config = {
            'db_url': str(settings.SQLALCHEMY_DATABASE_URI),
            'project_name': settings.PROJECT_NAME,
            'db_name': settings.POSTGRES_DB,
            'db_host': settings.POSTGRES_SERVER,
            'db_port': settings.POSTGRES_PORT,
            'db_user': settings.POSTGRES_USER,
            'environment': settings.ENVIRONMENT,
        }
        logger.info("成功读取项目配置")
        return config
    except ImportError as e:
        logger.warning(f"无法导入项目配置: {e}")
        return None
    except Exception as e:
        logger.warning(f"读取项目配置时出错: {e}")
        return None


def create_alembic_ini(config: Optional[Dict] = None) -> str:
    """创建 alembic.ini 配置内容"""
    if config and 'db_url' in config:
        db_url = config['db_url']
        logger.info("使用项目配置中的数据库 URL")
    else:
        db_url = "postgresql+psycopg://postgres:123456@127.0.0.1:5432/listening_ripples"
        logger.warning("使用默认数据库 URL")

    content = f"""# A generic, single database configuration.

[alembic]
# path to migration scripts
script_location = alembic

# template used to generate migration file names
file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s

# sys.path path, will be prepended to sys.path if present.
prepend_sys_path = .

# version path separator
version_path_separator = os

# the output encoding used when revision files are written
# output_encoding = utf-8

# 数据库连接 URL (从项目 config.py 自动读取)
# 注意: 此配置会被 env.py 中的动态配置覆盖
sqlalchemy.url = {db_url}


[post_write_hooks]
# post_write_hooks defines scripts or Python functions that are run
# on newly generated revision scripts.

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
    return content


def create_env_py() -> str:
    """创建 alembic/env.py 环境配置内容"""
    content = """from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 导入配置和模型
from listening_ripples.config import settings
from listening_ripples.extensions.db_extension import Base

# 导入所有模型（重要！必须导入才能自动检测）
from listening_ripples.models.users import User
# 添加新模型时在此导入，例如:
# from listening_ripples.models.posts import Post

# this is the Alembic Config object
config = context.config

# 使用项目配置中的数据库 URL（动态读取，支持不同环境）
config.set_main_option("sqlalchemy.url", str(settings.SQLALCHEMY_DATABASE_URI))

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    \"\"\"Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    \"\"\"
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    \"\"\"Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    \"\"\"
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""
    return content


def create_script_mako() -> str:
    """创建 alembic/script.py.mako 迁移模板内容"""
    content = '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''
    return content


def write_file(filepath: Path, content: str, dry_run: bool = False) -> bool:
    """写入文件"""
    try:
        if dry_run:
            logger.info(f"[DRY-RUN] 将创建文件: {filepath}")
            return True

        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"已创建文件: {filepath}")
        return True
    except Exception as e:
        logger.error(f"写入文件失败 {filepath}: {e}")
        return False


def check_requirements() -> bool:
    """检查必需的包是否安装"""
    try:
        import alembic
        logger.info("Alembic 已安装")
        return True
    except ImportError:
        logger.error("Alembic 未安装，请运行: pip install alembic")
        return False


def display_config_info(config: Optional[Dict]) -> None:
    """显示项目配置信息"""
    if not config:
        logger.warning("未能读取项目配置")
        return

    logger.info("=" * 60)
    logger.info("项目配置信息:")
    logger.info(f"  项目名称: {config.get('project_name', 'N/A')}")
    logger.info(f"  环境: {config.get('environment', 'N/A')}")
    logger.info(f"  数据库名: {config.get('db_name', 'N/A')}")
    logger.info(f"  数据库主机: {config.get('db_host', 'N/A')}:{config.get('db_port', 'N/A')}")
    logger.info(f"  数据库用户: {config.get('db_user', 'N/A')}")
    logger.info("=" * 60)


def confirm_action(message: str, auto_confirm: bool = False) -> bool:
    """确认操作"""
    if auto_confirm:
        logger.info(f"{message} - 自动确认")
        return True

    try:
        response = input(f"{message} (yes/no): ").strip().lower()
        return response == "yes"
    except (EOFError, KeyboardInterrupt):
        logger.info("\n操作已取消")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Alembic 自动初始化脚本")
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='跳过确认，直接创建文件'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='预览模式，不实际创建文件'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制覆盖已存在的文件'
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Alembic 初始化向导")
    logger.info("=" * 60)

    # 检查是否已经初始化
    alembic_exists = Path("alembic").exists()
    alembic_ini_exists = Path("alembic.ini").exists()

    if (alembic_exists or alembic_ini_exists) and not args.force:
        logger.warning("检测到 Alembic 已经初始化")
        if not confirm_action("是否要重新初始化?", args.no_confirm):
            logger.info("操作已取消")
            return 0

    # 检查依赖
    if not check_requirements():
        return 1

    # 获取项目配置
    logger.info("读取项目配置...")
    config = get_project_config()
    display_config_info(config)

    if args.dry_run:
        logger.info("=" * 60)
        logger.info("预览模式 - 不会实际创建文件")
        logger.info("=" * 60)

    # 确认是否继续
    if not args.dry_run:
        if not confirm_action("是否继续创建配置文件?", args.no_confirm):
            logger.info("操作已取消")
            return 0

    logger.info("开始创建配置文件...")

    # 创建文件
    success = True

    # 1. 创建 alembic.ini
    alembic_ini_content = create_alembic_ini(config)
    if not write_file(Path("alembic.ini"), alembic_ini_content, args.dry_run):
        success = False

    # 2. 创建 alembic/env.py
    env_py_content = create_env_py()
    if not write_file(Path("alembic/env.py"), env_py_content, args.dry_run):
        success = False

    # 3. 创建 alembic/script.py.mako
    script_mako_content = create_script_mako()
    if not write_file(Path("alembic/script.py.mako"), script_mako_content, args.dry_run):
        success = False

    # 4. 创建 alembic/versions 目录
    if not args.dry_run:
        try:
            versions_dir = Path("alembic/versions")
            versions_dir.mkdir(parents=True, exist_ok=True)
            (versions_dir / "__init__.py").touch()
            logger.info(f"已创建目录: {versions_dir}")
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            success = False
    else:
        logger.info("[DRY-RUN] 将创建目录: alembic/versions")

    # 总结
    logger.info("=" * 60)
    if args.dry_run:
        logger.info("预览完成 - 使用 --no-confirm 参数跳过确认并实际创建文件")
    elif success:
        logger.info("Alembic 初始化完成!")
        logger.info("")
        logger.info("下一步:")
        logger.info("  1. 运行: python manage.py makemigrations 'initial'")
        logger.info("  2. 运行: python manage.py migrate")
        logger.info("  3. 验证: python manage.py showmigrations")
        logger.info("")
        logger.info("提示:")
        logger.info("  - 数据库配置已从项目 config.py 自动读取")
        logger.info("  - 配置会根据 .env 文件中的环境变量动态更新")
        logger.info("  - 添加新模型后记得在 alembic/env.py 中导入")
        logger.info("  - 使用 python manage.py help 查看所有命令")

        if config:
            env = config.get('environment', 'unknown')
            logger.info("")
            logger.info(f"当前环境: {env}")
            if env == 'local':
                logger.info("开发环境已就绪")
            elif env == 'production':
                logger.warning("生产环境，请谨慎操作！")
    else:
        logger.error("初始化过程中出现错误")
        return 1

    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\n操作已取消")
        sys.exit(0)
    except Exception as e:
        logger.error(f"发生错误: {e}", exc_info=True)
        sys.exit(1)