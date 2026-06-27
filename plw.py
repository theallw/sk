"""
排列五预测系统 v5.0 - 优化逆推验证版（使用txt数据源）
"""

import requests
import numpy as np
from collections import Counter, defaultdict
import random
from scipy.stats import chi2
from scipy import stats
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
import warnings
import re
from datetime import datetime
warnings.filterwarnings('ignore')

# ============================================================================
# 配置管理
# ============================================================================

@dataclass
class PatternConfig:
    """模式配置类"""
    pattern_types: List[str] = field(default_factory=lambda: [
        'odd_even_ratio',
        'big_small_ratio',
        'hezhi_exact',
        'hezhi_range',
        'kuaju_exact',
        'kuaju_range',
        'duplicate_type',
        'consecutive_type',
        'trend_type',
        'cold_hot_mix',
        'first_last_sum',
        'middle_sum',
        'digit_sum_mod',
        'position_parity'
    ])
    
    validation_window: int = 30
    min_hit_rate: float = 0.015
    min_samples_for_pattern: int = 5
    decay_factor: float = 0.95
    max_patterns_per_strategy: int = 10
    
    roll_window: int = 50
    roll_step: int = 10
    min_roll_windows: int = 3
    chi2_alpha: float = 0.1
    
    combo_min_hit_rate: float = 0.01
    combo_min_samples: int = 3
    max_combo_size: int = 3

@dataclass
class StrategyConfig:
    max_strategies: int = 8
    min_strategy_score: float = 0.2
    candidates_per_strategy: int = 30
    final_recommendations: int = 10

# ============================================================================
# 数据获取与特征提取（使用txt数据源）
# ============================================================================

def fetch_pl5_data_from_txt(limit: int = None) -> Tuple[List[List[int]], List[Dict]]:
    """
    从txt数据源获取排列五数据（获取全部数据）
    数据格式: 期号 日期 开奖号码(5个数字) 其他字段...
    只提取期号、日期、开奖号码
    """
    url = "https://data.17500.cn/pl5_asc.txt"
    
    headers = {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        'Accept-Encoding': "gzip, deflate, br, zstd",
        'upgrade-insecure-requests': "1",
        'sec-ch-ua': '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
        'sec-ch-ua-mobile': "?0",
        'sec-ch-ua-platform': '"Windows"',
        'accept-language': "zh-CN,zh;q=0.9",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"数据获取失败，状态码: {response.status_code}")
            return [], []
        
        lines = response.text.strip().split('\n')
        numbers = []
        features = []
        
        for line in lines:
            if not line.strip():
                continue
            
            parts = line.strip().split()
            # 数据格式: 期号 日期 开奖号码(5个数字) 其他...
            if len(parts) < 7:  # 至少需要期号+日期+5个号码
                continue
            
            # --- 优化解析逻辑：更稳健地提取5个开奖号码 ---
            digits = []
            # 从索引2开始尝试提取数字，直到取到5个为止
            idx = 2
            while len(digits) < 5 and idx < len(parts):
                # 检查当前部分是否为数字，并且长度是否为1（即0-9的单个数字）
                if parts[idx].isdigit() and len(parts[idx]) == 1:
                    digits.append(int(parts[idx]))
                else:
                    # 如果遇到非单个数字，说明可能已经到后面的字段了，尝试从下一个位置开始
                    # 但更稳健的做法是，如果取不到5个数字，就跳过这一行
                    pass
                idx += 1
            
            # 如果获取到的数字不是5个，跳过该行
            if len(digits) != 5:
                continue
            
            # --- 计算特征 (保持原逻辑) ---
            try:
                hezhi = sum(digits)
                hezhi_tail = hezhi % 10
                kuaju = max(digits) - min(digits)
                odd_count = sum(1 for d in digits if d % 2 == 1)
                big_count = sum(1 for d in digits if d >= 5)
                duplicate_count = len(digits) - len(set(digits))
                
                sorted_digits = sorted(digits)
                consecutive_count = 0
                for i in range(len(sorted_digits) - 1):
                    if sorted_digits[i+1] - sorted_digits[i] == 1:
                        consecutive_count += 1
                
                is_ascending = all(digits[i] <= digits[i+1] for i in range(4))
                is_descending = all(digits[i] >= digits[i+1] for i in range(4))
                
                numbers.append(digits)
                features.append({
                    'digits': digits,
                    'hezhi': hezhi,
                    'hezhi_tail': hezhi_tail,
                    'kuaju': kuaju,
                    'odd_count': odd_count,
                    'big_count': big_count,
                    'duplicate_count': duplicate_count,
                    'consecutive_count': consecutive_count,
                    'is_ascending': is_ascending,
                    'is_descending': is_descending,
                    'max_digit': max(digits),
                    'min_digit': min(digits),
                    'period': parts[0] if len(parts) > 0 else '',
                    'date': parts[1] if len(parts) > 1 else ''
                })
                
            except (ValueError, IndexError):
                continue
        
        # --- 移除 limit 限制，获取全部数据 ---
        print(f"成功解析 {len(numbers)} 条数据")
        return numbers, features
        
    except Exception as e:
        print(f"数据获取失败: {e}")
        return [], []

# ============================================================================
# 模式匹配器
# ============================================================================

@dataclass
class Pattern:
    """模式数据结构"""
    pattern_type: str
    pattern_value: Any
    description: str
    hit_count: int = 0
    total_occurrences: int = 0
    hit_rate: float = 0.0
    rolling_hit_rates: List[float] = field(default_factory=list)
    chi2_p_value: float = 1.0
    is_significant: bool = False
    weight: float = 1.0
    hit_rate_lower: float = 0.0
    hit_rate_upper: float = 0.0
    recent_hit_rate: float = 0.0
    trend_direction: int = 0
    
    def update_weight(self, decay_factor: float = 0.95):
        """更新模式权重"""
        base_weight = self.hit_rate * 100
        significance_bonus = 2.0 if self.is_significant else 0.5
        
        if len(self.rolling_hit_rates) >= 2:
            trend = self.rolling_hit_rates[-1] / (self.rolling_hit_rates[-2] + 0.001)
            trend_weight = min(trend, 2.5)
            self.trend_direction = 1 if trend > 1.05 else (-1 if trend < 0.95 else 0)
        else:
            trend_weight = 1.0
            self.trend_direction = 0
        
        if len(self.rolling_hit_rates) >= 3:
            recent_avg = np.mean(self.rolling_hit_rates[-3:])
            self.recent_hit_rate = recent_avg
            recent_bonus = 1 + (recent_avg - self.hit_rate) * 0.5
            recent_bonus = max(0.5, min(1.5, recent_bonus))
        else:
            recent_bonus = 1.0
        
        self.weight = (base_weight * significance_bonus * trend_weight * recent_bonus) * decay_factor
        self.weight = max(0.05, min(15.0, self.weight))
        
        # 计算置信区间 (Wilson score)
        if self.total_occurrences > 0:
            z = 1.96
            p = self.hit_rate
            n = self.total_occurrences
            denom = 1 + z**2 / n
            center = (p + z**2 / (2*n)) / denom
            spread = z * np.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denom
            self.hit_rate_lower = max(0, center - spread)
            self.hit_rate_upper = min(1, center + spread)

class PatternMatcher:
    """模式匹配器"""
    
    def __init__(self, config: PatternConfig = PatternConfig()):
        self.config = config
    
    def extract_patterns_from_number(self, number: List[int], 
                                     cold_numbers: Set[int] = None, 
                                     hot_numbers: Set[int] = None) -> Dict[str, str]:
        """从单个号码提取所有模式特征"""
        if cold_numbers is None:
            cold_numbers = set()
        if hot_numbers is None:
            hot_numbers = set()
            
        patterns = {}
        
        # 1. 奇偶比
        odd_count = sum(1 for d in number if d % 2 == 1)
        patterns['odd_even_ratio'] = f"{odd_count}:{5-odd_count}"
        
        # 2. 大小比
        big_count = sum(1 for d in number if d >= 5)
        patterns['big_small_ratio'] = f"{big_count}:{5-big_count}"
        
        # 3. 精确和值
        hezhi = sum(number)
        patterns['hezhi_exact'] = str(hezhi)
        
        # 4. 和值区间
        if hezhi < 15:
            patterns['hezhi_range'] = '15以下'
        elif hezhi <= 19:
            patterns['hezhi_range'] = '15-19'
        elif hezhi <= 24:
            patterns['hezhi_range'] = '20-24'
        elif hezhi <= 29:
            patterns['hezhi_range'] = '25-29'
        elif hezhi <= 34:
            patterns['hezhi_range'] = '30-34'
        else:
            patterns['hezhi_range'] = '35+'
        
        # 5. 和值尾
        patterns['digit_sum_mod'] = str(hezhi % 10)
        
        # 6. 精确跨距
        kuaju = max(number) - min(number)
        patterns['kuaju_exact'] = str(kuaju)
        
        # 7. 跨距区间
        if kuaju <= 2:
            patterns['kuaju_range'] = '0-2'
        elif kuaju <= 4:
            patterns['kuaju_range'] = '3-4'
        elif kuaju <= 6:
            patterns['kuaju_range'] = '5-6'
        elif kuaju <= 8:
            patterns['kuaju_range'] = '7-8'
        else:
            patterns['kuaju_range'] = '9'
        
        # 8. 重复类型
        unique_count = len(set(number))
        if unique_count == 5:
            patterns['duplicate_type'] = '五不同'
        elif unique_count == 4:
            patterns['duplicate_type'] = '一组重复'
        elif unique_count == 3:
            patterns['duplicate_type'] = '两组重复'
        else:
            patterns['duplicate_type'] = '三重复'
        
        # 9. 连号类型
        sorted_num = sorted(number)
        consecutive_groups = []
        current_group = [sorted_num[0]]
        for i in range(1, len(sorted_num)):
            if sorted_num[i] - sorted_num[i-1] == 1:
                current_group.append(sorted_num[i])
            else:
                if len(current_group) >= 2:
                    consecutive_groups.append(current_group)
                current_group = [sorted_num[i]]
        if len(current_group) >= 2:
            consecutive_groups.append(current_group)
        
        if len(consecutive_groups) == 0:
            patterns['consecutive_type'] = '无连号'
        elif len(consecutive_groups) == 1:
            if len(consecutive_groups[0]) == 2:
                patterns['consecutive_type'] = '一组连号'
            else:
                patterns['consecutive_type'] = '三连号'
        else:
            patterns['consecutive_type'] = '两组连号'
        
        # 10. 趋势类型
        is_ascending = all(number[i] <= number[i+1] for i in range(4))
        is_descending = all(number[i] >= number[i+1] for i in range(4))
        if is_ascending:
            patterns['trend_type'] = '升序'
        elif is_descending:
            patterns['trend_type'] = '降序'
        else:
            diff_sum = sum(abs(number[i+1] - number[i]) for i in range(4))
            if diff_sum <= 4:
                patterns['trend_type'] = '平稳'
            else:
                patterns['trend_type'] = '震荡'
        
        # 11. 冷热混合
        if cold_numbers or hot_numbers:
            cold_count = sum(1 for d in number if d in cold_numbers)
            hot_count = sum(1 for d in number if d in hot_numbers)
            
            if hot_count == 5:
                patterns['cold_hot_mix'] = '全热'
            elif cold_count == 5:
                patterns['cold_hot_mix'] = '全冷'
            elif hot_count >= 3 and cold_count <= 1:
                patterns['cold_hot_mix'] = '热多冷少'
            elif cold_count >= 3 and hot_count <= 1:
                patterns['cold_hot_mix'] = '冷多热少'
            else:
                patterns['cold_hot_mix'] = '均衡'
        else:
            patterns['cold_hot_mix'] = '未知'
        
        # 12. 首尾和区间
        first_last_sum = number[0] + number[-1]
        if first_last_sum <= 4:
            patterns['first_last_sum'] = '0-4'
        elif first_last_sum <= 9:
            patterns['first_last_sum'] = '5-9'
        elif first_last_sum <= 14:
            patterns['first_last_sum'] = '10-14'
        else:
            patterns['first_last_sum'] = '15-18'
        
        # 13. 中间和区间
        middle_sum = sum(number[1:-1]) if len(number) >= 3 else 0
        if middle_sum <= 9:
            patterns['middle_sum'] = '0-9'
        elif middle_sum <= 14:
            patterns['middle_sum'] = '10-14'
        elif middle_sum <= 19:
            patterns['middle_sum'] = '15-19'
        else:
            patterns['middle_sum'] = '20-27'
        
        # 14. 各位奇偶
        pos_parity = ''.join('奇' if d % 2 == 1 else '偶' for d in number)
        patterns['position_parity'] = pos_parity
        
        return patterns

# ============================================================================
# 逆推验证引擎
# ============================================================================

class BacktestValidator:
    """逆推验证引擎"""
    
    def __init__(self, config: PatternConfig = PatternConfig()):
        self.config = config
        self.pattern_matcher = PatternMatcher(config)
        self._pattern_cache = {}
    
    def validate_patterns(self, historical_numbers: List[List[int]], 
                         features: List[Dict]) -> Dict[str, Pattern]:
        """验证所有模式在历史数据中的命中率"""
        
        cold_hot = self._calculate_cold_hot_numbers(historical_numbers)
        cold_numbers = cold_hot['cold']
        hot_numbers = cold_hot['hot']
        
        n = len(historical_numbers)
        all_pattern_stats = {}
        
        # 1. 全量验证
        full_stats = self._validate_single_window(
            historical_numbers, cold_numbers, hot_numbers,
            0, n, is_training=False
        )
        
        # 2. 滚动窗口验证
        windows = []
        window_size = min(self.config.roll_window, n // 2)
        step = self.config.roll_step
        
        for start in range(0, n - window_size, step):
            end = start + window_size
            if end < n - 1:
                windows.append((start, end))
        
        windows = windows[-max(self.config.min_roll_windows, 3):]
        
        for train_start, train_end in windows:
            train_data = historical_numbers[train_start:train_end]
            val_data = historical_numbers[train_end:min(train_end + 1, n)]
            
            if val_data:
                window_stats = self._validate_single_window(
                    train_data, cold_numbers, hot_numbers,
                    0, len(train_data), is_training=True,
                    val_sequence=val_data
                )
                
                for key, stats in window_stats.items():
                    if key not in all_pattern_stats:
                        all_pattern_stats[key] = {
                            'type': stats['type'],
                            'value': stats['value'],
                            'hits': 0,
                            'occurrences': 0,
                            'rolling_rates': [],
                            'matched_numbers': []
                        }
                    all_pattern_stats[key]['hits'] += stats['hits']
                    all_pattern_stats[key]['occurrences'] += stats['occurrences']
                    if stats['hits'] > 0:
                        all_pattern_stats[key]['matched_numbers'].extend(stats.get('matched_numbers', []))
        
        # 合并全量统计
        for key, stats in full_stats.items():
            if key not in all_pattern_stats:
                all_pattern_stats[key] = stats
            else:
                all_pattern_stats[key]['hits'] += stats['hits']
                all_pattern_stats[key]['occurrences'] += stats['occurrences']
        
        # 转换为Pattern对象
        result = self._create_patterns_from_stats(all_pattern_stats, historical_numbers)
        
        self._pattern_cache = {p.description: p for p in result.values()}
        
        return result
    
    def _validate_single_window(self, train_data: List[List[int]], 
                                cold_numbers: Set[int], hot_numbers: Set[int],
                                start_idx: int, end_idx: int,
                                is_training: bool = False,
                                val_sequence: List[List[int]] = None) -> Dict:
        """验证单个窗口"""
        pattern_stats = defaultdict(lambda: {
            'hits': 0, 
            'occurrences': 0, 
            'matched_numbers': [],
            'type': '',
            'value': ''
        })
        
        if val_sequence is None:
            # 使用向后验证
            for i in range(len(train_data) - 1):
                current = train_data[i]
                next_num = train_data[i + 1]
                
                current_patterns = self.pattern_matcher.extract_patterns_from_number(
                    current, cold_numbers, hot_numbers
                )
                next_patterns = self.pattern_matcher.extract_patterns_from_number(
                    next_num, cold_numbers, hot_numbers
                )
                
                for p_type, p_value in current_patterns.items():
                    key = f"{p_type}:{p_value}"
                    pattern_stats[key]['type'] = p_type
                    pattern_stats[key]['value'] = p_value
                    pattern_stats[key]['occurrences'] += 1
                    
                    if key in [f"{t}:{v}" for t, v in next_patterns.items()]:
                        pattern_stats[key]['hits'] += 1
                        pattern_stats[key]['matched_numbers'].append(next_num)
        else:
            # 使用指定验证序列
            for num in train_data:
                patterns = self.pattern_matcher.extract_patterns_from_number(
                    num, cold_numbers, hot_numbers
                )
                for p_type, p_value in patterns.items():
                    key = f"{p_type}:{p_value}"
                    pattern_stats[key]['type'] = p_type
                    pattern_stats[key]['value'] = p_value
                    pattern_stats[key]['occurrences'] += 1
            
            for val_num in val_sequence:
                val_patterns = self.pattern_matcher.extract_patterns_from_number(
                    val_num, cold_numbers, hot_numbers
                )
                for p_type, p_value in val_patterns.items():
                    key = f"{p_type}:{p_value}"
                    if key in pattern_stats:
                        pattern_stats[key]['hits'] += 1
                        pattern_stats[key]['matched_numbers'].append(val_num)
        
        return dict(pattern_stats)
    
    def _create_patterns_from_stats(self, stats: Dict, historical_numbers: List[List[int]]) -> Dict[str, Pattern]:
        """从统计信息创建Pattern对象"""
        result = {}
        
        for key, stat in stats.items():
            if stat['occurrences'] >= self.config.min_samples_for_pattern:
                hit_rate = stat['hits'] / stat['occurrences'] if stat['occurrences'] > 0 else 0
                
                dynamic_threshold = self.config.min_hit_rate * (1 + 5 / max(stat['occurrences'], 1))
                
                if hit_rate >= dynamic_threshold:
                    pattern = Pattern(
                        pattern_type=stat['type'],
                        pattern_value=stat['value'],
                        description=key,
                        hit_count=stat['hits'],
                        total_occurrences=stat['occurrences'],
                        hit_rate=hit_rate,
                        rolling_hit_rates=[hit_rate]
                    )
                    
                    pattern.chi2_p_value = self._chi2_test_with_continuity(
                        stat['hits'], stat['occurrences'], len(historical_numbers)
                    )
                    pattern.is_significant = pattern.chi2_p_value < self.config.chi2_alpha
                    pattern.update_weight(self.config.decay_factor)
                    
                    result[key] = pattern
        
        return result
    
    def _chi2_test_with_continuity(self, observed: int, total: int, population: int) -> float:
        """带连续性矫正的卡方检验"""
        expected_prob = 1 / min(population, 1000)
        expected = total * expected_prob
        
        if expected < 0.5:
            return 1.0
        
        chi2_stat = ((abs(observed - expected) - 0.5) ** 2) / expected if abs(observed - expected) > 0.5 else 0
        p_value = 1 - chi2.cdf(chi2_stat, df=1)
        return p_value
    
    def _calculate_cold_hot_numbers(self, historical_numbers: List[List[int]]) -> Dict:
        """计算冷热号码"""
        digit_counts = Counter()
        for num in historical_numbers:
            digit_counts.update(num)
        
        total = sum(digit_counts.values()) or 1
        avg_freq = total / 10
        
        cold_numbers = set()
        hot_numbers = set()
        for digit, count in digit_counts.items():
            if count < avg_freq * 0.6:
                cold_numbers.add(digit)
            elif count > avg_freq * 1.4:
                hot_numbers.add(digit)
        
        return {'cold': cold_numbers, 'hot': hot_numbers}
    
    def validate_pattern_combinations(self, patterns: Dict[str, Pattern],
                                      historical_numbers: List[List[int]],
                                      features: List[Dict]) -> Dict:
        """验证模式组合的有效性"""
        combo_stats = {}
        
        pattern_list = list(patterns.values())
        if len(pattern_list) < 3:
            return {}
        
        pattern_list.sort(key=lambda p: p.weight, reverse=True)
        top_patterns = pattern_list[:20]
        
        for i in range(len(top_patterns)):
            for j in range(i + 1, len(top_patterns)):
                p1 = top_patterns[i]
                p2 = top_patterns[j]
                combo_key = f"{p1.description}|{p2.description}"
                
                combo_hits = 0
                combo_occurrences = 0
                
                cold_hot = self._calculate_cold_hot_numbers(historical_numbers)
                
                for idx, num in enumerate(historical_numbers[:-1]):
                    num_patterns = self.pattern_matcher.extract_patterns_from_number(
                        num, cold_hot['cold'], cold_hot['hot']
                    )
                    
                    has_p1 = p1.description in [f"{t}:{v}" for t, v in num_patterns.items()]
                    has_p2 = p2.description in [f"{t}:{v}" for t, v in num_patterns.items()]
                    
                    if has_p1 and has_p2:
                        combo_occurrences += 1
                        next_num = historical_numbers[idx + 1]
                        next_patterns = self.pattern_matcher.extract_patterns_from_number(
                            next_num, cold_hot['cold'], cold_hot['hot']
                        )
                        if p1.description in [f"{t}:{v}" for t, v in next_patterns.items()] or \
                           p2.description in [f"{t}:{v}" for t, v in next_patterns.items()]:
                            combo_hits += 1
                
                if combo_occurrences >= self.config.combo_min_samples:
                    hit_rate = combo_hits / combo_occurrences
                    if hit_rate >= self.config.combo_min_hit_rate:
                        combo_stats[combo_key] = {
                            'patterns': [p1, p2],
                            'hit_rate': hit_rate,
                            'hits': combo_hits,
                            'occurrences': combo_occurrences
                        }
        
        return combo_stats

# ============================================================================
# 策略生成器
# ============================================================================

@dataclass
class Strategy:
    """选号策略"""
    strategy_id: str
    name: str
    patterns: List[Pattern]
    combined_score: float
    expected_hit_rate: float
    historical_hits: int
    historical_occurrences: int
    confidence: float
    generated_numbers: List[List[int]] = field(default_factory=list)
    pattern_weights: Dict[str, float] = field(default_factory=dict)
    combo_info: Dict = field(default_factory=dict)
    performance_history: List[float] = field(default_factory=list)

class StrategyGenerator:
    """策略生成器"""
    
    def __init__(self, config: StrategyConfig = StrategyConfig(),
                 pattern_config: PatternConfig = PatternConfig()):
        self.config = config
        self.pattern_config = pattern_config
        self.pattern_matcher = PatternMatcher(pattern_config)
    
    def generate_strategies(self, validated_patterns: Dict[str, Pattern],
                           combo_stats: Dict,
                           historical_numbers: List[List[int]],
                           features: List[Dict]) -> List[Strategy]:
        """生成选号策略"""
        strategies = []
        
        sorted_patterns = sorted(
            validated_patterns.values(),
            key=lambda p: p.weight * (1 + 0.5 * p.is_significant),
            reverse=True
        )
        
        # 基于组合的策略
        combo_patterns = []
        for combo_key, combo_info in combo_stats.items():
            combo_patterns.append({
                'patterns': combo_info['patterns'],
                'score': combo_info['hit_rate'] * 10,
                'hit_rate': combo_info['hit_rate']
            })
        
        combo_patterns.sort(key=lambda x: x['score'], reverse=True)
        
        used_patterns = set()
        
        # 从组合策略开始
        for combo in combo_patterns[:5]:
            patterns = combo['patterns']
            if any(p.description in used_patterns for p in patterns):
                continue
            
            strategy = self._create_strategy_from_patterns(
                patterns, historical_numbers, features,
                f"STRAT_COMBO_{len(strategies)+1:03d}",
                f"组合策略{chr(65+len(strategies))}"
            )
            
            if strategy and strategy.combined_score >= self.config.min_strategy_score:
                strategy.combo_info = {'is_combo': True, 'hit_rate': combo['hit_rate']}
                strategies.append(strategy)
                for p in patterns:
                    used_patterns.add(p.description)
        
        # 从单模式生成
        for i in range(0, len(sorted_patterns), 2):
            if len(strategies) >= self.config.max_strategies:
                break
            
            selected = sorted_patterns[i:i+3]
            if len(selected) < 2:
                continue
            
            if any(p.description in used_patterns for p in selected):
                continue
            
            strategy = self._create_strategy_from_patterns(
                selected, historical_numbers, features,
                f"STRAT_{len(strategies)+1:03d}",
                f"策略{chr(65+len(strategies))}"
            )
            
            if strategy and strategy.combined_score >= self.config.min_strategy_score:
                strategies.append(strategy)
                for p in selected:
                    used_patterns.add(p.description)
        
        # 多模式组合策略
        if len(strategies) < self.config.max_strategies:
            for i in range(0, len(sorted_patterns) - 2, 3):
                if len(strategies) >= self.config.max_strategies:
                    break
                
                selected = sorted_patterns[i:i+4]
                if len(selected) < 3:
                    continue
                
                if any(p.description in used_patterns for p in selected):
                    continue
                
                strategy = self._create_strategy_from_patterns(
                    selected, historical_numbers, features,
                    f"STRAT_MULTI_{len(strategies)+1:03d}",
                    f"多模策略{chr(65+len(strategies))}"
                )
                
                if strategy and strategy.combined_score >= self.config.min_strategy_score:
                    strategies.append(strategy)
                    for p in selected:
                        used_patterns.add(p.description)
        
        return strategies[:self.config.max_strategies]
    
    def _create_strategy_from_patterns(self, patterns: List[Pattern],
                                       historical_numbers: List[List[int]],
                                       features: List[Dict],
                                       strategy_id: str,
                                       name: str) -> Optional[Strategy]:
        """从模式列表创建策略"""
        if not patterns:
            return None
        
        combined_score = self._calculate_combined_score(patterns)
        if combined_score < self.config.min_strategy_score:
            return None
        
        expected_hit_rate = self._calculate_expected_hit_rate(patterns)
        
        candidates = self._generate_candidates_for_strategy(
            patterns, historical_numbers, features
        )
        
        if not candidates:
            return None
        
        historical_hits, historical_occurrences = self._calculate_strategy_history(
            patterns, features
        )
        
        strategy = Strategy(
            strategy_id=strategy_id,
            name=name,
            patterns=patterns,
            combined_score=combined_score,
            expected_hit_rate=expected_hit_rate,
            historical_hits=historical_hits,
            historical_occurrences=historical_occurrences,
            confidence=combined_score * expected_hit_rate * 10,
            generated_numbers=candidates[:self.config.candidates_per_strategy],
            pattern_weights={p.description: p.weight for p in patterns}
        )
        
        return strategy
    
    def _calculate_combined_score(self, patterns: List[Pattern]) -> float:
        """计算组合得分"""
        if not patterns:
            return 0.0
        
        weights = [p.weight for p in patterns]
        hit_rates = [p.hit_rate for p in patterns]
        
        weighted_score = np.average(hit_rates, weights=weights)
        
        unique_types = len(set(p.pattern_type for p in patterns))
        diversity_bonus = 1 + (unique_types / len(patterns)) * 0.5
        
        significance_bonus = 1 + sum(1 for p in patterns if p.is_significant) / len(patterns) * 0.5
        
        trend_bonus = 1 + sum(1 for p in patterns if p.trend_direction == 1) / len(patterns) * 0.3
        
        return weighted_score * diversity_bonus * significance_bonus * trend_bonus
    
    def _calculate_expected_hit_rate(self, patterns: List[Pattern]) -> float:
        """计算预期命中率"""
        if not patterns:
            return 0.0
        
        hit_rates = [max(p.hit_rate, 0.001) for p in patterns]
        harmonic_mean = len(hit_rates) / sum(1/h for h in hit_rates) if hit_rates else 0
        
        lower_rates = [p.hit_rate_lower for p in patterns if p.hit_rate_lower > 0]
        if lower_rates:
            avg_lower = np.mean(lower_rates)
            harmonic_mean = (harmonic_mean + avg_lower) / 2
        
        return min(harmonic_mean * 1.2, 0.6)
    
    def _generate_candidates_for_strategy(self, patterns: List[Pattern],
                                         historical_numbers: List[List[int]],
                                         features: List[Dict]) -> List[List[int]]:
        """生成候选号码"""
        candidates = []
        attempts = 0
        max_attempts = 20000
        
        cold_hot = self._calculate_cold_hot_numbers(historical_numbers)
        cold_numbers = cold_hot['cold']
        hot_numbers = cold_hot['hot']
        
        seed_numbers = []
        for num in historical_numbers:
            num_patterns = self.pattern_matcher.extract_patterns_from_number(
                num, cold_numbers, hot_numbers
            )
            matches = 0
            for pattern in patterns:
                key = f"{pattern.pattern_type}:{pattern.pattern_value}"
                pattern_key = f"{pattern.pattern_type}:{num_patterns.get(pattern.pattern_type, '')}"
                if key == pattern_key:
                    matches += 1
            if matches >= len(patterns) * 0.6:
                seed_numbers.append(num)
        
        if not seed_numbers and historical_numbers:
            seed_numbers = historical_numbers[-20:]
        
        while len(candidates) < self.config.candidates_per_strategy and attempts < max_attempts:
            attempts += 1
            
            if seed_numbers and random.random() < 0.7:
                base = random.choice(seed_numbers)
                new_num = base.copy()
                
                for pos in range(5):
                    if random.random() < 0.3:
                        if cold_numbers and random.random() < 0.3:
                            new_num[pos] = random.choice(list(cold_numbers))
                        elif hot_numbers and random.random() < 0.3:
                            new_num[pos] = random.choice(list(hot_numbers))
                        else:
                            new_num[pos] = (new_num[pos] + random.randint(-2, 2)) % 10
            else:
                new_num = []
                for pos in range(5):
                    if hot_numbers and random.random() < 0.3:
                        new_num.append(random.choice(list(hot_numbers)))
                    else:
                        new_num.append(random.randint(0, 9))
            
            num_patterns = self.pattern_matcher.extract_patterns_from_number(
                new_num, cold_numbers, hot_numbers
            )
            
            matches = 0
            for pattern in patterns:
                key = f"{pattern.pattern_type}:{pattern.pattern_value}"
                pattern_key = f"{pattern.pattern_type}:{num_patterns.get(pattern.pattern_type, '')}"
                if key == pattern_key:
                    matches += 1
            
            if matches >= max(2, len(patterns) * 0.5):
                candidates.append(new_num)
        
        return candidates
    
    def _calculate_strategy_history(self, patterns: List[Pattern],
                                   features: List[Dict]) -> Tuple[int, int]:
        """计算策略历史表现"""
        if patterns:
            total_hits = sum(p.hit_count * p.weight for p in patterns)
            total_occurrences = sum(p.total_occurrences * p.weight for p in patterns)
            if total_occurrences > 0:
                avg_hits = total_hits / total_occurrences * min(p.total_occurrences for p in patterns)
                return int(avg_hits), int(total_occurrences / len(patterns))
        return 0, 0
    
    def _calculate_cold_hot_numbers(self, historical_numbers: List[List[int]]) -> Dict:
        """计算冷热号码"""
        digit_counts = Counter()
        for num in historical_numbers:
            digit_counts.update(num)
        
        total = sum(digit_counts.values()) or 1
        avg_freq = total / 10
        
        cold_numbers = set()
        hot_numbers = set()
        for digit, count in digit_counts.items():
            if count < avg_freq * 0.6:
                cold_numbers.add(digit)
            elif count > avg_freq * 1.4:
                hot_numbers.add(digit)
        
        return {'cold': cold_numbers, 'hot': hot_numbers}

# ============================================================================
# 自适应权重管理器
# ============================================================================

class AdaptiveWeightManager:
    def __init__(self, decay_factor: float = 0.95, adaptation_window: int = 30):
        self.decay_factor = decay_factor
        self.adaptation_window = adaptation_window
        self.history = defaultdict(list)
    
    def update_weights(self, strategies: List[Strategy], recent_results: List[Dict]) -> List[Strategy]:
        """更新权重"""
        if not recent_results:
            return strategies
        
        for strategy in strategies:
            recent_performance = self._calculate_recent_performance(strategy, recent_results)
            
            for pattern in strategy.patterns:
                if pattern.description in recent_performance:
                    performance = recent_performance[pattern.description]
                    
                    self.history[pattern.description].append(performance)
                    
                    target_weight = performance * 20
                    current_weight = pattern.weight
                    
                    adjustment = (target_weight - current_weight) * 0.1
                    pattern.weight += adjustment
                    
                    pattern.weight = max(0.05, min(15.0, pattern.weight))
                    
                    pattern.recent_hit_rate = performance
            
            strategy.combined_score = self._calculate_combined_score(strategy.patterns)
            strategy.confidence = strategy.combined_score * strategy.expected_hit_rate * 10
            
            strategy.performance_history.append(strategy.confidence)
        
        return strategies
    
    def _calculate_recent_performance(self, strategy: Strategy, recent_results: List[Dict]) -> Dict[str, float]:
        """计算近期表现"""
        performance = {}
        
        for pattern in strategy.patterns:
            hits = 0
            total = 0
            
            for result in recent_results:
                if 'patterns' in result and pattern.description in result['patterns']:
                    total += 1
                    if result.get('hit', False):
                        hits += 1
            
            if total > 0:
                performance[pattern.description] = hits / total
            else:
                performance[pattern.description] = pattern.hit_rate
        
        return performance
    
    def _calculate_combined_score(self, patterns: List[Pattern]) -> float:
        """计算组合得分"""
        if not patterns:
            return 0.0
        
        weights = [p.weight for p in patterns]
        hit_rates = [p.hit_rate for p in patterns]
        
        log_sum = sum(w * np.log(max(h, 0.0001)) for w, h in zip(weights, hit_rates))
        total_weight = sum(weights)
        
        if total_weight > 0:
            return np.exp(log_sum / total_weight)
        return np.mean(hit_rates)

# ============================================================================
# 集成预测器
# ============================================================================

class PatternBasedEnsemblePredictor:
    def __init__(self, historical_numbers: List[List[int]], features: List[Dict],
                 pattern_config: PatternConfig = PatternConfig(),
                 strategy_config: StrategyConfig = StrategyConfig()):
        self.historical = historical_numbers
        self.features = features
        self.pattern_config = pattern_config
        self.strategy_config = strategy_config
        
        self.pattern_matcher = PatternMatcher(pattern_config)
        self.validator = BacktestValidator(pattern_config)
        self.strategy_generator = StrategyGenerator(strategy_config, pattern_config)
        self.weight_manager = AdaptiveWeightManager(decay_factor=pattern_config.decay_factor)
        
        self.validated_patterns = {}
        self.combo_stats = {}
        self.strategies = []
        self._run_validation()
    
    def _run_validation(self):
        """运行完整验证流程"""
        self.validated_patterns = self.validator.validate_patterns(
            self.historical, self.features
        )
        
        self.combo_stats = self.validator.validate_pattern_combinations(
            self.validated_patterns, self.historical, self.features
        )
        
        self.strategies = self.strategy_generator.generate_strategies(
            self.validated_patterns,
            self.combo_stats,
            self.historical,
            self.features
        )
        
        self.strategies = self.weight_manager.update_weights(
            self.strategies, self._create_recent_results()
        )
    
    def _create_recent_results(self) -> List[Dict]:
        """创建近期结果用于权重更新"""
        results = []
        n = len(self.historical)
        window = min(20, n)
        
        if n > window:
            for i in range(n - window, n - 1):
                result = {
                    'patterns': [],
                    'hit': False
                }
                current = self.historical[i]
                next_num = self.historical[i + 1]
                
                cold_hot = self.validator._calculate_cold_hot_numbers(self.historical[:i+1])
                patterns = self.pattern_matcher.extract_patterns_from_number(
                    current, cold_hot['cold'], cold_hot['hot']
                )
                next_patterns = self.pattern_matcher.extract_patterns_from_number(
                    next_num, cold_hot['cold'], cold_hot['hot']
                )
                
                for p_type, p_value in patterns.items():
                    key = f"{p_type}:{p_value}"
                    if key in [f"{t}:{v}" for t, v in next_patterns.items()]:
                        result['patterns'].append(key)
                        result['hit'] = True
                
                results.append(result)
        
        return results
    
    def predict_with_strategies(self) -> Dict[str, Any]:
        """执行预测"""
        if not self.strategies:
            return self._fallback_prediction()
        
        for strategy in self.strategies:
            if not strategy.generated_numbers:
                candidates = self.strategy_generator._generate_candidates_for_strategy(
                    strategy.patterns,
                    self.historical,
                    self.features
                )
                strategy.generated_numbers = candidates[:self.strategy_config.candidates_per_strategy]
        
        sorted_strategies = sorted(self.strategies, key=lambda s: s.confidence, reverse=True)
        
        final_recommendations = []
        used_numbers = set()
        
        for strategy in sorted_strategies:
            for num in strategy.generated_numbers:
                num_tuple = tuple(num)
                if num_tuple not in used_numbers:
                    score = self._calculate_number_score(num, strategy)
                    
                    final_recommendations.append({
                        'number': num,
                        'strategy_id': strategy.strategy_id,
                        'strategy_name': strategy.name,
                        'confidence': strategy.confidence,
                        'expected_hit_rate': strategy.expected_hit_rate,
                        'score': score,
                        'patterns': [p.description for p in strategy.patterns],
                        'pattern_weights': strategy.pattern_weights,
                        'is_combo': strategy.combo_info.get('is_combo', False)
                    })
                    used_numbers.add(num_tuple)
                    
                    if len(final_recommendations) >= self.strategy_config.final_recommendations:
                        break
            if len(final_recommendations) >= self.strategy_config.final_recommendations:
                break
        
        final_recommendations.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            'recommendations': final_recommendations[:self.strategy_config.final_recommendations],
            'strategies': sorted_strategies,
            'validated_patterns': self.validated_patterns,
            'combo_stats': self.combo_stats,
            'statistics': self._generate_statistics()
        }
    
    def _calculate_number_score(self, number: List[int], strategy: Strategy) -> float:
        """计算号码的综合得分"""
        score = 0.0
        
        score += strategy.confidence * 0.4
        
        cold_hot = self.validator._calculate_cold_hot_numbers(self.historical)
        num_patterns = self.pattern_matcher.extract_patterns_from_number(
            number, cold_hot['cold'], cold_hot['hot']
        )
        
        match_score = 0
        for pattern in strategy.patterns:
            key = f"{pattern.pattern_type}:{pattern.pattern_value}"
            if key in [f"{t}:{v}" for t, v in num_patterns.items()]:
                match_score += pattern.weight
        
        if strategy.patterns:
            match_score /= len(strategy.patterns)
        score += match_score * 0.3
        
        similarity_score = self._calculate_historical_similarity(number)
        score += similarity_score * 0.2
        
        balance_score = self._calculate_cold_hot_balance(number, cold_hot)
        score += balance_score * 0.1
        
        return score
    
    def _calculate_historical_similarity(self, number: List[int]) -> float:
        """计算与历史号码的相似度"""
        if not self.historical:
            return 0.5
        
        similarities = []
        for hist in self.historical[-50:]:
            matches = sum(1 for i in range(5) if hist[i] == number[i])
            similarities.append(matches / 5)
        
        return np.mean(similarities) if similarities else 0.5
    
    def _calculate_cold_hot_balance(self, number: List[int], cold_hot: Dict) -> float:
        """计算冷热平衡度"""
        cold_count = sum(1 for d in number if d in cold_hot['cold'])
        hot_count = sum(1 for d in number if d in cold_hot['hot'])
        
        if 2 <= hot_count <= 3 and 1 <= cold_count <= 2:
            return 1.0
        elif 1 <= hot_count <= 4 and 0 <= cold_count <= 3:
            return 0.7
        else:
            return 0.3
    
    def _fallback_prediction(self) -> Dict[str, Any]:
        """回退预测"""
        digit_freq = [Counter() for _ in range(5)]
        for num in self.historical[-100:]:
            for pos, d in enumerate(num):
                digit_freq[pos][d] += 1
        
        recommendations = []
        for _ in range(10):
            num = []
            for pos in range(5):
                most_common = digit_freq[pos].most_common(3)
                digit = random.choice([d for d, _ in most_common])
                num.append(digit)
            recommendations.append({
                'number': num,
                'strategy_id': 'FALLBACK',
                'strategy_name': '回退策略',
                'confidence': 0.1,
                'expected_hit_rate': 0.001,
                'score': 0.1,
                'patterns': ['基于频率'],
                'pattern_weights': {'频率': 0.5},
                'is_combo': False
            })
        
        return {
            'recommendations': recommendations,
            'strategies': [],
            'validated_patterns': {},
            'combo_stats': {},
            'statistics': {'fallback': True}
        }
    
    def _generate_statistics(self) -> Dict[str, Any]:
        """生成统计信息"""
        total_patterns = len(self.validated_patterns)
        significant_patterns = sum(1 for p in self.validated_patterns.values() if p.is_significant)
        
        pattern_hit_rates = [p.hit_rate for p in self.validated_patterns.values()]
        avg_hit_rate = np.mean(pattern_hit_rates) if pattern_hit_rates else 0
        max_hit_rate = max(pattern_hit_rates) if pattern_hit_rates else 0
        median_hit_rate = np.median(pattern_hit_rates) if pattern_hit_rates else 0
        
        return {
            'total_validated_patterns': total_patterns,
            'significant_patterns': significant_patterns,
            'avg_hit_rate': avg_hit_rate,
            'max_hit_rate': max_hit_rate,
            'median_hit_rate': median_hit_rate,
            'strategies_count': len(self.strategies),
            'combo_count': len(self.combo_stats),
            'validation_window': self.pattern_config.validation_window
        }

# ============================================================================
# 主函数
# ============================================================================

def main():
    print("=" * 90)
    print("排列五号码预测系统 v5.0 - 优化逆推验证版")
    print("数据源: https://data.17500.cn/pl5_asc.txt")
    print("核心思路: 细粒度模式 → 组合验证 → 动态阈值 → 自适应权重")
    print("=" * 90)
    
    # 获取数据
    numbers, features = fetch_pl5_data_from_txt(limit=800)
    
    if not numbers:
        print("数据获取失败！请检查网络连接。")
        return
    
    print(f"成功获取 {len(numbers)} 条历史开奖数据")
    
    print("\n" + "=" * 90)
    print("第一阶段：模式验证（逆推验证）")
    print("=" * 90)
    
    pattern_config = PatternConfig(
        validation_window=30,
        min_hit_rate=0.015,
        min_samples_for_pattern=5,
        decay_factor=0.95,
        roll_window=50,
        roll_step=10,
        chi2_alpha=0.1,
        combo_min_hit_rate=0.01,
        combo_min_samples=3
    )
    strategy_config = StrategyConfig(
        max_strategies=8,
        min_strategy_score=0.2,
        candidates_per_strategy=30,
        final_recommendations=10
    )
    
    predictor = PatternBasedEnsemblePredictor(
        numbers, features, pattern_config, strategy_config
    )
    
    stats = predictor._generate_statistics()
    print(f"验证的模式总数: {stats['total_validated_patterns']}")
    print(f"显著模式数 (p<{pattern_config.chi2_alpha}): {stats['significant_patterns']}")
    print(f"平均命中率: {stats['avg_hit_rate']:.4%}")
    print(f"中位数命中率: {stats['median_hit_rate']:.4%}")
    print(f"最高命中率: {stats['max_hit_rate']:.4%}")
    print(f"生成的策略数: {stats['strategies_count']}")
    print(f"有效组合数: {stats['combo_count']}")
    
    print("\n显著模式 Top 10:")
    significant_patterns = sorted(
        [p for p in predictor.validated_patterns.values() if p.is_significant],
        key=lambda p: p.weight,
        reverse=True
    )[:10]
    
    for i, pattern in enumerate(significant_patterns, 1):
        ci_lower = pattern.hit_rate_lower * 100
        ci_upper = pattern.hit_rate_upper * 100
        print(f"  {i:2d}. {pattern.description[:50]}")
        print(f"      命中率: {pattern.hit_rate:.4%} ({pattern.hit_count}/{pattern.total_occurrences})")
        print(f"      95%CI: [{ci_lower:.2f}%, {ci_upper:.2f}%]")
        print(f"      权重: {pattern.weight:.4f} | 趋势: {'↑' if pattern.trend_direction == 1 else '↓' if pattern.trend_direction == -1 else '→'}")
    
    print("\n" + "=" * 90)
    print("第二阶段：策略生成与预测")
    print("=" * 90)
    
    result = predictor.predict_with_strategies()
    
    print(f"\n生成 {len(result['strategies'])} 个选号策略:")
    for i, strategy in enumerate(result['strategies'], 1):
        combo_tag = " [组合策略]" if strategy.combo_info.get('is_combo', False) else ""
        print(f"\n策略 {chr(64+i)}: {strategy.name}{combo_tag}")
        print(f"  组合得分: {strategy.combined_score:.4f}")
        print(f"  预期命中率: {strategy.expected_hit_rate:.4%}")
        print(f"  置信度: {strategy.confidence:.4f}")
        print("  模式组合:")
        for pattern in strategy.patterns:
            trend = '↑' if pattern.trend_direction == 1 else '↓' if pattern.trend_direction == -1 else '→'
            print(f"    - {pattern.description[:40]} (权重: {pattern.weight:.4f} {trend})")
    
    print("\n" + "=" * 90)
    print("第三阶段：最终推荐号码")
    print("=" * 90)
    
    for i, rec in enumerate(result['recommendations'], 1):
        num_str = ''.join(map(str, rec['number']))
        num_sum = sum(rec['number'])
        num_range = max(rec['number']) - min(rec['number'])
        odd_count = sum(1 for d in rec['number'] if d % 2 == 1)
        combo_tag = " [组合]" if rec.get('is_combo', False) else ""
        
        print(f"\n推荐 #{i}：{num_str}{combo_tag}")
        print(f"  策略来源: {rec['strategy_name']} (ID: {rec['strategy_id']})")
        print(f"  综合得分: {rec['score']:.4f}")
        print(f"  置信度: {rec['confidence']:.4f}")
        print(f"  预期命中率: {rec['expected_hit_rate']:.4%}")
        print(f"  号码统计: 和值={num_sum}, 跨距={num_range}, 奇偶={odd_count}奇{5-odd_count}偶")
        print("  匹配模式:")
        for pattern in rec['patterns'][:5]:
            weight = rec['pattern_weights'].get(pattern, 1.0)
            print(f"    - {pattern[:40]} (权重: {weight:.4f})")
    
    print("\n" + "=" * 90)
    print("统计摘要")
    print("=" * 90)
    
    print(f"历史数据: {len(numbers)} 期")
    print(f"验证模式: {stats['total_validated_patterns']} 个")
    print(f"显著模式: {stats['significant_patterns']} 个")
    print(f"有效组合: {stats['combo_count']} 个")
    print(f"策略数量: {stats['strategies_count']} 个")
    print(f"推荐号码: {len(result['recommendations'])} 个")
    
    # 数据范围信息
    if features:
        first_date = features[0].get('date', '未知')
        last_date = features[-1].get('date', '未知')
        print(f"数据范围: {first_date} ~ {last_date}")
    
    print("\n" + "=" * 90)
    print("配置参数 (可用于调优)")
    print("=" * 90)
    print(f"验证窗口: {pattern_config.validation_window}")
    print(f"最小命中率: {pattern_config.min_hit_rate}")
    print(f"最小样本数: {pattern_config.min_samples_for_pattern}")
    print(f"衰减因子: {pattern_config.decay_factor}")
    print(f"卡方显著性: {pattern_config.chi2_alpha}")
    print(f"组合最小命中率: {pattern_config.combo_min_hit_rate}")
    
    print("\n" + "=" * 90)
    print("预测完成")
    print("=" * 90)

if __name__ == "__main__":
    main()
