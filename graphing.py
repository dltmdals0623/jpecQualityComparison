import argparse
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

COLORS = [ '#C92121', '#1B52C7']
REQUIRED = ['quality', 'width_px', 'height_px', 'jpeg_bytes',
            'original_png_bytes', 'size_percent_of_png', 'PSNR_dB', 'SSIM']


def load_data(path):
    df = pd.read_csv(path, encoding='utf-8-sig')
    missing = set(REQUIRED) - set(df.columns)
    if missing:
        raise ValueError(f'{path}: missing columns: {sorted(missing)}')
    for col in REQUIRED:
        df[col] = pd.to_numeric(df[col], errors='raise')
    if df.empty or df[REQUIRED].isna().any().any():
        raise ValueError(f'{path}: empty data or missing values')
    if df['quality'].duplicated().any():
        raise ValueError(f'{path}: duplicated quality values')
    finite_cols = [c for c in REQUIRED if c != 'PSNR_dB']
    if not np.isfinite(df[finite_cols].to_numpy()).all():
        raise ValueError(f'{path}: non-finite input values')
    if not df['quality'].between(0, 100).all():
        raise ValueError('quality must be between 0 and 100')
    for col in ['width_px', 'height_px', 'jpeg_bytes', 'original_png_bytes']:
        if (df[col] <= 0).any():
            raise ValueError(f'{col} must be positive')
    if not df['SSIM'].between(-1, 1).all():
        raise ValueError('SSIM must be between -1 and 1')
    if np.isneginf(df['PSNR_dB']).any():
        raise ValueError('PSNR cannot be negative infinity')
    if df[['width_px', 'height_px', 'original_png_bytes']].nunique().gt(1).any():
        raise ValueError(f'{path}: reference properties change within CSV')
    expected = df['jpeg_bytes'] / df['original_png_bytes'] * 100
    if not np.allclose(expected, df['size_percent_of_png'], rtol=1e-5, atol=1e-6):
        warnings.warn(f'{path}: PNG size ratio differs from byte counts; recomputing.')
    df['size_percent_of_png'] = expected
    df['jpeg_KiB'] = df['jpeg_bytes'] / 1024
    return df.sort_values('quality').reset_index(drop=True)


def style_axis(ax, title, xlabel, ylabel):
    ax.set_facecolor('#FDFDFF')
    ax.set_title(title, loc='left', fontsize=11, color='#1E2433', pad=10)
    ax.set_xlabel(xlabel, color='#505A74')
    ax.set_ylabel(ylabel, color='#505A74')
    ax.tick_params(colors='#505A74')
    ax.grid(True, color='#E2E6F0', linewidth=0.7)
    ax.set_axisbelow(True)
    for side in ['top', 'right']:
        ax.spines[side].set_visible(False)
    for side in ['bottom', 'left']:
        ax.spines[side].set_color('#CDD3E0')


def plot_line(ax, df, x, y, label, color, marker, linestyle):
    # inf PSNR는 CSV에 보존하고 그림에서는 제외. 누락 지점을 가로질러 잇지 않음.
    xv = df[x].to_numpy(dtype=float)
    yv = df[y].to_numpy(dtype=float)
    xv = np.where(np.isfinite(xv), xv, np.nan)
    yv = np.where(np.isfinite(yv), yv, np.nan)
    ax.plot(xv, yv, label=label, color=color, marker=marker,
            linestyle=linestyle, linewidth=1.7, markersize=3.5)


def compare(simple_path, complex_path, output_dir):
    """3개 개별 그래프 + 독립적인 3개 y축을 사용한 통합 그래프 저장."""
    simple, complex_df = load_data(simple_path), load_data(complex_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = [
        ('size_percent_of_png', 'JPEG / original PNG (%)', '#1751D0', '01_size_percent.png'),
        ('PSNR_dB', 'PSNR (dB)', '#E2661E', '02_psnr.png'),
        ('SSIM', 'SSIM', '#9117D0', '03_ssim.png'),
    ]
    series = [(simple, 'Simple image', 'o', '-'),
              (complex_df, 'Complex image', 's', '--')]
    def limits(ax, key):
        if key in ('size_percent_of_png', 'jpeg_KiB'):
            ax.set_ylim(bottom=0)
        elif key == 'SSIM':
            low = min(simple[key].min(), complex_df[key].min())
            ax.set_ylim(-1 if low < 0 else 0, 1.02)

    # 이미지별 기본 색을 유지하고 지표는 명도/채도와 선 스타일로 구분.
    # 개별 그림도 통합 그림(00_combined_3metrics)의 지표별 스타일과 동일하게 맞춤.
    image_metric_colors = {
        'Simple image': ['#C92121', '#D95656', '#8C1717'],
        'Complex image': ['#1B52C7', '#527ED6', '#13398B'],
    }
    metric_styles = ['-', '--', ':']

    for i, (key, label, color, filename) in enumerate(metrics):
        fig, ax = plt.subplots(figsize=(10, 6), facecolor='#FDFDFF')
        for df, name, marker, linestyle in series:
            y = df[key].to_numpy(dtype=float)
            y = np.where(np.isfinite(y), y, np.nan)
            ax.plot(df['quality'], y, color=image_metric_colors[name][i],
                    linestyle=metric_styles[i], linewidth=2.4, label=name)
        style_axis(ax, label + ': simple vs. complex', 'JPEG quality setting', label)
        ax.set_xlim(0, 102)
        ax.set_xticks(range(0, 101, 10))
        limits(ax, key)
        ax.legend(frameon=False, labelcolor='#505A74')
        fig.tight_layout()
        fig.savefig(output_dir / filename, dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close(fig)

    # 통합 그림: 지표별 색, 이미지별 선/마커. 세 축 모두 원래 단위 유지.
    fig, base = plt.subplots(figsize=(17, 9), facecolor='#FDFDFF')
    fig.subplots_adjust(left=0.09, right=0.77, bottom=0.27, top=0.88)
    axes = [base, base.twinx(), base.twinx()]
    axes[2].spines['right'].set_position(('outward', 85))
    for i, (ax, (key, label, color, filename)) in enumerate(zip(axes, metrics)):
        for df, name, marker, linestyle in series:
            y = df[key].to_numpy(dtype=float)
            y = np.where(np.isfinite(y), y, np.nan)
            ax.plot(df['quality'], y, color=image_metric_colors[name][i],
                    linestyle=metric_styles[i], linewidth=2.4,
                    label=f'{name}: {label}')
        ax.set_ylabel(label, color='#505A74', fontsize=11, labelpad=12)
        ax.tick_params(axis='y', colors='#505A74', labelsize=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right' if i else 'left'].set_color('#CDD3E0')
        if i:
            ax.spines['left'].set_visible(False)
            ax.patch.set_visible(False)
        limits(ax, key)
    base.set_facecolor('#FDFDFF')
    base.set_xlim(0, 102)
    base.set_xticks(range(0, 101, 10))
    base.set_xlabel('JPEG quality setting', color='#505A74', fontsize=12)
    base.tick_params(axis='x', colors='#505A74')
    base.grid(axis='x', color='#E2E6F0', linewidth=0.7)
    base.spines['bottom'].set_color('#CDD3E0')
    base.set_title('JPEG comparison | three metrics, independent y-axes',
                   loc='left', color='#1E2433', fontsize=16, pad=22)
    from matplotlib.lines import Line2D
    legend_handles = [
        Line2D([0], [0], color=image_metric_colors[name][i],
               linestyle=metric_styles[i], lw=2.4,
               label=f'{name} | {label}')
        for _, name, _, _ in series
        for i, (_, label, _, _) in enumerate(metrics)
    ]
    fig.legend(handles=legend_handles, loc='lower left',
               bbox_to_anchor=(0.08, 0.055), ncol=2, frameon=False,
               labelcolor='#505A74', fontsize=10, columnspacing=3)
    note = 'Independent scales: curve heights and intersections are NOT directly comparable across metrics.'
    if any(np.isposinf(df['PSNR_dB']).any() for df, *_ in series):
        note += ' Infinite PSNR points omitted.'
    fig.text(0.09, 0.025, note, fontsize=9, color='#737D96')
    fig.savefig(output_dir / '00_combined_3metrics.png', dpi=200, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    print('Saved exactly four PNG graphs to:', output_dir.resolve())
    for name in ['00_combined_3metrics.png'] + [m[3] for m in metrics]:
        print(' -', name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simple', type=Path, default=Path('results/simple_quality_metrics.csv'))
    parser.add_argument('--complex', type=Path, default=Path('results/complex_quality_metrics.csv'))
    parser.add_argument('--output', type=Path, default=Path('comparison'))
    args = parser.parse_args()
    compare(args.simple, args.complex, args.output)
