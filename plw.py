import requests
import numpy as np
from bs4 import BeautifulSoup
from collections import Counter, defaultdict
import random
from hmmlearn import hmm
from scipy.stats import poisson, chi2
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score
import warnings
warnings.filterwarnings('ignore')

class FeatureExtractor:
    """增强的特征提取器"""
    def __init__(self, data_rows):
        self.data_rows = data_rows
        self.numbers = []
        self.features = []
        self._extract_all_features()
    
    def _extract_all_features(self):
        """提取所有可用的特征"""
        for row in self.data_rows:
            if len(row) < 12:
                continue
            
            try:
                # 基础号码
                issue = row[0]
                date = row[1]
                number = row[3]
                
                # 各位数字
                digits = []
                for i in range(4, 9):
                    if row[i].isdigit():
                        digits.append(int(row[i]))
                    else:
                        break
                
                if len(digits) != 5:
                    continue
                
                # 和值
                hezhi = int(row[9]) if len(row) > 9 and row[9].isdigit() else sum(digits)
                
                # 跨距
                kuaju = int(row[11]) if len(row) > 11 and row[11].isdigit() else max(digits) - min(digits)
                
                # 合值（和值尾数）
                hezhi_tail = hezhi % 10
                
                # 奇偶比
                odd_count = sum(1 for d in digits if d % 2 == 1)
                
                # 大小比 (>=5为大)
                big_count = sum(1 for d in digits if d >= 5)
                
                # 重复数
                duplicate_count = len(digits) - len(set(digits))
                
                # 连号检测
                sorted_digits = sorted(digits)
                consecutive_count = 0
                for i in range(len(sorted_digits) - 1):
                    if sorted_digits[i+1] - sorted_digits[i] == 1:
                        consecutive_count += 1
                
                # 升序/降序
                is_ascending = all(digits[i] <= digits[i+1] for i in range(4))
                is_descending = all(digits[i] >= digits[i+1] for i in range(4))
                
                # 和值遗漏（相对于前100期的平均值）
                self.numbers.append(digits)
                self.features.append({
                    'issue': issue,
                    'date': date,
                    'number': number,
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
                    'sum_first_last': digits[0] + digits[-1],  # 首尾和
                    'sum_middle': digits[1] + digits[2] + digits[3],  # 中间和
                })
            except:
                continue

class HezhiHezhiKuajuAnalyzer:
    """和值遗漏、合值、跨距分析器（重点关注）"""
    def __init__(self, features):
        self.features = features
        self.recent_100 = features[-100:] if len(features) >= 100 else features
        self._analyze_hezhi_kuaju()
    
    def _analyze_hezhi_kuaju(self):
        """分析和值遗漏、合值、跨距"""
        # 和值分析
        all_hezhi = [f['hezhi'] for f in self.features]
        self.recent_hezhi = [f['hezhi'] for f in self.recent_100]  # 修复：添加这个属性
        
        self.hezhi_freq = Counter(all_hezhi)
        self.recent_hezhi_freq = Counter(self.recent_hezhi)
        
        # 计算和值遗漏
        self.hezhi_missing = {}
        for h in range(45):
            if h in self.recent_hezhi_freq:
                last_pos = None
                for i, f in enumerate(reversed(self.features)):
                    if f['hezhi'] == h:
                        last_pos = i
                        break
                if last_pos is not None:
                    self.hezhi_missing[h] = last_pos
                else:
                    self.hezhi_missing[h] = len(self.features)
            else:
                self.hezhi_missing[h] = len(self.features)
        
        # 合值分析
        all_hezhi_tail = [f['hezhi_tail'] for f in self.features]
        recent_hezhi_tail = [f['hezhi_tail'] for f in self.recent_100]
        self.hezhi_tail_freq = Counter(all_hezhi_tail)
        self.recent_hezhi_tail_freq = Counter(recent_hezhi_tail)
        
        # 跨距分析
        all_kuaju = [f['kuaju'] for f in self.features]
        recent_kuaju = [f['kuaju'] for f in self.recent_100]
        self.kuaju_freq = Counter(all_kuaju)
        self.recent_kuaju_freq = Counter(recent_kuaju)
        
        # 统计量
        self.avg_hezhi = np.mean(all_hezhi) if all_hezhi else 22.5
        self.std_hezhi = np.std(all_hezhi) if all_hezhi else 5.0
        self.avg_kuaju = np.mean(all_kuaju) if all_kuaju else 5.0
        self.std_kuaju = np.std(all_kuaju) if all_kuaju else 2.0
        
        # 获取热门和值区间
        self.hot_hezhi_ranges = self._get_hot_hezhi_ranges()
    
    def _get_hot_hezhi_ranges(self):
        """获取热门和值区间"""
        if not self.recent_hezhi:
            return [(20, 25)]
        
        # 计算和值分布
        hezhi_counts = Counter(self.recent_hezhi)
        sorted_hezhi = sorted(hezhi_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 取前10个热门和值
        top_hezhi = [h for h, _ in sorted_hezhi[:10]]
        top_hezhi.sort()
        
        # 分组为区间
        ranges = []
        if top_hezhi:
            current_range = [top_hezhi[0]]
            for i in range(1, len(top_hezhi)):
                if top_hezhi[i] - top_hezhi[i-1] <= 2:
                    current_range.append(top_hezhi[i])
                else:
                    if len(current_range) >= 2:
                        ranges.append((min(current_range), max(current_range)))
                    else:
                        ranges.append((current_range[0], current_range[0]))
                    current_range = [top_hezhi[i]]
            if current_range:
                if len(current_range) >= 2:
                    ranges.append((min(current_range), max(current_range)))
                else:
                    ranges.append((current_range[0], current_range[0]))
        
        return ranges[:5]  # 返回前5个区间
    
    def score_hezhi_kuaju(self, candidate):
        """基于和值、合值、跨距打分"""
        score = 0
        hezhi = sum(candidate)
        hezhi_tail = hezhi % 10
        kuaju = max(candidate) - min(candidate)
        
        # 1. 和值得分（考虑遗漏）
        missing = self.hezhi_missing.get(hezhi, len(self.features))
        missing_weight = min(missing / 20, 3.0)
        prob = self.recent_hezhi_freq.get(hezhi, 0) / max(1, len(self.recent_100))
        score += prob * 100 * missing_weight
        
        # 2. 合值得分
        tail_prob = self.recent_hezhi_tail_freq.get(hezhi_tail, 0) / max(1, len(self.recent_100))
        score += tail_prob * 50
        
        # 3. 跨距得分
        kuaju_prob = self.recent_kuaju_freq.get(kuaju, 0) / max(1, len(self.recent_100))
        score += kuaju_prob * 80
        
        # 4. 和值偏离度
        z_score = abs(hezhi - self.avg_hezhi) / (self.std_hezhi + 0.1)
        score += max(0, 30 - z_score * 5)
        
        return score
    
    def get_hezhi_score(self, hezhi):
        """单独获取和值得分"""
        missing = self.hezhi_missing.get(hezhi, len(self.features))
        missing_weight = min(missing / 20, 3.0)
        prob = self.recent_hezhi_freq.get(hezhi, 0) / max(1, len(self.recent_100))
        return prob * 100 * missing_weight

class MonteCarloPredictor:
    """蒙特卡洛预测器"""
    def __init__(self, historical_numbers, features):
        self.historical = historical_numbers
        self.features = features
        self.position_probs = []
        self._calculate_position_probabilities()
    
    def _calculate_position_probabilities(self):
        """计算位置概率"""
        for pos in range(5):
            counts = Counter([num[pos] for num in self.historical])
            recent_counts = Counter([num[pos] for num in self.historical[-100:]])
            
            total = len(self.historical)
            probs = {}
            for digit in range(10):
                base_prob = counts.get(digit, 0) / max(1, total)
                recent_prob = recent_counts.get(digit, 0) / max(1, min(100, len(self.historical)))
                probs[digit] = base_prob * 0.7 + recent_prob * 0.3
            
            total_prob = sum(probs.values())
            if total_prob > 0:
                probs = {k: v/total_prob for k, v in probs.items()}
            self.position_probs.append(probs)
    
    def generate_candidates_with_hezhi(self, target_hezhi, n=500):
        """生成指定和值的候选号码"""
        candidates = []
        attempts = 0
        max_attempts = n * 20
        
        while len(candidates) < n and attempts < max_attempts:
            attempts += 1
            number = []
            for pos in range(5):
                digits = list(self.position_probs[pos].keys())
                probs = list(self.position_probs[pos].values())
                digit = np.random.choice(digits, p=probs)
                number.append(digit)
            
            if sum(number) == target_hezhi:
                candidates.append(number)
        
        # 如果数量不够，随机补充
        while len(candidates) < n:
            number = [np.random.randint(0, 10) for _ in range(5)]
            if sum(number) == target_hezhi:
                candidates.append(number)
        
        return candidates[:n]

class HMMPredictor:
    """隐马尔可夫模型预测器"""
    def __init__(self, historical_numbers, n_states=8):
        self.historical = historical_numbers
        self.n_states = n_states
        self.model = None
        self.scaler = None
        self._train_hmm()
    
    def _train_hmm(self):
        if len(self.historical) < 50:
            return
        
        try:
            observations = []
            for i in range(len(self.historical) - 1):
                diff = [self.historical[i+1][j] - self.historical[i][j] for j in range(5)]
                obs = sum([abs(d) * (10 ** (4-j)) for j, d in enumerate(diff)])
                observations.append([obs])
            
            if len(observations) < 20:
                return
            
            observations = np.array(observations)
            scaler = StandardScaler()
            observations_scaled = scaler.fit_transform(observations)
            
            self.model = hmm.GaussianHMM(
                n_components=min(self.n_states, len(observations) // 3),
                covariance_type="diag",
                n_iter=100,
                random_state=42,
                tol=0.001
            )
            
            self.model.fit(observations_scaled)
            self.scaler = scaler
            
        except:
            self.model = None
            self.scaler = None
    
    def predict_next_sequence(self, n_predictions=800):
        if self.model is None or len(self.historical) < 20:
            return self._fallback_prediction(n_predictions)
        
        try:
            predictions = []
            samples, _ = self.model.sample(n_predictions * 2)
            
            for sample in samples:
                try:
                    sample_original = self.scaler.inverse_transform(sample.reshape(1, -1))
                    obs_value = int(abs(sample_original[0][0])) % 100000
                    
                    base_num = self.historical[-1]
                    change = [int(str(obs_value).zfill(5)[j]) if j < 5 else 0 for j in range(5)]
                    
                    new_num = [(base_num[j] + change[j]) % 10 for j in range(5)]
                    predictions.append(new_num)
                except:
                    continue
                
                if len(predictions) >= n_predictions:
                    break
            
            if len(predictions) < n_predictions:
                additional = self._fallback_prediction(n_predictions - len(predictions))
                predictions.extend(additional)
            
            return predictions[:n_predictions]
            
        except:
            return self._fallback_prediction(n_predictions)
    
    def _fallback_prediction(self, n):
        predictions = []
        for _ in range(n):
            if len(self.historical) >= 5:
                recent = self.historical[-5:]
                new_num = []
                for pos in range(5):
                    changes = [recent[i+1][pos] - recent[i][pos] for i in range(len(recent)-1)]
                    if changes:
                        avg_change = int(np.mean(changes))
                        last_val = recent[-1][pos]
                        new_val = (last_val + avg_change + np.random.randint(-2, 3)) % 10
                        new_num.append(new_val)
                    else:
                        new_num.append(np.random.randint(0, 10))
                predictions.append(new_num)
            else:
                predictions.append([np.random.randint(0, 10) for _ in range(5)])
        return predictions

class HistoricalPatternAnalyzer:
    """历史模式分析器"""
    def __init__(self, numbers, features):
        self.numbers = numbers
        self.features = features
        self.patterns = {}
        self._analyze_patterns()
    
    def _analyze_patterns(self):
        """分析历史模式"""
        # 奇偶模式
        odd_patterns = [f['odd_count'] for f in self.features]
        self.patterns['odd_dist'] = Counter(odd_patterns)
        
        # 大小模式
        big_patterns = [f['big_count'] for f in self.features]
        self.patterns['big_dist'] = Counter(big_patterns)
        
        # 重复模式
        duplicate_patterns = [f['duplicate_count'] for f in self.features]
        self.patterns['duplicate_dist'] = Counter(duplicate_patterns)
        
        # 连号模式
        consecutive_patterns = [f['consecutive_count'] for f in self.features]
        self.patterns['consecutive_dist'] = Counter(consecutive_patterns)
    
    def get_pattern_score(self, candidate):
        """计算候选号码的模式得分"""
        score = 0
        
        # 奇偶得分
        odd_count = sum(1 for d in candidate if d % 2 == 1)
        odd_prob = self.patterns['odd_dist'].get(odd_count, 0) / max(1, len(self.features))
        score += odd_prob * 15
        
        # 大小得分
        big_count = sum(1 for d in candidate if d >= 5)
        big_prob = self.patterns['big_dist'].get(big_count, 0) / max(1, len(self.features))
        score += big_prob * 15
        
        # 重复得分
        duplicate_count = len(candidate) - len(set(candidate))
        dup_prob = self.patterns['duplicate_dist'].get(duplicate_count, 0) / max(1, len(self.features))
        score += dup_prob * 20
        
        # 连号得分
        sorted_cand = sorted(candidate)
        consecutive_count = 0
        for i in range(len(sorted_cand) - 1):
            if sorted_cand[i+1] - sorted_cand[i] == 1:
                consecutive_count += 1
        cons_prob = self.patterns['consecutive_dist'].get(consecutive_count, 0) / max(1, len(self.features))
        score += cons_prob * 15
        
        return score

class CombinedPredictor:
    """组合预测器 - 按和值分组推荐"""
    def __init__(self, historical_numbers, features):
        self.historical = historical_numbers
        self.features = features
        
        self.monte_carlo = MonteCarloPredictor(historical_numbers, features)
        self.hmm = HMMPredictor(historical_numbers)
        self.hezhi_analyzer = HezhiHezhiKuajuAnalyzer(features)
        self.pattern_analyzer = HistoricalPatternAnalyzer(historical_numbers, features)
    
    def predict_top_5_with_diverse_hezhi(self):
        """预测Top 5号码，覆盖不同的和值"""
        # 1. 获取热门和值区间
        hot_ranges = self.hezhi_analyzer.hot_hezhi_ranges
        
        # 2. 生成目标和值列表（覆盖不同区间）
        target_hezhi_list = []
        for start, end in hot_ranges:
            if start == end:
                target_hezhi_list.append(start)
            else:
                # 从区间中选取2-3个和值
                step = max(1, (end - start) // 3)
                for h in range(start, end + 1, step):
                    if h not in target_hezhi_list:
                        target_hezhi_list.append(h)
        
        # 3. 补充遗漏较大的和值
        for h in range(15, 36):
            if h not in target_hezhi_list:
                missing = self.hezhi_analyzer.hezhi_missing.get(h, 0)
                if missing > 30:  # 遗漏较大
                    target_hezhi_list.append(h)
        
        # 4. 限制数量，选择最有潜力的和值
        scored_hezhi = []
        for h in target_hezhi_list:
            score = self.hezhi_analyzer.get_hezhi_score(h)
            scored_hezhi.append((h, score))
        
        scored_hezhi.sort(key=lambda x: x[1], reverse=True)
        top_hezhi = [h for h, _ in scored_hezhi[:15]]
        
        # 5. 为每个和值生成候选
        all_candidates = []
        for hezhi in top_hezhi:
            # 生成指定和值的候选
            mc_candidates = self.monte_carlo.generate_candidates_with_hezhi(hezhi, 200)
            hmm_candidates = self._generate_hmm_with_hezhi(hezhi, 100)
            
            candidates = mc_candidates + hmm_candidates
            
            # 去重并过滤历史数据
            historical_set = set(tuple(num) for num in self.historical)
            unique_candidates = []
            seen = set()
            for cand in candidates:
                key = tuple(cand)
                if key not in seen and key not in historical_set:
                    seen.add(key)
                    unique_candidates.append(cand)
            
            # 打分
            for cand in unique_candidates:
                score = self._comprehensive_score(cand)
                all_candidates.append((cand, score, hezhi))
        
        # 6. 按得分排序
        all_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # 7. 选择Top 5，但确保和值不同
        selected = []
        selected_hezhi = set()
        
        for cand, score, hezhi in all_candidates:
            if hezhi not in selected_hezhi:
                selected.append((cand, score))
                selected_hezhi.add(hezhi)
                if len(selected) >= 5:
                    break
        
        # 如果不够5个，补充其他
        if len(selected) < 5:
            for cand, score, hezhi in all_candidates:
                if len(selected) >= 5:
                    break
                if cand not in [s[0] for s in selected]:
                    selected.append((cand, score))
        
        return selected[:5]
    
    def _generate_hmm_with_hezhi(self, target_hezhi, n):
        """生成指定和值的HMM候选"""
        candidates = []
        hmm_candidates = self.hmm.predict_next_sequence(n * 3)
        
        for cand in hmm_candidates:
            if sum(cand) == target_hezhi:
                candidates.append(cand)
                if len(candidates) >= n:
                    break
        
        # 补充
        while len(candidates) < n:
            cand = [np.random.randint(0, 10) for _ in range(5)]
            if sum(cand) == target_hezhi:
                candidates.append(cand)
        
        return candidates
    
    def _comprehensive_score(self, candidate):
        """综合打分"""
        score = 0
        
        # 1. 和值、合值、跨距得分
        score += self.hezhi_analyzer.score_hezhi_kuaju(candidate) * 0.6
        
        # 2. 模式得分
        score += self.pattern_analyzer.get_pattern_score(candidate) * 0.3
        
        # 3. 位置概率
        for pos in range(5):
            if candidate[pos] in self.monte_carlo.position_probs[pos]:
                score += self.monte_carlo.position_probs[pos][candidate[pos]] * 20
        
        # 4. 多样性奖励
        unique_digits = len(set(candidate))
        score += unique_digits * 3
        
        return max(0, score)

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

def analyze_historical_trends(features):
    """分析历史趋势"""
    if not features:
        return {}
    
    recent = features[-100:] if len(features) > 100 else features
    
    # 位置热门数字
    position_hot = []
    for pos in range(5):
        digits = [f['digits'][pos] for f in recent]
        counter = Counter(digits)
        top5 = counter.most_common(5)
        position_hot.append([d for d, _ in top5])
    
    # 和值统计
    sums = [f['hezhi'] for f in recent if f['hezhi'] > 0]
    if sums:
        sum_range = f"{min(sums)}-{max(sums)}"
        avg_sum = np.mean(sums)
        sum_std = np.std(sums)
    else:
        sum_range = "未知"
        avg_sum = 0
        sum_std = 0
    
    # 跨距统计
    ranges = [f['kuaju'] for f in recent if f['kuaju'] > 0]
    if ranges:
        range_range = f"{min(ranges)}-{max(ranges)}"
        avg_range = np.mean(ranges)
        range_std = np.std(ranges)
    else:
        range_range = "未知"
        avg_range = 0
        range_std = 0
    
    # 奇偶统计
    odd_counts = [f['odd_count'] for f in recent]
    odd_dist = Counter(odd_counts)
    
    # 大小统计
    big_counts = [f['big_count'] for f in recent]
    big_dist = Counter(big_counts)
    
    # 重复数统计
    dup_counts = [f['duplicate_count'] for f in recent]
    dup_dist = Counter(dup_counts)
    
    # 连号统计
    cons_counts = [f['consecutive_count'] for f in recent]
    cons_dist = Counter(cons_counts)
    
    return {
        'position_hot': position_hot,
        'sum_range': sum_range,
        'avg_sum': avg_sum,
        'sum_std': sum_std,
        'range_range': range_range,
        'avg_range': avg_range,
        'range_std': range_std,
        'total_samples': len(recent),
        'odd_dist': odd_dist,
        'big_dist': big_dist,
        'dup_dist': dup_dist,
        'cons_dist': cons_dist
    }

def main():
    """主函数"""
    print("=" * 80)
    print("排列五号码预测系统 v2.0 - 多样化和值推荐")
    print("=" * 80)
    
    # 获取数据
    result = fetch_pl5_statistics(limit=1000)
    
    if not result:
        print("数据获取失败！请检查网络连接。")
        return
    
    print(f"成功获取 {result['total_count']} 条历史数据")
    
    # 提取特征
    extractor = FeatureExtractor(result['data_rows'])
    numbers = extractor.numbers
    features = extractor.features
    
    print(f"提取到 {len(numbers)} 条有效开奖号码")
    
    # 分析趋势
    trends = analyze_historical_trends(features)
    print("\n" + "=" * 80)
    print("历史数据统计（近100期）")
    print("=" * 80)
    print(f"  - 样本数量: {trends['total_samples']}")
    print(f"  - 和值范围: {trends['sum_range']}")
    print(f"  - 平均和值: {trends['avg_sum']:.2f} ± {trends.get('sum_std', 0):.2f}")
    print(f"  - 跨距范围: {trends['range_range']}")
    print(f"  - 平均跨距: {trends['avg_range']:.2f} ± {trends.get('range_std', 0):.2f}")
    
    # 显示分布信息
    print("\n特征分布:")
    print(f"  - 奇偶分布: {dict(sorted(trends['odd_dist'].items()))}")
    print(f"  - 大小分布: {dict(sorted(trends['big_dist'].items()))}")
    print(f"  - 重复数分布: {dict(sorted(trends['dup_dist'].items()))}")
    print(f"  - 连号分布: {dict(sorted(trends['cons_dist'].items()))}")
    
    # 预测
    predictor = CombinedPredictor(numbers, features)
    top_5 = predictor.predict_top_5_with_diverse_hezhi()
    
    print("\n" + "=" * 80)
    print("推荐号码 Top 5（覆盖不同和值）")
    print("=" * 80)
    
    for i, (number, score) in enumerate(top_5, 1):
        num_str = ''.join(map(str, number))
        num_sum = sum(number)
        num_range = max(number) - min(number)
        odd_count = sum(1 for d in number if d % 2 == 1)
        big_count = sum(1 for d in number if d >= 5)
        duplicate = len(number) - len(set(number))
        
        # 连号检测
        sorted_num = sorted(number)
        consecutive = 0
        for j in range(len(sorted_num) - 1):
            if sorted_num[j+1] - sorted_num[j] == 1:
                consecutive += 1
        
        print(f"\n推荐 #{i}：{num_str}")
        print(f"  综合得分: {score:.2f}")
        print(f"  和值: {num_sum} | 跨距: {num_range} | 合值: {num_sum % 10}")
        print(f"  奇偶: {odd_count}奇 {5-odd_count}偶")
        print(f"  大小: {big_count}大 {5-big_count}小")
        print(f"  重复数: {duplicate}个 | 连号: {consecutive}对")
        
        if duplicate == 0:
            print("  特征: 五不同")
        elif duplicate == 1:
            print("  特征: 一组重复")
        elif duplicate == 2:
            print("  特征: 两组重复")
        
        if consecutive >= 2:
            print("  特征: 含连号")
    
    print("\n" + "=" * 80)
    print("各位置热门数字（Top 5）")
    print("=" * 80)
    
    pos_names = ['万位', '千位', '百位', '十位', '个位']
    for i, (pos_name, hot_digits) in enumerate(zip(pos_names, trends['position_hot'])):
        print(f"{pos_name}: {', '.join(map(str, hot_digits))}")
    
    print("\n" + "=" * 80)
    print("=" * 80)

if __name__ == "__main__":
    main()
