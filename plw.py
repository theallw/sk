import requests
import numpy as np
from bs4 import BeautifulSoup
from collections import Counter
import random
from hmmlearn import hmm
import warnings
warnings.filterwarnings('ignore')

def fetch_pl5_statistics(limit=2000):
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
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
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
        
        return parse_html(response.text)
    except:
        return None

def parse_html(html_content):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
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
    except:
        return None

def extract_historical_data(data_rows):
    numbers = []
    features = []
    
    for row in data_rows:
        if len(row) >= 9:
            try:
                issue = row[0]
                date = row[1]
                number = row[3]
                
                wan = int(row[4]) if row[4].isdigit() else -1
                qian = int(row[5]) if row[5].isdigit() else -1
                bai = int(row[6]) if row[6].isdigit() else -1
                shi = int(row[7]) if row[7].isdigit() else -1
                ge = int(row[8]) if row[8].isdigit() else -1
                
                hezhi = int(row[9]) if row[9].isdigit() else 0
                kuaju = int(row[11]) if row[11].isdigit() else 0
                
                if all(d >= 0 for d in [wan, qian, bai, shi, ge]):
                    numbers.append([wan, qian, bai, shi, ge])
                    features.append({
                        'issue': issue,
                        'date': date,
                        'number': number,
                        'hezhi': hezhi,
                        'kuaju': kuaju,
                        'digits': [wan, qian, bai, shi, ge]
                    })
            except:
                continue
    
    return numbers, features

class MonteCarloPredictor:
    def __init__(self, historical_numbers):
        self.historical = historical_numbers
        self.position_probs = []
        self._calculate_position_probabilities()
    
    def _calculate_position_probabilities(self):
        for pos in range(5):
            counts = Counter([num[pos] for num in self.historical])
            total = len(self.historical)
            probs = {digit: count/total for digit, count in counts.items()}
            self.position_probs.append(probs)
    
    def generate_candidates(self, n=1000):
        candidates = []
        for _ in range(n):
            number = []
            for pos in range(5):
                digits = list(self.position_probs[pos].keys())
                probs = list(self.position_probs[pos].values())
                digit = np.random.choice(digits, p=probs)
                number.append(digit)
            candidates.append(number)
        return candidates
    
    def score_candidates(self, candidates, features):
        scores = []
        for cand in candidates:
            score = 0
            
            for pos in range(5):
                if cand[pos] in self.position_probs[pos]:
                    score += self.position_probs[pos][cand[pos]] * 10
            
            cand_sum = sum(cand)
            if features:
                recent_features = [f for f in features if f['hezhi'] > 0][-50:]
                if recent_features:
                    avg_sum = np.mean([f['hezhi'] for f in recent_features])
                    sum_diff = abs(cand_sum - avg_sum)
                    score += max(0, 10 - sum_diff * 0.5)
            
            recent_numbers = [f['digits'] for f in features[-10:]] if features else []
            if cand not in recent_numbers:
                score += 5
            
            unique_digits = len(set(cand))
            if unique_digits == 5:
                score += 3
            elif unique_digits == 4:
                score += 2
            
            scores.append(score)
        
        return scores

class HMMPredictor:
    def __init__(self, historical_numbers, n_states=8):
        self.historical = historical_numbers
        self.n_states = n_states
        self.model = None
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
            
            self.model = hmm.GaussianHMM(
                n_components=min(self.n_states, len(observations) // 3),
                covariance_type="diag",
                n_iter=50,
                random_state=42,
                tol=0.01
            )
            
            self.model.fit(observations)
            
        except:
            self.model = None
    
    def predict_next_sequence(self, n_predictions=500):
        if self.model is None or len(self.historical) < 20:
            return self._fallback_prediction(n_predictions)
        
        try:
            predictions = []
            samples, _ = self.model.sample(n_predictions)
            
            for sample in samples:
                try:
                    obs_value = int(abs(sample[0]))
                    obs_value = obs_value % 100000
                    
                    base_num = self.historical[-1]
                    change = [int(str(obs_value).zfill(5)[j]) if j < 5 else 0 for j in range(5)]
                    
                    new_num = [(base_num[j] + change[j]) % 10 for j in range(5)]
                    predictions.append(new_num)
                except:
                    continue
            
            if len(predictions) < n_predictions:
                additional = self._fallback_prediction(n_predictions - len(predictions))
                predictions.extend(additional)
            
            return predictions
            
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

class CombinedPredictor:
    def __init__(self, historical_numbers, features):
        self.historical = historical_numbers
        self.features = features
        self.monte_carlo = MonteCarloPredictor(historical_numbers)
        self.hmm = HMMPredictor(historical_numbers)
    
    def predict_top_5(self):
        try:
            mc_candidates = self.monte_carlo.generate_candidates(1500)
            mc_scores = self.monte_carlo.score_candidates(mc_candidates, self.features)
            
            hmm_candidates = self.hmm.predict_next_sequence(800)
            
            all_candidates = mc_candidates + hmm_candidates
            
            unique_candidates = []
            seen = set()
            for cand in all_candidates:
                key = tuple(cand)
                if key not in seen:
                    seen.add(key)
                    unique_candidates.append(cand)
            
            if not unique_candidates:
                unique_candidates = self.monte_carlo.generate_candidates(100)
            
            historical_set = set(tuple(num) for num in self.historical)
            filtered_candidates = [cand for cand in unique_candidates if tuple(cand) not in historical_set]
            
            if not filtered_candidates:
                for _ in range(1000):
                    cand = [np.random.randint(0, 10) for _ in range(5)]
                    if tuple(cand) not in historical_set:
                        filtered_candidates.append(cand)
                        if len(filtered_candidates) >= 100:
                            break
            
            scores = []
            for cand in filtered_candidates:
                score = 0
                
                try:
                    mc_score = self.monte_carlo.score_candidates([cand], self.features)[0]
                    score += mc_score * 0.6
                except:
                    score += 50
                
                cand_sum = sum(cand)
                if self.features:
                    recent_sums = [f['hezhi'] for f in self.features[-20:] if f['hezhi'] > 0]
                    if recent_sums:
                        avg_sum = np.mean(recent_sums)
                        score += max(0, 15 - abs(cand_sum - avg_sum) * 0.3)
                    else:
                        score += 5
                
                cand_range = max(cand) - min(cand)
                if self.features:
                    recent_ranges = [f['kuaju'] for f in self.features[-20:] if f['kuaju'] > 0]
                    if recent_ranges:
                        avg_range = np.mean(recent_ranges)
                        score += max(0, 10 - abs(cand_range - avg_range) * 0.4)
                    else:
                        score += 3
                
                odd_count = sum(1 for d in cand if d % 2 == 1)
                score += 2 if odd_count in [2, 3] else 0
                
                big_count = sum(1 for d in cand if d >= 5)
                score += 2 if big_count in [2, 3] else 0
                
                if len(set(cand)) >= 3:
                    score += 3
                
                scores.append(score)
            
            sorted_pairs = sorted(zip(filtered_candidates, scores), key=lambda x: x[1], reverse=True)
            top_5 = sorted_pairs[:5]
            return top_5
            
        except:
            return self._fallback_prediction()
    
    def _fallback_prediction(self):
        historical_set = set(tuple(num) for num in self.historical)
        predictions = []
        for _ in range(1000):
            cand = [np.random.randint(0, 10) for _ in range(5)]
            if tuple(cand) not in historical_set:
                predictions.append(cand)
                if len(predictions) >= 5:
                    break
        return [(p, 50) for p in predictions[:5]]

def analyze_historical_trends(features):
    if not features:
        return {}
    
    recent = features[-100:] if len(features) > 100 else features
    
    position_hot = []
    for pos in range(5):
        digits = [f['digits'][pos] for f in recent]
        counter = Counter(digits)
        top3 = counter.most_common(3)
        position_hot.append([d for d, _ in top3])
    
    sums = [f['hezhi'] for f in recent if f['hezhi'] > 0]
    if sums:
        sum_range = f"{min(sums)}-{max(sums)}"
        avg_sum = np.mean(sums)
    else:
        sum_range = "未知"
        avg_sum = 0
    
    ranges = [f['kuaju'] for f in recent if f['kuaju'] > 0]
    if ranges:
        range_range = f"{min(ranges)}-{max(ranges)}"
        avg_range = np.mean(ranges)
    else:
        range_range = "未知"
        avg_range = 0
    
    return {
        'position_hot': position_hot,
        'sum_range': sum_range,
        'avg_sum': avg_sum,
        'range_range': range_range,
        'avg_range': avg_range,
        'total_samples': len(recent)
    }

if __name__ == "__main__":
    print("=" * 70)
    print("排列五号码预测系统 - 蒙特卡洛 + 隐马尔可夫模型")
    print("=" * 70)
    
    result = fetch_pl5_statistics(limit=1000)
    
    if not result:
        print("数据获取失败！")
        exit()
    
    print(f"成功获取 {result['total_count']} 条历史数据")
    
    numbers, features = extract_historical_data(result['data_rows'])
    print(f"提取到 {len(numbers)} 条有效开奖号码")
    
    trends = analyze_historical_trends(features)
    print("\n历史数据统计:")
    print(f"  - 样本数量: {trends['total_samples']}")
    print(f"  - 和值范围: {trends['sum_range']}")
    print(f"  - 平均和值: {trends['avg_sum']:.1f}")
    print(f"  - 跨距范围: {trends['range_range']}")
    print(f"  - 平均跨距: {trends['avg_range']:.1f}")
    
    predictor = CombinedPredictor(numbers, features)
    top_5 = predictor.predict_top_5()
    
    print("\n" + "=" * 70)
    print("推荐号码")
    print("=" * 70)
    
    for i, (number, score) in enumerate(top_5, 1):
        num_str = ''.join(map(str, number))
        num_sum = sum(number)
        num_range = max(number) - min(number)
        odd_count = sum(1 for d in number if d % 2 == 1)
        big_count = sum(1 for d in number if d >= 5)
        duplicate = len(number) - len(set(number))
        
        print(f"\n推荐 #{i}：{num_str}")
        print(f"  综合得分: {score:.2f}")
        print(f"  和值: {num_sum} | 跨距: {num_range}")
        print(f"  奇偶: {odd_count}奇 {5-odd_count}偶")
        print(f"  大小: {big_count}大 {5-big_count}小")
        print(f"  重复数: {duplicate}个")
        
        if duplicate == 0:
            print("  特征: 五不同")
        elif duplicate == 1:
            print("  特征: 一组重复")
        elif duplicate == 2:
            print("  特征: 两组重复")
        
        if tuple(number) in set(tuple(num) for num in numbers):
            print("  ⚠️  警告: 此号码在历史数据中出现过!")
    
    print("\n" + "=" * 70)
    print("各位置热门数字")
    print("=" * 70)
    
    pos_names = ['万位', '千位', '百位', '十位', '个位']
    for i, (pos_name, hot_digits) in enumerate(zip(pos_names, trends['position_hot'])):
        print(f"{pos_name}: {', '.join(map(str, hot_digits))}")
    
    print("=" * 70)
