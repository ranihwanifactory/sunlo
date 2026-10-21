from datetime import datetime, timezone, timedelta
import math
import streamlit as st
import plotly.graph_objects as go

# 페이지 설정 (와이드 모드)
st.set_page_config(
    page_title="3D 태양·달 천구 시뮬레이터",
    page_icon="☀️",
    layout="wide"
)

# --- 1. 천문 계산 함수들 ---
def calculate_sun_position(lat, lon, dt):
    """위도, 경도, 시간을 기반으로 태양 고도와 방위각 계산"""
    lat_rad = math.radians(lat)
    utc_dt = dt.astimezone(timezone.utc)
    day_of_year = utc_dt.timetuple().tm_yday

    gamma = (2 * math.pi / 365) * (
        day_of_year - 1 + (utc_dt.hour - 12) / 24.0
    )

    eq_time = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )

    declination = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )

    time_offset = eq_time + 4 * lon
    solar_time = (
        utc_dt.hour * 60
        + utc_dt.minute
        + utc_dt.second / 60
        + utc_dt.microsecond / 1_000_000 / 60
        + time_offset
    )

    solar_hour_angle = (solar_time / 4) - 180
    ha_rad = math.radians(solar_hour_angle)

    cos_zenith = math.sin(lat_rad) * math.sin(declination) + math.cos(
        lat_rad
    ) * math.cos(declination) * math.cos(ha_rad)
    cos_zenith = max(-1.0, min(1.0, cos_zenith))

    zenith_rad = math.acos(cos_zenith)
    altitude_deg = 90 - math.degrees(zenith_rad)

    sin_zenith = max(math.sin(zenith_rad), 1e-9)
    sin_azimuth = -(math.sin(ha_rad) * math.cos(declination)) / sin_zenith
    sin_azimuth = max(-1.0, min(1.0, sin_azimuth))

    cos_azimuth = -(
        math.sin(lat_rad) * math.cos(zenith_rad) - math.sin(declination)
    ) / (math.cos(lat_rad) * sin_zenith)
    cos_azimuth = max(-1.0, min(1.0, cos_azimuth))

    azimuth = math.degrees(math.atan2(sin_azimuth, cos_azimuth))
    if azimuth < 0:
        azimuth += 360

    return altitude_deg, azimuth


def calculate_moon_position(lat, lon, dt):
    """달의 실시간 고도와 방위각 근사 계산"""
    lat_rad = math.radians(lat)
    utc_dt = dt.astimezone(timezone.utc)
    
    base_date = datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc)
    days_elapsed = (utc_dt - base_date).total_seconds() / 86400.0
    
    moon_mean_long = (218.316 + 13.176396 * days_elapsed) % 360
    moon_declination = 5.1 * math.sin(math.radians(moon_mean_long))
    
    lunar_time = (utc_dt.hour * 60 + utc_dt.minute) / 4.0 + lon - (moon_mean_long * 0.9)
    lunar_hour_angle = lunar_time - 180
    ha_rad = math.radians(lunar_hour_angle)

    dec_rad = math.radians(moon_declination)
    cos_zenith = math.sin(lat_rad) * math.sin(dec_rad) + math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad)
    cos_zenith = max(-1.0, min(1.0, cos_zenith))

    zenith_rad = math.acos(cos_zenith)
    alt_deg = 90 - math.degrees(zenith_rad)

    sin_zenith = max(math.sin(zenith_rad), 1e-9)
    sin_az = -(math.sin(ha_rad) * math.cos(dec_rad)) / sin_zenith
    cos_az = -(math.sin(lat_rad) * math.cos(zenith_rad) - math.sin(dec_rad)) / (math.cos(lat_rad) * sin_zenith)
    
    az_deg = math.degrees(math.atan2(max(-1.0, min(1.0, sin_az)), max(-1.0, min(1.0, cos_az))))
    if az_deg < 0:
        az_deg += 360

    return alt_deg, az_deg


def get_sun_times(lat, lon, dt):
    """오늘의 일출, 남중, 일몰 시각 추정"""
    base_midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    rise_time, transit_time, set_time = None, None, None
    max_alt = -999
    
    for h in range(24):
        for m in range(0, 60, 10):
            check_dt = base_midnight + timedelta(hours=h, minutes=m)
            alt, _ = calculate_sun_position(lat, lon, check_dt)
            if alt > max_alt:
                max_alt = alt
                transit_time = check_dt
                
    for h in range(4, 21):
        for m in range(60):
            check_dt = base_midnight + timedelta(hours=h, minutes=m)
            alt, _ = calculate_sun_position(lat, lon, check_dt)
            if -0.3 <= alt <= 0.3:
                if h < 12 and not rise_time:
                    rise_time = check_dt
                elif h >= 12:
                    set_time = check_dt
                    
    return (
        rise_time.strftime('%H:%M') if rise_time else "05:30",
        transit_time.strftime('%H:%M') if transit_time else "12:30",
        set_time.strftime('%H:%M') if set_time else "19:30"
    )


# --- 2. Streamlit UI 구성 ---
st.title("☀️ 3D 실시간 태양·달 천구 시뮬레이터")
st.markdown("국내 주요 도시별 관측 지점에서 바라본 태양과 달의 실시간 위치 및 계절별 궤도를 3D로 시뮬레이션합니다.")

# 사이드바 설정
st.sidebar.header("📍 관측 설정")

CITIES = {
    "대구": (35.8714, 128.6014),
    "서울": (37.5665, 126.9780),
    "부산": (35.1796, 129.0756),
    "인천": (37.4563, 126.7052),
    "광주": (35.1595, 126.8526),
    "대전": (36.3504, 127.3845),
    "울산": (35.5384, 129.3114),
    "제주": (33.4996, 126.5312),
    "강릉": (37.7519, 128.8761),
    "전주": (35.8242, 127.1480),
}

selected_city = st.sidebar.selectbox("국내 도시 선택", list(CITIES.keys()), index=0)
lat, lon = CITIES[selected_city]

st.sidebar.text(f"위도: {lat}° / 경도: {lon}°")

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)

# --- 3. 데이터 계산 ---
sun_alt, sun_az = calculate_sun_position(lat, lon, now)
moon_alt, moon_az = calculate_moon_position(lat, lon, now)
rise, transit, set_t = get_sun_times(lat, lon, now)

# 상단 정보 메트릭 표시
col1, col2, col3, col4 = st.columns(4)
col1.metric("현재 시각 (KST)", now.strftime("%H:%M:%S"))
col2.metric("일출 / 남중 / 일몰", f"{rise} / {transit} / {set_t}")
col3.metric("☀️ 태양 위치", f"고도 {sun_alt:.1f}° / 방위 {sun_az:.1f}°")
col4.metric("🌙 달 위치", f"고도 {moon_alt:.1f}° / 방위 {moon_az:.1f}°")

# --- 4. Plotly 3D 천구 뷰 구현 (동서 방향 교정) ---
def alt_az_to_cartesian(azimuth, altitude, radius=10):
    az_rad = math.radians(azimuth)
    alt_rad = math.radians(altitude)
    # 핵심 교정: 동쪽(90도)이 왼쪽(-X), 서쪽(270도)이 오른쪽(+X)으로 오도록 부호 변경
    x = radius * math.cos(alt_rad) * math.sin(az_rad)
    y = radius * math.cos(alt_rad) * math.cos(az_rad)
    z = radius * math.sin(alt_rad)
    return x, y, z

fig = go.Figure()

# 1. 지평선 바닥면 (원)
h_az = list(range(0, 361, 5))
hx, hy, hz = [], [], []
for a in h_az:
    x, y, z = alt_az_to_cartesian(a, 0, 10)
    hx.append(x); hy.append(y); hz.append(z)

fig.add_trace(go.Scatter3d(
    x=hx, y=hy, z=hz,
    mode='lines',
    line=dict(color='gray', width=3),
    name='지평선'
))

# 2. 방위 표시 (정면=남, 뒤=북, 왼쪽=동, 오른쪽=서)
directions = [
    (180, "남 (정면)", "red"), 
    (0, "북 (뒤)", "blue"), 
    (90, "동 (왼쪽)", "orange"), 
    (270, "서 (오른쪽)", "green")
]
for az, label, color in directions:
    dx, dy, dz = alt_az_to_cartesian(az, 0, 10)
    fig.add_trace(go.Scatter3d(
        x=[0, dx], y=[0, dy], z=[0, dz],
        mode='lines',
        line=dict(color='gray', width=1, dash='dash'),
        showlegend=False
    ))
    fig.add_trace(go.Scatter3d(
        x=[dx], y=[dy], z=[dz + 0.5],
        mode='text',
        text=[label],
        textfont=dict(size=12, color=color),
        showlegend=False
    ))

# 3. 관측자 아이콘
fig.add_trace(go.Scatter3d(
    x=[0], y=[0], z=[0],
    mode='text+markers',
    marker=dict(size=6, color='white'),
    text=[f"🧑 관측자 ({selected_city})"],
    textfont=dict(size=12, color='white'),
    name='관측자'
))

# 4. 계절별 궤도선 (하지, 춘추분, 동지)
seasons = [
    ("하지", 23.44, "red"),
    ("춘·추분", 0.0, "cyan"),
    ("동지", -23.44, "blue")
]
lat_rad = math.radians(lat)

for name, decl, color in seasons:
    decl_rad = math.radians(decl)
    sx, sy, sz = [], [], []
    for ha in range(-115, 116, 4):
        ha_rad = math.radians(ha)
        sin_alt = math.sin(lat_rad) * math.sin(decl_rad) + math.cos(lat_rad) * math.cos(decl_rad) * math.cos(ha_rad)
        alt = math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))
        if alt >= -3:
            cos_az = (math.sin(decl_rad) - math.sin(lat_rad) * sin_alt) / (math.cos(lat_rad) * math.cos(math.radians(alt)))
            az = math.degrees(math.acos(max(-1.0, min(1.0, cos_az))))
            if ha > 0: az = 360 - az
            x, y, z = alt_az_to_cartesian(az, alt, 10)
            sx.append(x); sy.append(y); sz.append(z)
    
    fig.add_trace(go.Scatter3d(
        x=sx, y=sy, z=sz,
        mode='lines',
        line=dict(color=color, width=2, dash='dash'),
        name=f'{name} 궤도'
    ))

# 5. 현재 태양 위치
if sun_alt > 0:
    s_x, s_y, s_z = alt_az_to_cartesian(sun_az, sun_alt, 10)
    fig.add_trace(go.Scatter3d(
        x=[s_x], y=[s_y], z=[s_z],
        mode='text+markers',
        marker=dict(size=12, color='yellow', symbol='circle'),
        text=["☀️ 현재 태양"],
        textfont=dict(size=12, color='yellow'),
        name='태양'
    ))

# 6. 현재 달 위치
if moon_alt > -5:
    m_x, m_y, m_z = alt_az_to_cartesian(moon_az, moon_alt, 10)
    fig.add_trace(go.Scatter3d(
        x=[m_x], y=[m_y], z=[m_z],
        mode='text+markers',
        marker=dict(size=10, color='lightgray', symbol='circle'),
        text=["🌙 달"],
        textfont=dict(size=12, color='lightgray'),
        name='달'
    ))

# 레이아웃 디자인 설정
fig.update_layout(
    scene=dict(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        zaxis=dict(visible=False),
        camera=dict(
            eye=dict(x=0, y=-1.8, z=0.8) # 남쪽 정면에서 바라보는 초기 시점
        ),
        aspectmode='cube'
    ),
    margin=dict(l=0, r=0, b=0, t=0),
    legend=dict(x=0, y=0.9)
)

# 스트림릿에 3D 그래프 출력
st.plotly_chart(fig, use_container_width=True)

# 자동 새로고침 버튼
st.markdown("---")
if st.button("🔄 화면 새로고침"):
    st.rerun()