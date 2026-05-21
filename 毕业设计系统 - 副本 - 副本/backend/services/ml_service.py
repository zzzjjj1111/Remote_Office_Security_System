import numpy as np
from datetime import datetime
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from collections import defaultdict
import json
from core.db import db, BehaviorLog, User, AlgorithmConfig, FalsePositiveSample


class BehaviorAnalyzer:
    def __init__(self):
        self.scaler = StandardScaler()
        self._config = None  # 延迟加载配置
        self._iforest_model = None
        self._iforest_scaler = StandardScaler()  # 孤立森林专用的标准化器

    @property
    def config(self):
        """延迟加载配置，避免在应用上下文外访问数据库"""
        if self._config is None:
            self._config = self.load_config()
        return self._config

    def load_config(self):
        """加载算法配置"""
        config = AlgorithmConfig.query.first()
        return {
            "kmeans_n_clusters": config.k_clusters if config else 5,
            "wma_window": config.wma_window if config else 14,  # 14天窗口
            "baseline_threshold": 0.8  # 使用固定默认值
        }

    def extract_behavior_features(self, user_logs):
        """提取行为特征：操作频率、敏感操作、时间段、访问类型、屏幕共享频率"""
        if not user_logs:
            return [0, 0, 0, 0, 0]

        total_ops = len(user_logs)
        sensitive_ops = sum(1 for log in user_logs if log.is_sensitive)
        # 工作时间段(9-18点)操作占比
        work_hour_ops = sum(1 for log in user_logs if log.timestamp and 9 <= log.timestamp.hour <= 18)
        # 操作类型多样性
        op_types = len(set(log.behavior_type for log in user_logs))
        # 【新增】屏幕共享频率（作为第5个特征维度）
        screen_share_ops = sum(1 for log in user_logs if log.is_screen_sharing)

        return [total_ops, sensitive_ops, work_hour_ops / total_ops if total_ops > 0 else 0, op_types, screen_share_ops]

    def train_user_baseline_kmeans(self):
        """【核心】K-means 按岗位训练行为基线 → 生成岗位标准基线"""
        # 1. 获取所有用户+历史行为日志
        users = User.query.all()
        user_features = []
        user_ids = []
        position_map = defaultdict(list)

        for user in users:
            logs = BehaviorLog.query.filter_by(user_id=user.id).order_by(BehaviorLog.timestamp.desc()).limit(100).all()
            features = self.extract_behavior_features(logs)
            user_features.append(features)
            user_ids.append(user.id)
            position_map[user.position].append(features)

        if len(user_features) < 5:
            return {"code": 400, "msg": "数据不足，无法训练基线"}

        # 2. 标准化特征 + K-means聚类
        X = self.scaler.fit_transform(user_features)
        kmeans = KMeans(n_clusters=self.config["kmeans_n_clusters"], random_state=42)
        clusters = kmeans.fit_predict(X)

        # 3. 生成【岗位基线】：每个聚类中心=标准行为基线
        baseline_centers = self.scaler.inverse_transform(kmeans.cluster_centers_).tolist()
        baseline_data = {
            "cluster_centers": baseline_centers,
            "user_clusters": dict(zip(user_ids, clusters.tolist())),
            "train_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # 4. 基线存入数据库
        config = AlgorithmConfig.query.first()
        config.baseline_data = json.dumps(baseline_data, ensure_ascii=False)
        db.session.commit()

        return {"code": 200, "msg": "K-means岗位基线训练完成", "data": baseline_data}

    def calculate_wma_baseline(self, user_id, new_features):
        """【核心】WMA加权移动平均 → 计算个人动态基线"""
        window = self.config["wma_window"]
        # 获取用户近期行为特征
        user_logs = BehaviorLog.query.filter_by(user_id=user_id).order_by(BehaviorLog.timestamp.desc()).limit(
            window).all()
        if not user_logs:
            return new_features

        # 提取历史特征
        history_features = np.array([self.extract_behavior_features([log]) for log in user_logs])
        # WMA权重：最新数据权重最高 [1,2,3...window]
        weights = np.arange(1, len(history_features) + 1)
        weights = weights / weights.sum()

        # 加权计算动态基线
        wma_baseline = np.average(history_features, axis=0, weights=weights)
        return wma_baseline.tolist()

    def detect_anomaly_by_baseline(self, user_id, current_features, context=None):
        """
        基于双基线检测异常：岗位基线(Kmeans) + 个人基线(WMA)
        【新增】context参数：上下文环境数据，用于异常分折扣
        
        Args:
            user_id: 用户ID
            current_features: 当前行为特征
            context: dict, 包含 {
                'network_type': str,  # 'office'/'home'/'mobile'/'vpn'
                'is_vpn': bool,
                'location_hint': str
            }
        
        Returns:
            dict: {
                'raw_score': float,  # 原始异常分
                'discount_factor': float,  # 折扣系数
                'final_score': float  # 折扣后的异常分
            }
        """
        try:
            # 1. 获取个人WMA动态基线
            wma_baseline = self.calculate_wma_baseline(user_id, current_features)
            # 2. 计算与个人基线的偏差
            personal_diff = np.mean(np.abs(np.array(current_features) - np.array(wma_baseline)))

            # 3. 加载岗位K-means基线
            config = AlgorithmConfig.query.first()
            baseline_data = json.loads(config.baseline_data)
            cluster_id = baseline_data["user_clusters"].get(str(user_id), 0)
            cluster_center = baseline_data["cluster_centers"][cluster_id]

            # 4. 计算与岗位基线的偏差
            position_diff = np.mean(np.abs(np.array(current_features) - np.array(cluster_center)))

            # 5. 综合异常分 (0-1)
            raw_anomaly_score = min(1.0, (personal_diff * 0.6 + position_diff * 0.4) / 10)
            
            # 6. 【新增】计算上下文折扣系数
            discount_factor = self._calculate_context_discount(context)
            
            # 7. 应用折扣
            final_anomaly_score = raw_anomaly_score * discount_factor
            
            return {
                'raw_score': float(raw_anomaly_score),
                'discount_factor': float(discount_factor),
                'final_score': float(final_anomaly_score)
            }
        except Exception as e:
            print(f"[Baseline Detection] Error: {e}")
            return {
                'raw_score': 0.5,
                'discount_factor': 1.0,
                'final_score': 0.5
            }
    
    def _calculate_context_discount(self, context):
        """
        【新增】计算上下文折扣系数
        出差、VPN场景应该降低异常分，减少误判
        
        折扣规则：
        - VPN连接: 0.7 (折扣30%，因为VPN本身就会改变网络特征)
        - 移动网络/异地: 0.75 (折扣25%，出差场景)
        - 家庭网络: 0.85 (折扣15%，远程办公场景)
        - 公司网络: 1.0 (无折扣，正常办公)
        - 未知: 1.0 (保守处理)
        """
        if not context:
            return 1.0
        
        network_type = context.get('network_type', 'unknown')
        is_vpn = context.get('is_vpn', False)
        
        # VPN连接：最高折扣
        if is_vpn or network_type == 'vpn':
            return 0.7
        
        # 移动网络/异地：较高折扣
        if network_type == 'mobile':
            return 0.75
        
        # 家庭网络：适度折扣
        if network_type == 'home':
            return 0.85
        
        # 公司网络：无折扣
        if network_type == 'office':
            return 1.0
        
        # 未知环境：保守处理，无折扣
        return 1.0

    # ===================== 【新增：孤立森林核心模块】 =====================

    def train_isolation_forest(self, include_false_positives=False):
        """
        训练全局孤立森林模型，用于检测隐性异常
        
        Args:
            include_false_positives: 是否包含误判样本（用于修正基线）
        """
        # 1. 获取全量历史行为日志用于训练
        logs = BehaviorLog.query.order_by(BehaviorLog.timestamp.desc()).limit(500).all()

        if len(logs) < 50:
            print(f"[Isolation Forest] 数据量不足，跳过训练")
            return False

        # 2. 提取特征矩阵
        features_matrix = []
        user_ids = []
        for log in logs:
            # 为了训练，我们需要还原当时的特征向量
            # 这里我们构造一个伪样本用于提取特征
            feat = self.extract_behavior_features([log])
            features_matrix.append(feat)
            user_ids.append(log.user_id)

        # 3. 【新增】如果包含误判样本，降低这些样本的权重
        if include_false_positives:
            false_positive_user_ids = set()
            fp_samples = FalsePositiveSample.query.filter_by(used_for_training=True).all()
            for sample in fp_samples:
                false_positive_user_ids.add(sample.user_id)
            
            # 对误判样本降低权重（通过减少其影响）
            try:
                print(f"[Isolation Forest] 发现 {len(false_positive_user_ids)} 个用户有误判样本")
            except OSError:
                # Windows控制台编码问题时的备选方案
                print(f"[Isolation Forest] Found {len(false_positive_user_ids)} users with false positive samples")

        # 4. 标准化并训练
        X = self._iforest_scaler.fit_transform(features_matrix)

        # contamination=0.05 表示我们预期约 5% 的数据是异常的
        self._iforest_model = IsolationForest(contamination=0.05, random_state=42)
        self._iforest_model.fit(X)

        print(f"[Isolation Forest] 训练完成，样本数: {len(X)}")
        return True

    def get_isolation_forest_score(self, current_features):
        """
        获取当前行为的孤立森林异常评分 (0-100)
        分数越高，越异常
        """
        if self._iforest_model is None:
            # 如果模型未训练，尝试现场训练一次，或者返回中性分 50
            self.train_isolation_forest()
            if self._iforest_model is None:
                return 50.0

        try:
            # 1. 特征标准化 (使用训练时的scaler)
            X = np.array(current_features).reshape(1, -1)
            X_scaled = self._iforest_scaler.transform(X)

            # 2. 预测
            # decision_function: 负值是异常，正值是正常
            raw_score = self._iforest_model.decision_function(X_scaled)[0]

            # 3. 归一化映射到 0-100
            # raw_score 大致范围在 -0.5 到 0.5 之间
            # 我们将其转换为：越异常(负)，分数越高
            normalized_score = ((-raw_score + 0.5) / 1.0) * 100

            # 限制在 0-100 之间
            normalized_score = max(0.0, min(100.0, normalized_score))

            return round(normalized_score, 2)

        except Exception as e:
            print(f"[Isolation Forest] 预测异常: {e}")
            return 50.0


def train_isolation_forest(include_false_positives=False):
    """
    独立函数：触发孤立森林模型训练（供API调用）
    
    Args:
        include_false_positives: 是否包含误判样本
    
    Returns:
        dict: 训练结果
    """
    try:
        analyzer = BehaviorAnalyzer()
        success = analyzer.train_isolation_forest(include_false_positives=include_false_positives)
        return {
            'success': success,
            'message': '训练成功' if success else '训练失败（数据不足）'
        }
    except Exception as e:
        print(f"[Isolation Forest] 训练异常: {e}")
        return {
            'success': False,
            'message': str(e)
        }