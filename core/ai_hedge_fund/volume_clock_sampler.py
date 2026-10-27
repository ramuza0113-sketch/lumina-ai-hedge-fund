"""
Lumina Quantitative Core: Volume & Dollar Clock Sampler (SoA Accelerated)
========================================================================
Subordinating the price process to market transaction flow (Peter K. Clark 1973 / Marcos Lopez de Prado 2018).
Replaces arbitrary wall-clock intervals (1m/5m bars) with Information-Driven Bars (Volume Bars / Dollar Bars)
computed via cache-friendly Structure of Arrays (SoA) NumPy vectorization.
"""

from typing import Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd


class VolumeClockSampler:
    """
    時間足（Wall-clock）の統計的歪みと閑散期ノイズを排除し、
    出来高（Volume Clock）または売買代金（Dollar Clock）に基づく
    情報主導バー（Information-Driven Bars）を高速生成するエンジン。
    """

    @staticmethod
    def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        """DataFrameのカラム名（大文字・小文字・MultiIndex）を安全に正規化する。"""
        if df is None or df.empty:
            return pd.DataFrame()
        out = df.copy()
        if isinstance(out.columns, pd.MultiIndex):
            out.columns = [c[0].lower() if isinstance(c, tuple) else str(c).lower() for c in out.columns]
        else:
            out.columns = [str(c).lower() for c in out.columns]
        return out

    @classmethod
    def calc_dynamic_threshold(
        cls,
        df: pd.DataFrame,
        bars_per_day: int = 26,
        clock_type: str = "volume",
    ) -> float:
        """
        銘柄ごとの流動性に応じて、1営業日あたり目標のバー本数（デフォルト26本＝15分足相当の粒度）
        になるよう出来高または売買代金しきい値を動的に自動算出する。
        """
        norm_df = cls._normalize_ohlcv(df)
        if norm_df.empty or "volume" not in norm_df.columns:
            return 1000.0

        vols = norm_df["volume"].to_numpy(dtype=np.float64)
        closes = norm_df["close"].to_numpy(dtype=np.float64)

        valid_mask = ~np.isnan(vols) & (vols > 0)
        if not np.any(valid_mask):
            return 1000.0

        # 営業日数の推定
        try:
            unique_days = len(np.unique(norm_df.index.date))
        except Exception:
            unique_days = max(1, len(norm_df) // 78)
        unique_days = max(1, unique_days)

        if clock_type == "dollar":
            total_flow = float(np.sum(vols[valid_mask] * closes[valid_mask]))
        else:
            total_flow = float(np.sum(vols[valid_mask]))

        avg_daily_flow = total_flow / unique_days
        threshold = avg_daily_flow / max(1, bars_per_day)
        return max(1.0, threshold)

    @classmethod
    def to_information_bars(
        cls,
        df: pd.DataFrame,
        threshold: Optional[float] = None,
        bars_per_day: int = 26,
        clock_type: str = "volume",
        max_timeout_sec: Optional[float] = 1800.0,
    ) -> pd.DataFrame:
        """
        SoA（Structure of Arrays）メモリレイアウトによる高速演算で、
        時系列OHLCVデータを出来高バー（volume）またはドルバー（dollar）へ変換する。
        閑散相場や取引停止（サーキットブレーカー）時のシグナル遅延を防ぐため、
        実時間タイムアウト・フォールバック（max_timeout_sec）を完備。

        Parameters
        ----------
        df : pd.DataFrame
            元の時間足データ（open, high, low, close, volume）
        threshold : float, optional
            1バーを確定させる累積出来高（または累積売買代金）のしきい値。
            未指定の場合は `bars_per_day` に基づき自動計算。
        bars_per_day : int
            1日あたりの標準バー生成目標本数（デフォルト26本）
        clock_type : str
            'volume'（出来高クロック）または 'dollar'（売買代金クロック）
        max_timeout_sec : float, optional
            出来高しきい値未達でも強制的にバーを区切る最大経過秒数（デフォルト1800秒＝30分、または元足周期の4倍）

        Returns
        -------
        pd.DataFrame
            出来高/ドルクロックで再構築されたOHLCVデータフレーム。
            追加列:
            - `vwap`: バー内の出来高加重平均価格
            - `tick_count`: そのバーを形成するのに要した元時間足の本数（少ないほど大口急増＝高流速）
            - `duration_sec`: バー形成にかかった実時間（秒）
            - `flow_velocity`: 情報流速スコア（標準速度に対する倍率。高いほど機関投資家の大口資金流入）
            - `is_timeout_bar`: 出来高未達のままタイムアウトで強制確定されたバーかどうか（bool）
        """
        norm_df = cls._normalize_ohlcv(df)
        if norm_df.empty:
            return pd.DataFrame()

        required_cols = {"open", "high", "low", "close", "volume"}
        if not required_cols.issubset(set(norm_df.columns)):
            return pd.DataFrame()

        # 出来高0の完全停止足を除外
        norm_df = norm_df[norm_df["volume"] > 0].copy()
        if norm_df.empty:
            return pd.DataFrame()

        if threshold is None or threshold <= 0:
            threshold = cls.calc_dynamic_threshold(norm_df, bars_per_day=bars_per_day, clock_type=clock_type)

        # --- Cache-Resident SoA (Structure of Arrays) 抽出 ---
        # DataFrameの行オブジェクト参照を排除し、連続メモリ上の1次元float64配列として一括抽出
        opens = norm_df["open"].to_numpy(dtype=np.float64, copy=True)
        highs = norm_df["high"].to_numpy(dtype=np.float64, copy=True)
        lows = norm_df["low"].to_numpy(dtype=np.float64, copy=True)
        closes = norm_df["close"].to_numpy(dtype=np.float64, copy=True)
        volumes = norm_df["volume"].to_numpy(dtype=np.float64, copy=True)
        timestamps = norm_df.index.to_numpy()

        typical_prices = (highs + lows + closes) / 3.0
        dollar_vols = typical_prices * volumes

        if clock_type == "dollar":
            flow_array = dollar_vols
        else:
            flow_array = volumes

        base_interval = 300.0
        try:
            if len(timestamps) > 1:
                diffs = np.diff(timestamps) / np.timedelta64(1, "s")
                valid_diffs = diffs[diffs > 0]
                if len(valid_diffs) > 0:
                    base_interval = float(np.median(valid_diffs))
        except Exception:
            base_interval = 300.0

        # 累積フローとタイムアウト・フォールバック付きバー境界インデックスの算出
        n_rows = len(flow_array)
        if max_timeout_sec is not None and max_timeout_sec > 0:
            eff_timeout = max(float(max_timeout_sec), base_interval * 4.0)
            try:
                rel_sec = ((timestamps - timestamps[0]) / np.timedelta64(1, "s")).astype(np.float64)
            except Exception:
                rel_sec = np.arange(n_rows, dtype=np.float64) * base_interval

            bar_ids = np.zeros(n_rows, dtype=np.int64)
            timeout_bar_set = set()
            cur_bar_id = 0
            acc_flow = 0.0
            bar_start_sec = rel_sec[0]

            for idx in range(n_rows):
                elapsed = rel_sec[idx] - bar_start_sec
                if acc_flow > 0.0 and elapsed >= eff_timeout:
                    # 前の足まででタイムアウト確定し、現在足から新しいバーを開始
                    timeout_bar_set.add(cur_bar_id)
                    cur_bar_id += 1
                    acc_flow = 0.0
                    bar_start_sec = rel_sec[idx]

                bar_ids[idx] = cur_bar_id
                acc_flow += flow_array[idx]

                if acc_flow >= threshold and idx < n_rows - 1:
                    cur_bar_id += 1
                    acc_flow = 0.0
                    bar_start_sec = rel_sec[idx + 1]
        else:
            cum_flow = np.cumsum(flow_array)
            bar_ids = (cum_flow // threshold).astype(np.int64)
            timeout_bar_set = set()

        # 境界変化点を高速特定（np.unique + reduceat でPythonループを最小化）
        unique_ids, start_indices, counts = np.unique(bar_ids, return_index=True, return_counts=True)
        end_indices = start_indices + counts - 1
        is_timeout_bars = np.array([int(uid) in timeout_bar_set for uid in unique_ids], dtype=bool)

        # ベクトル集計（np.ufunc.reduceat によるL1/L2キャッシュ高速集約）
        bar_opens = opens[start_indices]
        bar_closes = closes[end_indices]
        bar_highs = np.maximum.reduceat(highs, start_indices)
        bar_lows = np.minimum.reduceat(lows, start_indices)
        bar_volumes = np.add.reduceat(volumes, start_indices)
        bar_dollar_vols = np.add.reduceat(dollar_vols, start_indices)
        bar_vwaps = np.where(bar_volumes > 0, bar_dollar_vols / bar_volumes, bar_closes)

        bar_timestamps = timestamps[end_indices]
        start_timestamps = timestamps[start_indices]

        # 所要時間（秒）と連続情報流速（Flow Velocity: 単位時間あたり出来高消化速度の過去20バー比）の算出
        try:
            durations_sec = (bar_timestamps - start_timestamps) / np.timedelta64(1, "s")
            durations_sec = np.where(counts <= 1, base_interval, durations_sec + base_interval)
        except Exception:
            durations_sec = counts.astype(np.float64) * 300.0

        # 1秒あたりの実質出来高流速 (shares / sec)
        vol_per_sec = bar_volumes / np.maximum(1.0, durations_sec)
        rolling_base_rate = (
            pd.Series(vol_per_sec).rolling(20, min_periods=1).mean().to_numpy(dtype=np.float64)
        )
        flow_velocity = vol_per_sec / np.maximum(1e-9, rolling_base_rate)

        result = pd.DataFrame(
            {
                "open": bar_opens,
                "high": bar_highs,
                "low": bar_lows,
                "close": bar_closes,
                "volume": bar_volumes,
                "vwap": bar_vwaps,
                "tick_count": counts,
                "duration_sec": durations_sec,
                "flow_velocity": flow_velocity,
                "is_timeout_bar": is_timeout_bars,
            },
            index=pd.DatetimeIndex(bar_timestamps, name="timestamp"),
        )

        # 同一タイムスタンプの重複があれば最新を保持
        result = result[~result.index.duplicated(keep="last")]
        return result

    @classmethod
    def to_volume_bars(
        cls,
        df: pd.DataFrame,
        volume_threshold: Optional[float] = None,
        bars_per_day: int = 26,
        max_timeout_sec: Optional[float] = 1800.0,
    ) -> pd.DataFrame:
        """出来高クロック（Volume Bars）を生成するショートカット。"""
        return cls.to_information_bars(
            df,
            threshold=volume_threshold,
            bars_per_day=bars_per_day,
            clock_type="volume",
            max_timeout_sec=max_timeout_sec,
        )

    @classmethod
    def to_dollar_bars(
        cls, df: pd.DataFrame, dollar_threshold: Optional[float] = None, bars_per_day: int = 26
    ) -> pd.DataFrame:
        """売買代金クロック（Dollar Bars）を生成するショートカット。"""
        return cls.to_information_bars(
            df, threshold=dollar_threshold, bars_per_day=bars_per_day, clock_type="dollar"
        )

    @staticmethod
    def compute_normality_stats(df: pd.DataFrame) -> Dict[str, float]:
        """
        リターン分布の統計的特性（尖度・歪度・正規性）を算出する。
        Clark (1973) の理論通り、時間足よりも出来高足の方が尖度（Excess Kurtosis）が低下し、
        ガウス正規分布へ近づくことを定量検証する。
        """
        if df is None or df.empty or len(df) < 10:
            return {"kurtosis": 0.0, "skewness": 0.0, "jarque_bera": 0.0, "autocorr_lag1": 0.0}

        closes = df["close"].to_numpy(dtype=np.float64)
        log_returns = np.diff(np.log(np.maximum(1e-8, closes)))
        log_returns = log_returns[~np.isnan(log_returns)]

        n = len(log_returns)
        if n < 10:
            return {"kurtosis": 0.0, "skewness": 0.0, "jarque_bera": 0.0, "autocorr_lag1": 0.0}

        mean_r = np.mean(log_returns)
        std_r = np.std(log_returns, ddof=1)
        if std_r <= 1e-12:
            return {"kurtosis": 0.0, "skewness": 0.0, "jarque_bera": 0.0, "autocorr_lag1": 0.0}

        z = (log_returns - mean_r) / std_r
        skewness = float(np.mean(z**3))
        excess_kurtosis = float(np.mean(z**4) - 3.0)

        # Jarque-Bera 統計量（0に近いほど理想的な正規分布）
        jb_stat = float((n / 6.0) * (skewness**2 + 0.25 * (excess_kurtosis**2)))

        # 1次自己相関（ノイズによる過剰反転の少なさ）
        if n > 2:
            autocorr = float(np.corrcoef(log_returns[:-1], log_returns[1:])[0, 1])
        else:
            autocorr = 0.0

        return {
            "kurtosis": round(excess_kurtosis, 3),
            "skewness": round(skewness, 3),
            "jarque_bera": round(jb_stat, 1),
            "autocorr_lag1": round(autocorr, 4),
            "sample_count": n,
        }
