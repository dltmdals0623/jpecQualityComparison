"""PNG 기준 JPEG 품질별 PSNR·SSIM 비교.
설치: pip install pillow numpy scikit-image matplotlib
실행: python jpeg_quality_test.py original.png --output results
RGB 픽셀(0~255) 기준이며, 알파 채널은 지정 배경에 합성합니다.
"""
import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageOps
from skimage.metrics import peak_signal_noise_ratio, structural_similarity


def plot_metrics(csv_path, input_path, output_path=None, show=False):
    input_path = Path(input_path)
    csv_path = Path(csv_path)
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = ["quality", "size_percent_of_png", "PSNR_dB", "SSIM"]
        if not set(required).issubset(reader.fieldnames or []):
            raise ValueError(f"CSV에 필요한 열: {required}")
        rows = [{key: float(row[key]) for key in required} for row in reader]
    if not rows:
        raise ValueError("CSV에 데이터가 없습니다.")
    rows.sort(key=lambda row: row["quality"])
    x = np.array([row["quality"] for row in rows])
    colors = ["#1751D0", "#E2661E", "#0E9E8F"]
    fig, ax_size = plt.subplots(figsize=(11, 6), facecolor="#FDFDFF")
    fig.subplots_adjust(left=0.10, right=0.73, bottom=0.23, top=0.86)
    ax_size.set_facecolor("#FDFDFF")
    ax_psnr = ax_size.twinx()
    ax_ssim = ax_size.twinx()
    ax_ssim.spines["right"].set_position(("outward", 80))
    axes = [ax_size, ax_psnr, ax_ssim]
    keys = ["size_percent_of_png", "PSNR_dB", "SSIM"]
    labels = ["Size / original PNG (%)", "PSNR (dB)", "SSIM"]
    styles = [("o", "-"), ("s", "--"), ("^", "-.")]
    lines = []
    notes = []
    for ax, key, label, color, (marker, linestyle) in zip(axes, keys, labels, colors, styles):
        y = np.array([row[key] for row in rows])
        finite = np.isfinite(y)
        if not finite.all():
            bad = ", ".join(f"{q:g}" for q in x[~finite])
            notes.append(f"{key}: non-finite values omitted at quality {bad}.")
        y = np.where(finite, y, np.nan)
        line, = ax.plot(x, y, label=label, color=color, marker=marker,
                        linestyle=linestyle, linewidth=1.8, markersize=5)
        lines.append(line)
        ax.set_ylabel(label, color="#505A74", labelpad=12)
        ax.tick_params(axis="both", colors="#505A74")
        ax.spines["top"].set_visible(False)
        for side in ["left", "right", "bottom"]:
            ax.spines[side].set_color("#CDD3E0")
    # 세 y축은 독립적인 눈금입니다. SSIM은 보통 0~1 범위로 표시합니다.
    ax_size.set_ylim(bottom=0)
    ax_psnr.set_ylim(bottom=0)
    ssim_values = np.array([r["SSIM"] for r in rows])
    ax_ssim.set_ylim(-1 if np.any(ssim_values < 0) else 0, 1.02)
    ax_size.set_xticks(x)
    ax_size.set_xlabel("JPEG quality setting", color="#505A74")
    ax_size.grid(True, color="#E2E6F0", linewidth=0.8)
    ax_size.set_axisbelow(True)
    ax_size.set_title("JPEG quality vs. size, PSNR and SSIM", loc="left",
                      color="#1E2433", fontsize=14, pad=18)
    fig.legend(handles=lines, loc="lower left", bbox_to_anchor=(0.09, 0.08),
               ncol=3, frameon=False, labelcolor="#505A74")
    footnote = "Independent y-axis scales: line heights and crossings are not directly comparable."
    if notes:
        footnote += "\n" + "\n".join(notes)
    fig.text(0.10, 0.025, footnote, fontsize=8, color="#737D96")
    output_path = Path(output_path) if output_path else csv_path.with_name(f"{input_path}_quality_metrics_overlay.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    if show:
        plt.show()
    plt.close(fig)
    print(f"Graph: {output_path.resolve()}")
    return output_path


def run(input_path, output_dir, background=(255, 255, 255)):
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    with Image.open(input_path) as image:
        if image.format != "PNG":
            raise ValueError("기준 파일은 PNG여야 합니다.")
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError("애니메이션 PNG는 지원하지 않습니다.")
        if image.mode not in ("RGB", "RGBA", "L", "LA", "P", "1"):
            raise ValueError("8비트 RGB/회색조/팔레트 PNG를 사용하세요. 16비트 PNG는 먼저 변환하세요.")
        image = ImageOps.exif_transpose(image)
        rgba = image.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (*background, 255))
        reference = Image.alpha_composite(base, rgba).convert("RGB")
    width, height = reference.size
    if min(width, height) < 3:
        raise ValueError("SSIM 계산을 위해 가로·세로가 각각 3픽셀 이상이어야 합니다.")
    win_size = min(7, width, height)
    if win_size % 2 == 0:
        win_size -= 1
    reference_array = np.asarray(reference, dtype=np.uint8)
    output_dir.mkdir(parents=True, exist_ok=True)
    reference.save(output_dir / f"{input_path}_reference_rgb.png")
    original_bytes = input_path.stat().st_size
    rows = []
    for quality in range(100, 0, -5):
        jpeg_path = output_dir / f"{input_path}_quality_{quality:03d}.jpg"
        # 반드시 원본에서 각각 저장. 색차 서브샘플링 등 다른 조건은 고정.
        reference.save(jpeg_path, format="JPEG", quality=quality, subsampling=0, optimize=False, progressive=False)
        with Image.open(jpeg_path) as decoded:
            test_array = np.asarray(decoded.convert("RGB"), dtype=np.uint8)
        if np.array_equal(reference_array, test_array):
            psnr = float("inf")
        else:
            psnr = float(peak_signal_noise_ratio(reference_array, test_array, data_range=255))
        ssim = float(structural_similarity(reference_array, test_array, channel_axis=-1, data_range=255, win_size=win_size))
        size_bytes = jpeg_path.stat().st_size
        rows.append({"quality": quality, "width_px": width, "height_px": height,
                     "jpeg_bytes": size_bytes, "jpeg_KiB": size_bytes / 1024,
                     "original_png_bytes": original_bytes,
                     "size_percent_of_png": size_bytes / original_bytes * 100,
                     "PSNR_dB": psnr, "SSIM": ssim})
    csv_path = output_dir / f"{input_path}_quality_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{'Quality':>7} {'Size(KiB)':>12} {'PSNR(dB)':>12} {'SSIM':>12}")
    for row in rows:
        print(f"{row['quality']:7d} {row['jpeg_KiB']:12.2f} {row['PSNR_dB']:12.4f} {row['SSIM']:12.6f}")
    print(f"\nCSV: {csv_path.resolve()}")
    print("JPEG 및 실제 비교 기준 reference_rgb.png도 같은 폴더에 저장했습니다.")
    plot_metrics(csv_path, input_path)
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_png", type=Path, help="기준 원본 PNG 경로")
    parser.add_argument("--output", type=Path, default=Path("jpeg_results"))
    parser.add_argument("--background", type=int, nargs=3, default=(255, 255, 255),
                        metavar=("R", "G", "B"), help="투명 영역 합성 배경, 기본 흰색")
    args = parser.parse_args()
    if any(value < 0 or value > 255 for value in args.background):
        parser.error("배경 RGB 값은 각각 0~255여야 합니다.")
    run(args.input_png, args.output, tuple(args.background))
    