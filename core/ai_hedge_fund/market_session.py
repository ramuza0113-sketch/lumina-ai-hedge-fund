# -*- coding: utf-8 -*-
"""
Lumina AI Hedge Fund: Global Market Trading Session Utility
Accurately detects real-time market open/closed status for Tokyo (TSE) and US (NYSE/NASDAQ),
accounting for US Daylight Saving Time (DST).
Enables smart patrol prioritization:
- Focus on Japanese stocks during Tokyo trading hours (09:00 - 15:30 JST).
- Focus on US stocks during New York trading hours (22:30/23:30 - 05:00/06:00 JST).
"""

import datetime
from typing import Dict, Any, Optional

class MarketSession:
    """Tokyo & New York Trading Session Inspector"""

    @classmethod
    def _is_us_dst(cls, dt_utc: datetime.datetime) -> bool:
        """
        Check if US Eastern Time is in Daylight Saving Time (DST).
        Starts: Second Sunday in March at 02:00 local (07:00 UTC)
        Ends: First Sunday in November at 02:00 local (06:00 UTC)
        """
        year = dt_utc.year
        # Second Sunday in March
        mar1 = datetime.datetime(year, 3, 1, tzinfo=datetime.timezone.utc)
        mar_first_sun = 1 + (6 - mar1.weekday()) % 7
        dst_start = datetime.datetime(year, 3, mar_first_sun + 7, 7, 0, tzinfo=datetime.timezone.utc)

        # First Sunday in November
        nov1 = datetime.datetime(year, 11, 1, tzinfo=datetime.timezone.utc)
        nov_first_sun = 1 + (6 - nov1.weekday()) % 7
        dst_end = datetime.datetime(year, 11, nov_first_sun, 6, 0, tzinfo=datetime.timezone.utc)

        return dst_start <= dt_utc < dst_end

    @classmethod
    def is_tse_open(cls, dt_jst: Optional[datetime.datetime] = None) -> bool:
        """
        Check if Tokyo Stock Exchange (TSE) is currently in open trading session.
        Session: Monday - Friday, 09:00 - 15:30 JST.
        """
        if dt_jst is None:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            jst_offset = datetime.timezone(datetime.timedelta(hours=9))
            dt_jst = now_utc.astimezone(jst_offset)

        # Weekend check (5=Saturday, 6=Sunday) and Japanese holiday check
        if dt_jst.weekday() >= 5 or not cls.is_tse_trading_day(dt_jst.date()):
            return False

        t = dt_jst.time()
        start = datetime.time(9, 0)
        end = datetime.time(15, 30)
        return start <= t <= end

    @classmethod
    def is_us_open(cls, dt_utc: Optional[datetime.datetime] = None) -> bool:
        """
        Check if US Stock Markets (NYSE/NASDAQ) are currently open.
        Regular hours: Monday - Friday 09:30 - 16:00 US Eastern Time (ET).
        - Summer (EDT, UTC-4): 13:30 - 20:00 UTC (22:30 - 05:00 JST)
        - Winter (EST, UTC-5): 14:30 - 21:00 UTC (23:30 - 06:00 JST)
        """
        if dt_utc is None:
            dt_utc = datetime.datetime.now(datetime.timezone.utc)

        # Convert UTC to US Eastern Time
        is_dst = cls._is_us_dst(dt_utc)
        et_offset = datetime.timezone(datetime.timedelta(hours=-4 if is_dst else -5))
        dt_et = dt_utc.astimezone(et_offset)

        # Weekend check
        if dt_et.weekday() >= 5:
            return False

        t = dt_et.time()
        start = datetime.time(9, 30)
        end = datetime.time(16, 0)
        return start <= t <= end

    @classmethod
    def is_eu_open(cls, dt_utc: Optional[datetime.datetime] = None) -> bool:
        """
        Check if European Stock Markets (Euronext, XETRA, LSE) are currently open.
        Regular hours: Monday - Friday 08:00 - 16:30 / 09:00 - 17:30 CET (approx 07:00 - 15:30 UTC / 16:00 - 00:30 JST).
        """
        if dt_utc is None:
            dt_utc = datetime.datetime.now(datetime.timezone.utc)

        if dt_utc.weekday() >= 5:
            return False

        t = dt_utc.time()
        start = datetime.time(7, 0)
        end = datetime.time(15, 30)
        return start <= t <= end

    @classmethod
    def get_market_status(cls) -> Dict[str, Any]:
        """
        Get comprehensive real-time status of markets (Tokyo, US, Europe) and recommended patrol target.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        jst_offset = datetime.timezone(datetime.timedelta(hours=9))
        now_jst = now_utc.astimezone(jst_offset)

        tse_open = cls.is_tse_open(now_jst)
        us_open = cls.is_us_open(now_utc)
        eu_open = cls.is_eu_open(now_utc)
        is_dst = cls._is_us_dst(now_utc)

        if tse_open:
            active_market = "JP"
            status_desc = "🇯🇵 東証取引時間中（09:00〜15:30）: 日本株重点パトロール"
        elif eu_open and not us_open:
            active_market = "EU"
            status_desc = "🇪🇺 欧州市場取引時間中（16:00〜00:30 JST）: 欧州優良モート株重点パトロール"
        elif us_open:
            active_market = "US"
            status_desc = "🇺🇸 米国市場取引時間中: 米国ハイテク・バリュー重点パトロール"
        else:
            active_market = "CLOSED"
            status_desc = "⏸️ 主要市場閉場中: ニュース材料スキャン＆評価損益監視モード"

        return {
            "current_jst": now_jst.strftime("%Y-%m-%d %H:%M:%S"),
            "tse_open": tse_open,
            "us_open": us_open,
            "eu_open": eu_open,
            "us_dst": is_dst,
            "active_market": active_market,
            "status_desc": status_desc
        }

    @classmethod
    def get_japanese_holidays(cls, year: int) -> set:
        """
        Calculate Japanese national holidays (国民の祝日・振替休日・国民の休日) for a given year.
        Supports automatic astronomical calculation for Vernal and Autumnal Equinox.
        """
        try:
            import jpholiday
            # If jpholiday package is available, use it
            start = datetime.date(year, 1, 1)
            end = datetime.date(year, 12, 31)
            return set(jpholiday.between(start, end))
        except ImportError:
            pass

        holidays = set()
        # 元日
        holidays.add(datetime.date(year, 1, 1))

        # 成人の日: 1月第2月曜日
        d = datetime.date(year, 1, 1)
        mon_count = 0
        while d.month == 1:
            if d.weekday() == 0:
                mon_count += 1
                if mon_count == 2:
                    holidays.add(d)
                    break
            d += datetime.timedelta(days=1)

        # 建国記念の日 (2/11), 天皇誕生日 (2/23)
        holidays.add(datetime.date(year, 2, 11))
        holidays.add(datetime.date(year, 2, 23))

        # 春分の日 (約3月20日〜21日)
        v_day = int(20.8431 + 0.242194 * (year - 1980) - int((year - 1980) / 4))
        holidays.add(datetime.date(year, 3, v_day))

        # 昭和の日 (4/29), 憲法記念日 (5/3), みどりの日 (5/4), こどもの日 (5/5)
        holidays.add(datetime.date(year, 4, 29))
        holidays.add(datetime.date(year, 5, 3))
        holidays.add(datetime.date(year, 5, 4))
        holidays.add(datetime.date(year, 5, 5))

        # 海の日: 7月第3月曜日
        d = datetime.date(year, 7, 1)
        mon_count = 0
        while d.month == 7:
            if d.weekday() == 0:
                mon_count += 1
                if mon_count == 3:
                    holidays.add(d)
                    break
            d += datetime.timedelta(days=1)

        # 山の日 (8/11)
        holidays.add(datetime.date(year, 8, 11))

        # 敬老の日: 9月第3月曜日
        d = datetime.date(year, 9, 1)
        mon_count = 0
        while d.month == 9:
            if d.weekday() == 0:
                mon_count += 1
                if mon_count == 3:
                    holidays.add(d)
                    break
            d += datetime.timedelta(days=1)

        # 秋分の日 (約9月22日〜23日)
        a_day = int(23.2488 + 0.242194 * (year - 1980) - int((year - 1980) / 4))
        holidays.add(datetime.date(year, 9, a_day))

        # スポーツの日: 10月第2月曜日
        d = datetime.date(year, 10, 1)
        mon_count = 0
        while d.month == 10:
            if d.weekday() == 0:
                mon_count += 1
                if mon_count == 2:
                    holidays.add(d)
                    break
            d += datetime.timedelta(days=1)

        # 文化の日 (11/3), 勤労感謝の日 (11/23)
        holidays.add(datetime.date(year, 11, 3))
        holidays.add(datetime.date(year, 11, 23))

        # 振替休日 (祝日が日曜日の場合、翌平日が休日)
        substitutes = set()
        for h in sorted(holidays):
            if h.weekday() == 6:  # Sunday
                sub = h + datetime.timedelta(days=1)
                while sub in holidays or sub in substitutes:
                    sub += datetime.timedelta(days=1)
                substitutes.add(sub)
        holidays.update(substitutes)

        # 国民の休日 (祝日と祝日に挟まれた平日)
        citizens = set()
        for h in holidays:
            next_day = h + datetime.timedelta(days=1)
            next_next = h + datetime.timedelta(days=2)
            if next_next in holidays and next_day not in holidays and next_day.weekday() not in (5, 6):
                citizens.add(next_day)
        holidays.update(citizens)

        return holidays

    @classmethod
    def is_tse_trading_day(cls, target_date: Optional[datetime.date] = None) -> bool:
        """
        Check if the specified date was/is a Tokyo Stock Exchange (TSE) trading day (営業日).
        Returns False for:
        - Saturdays and Sundays
        - Japanese national holidays and substitute holidays
        - Year-end and New Year holidays (Dec 31, Jan 2, Jan 3)
        """
        if target_date is None:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            jst_offset = datetime.timezone(datetime.timedelta(hours=9))
            target_date = now_utc.astimezone(jst_offset).date()

        # 1. 土日チェック
        if target_date.weekday() >= 5:
            return False

        # 2. 年末年始（東証休業日: 12/31, 1/2, 1/3。1/1は祝日として判定）
        if (target_date.month == 12 and target_date.day == 31) or \
           (target_date.month == 1 and target_date.day in (2, 3)):
            return False

        # 3. 日本の祝日チェック
        holidays = cls.get_japanese_holidays(target_date.year)
        if target_date in holidays:
            return False

        return True

    @classmethod
    def get_adaptive_interval(cls, default_interval_minutes: int = 15, strategy: str = "ALL") -> tuple:
        """
        AIアダプティブ巡回インターバル判定:
        - 開場中: 設定通りのインターバル (例: 15分) で迅速パトロール
        - 閉場中・夜間・土日祝: 1時間 (60分) の省エネ見守りモードにギアチェンジ。
          ただし次の市場開場時刻まで60分未満の場合は、開場タイミングに合わせて起きるよう調整。
        """
        status = cls.get_market_status()
        tse_open = status.get("tse_open", False)
        us_open = status.get("us_open", False)
        eu_open = status.get("eu_open", False)

        # 欧州株も米国ADR（USD建て）としてNYSE/NASDAQで取引されるため、
        # 実際に注文約定できる市場は「東証（TSE）」または「米国（US）」のみ。
        # したがって、通常パトロール（15分）は東証または米国が開いている時のみ作動させ、
        # 欧州時間中であっても米国が開くまでは省エネ見守り（1時間間隔・開場合わせ）にする。
        is_active = tse_open or us_open

        if is_active:
            market_names = []
            if tse_open:
                market_names.append("東証")
            if us_open:
                market_names.append("米国")
            desc = f"⚡ 取引時間中（{'・'.join(market_names)}）: 通常パトロール（{default_interval_minutes}分間隔）"
            return default_interval_minutes, desc

        # 閉場中: 基本60分。次の市場開場時刻までの分数を推定
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        jst_offset = datetime.timezone(datetime.timedelta(hours=9))
        now_jst = now_utc.astimezone(jst_offset)

        # 米国市場開場時刻 (夏時間: 22:30 JST / 冬時間: 23:30 JST)
        is_dst = cls._is_us_dst(now_utc)
        us_open_jst_hour = 22 if is_dst else 23
        us_open_jst_min = 30

        next_opens = []
        # 今日または明日の東証オープン (土日以外)
        for days_ahead in range(4):
            candidate_date = (now_jst + datetime.timedelta(days=days_ahead)).date()
            if candidate_date.weekday() < 5 and cls.is_tse_trading_day(candidate_date):
                open_tse = datetime.datetime.combine(candidate_date, datetime.time(9, 0), tzinfo=jst_offset)
                if open_tse > now_jst:
                    next_opens.append(open_tse)
                    break

        # 今日または明日の米国オープン (土日以外)
        for days_ahead in range(4):
            candidate_date = (now_jst + datetime.timedelta(days=days_ahead)).date()
            if candidate_date.weekday() < 5:
                open_us = datetime.datetime.combine(candidate_date, datetime.time(us_open_jst_hour, us_open_jst_min), tzinfo=jst_offset)
                if open_us > now_jst:
                    next_opens.append(open_us)
                    break

        # 休日（土日または日本の祝日で米国も開いていない時間）の省エネギア判定
        is_weekend = now_jst.weekday() >= 5
        is_holiday = not cls.is_tse_trading_day(now_jst.date())
        is_rest_day = is_weekend or (is_holiday and not us_open)

        base_closed_mins = 720 if is_rest_day else 60  # 休日は12時間（720分）、平日の閉場時は1時間（60分）
        mode_text = "12時間間隔モード（休日省エネ）" if is_rest_day else "1時間間隔モード"

        mins_to_next = base_closed_mins
        target_time_str = ""
        if next_opens:
            earliest_next = min(next_opens)
            diff_mins = int((earliest_next - now_jst).total_seconds() / 60)
            target_time_str = earliest_next.strftime('%m/%d %H:%M')
            if 0 < diff_mins < base_closed_mins:
                mins_to_next = max(1, diff_mins)
            else:
                mins_to_next = base_closed_mins
        else:
            mins_to_next = base_closed_mins

        if target_time_str and mins_to_next < base_closed_mins:
            desc = f"🌙 市場閉場中（開場待機）: 次回巡回は約{mins_to_next}分後（{target_time_str} 開場に合わせて同期）"
        else:
            if mins_to_next >= 60:
                hours_val = mins_to_next / 60.0
                h_str = f"{int(hours_val)}時間" if hours_val.is_integer() else f"{hours_val:.1f}時間"
                desc = f"🌙 市場閉場中（省エネ見守り）: 次回巡回は約{h_str}後（{mode_text}）"
            else:
                desc = f"🌙 市場閉場中（省エネ見守り）: 次回巡回は約{mins_to_next}分後（{mode_text}）"
        return mins_to_next, desc


