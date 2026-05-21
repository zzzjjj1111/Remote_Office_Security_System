import pymysql
import os
from pymysql.constants import CLIENT


def setup_database():
    print("开始连接 MySQL 并初始化数据库...")
    try:
        # 首先只连服务器，不连具体的库
        # 密码假设使用的是开发配置里的 '123456'，如果您本机的root密码不是这个，脚本会报错提示修改。
        connection = pymysql.connect(
            host='127.0.0.1',
            user='root',
            password='root',  # 请根据实际情况修改
            charset='utf8mb4',
            client_flag=CLIENT.MULTI_STATEMENTS  # 允许一次执行多条 SQL 语句
        )
        print("✅ 成功连接到 MySQL 服务器。")
    except Exception as e:
        print("❌ 连接 MySQL 失败，请检查数据库服务是否开启，或者 root 密码是否为 123456。")
        print(f"错误信息: {e}")
        return

    try:
        with connection.cursor() as cursor:
            # ========== 新增：删除旧数据库（开发环境），确保重建最新表结构 ==========
            print("正在清理旧数据库（开发环境）...")
            cursor.execute("DROP DATABASE IF EXISTS remote_office_protection_empty;")
            cursor.execute(
                "CREATE DATABASE IF NOT EXISTS remote_office_protection_empty DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.execute("USE remote_office_protection_empty;")
            # ========== 新增结束 ==========

            # 读取我们先前的建表 SQL 文件（需确保该文件是最新的，与db.py模型一致）
            sql_file_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'schema.sql')
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()

            print("正在执行 schema.sql 语句...")
            # 一次性执行整个 SQL 脚本
            cursor.execute(sql_script)
            connection.commit()
            print("✅ 数据库 [remote_office_protection_empty] 以及所有数据表初始化成功！")
    except Exception as e:
        print(f"❌ 初始化数据表失败: {e}")
    finally:
        connection.close()


if __name__ == "__main__":
    setup_database()