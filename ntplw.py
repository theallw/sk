"""
排列五预测系统 v4.0 - 模式匹配+逆推验证版（修复版）
"""

import requests
import numpy as np
from bs4 import BeautifulSoup
from collections import Counter, defaultdict
import random
from scipy.stats import chi2
from scipy import stats
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import warnings
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
        'hezhi_range',
        'kuaju_range',
        'duplicate_type',
        'consecutive_type',
        'trend_type',
        'cold_hot_mix',
        'first_last_sum',
        'middle_sum'
    ])
    
    validation_window: int = 50
    min_hit_rate: float = 0.02
    min_samples_for_pattern: int = 10
    decay_factor: float = 0.9
    max_patterns_per_strategy: int = 8
    
    roll_window: int = 100
    roll_step: int = 20
    min_roll_windows: int = 3
    chi2_alpha: float = 0.05

@dataclass
class StrategyConfig:
    max_strategies: int = 5
    min_strategy_score: float = 0.3
    candidates_per_strategy: int = 20
    final_recommendations: int = 5

# ============================================================================
# 模式定义与匹配
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
    
    def update_weight(self, decay_factor: float = 0.9):
        """更新模式权重"""
        base_weight = self.hit_rate * 100
        significance_bonus = 1.5 if self.is_significant else 0.5
        
        if len(self.rolling_hit_rates) >= 2:
            trend = self.rolling_hit_rates[-1] / (self.rolling_hit_rates[-2] + 0.001)
            trend_weight = min(trend, 2.0)
        else:
            trend_weight = 1.0
        
        self.weight = (base_weight * significance_bonus * trend_weight) * decay_factor
        self.weight = max(0.1, min(10.0, self.weight))

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
        
        # 3. 和值区间
        hezhi = sum(number)
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
        
        # 4. 跨距区间
        kuaju = max(number) - min(number)
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
        
        # 5. 重复类型
        unique_count = len(set(number))
        if unique_count == 5:
            patterns['duplicate_type'] = '五不同'
        elif unique_count == 4:
            patterns['duplicate_type'] = '一组重复'
        elif unique_count == 3:
            patterns['duplicate_type'] = '两组重复'
        else:
            patterns['duplicate_type'] = '三重复'
        
        # 6. 连号类型
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
        
        # 7. 趋势类型
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
        
        # 8. 冷热混合
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
        
        # 9. 首尾和区间
        first_last_sum = number[0] + number[-1]
        if first_last_sum <= 4:
            patterns['first_last_sum'] = '0-4'
        elif first_last_sum <= 9:
            patterns['first_last_sum'] = '5-9'
        elif first_last_sum <= 14:
            patterns['first_last_sum'] = '10-14'
        else:
            patterns['first_last_sum'] = '15-18'
        
        # 10. 中间和区间
        middle_sum = sum(number[1:-1]) if len(number) >= 3 else 0
        if middle_sum <= 9:
            patterns['middle_sum'] = '0-9'
        elif middle_sum <= 14:
            patterns['middle_sum'] = '10-14'
        elif middle_sum <= 19:
            patterns['middle_sum'] = '15-19'
        else:
            patterns['middle_sum'] = '20-27'
        
        return patterns

# ============================================================================
# 逆推验证引擎
# ============================================================================

class BacktestValidator:
    """逆推验证引擎"""
    
    def __init__(self, config: PatternConfig = PatternConfig()):
        self.config = config
        self.pattern_matcher = PatternMatcher(config)
    
    def validate_patterns(self, historical_numbers: List[List[int]], 
                         features: List[Dict]) -> Dict[str, Pattern]:
        """验证所有模式在历史数据中的命中率"""
        
        # 计算冷热号码
        cold_hot = self._calculate_cold_hot_numbers(historical_numbers)
        cold_numbers = cold_hot['cold']
        hot_numbers = cold_hot['hot']
        
        n = len(historical_numbers)
        if n < self.config.roll_window + self.config.roll_step:
            return self._validate_full(historical_numbers, cold_numbers, hot_numbers)
        
        # 滚动窗口验证
        pattern_stats = {}
        windows = []
        
        for start in range(0, n - self.config.roll_window, self.config.roll_step):
            end = start + self.config.roll_window
            if end + self.config.roll_step > n:
                break
            windows.append((start, end))
        
        if len(windows) < self.config.min_roll_windows:
            return self._validate_full(historical_numbers, cold_numbers, hot_numbers)
        
        for train_start, train_end in windows:
            train_data = historical_numbers[train_start:train_end]
            if train_end < n:
                val_number = historical_numbers[train_end]
                val_patterns = self.pattern_matcher.extract_patterns_from_number(
                    val_number, cold_numbers, hot_numbers
                )
                
                for num in train_data:
                    patterns = self.pattern_matcher.extract_patterns_from_number(
                        num, cold_numbers, hot_numbers
                    )
                    for pattern_type, pattern_value in patterns.items():
                        key = f"{pattern_type}:{pattern_value}"
                        if key not in pattern_stats:
                            pattern_stats[key] = {
                                'type': pattern_type,
                                'value': pattern_value,
                                'hits': 0,
                                'occurrences': 0,
                                'rolling_rates': [],
                                'matched_numbers': []
                            }
                        pattern_stats[key]['occurrences'] += 1
                
                for pattern_type, pattern_value in val_patterns.items():
                    key = f"{pattern_type}:{pattern_value}"
                    if key in pattern_stats:
                        pattern_stats[key]['hits'] += 1
                        pattern_stats[key]['matched_numbers'].append(val_number)
        
        # 计算命中率
        result = {}
        for key, stats in pattern_stats.items():
            if stats['occurrences'] >= self.config.min_samples_for_pattern:
                hit_rate = stats['hits'] / stats['occurrences'] if stats['occurrences'] > 0 else 0
                if hit_rate >= self.config.min_hit_rate:
                    pattern = Pattern(
                        pattern_type=stats['type'],
                        pattern_value=stats['value'],
                        description=key,
                        hit_count=stats['hits'],
                        total_occurrences=stats['occurrences'],
                        hit_rate=hit_rate,
                        rolling_hit_rates=[hit_rate]
                    )
                    
                    # 卡方检验
                    pattern.chi2_p_value = self._chi2_test(stats['hits'], stats['occurrences'])
                    pattern.is_significant = pattern.chi2_p_value < self.config.chi2_alpha
                    pattern.update_weight(self.config.decay_factor)
                    
                    result[key] = pattern
        
        return result
    
    def _validate_full(self, historical_numbers: List[List[int]], 
                       cold_numbers: Set[int], hot_numbers: Set[int]) -> Dict[str, Pattern]:
        """全量验证"""
        pattern_stats = defaultdict(lambda: {'hits': 0, 'occurrences': 0, 'matched_numbers': []})
        
        for i, num in enumerate(historical_numbers):
            patterns = self.pattern_matcher.extract_patterns_from_number(
                num, cold_numbers, hot_numbers
            )
            for pattern_type, pattern_value in patterns.items():
                key = f"{pattern_type}:{pattern_value}"
                pattern_stats[key]['occurrences'] += 1
                
                if i + 1 < len(historical_numbers):
                    next_patterns = self.pattern_matcher.extract_patterns_from_number(
                        historical_numbers[i+1], cold_numbers, hot_numbers
                    )
                    if key in [f"{t}:{v}" for t, v in next_patterns.items()]:
                        pattern_stats[key]['hits'] += 1
                        pattern_stats[key]['matched_numbers'].append(historical_numbers[i+1])
        
        result = {}
        for key, stats in pattern_stats.items():
            if stats['occurrences'] >= self.config.min_samples_for_pattern:
                pattern_type, pattern_value = key.split(':', 1)
                hit_rate = stats['hits'] / stats['occurrences'] if stats['occurrences'] > 0 else 0
                
                if hit_rate >= self.config.min_hit_rate:
                    pattern = Pattern(
                        pattern_type=pattern_type,
                        pattern_value=pattern_value,
                        description=key,
                        hit_count=stats['hits'],
                        total_occurrences=stats['occurrences'],
                        hit_rate=hit_rate,
                        rolling_hit_rates=[hit_rate]
                    )
                    
                    pattern.chi2_p_value = self._chi2_test(stats['hits'], stats['occurrences'])
                    pattern.is_significant = pattern.chi2_p_value < self.config.chi2_alpha
                    pattern.update_weight(self.config.decay_factor)
                    
                    result[key] = pattern
        
        return result
    
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
            if count < avg_freq * 0.7:
                cold_numbers.add(digit)
            elif count > avg_freq * 1.3:
                hot_numbers.add(digit)
        
        return {'cold': cold_numbers, 'hot': hot_numbers}
    
    def _chi2_test(self, observed: int, total: int) -> float:
        """卡方检验"""
        expected = total / 100000
        if expected < 0.1:
            return 1.0
        
        chi2_stat = ((observed - expected) ** 2) / expected
        p_value = 1 - chi2.cdf(chi2_stat, df=1)
        return p_value

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

class StrategyGenerator:
    """策略生成器"""
    
    def __init__(self, config: StrategyConfig = StrategyConfig(),
                 pattern_config: PatternConfig = PatternConfig()):
        self.config = config
        self.pattern_config = pattern_config
        self.pattern_matcher = PatternMatcher(pattern_config)
    
    def generate_strategies(self, validated_patterns: Dict[str, Pattern],
                           historical_numbers: List[List[int]],
                           features: List[Dict]) -> List[Strategy]:
        """生成选号策略"""
        strategies = []
        
        sorted_patterns = sorted(
            validated_patterns.values(),
            key=lambda p: p.weight,
            reverse=True
        )
        
        top_patterns = sorted_patterns[:self.pattern_config.max_patterns_per_strategy * 2]
        
        for i in range(self.config.max_strategies):
            if not top_patterns:
                break
            
            selected_patterns = []
            pattern_types_used = set()
            
            for pattern in top_patterns:
                if pattern.pattern_type not in pattern_types_used:
                    selected_patterns.append(pattern)
                    pattern_types_used.add(pattern.pattern_type)
                    if len(selected_patterns) >= 3:
                        break
            
            if len(selected_patterns) < 2:
                continue
            
            combined_score = self._calculate_combined_score(selected_patterns)
            if combined_score < self.config.min_strategy_score:
                continue
            
            expected_hit_rate = self._calculate_expected_hit_rate(selected_patterns)
            
            candidates = self._generate_candidates_for_strategy(
                selected_patterns, historical_numbers, features
            )
            
            historical_hits, historical_occurrences = self._calculate_strategy_history(
                selected_patterns, features
            )
            
            strategy = Strategy(
                strategy_id=f"STRAT_{i+1:03d}",
                name=f"策略{chr(65+i)}",
                patterns=selected_patterns,
                combined_score=combined_score,
                expected_hit_rate=expected_hit_rate,
                historical_hits=historical_hits,
                historical_occurrences=historical_occurrences,
                confidence=combined_score * expected_hit_rate,
                generated_numbers=candidates[:self.config.candidates_per_strategy],
                pattern_weights={p.description: p.weight for p in selected_patterns}
            )
            
            strategies.append(strategy)
            
            for p in selected_patterns:
                if p in top_patterns:
                    top_patterns.remove(p)
        
        return strategies[:self.config.max_strategies]
    
    def _calculate_combined_score(self, patterns: List[Pattern]) -> float:
        if not patterns:
            return 0.0
        
        weights = [p.weight for p in patterns]
        hit_rates = [p.hit_rate for p in patterns]
        
        weighted_score = np.average(hit_rates, weights=weights)
        
        unique_types = len(set(p.pattern_type for p in patterns))
        diversity_bonus = unique_types / len(patterns) if patterns else 1
        
        significance_bonus = sum(1 for p in patterns if p.is_significant) / len(patterns)
        
        return weighted_score * (1 + diversity_bonus * 0.3) * (1 + significance_bonus * 0.5)
    
    def _calculate_expected_hit_rate(self, patterns: List[Pattern]) -> float:
        if not patterns:
            return 0.0
        
        hit_rates = [p.hit_rate for p in patterns]
        expected = np.prod(hit_rates) if hit_rates else 0
        return min(expected, 0.5)
    
    def _generate_candidates_for_strategy(self, patterns: List[Pattern],
                                         historical_numbers: List[List[int]],
                                         features: List[Dict]) -> List[List[int]]:
        candidates = []
        attempts = 0
        max_attempts = 10000
        
        cold_hot = self._calculate_cold_hot_numbers(historical_numbers)
        cold_numbers = cold_hot['cold']
        hot_numbers = cold_hot['hot']
        
        pattern_numbers = []
        for num in historical_numbers:
            num_patterns = self.pattern_matcher.extract_patterns_from_number(
                num, cold_numbers, hot_numbers
            )
            matches = True
            for pattern in patterns:
                key = f"{pattern.pattern_type}:{pattern.pattern_value}"
                pattern_key = f"{pattern.pattern_type}:{num_patterns.get(pattern.pattern_type, '')}"
                if key != pattern_key:
                    matches = False
                    break
            if matches:
                pattern_numbers.append(num)
        
        while len(candidates) < self.config.candidates_per_strategy and attempts < max_attempts:
            attempts += 1
            
            if pattern_numbers:
                base = random.choice(pattern_numbers)
                new_num = base.copy()
                for pos in range(5):
                    if random.random() < 0.2:
                        new_num[pos] = (new_num[pos] + random.randint(-1, 1)) % 10
                current_sum = sum(new_num)
                target_sum = sum(base)
                if current_sum != target_sum:
                    diff = target_sum - current_sum
                    pos = random.randint(0, 4)
                    new_num[pos] = (new_num[pos] + diff) % 10
            else:
                new_num = [random.randint(0, 9) for _ in range(5)]
            
            num_patterns = self.pattern_matcher.extract_patterns_from_number(
                new_num, cold_numbers, hot_numbers
            )
            
            matches = True
            for pattern in patterns:
                key = f"{pattern.pattern_type}:{pattern.pattern_value}"
                pattern_key = f"{pattern.pattern_type}:{num_patterns.get(pattern.pattern_type, '')}"
                if key != pattern_key:
                    matches = False
                    break
            
            if matches:
                candidates.append(new_num)
        
        return candidates
    
    def _calculate_strategy_history(self, patterns: List[Pattern],
                                   features: List[Dict]) -> Tuple[int, int]:
        if patterns:
            min_hits = min(p.hit_count for p in patterns)
            min_occurrences = min(p.total_occurrences for p in patterns)
            return min_hits, min_occurrences
        return 0, 0
    
    def _calculate_cold_hot_numbers(self, historical_numbers: List[List[int]]) -> Dict:
        digit_counts = Counter()
        for num in historical_numbers:
            digit_counts.update(num)
        
        total = sum(digit_counts.values()) or 1
        avg_freq = total / 10
        
        cold_numbers = set()
        hot_numbers = set()
        for digit, count in digit_counts.items():
            if count < avg_freq * 0.7:
                cold_numbers.add(digit)
            elif count > avg_freq * 1.3:
                hot_numbers.add(digit)
        
        return {'cold': cold_numbers, 'hot': hot_numbers}

# ============================================================================
# 自适应权重管理器
# ============================================================================

class AdaptiveWeightManager:
    def __init__(self, decay_factor: float = 0.9, adaptation_window: int = 20):
        self.decay_factor = decay_factor
        self.adaptation_window = adaptation_window
    
    def update_weights(self, strategies: List[Strategy], recent_results: List[Dict]) -> List[Strategy]:
        if not recent_results:
            return strategies
        
        for strategy in strategies:
            recent_performance = self._calculate_recent_performance(strategy, recent_results)
            
            for pattern in strategy.patterns:
                if pattern.description in recent_performance:
                    performance = recent_performance[pattern.description]
                    if performance > pattern.hit_rate:
                        pattern.weight *= (1 + self.decay_factor * 0.1)
                    else:
                        pattern.weight *= (1 - self.decay_factor * 0.05)
                    pattern.weight = max(0.1, min(10.0, pattern.weight))
            
            strategy.combined_score = self._calculate_combined_score(strategy.patterns)
            strategy.confidence = strategy.combined_score * strategy.expected_hit_rate
        
        return strategies
    
    def _calculate_recent_performance(self, strategy: Strategy, recent_results: List[Dict]) -> Dict[str, float]:
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
        if not patterns:
            return 0.0
        
        weights = [p.weight for p in patterns]
        hit_rates = [p.hit_rate for p in patterns]
        
        return np.average(hit_rates, weights=weights)

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
        self.strategies = []
        self._run_validation()
    
    def _run_validation(self):
        self.validated_patterns = self.validator.validate_patterns(
            self.historical, self.features
        )
        
        self.strategies = self.strategy_generator.generate_strategies(
            self.validated_patterns,
            self.historical,
            self.features
        )
    
    def predict_with_strategies(self) -> Dict[str, Any]:
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
                    final_recommendations.append({
                        'number': num,
                        'strategy_id': strategy.strategy_id,
                        'strategy_name': strategy.name,
                        'confidence': strategy.confidence,
                        'expected_hit_rate': strategy.expected_hit_rate,
                        'patterns': [p.description for p in strategy.patterns],
                        'pattern_weights': strategy.pattern_weights
                    })
                    used_numbers.add(num_tuple)
                    if len(final_recommendations) >= self.strategy_config.final_recommendations:
                        break
            if len(final_recommendations) >= self.strategy_config.final_recommendations:
                break
        
        return {
            'recommendations': final_recommendations,
            'strategies': sorted_strategies,
            'validated_patterns': self.validated_patterns,
            'statistics': self._generate_statistics()
        }
    
    def _fallback_prediction(self) -> Dict[str, Any]:
        digit_freq = [Counter() for _ in range(5)]
        for num in self.historical[-100:]:
            for pos, d in enumerate(num):
                digit_freq[pos][d] += 1
        
        recommendations = []
        for _ in range(5):
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
                'patterns': ['基于频率'],
                'pattern_weights': {'频率': 0.5}
            })
        
        return {
            'recommendations': recommendations,
            'strategies': [],
            'validated_patterns': {},
            'statistics': {'fallback': True}
        }
    
    def _generate_statistics(self) -> Dict[str, Any]:
        total_patterns = len(self.validated_patterns)
        significant_patterns = sum(1 for p in self.validated_patterns.values() if p.is_significant)
        
        pattern_hit_rates = [p.hit_rate for p in self.validated_patterns.values()]
        avg_hit_rate = np.mean(pattern_hit_rates) if pattern_hit_rates else 0
        max_hit_rate = max(pattern_hit_rates) if pattern_hit_rates else 0
        
        return {
            'total_validated_patterns': total_patterns,
            'significant_patterns': significant_patterns,
            'avg_hit_rate': avg_hit_rate,
            'max_hit_rate': max_hit_rate,
            'strategies_count': len(self.strategies),
            'validation_window': self.pattern_config.validation_window
        }

# ============================================================================
# 数据获取与特征提取
# ============================================================================

def fetch_pl5_statistics(limit=2000):
    """获取排列五统计数据"""
    url = "https://www.17500.cn/api/chart/pl5/tjb"
    
    payload = {
        '': "",
        'limit': str(limit),
        'week': "9",
        'term': "all",
        'st': "0",
        'rsx': "",
        'bsx': "",
        'eissue': "",
        'sissue': "",
        'xfrom': ""
    }
    
    headers = {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        'Accept-Encoding': "gzip, deflate, br, zstd",
        'sec-ch-ua-platform': "\"Windows\"",
        'sec-ch-ua': "\"Google Chrome\";v=\"149\", \"Chromium\";v=\"149\", \"Not)A;Brand\";v=\"24\"",
        'sec-ch-ua-mobile': "?0",
        'origin': "https://www.17500.cn",
        'sec-fetch-site': "same-origin",
        'sec-fetch-mode': "cors",
        'sec-fetch-dest': "empty",
        'referer': "https://www.17500.cn/chart/pl5-tjb.html",
        'accept-language': "zh-CN,zh;q=0.9",
        'priority': "u=1, i",
    }
    
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        if not table:
            return None
        
        data_rows = []
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if cells:
                    row_data = [cell.get_text(strip=True) for cell in cells]
                    data_rows.append(row_data)
        
        return {
            'data_rows': data_rows,
            'total_count': len(data_rows)
        }
    except Exception as e:
        print(f"数据获取失败: {e}")
        return None

def extract_features(data_rows: List[List[str]]) -> Tuple[List[List[int]], List[Dict]]:
    """特征提取"""
    numbers = []
    features = []
    
    for row in data_rows:
        if len(row) < 12:
            continue
        
        try:
            digits = []
            for i in range(4, 9):
                if row[i].isdigit():
                    digits.append(int(row[i]))
                else:
                    break
            
            if len(digits) != 5:
                continue
            
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
            })
        except:
            continue
    
    return numbers, features

# ============================================================================
# 主函数
# ============================================================================

def main():
    print("=" * 90)
    print("排列五号码预测系统 v4.0 - 模式匹配+逆推验证版")
    print("核心思路: 模式组合匹配 → 逆推验证 → 命中率统计 → 自适应权重")
    print("=" * 90)
    
    result = fetch_pl5_statistics(limit=500)
    
    if not result:
        print("数据获取失败！请检查网络连接。")
        return
    
    print(f"成功获取 {result['total_count']} 条历史数据")
    
    numbers, features = extract_features(result['data_rows'])
    print(f"提取到 {len(numbers)} 条有效开奖号码")
    
    print("\n" + "=" * 90)
    print("第一阶段：模式验证（逆推验证）")
    print("=" * 90)
    
    pattern_config = PatternConfig(
        validation_window=50,
        min_hit_rate=0.02,
        min_samples_for_pattern=10
    )
    strategy_config = StrategyConfig(
        max_strategies=5,
        min_strategy_score=0.3,
        candidates_per_strategy=20,
        final_recommendations=5
    )
    
    predictor = PatternBasedEnsemblePredictor(
        numbers, features, pattern_config, strategy_config
    )
    
    stats = predictor._generate_statistics()
    print(f"验证的模式总数: {stats['total_validated_patterns']}")
    print(f"显著模式数 (p<{pattern_config.chi2_alpha}): {stats['significant_patterns']}")
    print(f"平均命中率: {stats['avg_hit_rate']:.4%}")
    print(f"最高命中率: {stats['max_hit_rate']:.4%}")
    print(f"生成的策略数: {stats['strategies_count']}")
    
    print("\n显著模式 Top 5:")
    significant_patterns = sorted(
        [p for p in predictor.validated_patterns.values() if p.is_significant],
        key=lambda p: p.weight,
        reverse=True
    )[:5]
    
    for i, pattern in enumerate(significant_patterns, 1):
        print(f"  {i}. {pattern.description}")
        print(f"     命中率: {pattern.hit_rate:.4%} ({pattern.hit_count}/{pattern.total_occurrences})")
        print(f"     权重: {pattern.weight:.4f}")
        print(f"     卡方p值: {pattern.chi2_p_value:.6f}")
    
    print("\n" + "=" * 90)
    print("第二阶段：策略生成与预测")
    print("=" * 90)
    
    result = predictor.predict_with_strategies()
    
    print(f"\n生成 {len(result['strategies'])} 个选号策略:")
    for i, strategy in enumerate(result['strategies'], 1):
        print(f"\n策略 {chr(64+i)}: {strategy.name}")
        print(f"  组合得分: {strategy.combined_score:.4f}")
        print(f"  预期命中率: {strategy.expected_hit_rate:.4%}")
        print(f"  历史命中: {strategy.historical_hits}/{strategy.historical_occurrences}")
        print(f"  置信度: {strategy.confidence:.4f}")
        print("  模式组合:")
        for pattern in strategy.patterns:
            print(f"    - {pattern.description} (权重: {pattern.weight:.4f})")
    
    print("\n" + "=" * 90)
    print("第三阶段：最终推荐号码")
    print("=" * 90)
    
    for i, rec in enumerate(result['recommendations'], 1):
        num_str = ''.join(map(str, rec['number']))
        num_sum = sum(rec['number'])
        num_range = max(rec['number']) - min(rec['number'])
        odd_count = sum(1 for d in rec['number'] if d % 2 == 1)
        
        print(f"\n推荐 #{i}：{num_str}")
        print(f"  策略来源: {rec['strategy_name']} (ID: {rec['strategy_id']})")
        print(f"  置信度: {rec['confidence']:.4f}")
        print(f"  预期命中率: {rec['expected_hit_rate']:.4%}")
        print(f"  号码统计: 和值={num_sum}, 跨距={num_range}, 奇偶={odd_count}奇{5-odd_count}偶")
        print("  匹配模式:")
        for pattern in rec['patterns']:
            weight = rec['pattern_weights'].get(pattern, 1.0)
            print(f"    - {pattern} (权重: {weight:.4f})")
    
    print("\n" + "=" * 90)
    print("统计摘要")
    print("=" * 90)
    
    print(f"历史数据: {len(numbers)} 期")
    print(f"验证模式: {stats['total_validated_patterns']} 个")
    print(f"显著模式: {stats['significant_patterns']} 个")
    print(f"策略数量: {stats['strategies_count']} 个")
    print(f"推荐号码: {len(result['recommendations'])} 个")
    
    print("\n" + "=" * 90)
    print("预测完成")
    print("=" * 90)

if __name__ == "__main__":
    main()
