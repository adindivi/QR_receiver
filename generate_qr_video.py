#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RG QR Video Transfer - Encoder Script
======================================
제품명: RG QR Video Transfer 인코더 (generate_qr_video.py)
목적: 텍스트 파일을 분할 QR 애니메이션 GIF로 변환하여 수신기(receiver.html)로 전송
"""

import sys
import os
import random
import argparse
from PIL import Image, ImageDraw, ImageFont
import qrcode
from qrcode.constants import ERROR_CORRECT_M

# Windows 콘솔 UTF-8 출력 재설정
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def generate_session_id() -> str:
    """4자리 무작위 대문자 16진수 세션 ID 생성 (0000~FFFF)"""
    return f"{random.randint(0, 0xFFFF):04X}"

def split_text_by_bytes(text: str, max_bytes: int = 30) -> list[str]:
    """UTF-8 바이트 크기 기준으로 텍스트 분할 (스마트폰 인식을 위한 최적 분할)"""
    chunks = []
    current_chunk = ""
    for char in text:
        test_chunk = current_chunk + char;
        if len(test_chunk.encode('utf-8')) > max_bytes:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = char
        else:
            current_chunk = test_chunk
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def split_text_by_chars(text: str, chunk_chars: int = 90) -> list[str]:
    """글자 수 기준 텍스트 분할"""
    return [text[i:i + chunk_chars] for i in range(0, len(text), chunk_chars)]

def load_korean_font(size: int = 24):
    """OS별 한글 폰트 로드 및 폴백 처리"""
    font_candidates = [
        "malgun.ttf",       # Windows 맑은 고딕
        "AppleGothic.ttf",  # macOS 애플 고딕
        "NanumGothic.ttf",  # Linux 나눔 고딕
        "arial.ttf"         # Standard Fallback
    ]
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    return ImageFont.load_default()

def create_qr_frame(payload: str, session_id: str, current_idx: int, total_count: int, font) -> Image.Image:
    """
    단일 QR 프레임 이미지 생성 (640x700px)
    - 640x640px NEAREST 리샘플링 QR 코드
    - 하단 60px 라벨 영역 ("RG <세션ID> | <인덱스+1> / <총개수>")
    """
    # 1. QR 코드 생성 (오류정정 레벨 M, box_size=10, border=3)
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=3
    )
    
    qr.add_data(payload)
    qr.make(fit=True)

    # 2. QR 이미지를 640x640px 로 NEAREST 보간 리샘플링 (FR-6)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((640, 640), resample=Image.Resampling.NEAREST)

    # 3. 하단 60px 라벨 영역이 포함된 640x700px 캔버스 생성 (FR-7)
    canvas = Image.new("RGB", (640, 700), "white")
    canvas.paste(qr_img, (0, 0))

    # 4. 하단 라벨 텍스트 그리기 ("RG <세션ID> | <인덱스+1> / <총개수>")
    draw = ImageDraw.Draw(canvas)
    label_text = f"RG {session_id} | {current_idx + 1} / {total_count}"
    
    try:
        bbox = draw.textbbox((0, 0), label_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        text_width, text_height = draw.textsize(label_text, font=font)

    text_x = (640 - text_width) // 2
    text_y = 640 + (60 - text_height) // 2 - 4

    draw.text((text_x, text_y), label_text, fill="#111827", font=font)
    return canvas

def main():
    parser = argparse.ArgumentParser(
        description="RG QR Video Transfer - 텍스트 파일 분할 QR 애니메이션 GIF 생성기"
    )
    parser.add_argument("input_file", help="입력 텍스트 파일 (.txt)")
    parser.add_argument("output_gif", nargs="?", default="qr_video.gif", help="출력 GIF 파일명 (기본값: qr_video.gif)")
    parser.add_argument("frame_ms", nargs="?", type=int, default=150, help="프레임 재생 간격 (ms, 기본값: 150ms)")
    parser.add_argument("--chunk-bytes", type=int, default=30, help="조각당 바이트 용량 (기본값: 30 Byte - 카메라 스캔 최적화)")
    parser.add_argument("--chunk-chars", type=int, default=None, help="조각당 글자 수 (설정 시 바이트 단위 대신 사용)")

    args = parser.parse_args()

    # EC-1 입력 파일 존재 및 내용 검증
    if not os.path.exists(args.input_file):
        print(f"[오류] 입력 파일 '{args.input_file}'을(를) 찾을 수 없습니다.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.input_file, "r", encoding="utf-8") as f:
            raw_content = f.read()
    except UnicodeDecodeError:
        with open(args.input_file, "r", encoding="cp949") as f:
            raw_content = f.read()

    # UTF-8 BOM (\uFEFF) 및 공백 정리
    clean_content = raw_content.replace("\uFEFF", "").replace("ï»¿", "")
    if not clean_content.strip():
        print("[오류] 입력 파일이 비어 있습니다. (EC-1)", file=sys.stderr)
        sys.exit(1)

    # 텍스트 분할 (CHUNK_BYTES vs CHUNK_CHARS)
    if args.chunk_chars:
        chunks = split_text_by_chars(clean_content, args.chunk_chars)
        split_msg = f"글자 수 기준 ({args.chunk_chars}자)"
    else:
        chunks = split_text_by_bytes(clean_content, args.chunk_bytes)
        split_msg = f"바이트 기준 ({args.chunk_bytes} Byte)"

    total_count = len(chunks)
    session_id = generate_session_id()

    print("==================================================")
    print(f"RG QR Video Transfer 인코딩 시작")
    print(f"* 입력 파일: {args.input_file}")
    print(f"* 세션 ID : {session_id}")
    print(f"* 총 조각 수: {total_count}개 ({split_msg})")
    print(f"* 프레임 간격: {args.frame_ms} ms (초당 약 {1000 / args.frame_ms:.1f} FPS)")
    print(f"* 예상 재생 시간: {(total_count * args.frame_ms) / 1000:.1f}초 (1회 루프)")
    print("==================================================")

    # 폰트 로드
    font = load_korean_font(size=26)
    frames = []

    # FR-4 & FR-10 프레임 생성 및 콘솔 출력
    for idx, chunk in enumerate(chunks):
        # 포맷: RG:<세션ID>:<인덱스>:<총개수>:<내용>
        payload = f"RG:{session_id}:{idx}:{total_count}:{chunk}"
        frame_img = create_qr_frame(payload, session_id, idx, total_count, font)
        frames.append(frame_img)

        if (idx + 1) % 10 == 0 or (idx + 1) == total_count:
            print(f"  [프레임 {idx + 1:3d} / {total_count:3d}] 생성 완료 ({(idx + 1) / total_count * 100:.0f}%)")

    # FR-8 애니메이션 GIF 저장 (최적화 옵션)
    print(f"\nGIF 파일 저장 중... ({args.output_gif})")
    frames[0].save(
        args.output_gif,
        save_all=True,
        append_images=frames[1:],
        duration=args.frame_ms,
        loop=0,
        optimize=True
    )

    print("==================================================")
    print(f"성공! QR 애니메이션 GIF가 완성되었습니다.")
    print(f"저장 경로: {os.path.abspath(args.output_gif)}")
    print(f"수신 방법: receiver.html 을 스마트폰에서 열어 화면을 스캔하세요!")
    print("==================================================")

if __name__ == "__main__":
    main()
