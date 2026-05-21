import ahocorasick
# 导入数据库模型和会话（必须添加）
from core.db import db, SensitiveWord


class SensitiveDataIdentifier:
    def __init__(self):
        self.A = ahocorasick.Automaton()
        self.is_built = False
        # 移除硬编码敏感词，改为从数据库加载
        self.sensitive_keywords = []
        self._build_automaton()

    def _build_automaton(self):
        """从数据库加载敏感词，构建AC自动机（核心修改）"""
        try:
            # 从数据库查询所有敏感词
            word_records = SensitiveWord.query.all()
            # 提取敏感词文本
            self.sensitive_keywords = [record.word for record in word_records]
            print(f"✅ 从数据库加载敏感词: {self.sensitive_keywords}")
        except Exception as e:
            # 数据库未初始化时，使用备用默认词（兼容演示）
            self.sensitive_keywords = [
                "核心源码", "源码", "源代码", "工资单", "财务报表", "离职名单",
                "身份证号", "绝密", "密码本", "客户流水", "未公开", "未公开源码"
            ]
            print(f"⚠️ 数据库未加载，使用默认敏感词库: {str(e)}")

        # 重建AC自动机
        self.A = ahocorasick.Automaton()
        for idx, word in enumerate(self.sensitive_keywords):
            self.A.add_word(word, (idx, word))
        self.A.make_automaton()
        self.is_built = True
        try:
            print(f"✅ AC自动机构建完成，加载敏感词数量：{len(self.sensitive_keywords)}")
            print(f"   敏感词列表: {self.sensitive_keywords}")
        except OSError:
            # Windows控制台编码问题时的备选方案
            print(f"AC automaton built, loaded {len(self.sensitive_keywords)} keywords")
            print(f"Keywords: {self.sensitive_keywords}")

    def rebuild(self):
        """对外提供的重建方法（页面添加/删除敏感词后调用）"""
        self._build_automaton()

    def update_keywords(self, new_keywords):
        """支持动态更新敏感词库（兼容原有接口）"""
        # 该方法保留，不影响原有代码调用
        self.A = ahocorasick.Automaton()
        self.sensitive_keywords.extend(new_keywords)
        self.sensitive_keywords = list(set(self.sensitive_keywords))
        self._build_automaton()

    def is_sensitive(self, text):
        """
        利用AC自动机进行多模式匹配
        检查text中是否包含敏感词
        【原有逻辑完全不变】
        """
        if not self.is_built:
            return False, []

        found_keywords = []
        for end_index, (insert_order, original_value) in self.A.iter(text):
            found_keywords.append(original_value)
        
        # 【调试】打印检测详情
        if found_keywords:
            try:
                print(f"🔍 [AC匹配] 在文本中找到敏感词: {found_keywords}")
                print(f"   原文: {text[:100]}...")
            except OSError:
                # Windows控制台编码问题时的备选方案
                print(f"[AC Match] Found sensitive keywords: {found_keywords}")
                print(f"Text: {text[:100]}...")

        return len(found_keywords) > 0, found_keywords


# 全局单例（完全不变，其他代码正常调用）
acs_monitor = SensitiveDataIdentifier()

if __name__ == '__main__':
    # 简单测试（原有逻辑不变）
    text = "昨天的财务报表已经发给李总了，另外客户流水也一并打包了。"
    has_sensitive, words = acs_monitor.is_sensitive(text)
    print(f"Contains sensitive data: {has_sensitive}, Keywords: {words}")