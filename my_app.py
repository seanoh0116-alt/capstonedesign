import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re

# 분석 기능 함수 (기존 코드 GUI 제외한 핵심 로직 분리)
def extract_first_three_digits(code):
    try:
        code_str = str(code)
        digits = ''.join(filter(str.isdigit, code_str))
        return digits[:3].ljust(3, '0')
    except:
        return '000'

def parse_time_from_column(column_name):
    patterns = [
        r'(오전|오후)\s*(\d{1,2}):(\d{2})',
        r'(\d{1,2}):(\d{2})',
        r'(\d{1,2})시\s*(\d{1,2})분?',
    ]
    for pattern in patterns:
        match = re.search(pattern, column_name)
        if match:
            if len(match.groups()) == 3:
                period = match.group(1)
                hour = int(match.group(2))
                minute = int(match.group(3))
                if period == '오전':
                    if hour == 12:
                        hour = 0
                    hour_24 = hour
                else:
                    if hour == 12:
                        hour_24 = 12
                    else:
                        hour_24 = hour + 12
                if hour_24 > 23:
                    hour_24 -= 24
            elif len(match.groups()) == 2:
                hour = int(match.group(1))
                minute = int(match.group(2)) if match.group(2) else 0
                hour_24 = hour % 24
            else:
                continue
            minute = min(minute, 59)
            return hour_24 * 60 + minute
    return 9999

def is_main_activity_column(col_name):
    return '주행동시간대' in col_name and '동시행동시간대' not in col_name

def find_column_mapping(df):
    patterns = {
        'region': ['SIDO', '시도', '행정구역', '지역', 'region'],
        'weekday': ['WEEKDAY', '요일', 'day', '요일구분'],
        'household': ['HH_SIZE', '가구원수', '전체가구원수', 'household'],
        'gender': ['SEX', '성별', 'gender', '성별코드'],
        'age': ['AGE_GRP', '연령코드', '연령그룹', 'age_code', 'age_group'],
        'marriage': ['MARITAL', '혼인', '혼인상태', 'marriage']
    }
    mapping = {}
    for key, options in patterns.items():
        for col in df.columns:
            lower_col = col.lower()
            for o in options:
                if o.lower() in lower_col:
                    mapping[key] = col
                    break
            if key in mapping:
                break
    return mapping

def group_by_hour(analysis_results):
    hourly = {}
    for r in analysis_results:
        hour = r['sort_key'] // 60
        if hour not in hourly:
            hourly[hour] = {'total_count':0, 'behavior_counts':{}}
        hourly[hour]['total_count'] += r['total_count']
        for b in r['top_behaviors']:
            hourly[hour]['behavior_counts'][b['code']] = hourly[hour]['behavior_counts'].get(b['code'],0) + b['count']
    result = []
    for hour in range(24):
        if hour in hourly:
            data = hourly[hour]
            total = data['total_count']
            bc = data['behavior_counts']
            behaviors = [{'code':code, 'name':code, 'count':count, 'percentage':count/total*100} for code,count in bc.items()]
            behaviors.sort(key=lambda x: x['percentage'], reverse=True)
            result.append({'hour':hour, 'total_count':total, 'top_behaviors':behaviors[:3]})
        else:
            result.append({'hour':hour, 'total_count':0, 'top_behaviors':[]})
    return result

def analyze_data(df, filters, behavior_map):
    # 필터 적용
    mapping = find_column_mapping(df)
    filtered = df.copy()
    if filters['region'] != '전체' and 'region' in mapping:
        code = int(filters['region'].split('-')[0])
        filtered = filtered[filtered[mapping['region']] == code]
    if filters['weekday'] != '전체' and 'weekday' in mapping:
        code = int(filters['weekday'].split('-')[0])
        filtered = filtered[filtered[mapping['weekday']] == code]
    if filters['household'] != '전체' and 'household' in mapping:
        code_str = filters['household'].replace('명','')
        try:
            code = int(code_str)
            filtered = filtered[filtered[mapping['household']] == code]
        except:
            pass
    if filters['gender'] != '전체' and 'gender' in mapping:
        code = int(filters['gender'].split('-')[0])
        filtered = filtered[filtered[mapping['gender']] == code]
    if filters['age'] != '전체' and 'age' in mapping:
        code = int(filters['age'].split('-')[0])
        filtered = filtered[filtered[mapping['age']] == code]
    if filters['marriage'] != '전체' and 'marriage' in mapping:
        code = int(filters['marriage'].split('-')[0])
        filtered = filtered[filtered[mapping['marriage']] == code]

    # 행동 분석
    main_cols = [c for c in filtered.columns if is_main_activity_column(c)]
    main_cols.sort(key=parse_time_from_column)
    analysis_results = []
    for col in main_cols:
        codes = filtered[col].dropna()
        if len(codes) == 0:
            continue
        three_codes = codes.apply(extract_first_three_digits)
        vc = three_codes.value_counts()
        total = len(three_codes)
        top_behaviors = []
        for i,(code,count) in enumerate(vc.items()):
            per = count / total * 100
            top_behaviors.append({'rank':i+1, 'code':code, 'name':behavior_map.get(code,code), 'count':count, 'percentage':per})
        analysis_results.append({'time':col, 'total_count':total, 'unique_codes':len(vc), 'top_behaviors':top_behaviors, 'sort_key':parse_time_from_column(col)})
    analysis_results.sort(key=lambda x:x['sort_key'])
    return group_by_hour(analysis_results), analysis_results

# Main Streamlit app   
def main():
    # 행동코드 한글명 매핑 예시(원래 전체 넣으세요)
    behavior_map = {
        '111': '수면',
        '121': '식사하기',
        '131': '자기치료',
        '711': '대면교제',
        '821': '책읽기',
        # 추가 필요
    }

    st.title("생활시간조사 행동 분석")
    uploaded_file = st.file_uploader("CSV 파일 업로드", type=['csv'])
    if not uploaded_file:
        st.info("먼저 CSV 파일을 업로드하세요.")
        return

    df = pd.read_csv(uploaded_file)
    # 필터 UI
    col1, col2, col3 = st.columns(3)
    with col1:
        region = st.selectbox("행정구역", ["전체", "11-서울", "21-부산", "22-대구", "23-인천", "24-광주"])
        household = st.selectbox("가구원수", ["전체"] + [str(i)+"명" for i in range(1,10)])
        age = st.selectbox("연령대", ["전체", "1-10대", "2-20대", "3-30대", "4-40대"])
    with col2:
        weekday = st.selectbox("요일", ["전체", "0-일요일", "1-월요일", "2-화요일"])
        gender = st.selectbox("성별", ["전체", "1-남자", "2-여자"])
        marriage = st.selectbox("혼인상태", ["전체", "1-미혼", "2-배우자있음", "3-사별"])
    filters = {
        'region': region,
        'weekday': weekday,
        'household': household,
        'gender': gender,
        'age': age,
        'marriage': marriage
    }

    if st.button("분석 실행"):
        hourly_results, analysis_results = analyze_data(df, filters, behavior_map)
        st.write("=== 시간대별 상위 3개 행동 표 ===")
        for r in hourly_results:
            st.write(f"{r['hour']:02d}시: ", 
                     ", ".join(f"{b['name']}({b['percentage']:.1f}%)" for b in r['top_behaviors']))
        # 막대그래프 크기 조절
        width = st.slider("그래프 크기 조절", 5, 20, 10)
        fig, ax = plt.subplots(figsize=(width,6))
        hours = [r['hour'] for r in hourly_results]
        colors = ['#2E86AB', '#A23B72', '#F18F01']
        for i in range(3):
            vals = [r['top_behaviors'][i]['percentage'] if len(r['top_behaviors'])>i else 0 for r in hourly_results]
            ax.bar(np.array(hours)+i*0.25, vals, width=0.25, label=f'{i+1}위 행동', color=colors[i])
            for j, val in enumerate(vals):
                if val > 2:
                    name = hourly_results[j]['top_behaviors'][i]['name']
                    ax.text(hours[j]+i*0.25, val+0.5, f"{name}\n{val:.1f}%", ha='center', rotation=35, fontsize=8)
        ax.set_xticks(np.array(hours)+0.25)
        ax.set_xticklabels([f"{h:02d}시" for h in hours], rotation=30)
        ax.set_ylabel("비율 (%)")
        ax.set_title("시간대별 상위 3개 행동 비율")
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.5)
        st.pyplot(fig)


if __name__ == "__main__":
    main()
